"""Red team for REF H3b (scope judged by today), second round. Each test is one attempted break of a stated promise;
hermetic: every outbound connection is refused and the model echoes its whole prompt, so any evidence it was given shows.

These breaks triggered the stop rule a second time (docs/benchmark/evidence/2026-10-03-h3b-stop-rule.md). The Human
chose the simpler design: one date reader, one recheck of what the answer rests on, and no site guessing. The site
breaks are restated to the new promise (no site is left out for being another site's; each site passage says its
sites); the rest hold as the red team wrote them, apart from the editor storing a date in one form. After round 3 the
Human dropped the mid-answer recheck (one reading per answer), and the interleaving tests are restated to that."""
import os
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from iam_helpers import sign_in  # noqa: E402
from test_space_leaks import hermetic, refuse  # noqa: E402

TODAY = "2026-10-03"
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


# --- Sites (restated: no site guessing): no site's guidance is left out, and each site passage says its sites ---

@pytest.mark.parametrize("other_site, question", [
    ("Bristol Returns Centre", "What is the returns process at Leeds?"),
    ("Reading", "What is the meter reading process at Leeds?"),
    ("DC (B)", "What is the returns process at DC (A)?"),
    ("March", "What is the returns process in March?"),
])
def test_whatever_site_the_question_names_each_site_passage_says_its_own(space, other_site, question):
    space.add("leeds.md", plain_doc("Leeds returns", "LEEDS-ONLY-11"), applies_to=["Leeds"])
    space.add("other.md", plain_doc("Other site returns", "OTHER-SITE-22"), applies_to=[other_site])
    answer = space.ask(question)["answer"]
    assert "(Applies to: Leeds.) " in answer and "LEEDS-ONLY-11" in answer
    assert f"(Applies to: {other_site}.) " in answer and "OTHER-SITE-22" in answer


# --- Promise 1: a scope date that is present but unreadable keeps the source out ---

@pytest.mark.parametrize("field, value", [("effective_to", "2026-12-311"), ("effective_from", "2026-01-015")])
def test_unreadable_date_with_trailing_digits_is_read_as_a_date(space, field, value):
    space.add("keep.md", plain_doc("Returns basics", "KEEP-33"))
    space.add("bad.md", plain_doc("Returns typo", "TYPO-44"), **{field: value})
    answer = space.ask("What is the returns process?")["answer"]
    assert "KEEP-33" in answer
    assert "TYPO-44" not in answer, f"{field}={value!r} is not a date, yet the source answered"


# --- Promise 3: a date the details editor accepts, scope reads; the editor stores it in one form ---

@pytest.mark.parametrize("field, value, label", [
    ("effective_to", "20261231", "In force until 31 December 2026"),
    ("effective_from", "20270101", "In force from 1 January 2027"),
])
def test_basic_iso_date_accepted_by_editor_drops_the_source(space, field, value, label):
    space.add("keep.md", plain_doc("Returns basics", "KEEP-71"))
    sid = space.add("dated.md", plain_doc("Returns dated", "DATED-72"))
    r = space.client.patch(f"/api/content/documents/{sid}/details", json={"fields": {field: value}}, headers=HEAD)
    assert r.status_code == 200, r.text  # the editor accepts it as a date (date.fromisoformat, Python 3.11+)
    stored = space.register.get(sid)
    assert stored.approval_status == "approved" and getattr(stored, field) == f"{value[:4]}-{value[4:6]}-{value[6:]}"
    os.environ["KP_SCOPE_EVIDENCE"] = "0"
    assert "DATED-72" in space.ask("What is the returns process?")["answer"]  # control: present with scope off
    os.environ["KP_SCOPE_EVIDENCE"] = "1"
    answer = space.ask("What is the returns process?")["answer"]
    assert "KEEP-71" in answer
    assert "DATED-72" in answer and label in answer, (
        f"{field}={value!r} was accepted as a date, yet scope left the source out instead of keeping and labelling it")


# --- Promise 4: adding a month to the question changes nothing ---

def test_a_month_in_the_question_changes_which_sources_answer(space):
    space.add("leeds.md", plain_doc("Leeds returns", "LEEDS-55"), applies_to=["Leeds"])
    space.add("march.md", plain_doc("March returns", "MARCH-66"), applies_to=["March"])
    plain = space.ask("What is the returns process?")["answer"]
    dated = space.ask("What is the returns process in March?")["answer"]
    def marks(text):
        return {m for m in ("LEEDS-55", "MARCH-66", "Applies to: Leeds", "Applies to: March") if m in text}
    assert marks(plain) == {"LEEDS-55", "MARCH-66", "Applies to: Leeds", "Applies to: March"}
    assert marks(dated) == marks(plain), "adding a month to the question changed the sources and labels"


# --- Restated (the Human's decision after round 3: one reading per answer, no mid-answer recheck): an edit that lands
# while an answer is prepared applies from the next answer, on the facts-map path as on the documents ---

def test_facts_map_answer_skips_the_scope_recheck(space):
    sid = space.add("p.md", process_doc("Acme returns", "Returns Warden", "RETVAULT-77", "MARK-77"))
    space.core.state.answer.generator = HookEcho(lambda: space.register.update(sid, effective_to="2026-10-02"))
    r = space.ask("Which systems are used?")
    assert r["answer_path"] == "oag" and "RETVAULT-77" in r["answer"]  # judged on the reading taken as it began
    r = space.ask("Which systems are used?")
    assert r["answer_path"] != "oag" and "RETVAULT-77" not in r["answer"], (
        "the next answer still used the facts map, or the expired source, after the source expired")


def test_document_answer_rechecks_the_same_interleaving(space):
    sid = space.add("p.md", plain_doc("Returns basics", "DOC-88"))
    space.core.state.answer.generator = HookEcho(lambda: space.register.update(sid, effective_to="2026-10-02"))
    assert "DOC-88" in space.ask("What is the returns process?")["answer"]
    assert "DOC-88" not in space.ask("What is the returns process?")["answer"]


def test_label_that_appears_mid_answer_is_not_rechecked(space):
    sid = space.add("p.md", plain_doc("Returns basics", "LATER-99"))
    space.core.state.answer.generator = HookEcho(lambda: space.register.update(sid, effective_from="2027-01-01"))
    assert "In force from 1 January 2027" not in space.ask("What is the returns process?")["answer"]
    r = space.ask("What is the returns process?")
    assert "LATER-99" in r["answer"] and "In force from 1 January 2027" in r["answer"], (
        "the next answer presents the source approved for 2027 without its 'In force from' label")


# --- Promise 5 (interleaving): nothing scoped, yet scope on answers differently from scope off ---

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
