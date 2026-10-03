"""Red team for REF H3b (scope judged by today). Each test is one attempted break of a stated promise; hermetic:
every outbound connection is refused and the model echoes its whole prompt, so any evidence it was given shows."""
import os
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from iam_helpers import sign_in  # noqa: E402
from test_space_leaks import hermetic, refuse  # noqa: E402

TODAY = "2026-10-03"
# The stop rule applied (docs/benchmark/evidence/2026-10-03-h3b-stop-rule.md): these breaks wait for the simpler design.
PENDING = pytest.mark.xfail(strict=True, reason="REF H3b stop rule: awaiting the simpler design")
HEAD = {"X-OpsAtlas-Space": "acme"}


def process_doc(title: str, role: str, system: str, marker: str, topic: str = "returns") -> str:
    return f"""# {title}

The {role} handles every {topic} request after checking it in {system}. Reference {marker}.

## Roles and responsibilities

| Role | Responsibility |
|---|---|
| {role} | Approves the {topic} request and records it in {system} |
| Store manager | Raises the {topic} request |

## Systems and data dependencies

| System | Purpose |
|---|---|
| {system} | Holds the {topic} ledger and the approval record |

## Process steps

1. The store manager raises the {topic} request.
2. The {role} checks it in {system} ({marker}).
3. The {role} approves the {topic} request.
"""


def plain_doc(title: str, marker: str, topic: str = "returns") -> str:
    return f"# {title}\n\nThe {topic} process: a customer brings the item back within 30 days. Reference {marker}.\n"


class Space:
    def __init__(self, client, app):
        self.client, self.app = client, app
        self.core = app.state.cores["acme"]
        self.register = self.core.state.register

    def add(self, name: str, text: str, approve: bool = True, **scope) -> str:
        up = self.client.post("/api/sources/upload", files={"file": (name, text.encode(), "text/markdown")}, headers=HEAD)
        assert up.status_code == 200, up.text
        body = up.json()
        sid = body["id"] if "id" in body else body["source"]["id"]
        assert self.client.post(f"/api/sources/{sid}/ingest", headers=HEAD).status_code == 200
        if approve:
            r = self.client.post(f"/api/governance/sources/{sid}/approve", headers=HEAD)
            assert r.status_code == 200, r.text
        if scope:
            self.register.update(sid, **scope)
        return sid

    def ask(self, q: str) -> dict:
        r = self.client.post("/api/ask", json={"q": q}, headers=HEAD)
        assert r.status_code == 200, r.text
        return r.json()


@pytest.fixture
def space(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    os.environ["SME_TIBI_VOICE_URL"] = "http://127.0.0.1:9"
    os.environ["SALES_GOVERNANCE_AUTO_REVIEW"] = "0"
    os.environ["KP_SCOPE_EVIDENCE"] = "1"
    os.environ["KP_SCOPE_TODAY"] = TODAY
    app = create_sales_app(tmp_path / "sales")
    hermetic(app)
    with TestClient(app) as client:
        client.headers.update({"Authorization": f"Bearer {sign_in(client, app)}"})
        assert client.post("/api/spaces", json={"name": "Acme"}).status_code == 200
        hermetic(app.state.cores["acme"])
        yield Space(client, app)


class HookEcho:
    """The echo model, with an edit that lands while the answer is being prepared (once)."""
    def __init__(self, edit):
        self.edit, self.done = edit, False

    def generate(self, prompt: str) -> str:
        if not self.done:
            self.done = True
            self.edit()
        return prompt + "\n[1]"


# --- Promise 1: another site's guidance is left out when the question names exactly one site the space knows ---

@pytest.mark.parametrize("other_site, question", [
    ("Bristol Returns Centre", "What is the returns process at Leeds?"),
    ("Reading", "What is the meter reading process at Leeds?"),
])
@PENDING
def test_one_named_site_still_gets_another_sites_guidance(space, other_site, question):
    space.add("leeds.md", plain_doc("Leeds returns", "LEEDS-ONLY-11"), applies_to=["Leeds"])
    space.add("other.md", plain_doc("Other site returns", "OTHER-SITE-22"), applies_to=[other_site])
    answer = space.ask(question)["answer"]
    assert "LEEDS-ONLY-11" in answer
    assert "OTHER-SITE-22" not in answer, "the question names only Leeds, yet another site's source reached the model"


@PENDING
def test_site_name_ending_in_punctuation_is_never_named(space):
    space.add("a.md", plain_doc("DC A returns", "DC-A-12"), applies_to=["DC (A)"])
    space.add("b.md", plain_doc("DC B returns", "DC-B-13"), applies_to=["DC (B)"])
    answer = space.ask("What is the returns process at DC (A)?")["answer"]
    assert "DC-A-12" in answer
    assert "DC-B-13" not in answer, "the question names exactly one site, DC (A), yet DC (B)'s source reached the model"


# --- Promise 1: a scope date that is present but unreadable keeps the source out ---

@pytest.mark.parametrize("field, value", [("effective_to", "2026-12-311"), ("effective_from", "2026-01-015")])
@PENDING
def test_unreadable_date_with_trailing_digits_is_read_as_a_date(space, field, value):
    space.add("keep.md", plain_doc("Returns basics", "KEEP-33"))
    space.add("bad.md", plain_doc("Returns typo", "TYPO-44"), **{field: value})
    answer = space.ask("What is the returns process?")["answer"]
    assert "KEEP-33" in answer
    assert "TYPO-44" not in answer, f"{field}={value!r} is not a date, yet the source answered"


# --- Promise 2: a date the details editor accepts as ISO is one scope cannot read, so the source vanishes ---

@pytest.mark.parametrize("field, value, label", [
    ("effective_to", "20261231", "In force until 31 December 2026"),
    ("effective_from", "20270101", "In force from 1 January 2027"),
])
@PENDING
def test_basic_iso_date_accepted_by_editor_drops_the_source(space, field, value, label):
    space.add("keep.md", plain_doc("Returns basics", "KEEP-71"))
    sid = space.add("dated.md", plain_doc("Returns dated", "DATED-72"))
    r = space.client.patch(f"/api/content/documents/{sid}/details", json={"fields": {field: value}}, headers=HEAD)
    assert r.status_code == 200, r.text  # the editor accepts it as a date (date.fromisoformat, Python 3.11+)
    stored = space.register.get(sid)
    assert stored.approval_status == "approved" and getattr(stored, field) == value
    os.environ["KP_SCOPE_EVIDENCE"] = "0"
    assert "DATED-72" in space.ask("What is the returns process?")["answer"]  # control: present with scope off
    os.environ["KP_SCOPE_EVIDENCE"] = "1"
    answer = space.ask("What is the returns process?")["answer"]
    assert "KEEP-71" in answer
    assert "DATED-72" in answer and label in answer, (
        f"{field}={value!r} was accepted as a date, yet scope left the source out instead of keeping and labelling it")


# --- Promise 4: adding a month to the question changes nothing ---

@PENDING
def test_a_month_in_the_question_changes_which_sources_answer(space):
    space.add("leeds.md", plain_doc("Leeds returns", "LEEDS-55"), applies_to=["Leeds"])
    space.add("march.md", plain_doc("March returns", "MARCH-66"), applies_to=["March"])
    plain = space.ask("What is the returns process?")["answer"]
    dated = space.ask("What is the returns process in March?")["answer"]
    marks = lambda text: {m for m in ("LEEDS-55", "MARCH-66", "Applies to: Leeds", "Applies to: March") if m in text}
    assert marks(plain) == {"LEEDS-55", "MARCH-66", "Applies to: Leeds", "Applies to: March"}
    assert marks(dated) == marks(plain), "adding a month to the question changed the sources and labels"


# --- Promise 1 (interleaving): a source expired while a facts-map answer is prepared is still used ---

@PENDING
def test_facts_map_answer_skips_the_scope_recheck(space):
    sid = space.add("p.md", process_doc("Acme returns", "Returns Warden", "RETVAULT-77", "MARK-77"))
    space.core.state.answer.generator = HookEcho(lambda: space.register.update(sid, effective_to="2026-10-02"))
    r = space.ask("Which systems are used?")
    assert r["answer_path"] == "oag" or r["mode"] == "evidence-changed"
    assert r["mode"] == "evidence-changed" or "RETVAULT-77" not in r["answer"], (
        "the source expired while the facts-map answer was prepared, and the answer still rests on it")


def test_document_answer_rechecks_the_same_interleaving(space):
    """Control: the document path refuses in the same interleaving (so the facts-map path is the odd one out)."""
    sid = space.add("p.md", plain_doc("Returns basics", "DOC-88"))
    space.core.state.answer.generator = HookEcho(lambda: space.register.update(sid, effective_to="2026-10-02"))
    assert space.ask("What is the returns process?")["mode"] == "evidence-changed"


# --- Promise 2 (interleaving): a source given a later start while the answer is prepared reaches the reader unlabelled ---

@PENDING
def test_label_that_appears_mid_answer_is_not_rechecked(space):
    sid = space.add("p.md", plain_doc("Returns basics", "LATER-99"))
    space.core.state.answer.generator = HookEcho(lambda: space.register.update(sid, effective_from="2027-01-01"))
    r = space.ask("What is the returns process?")
    assert r["mode"] == "evidence-changed" or "In force from 1 January 2027" in r["answer"], (
        "the source is now approved for 2027, but the answer delivered presents it with no 'In force from' label")


# --- Promise 5 (interleaving): nothing scoped, yet scope on answers differently from scope off ---

@PENDING
def test_unscoped_approval_mid_answer_refuses_only_with_scope_on(space):
    space.add("base.md", plain_doc("Returns basics", "BASE-10"))
    p1 = space.add("p1.md", plain_doc("Exchanges", "P1-20", topic="exchanges"), approve=False)
    p2 = space.add("p2.md", plain_doc("Refunds", "P2-30", topic="refunds"), approve=False)
    os.environ["KP_SCOPE_EVIDENCE"] = "0"
    space.core.state.answer.generator = HookEcho(lambda: space.register.update(p1, approval_status="approved"))
    off = space.ask("What is the returns process?")
    assert not off["refused"] and "BASE-10" in off["answer"]
    os.environ["KP_SCOPE_EVIDENCE"] = "1"
    space.core.state.answer.generator = HookEcho(lambda: space.register.update(p2, approval_status="approved"))
    on = space.ask("What is the returns process?")
    assert (on["refused"], on["mode"]) == (off["refused"], off["mode"]), (
        "no source has any scope, yet with scope on the answer is withheld as 'evidence changed'")
