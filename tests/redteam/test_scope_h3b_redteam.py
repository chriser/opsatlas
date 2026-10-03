"""Red team for REF H3b (scope on the written answer path). Hermetic: no network, no model; the model echoes its prompt,
so any evidence it was given appears in the answer."""
from __future__ import annotations

import os
import socket

import pytest

from tests.iam_helpers import sign_in
from tests.test_space_leaks import hermetic, refuse

HEAD = {"X-OpsAtlas-Space": "acme"}
TODAY = "2026-10-03"

# Over 24,000 characters (the full-context limit) with no word of the refund question, so answers go through retrieval.
FILLER = "# Lighting maintenance\n\n" + "\n\n".join(
    f"## Lamp bay {n}\n\nLamp bay {n} fluorescent tubes are checked monthly by the facilities crew; ballast hum, "
    "flicker and dust on diffusers are logged, and the ladder is inspected before climbing. " * 6
    for n in range(40)
)


@pytest.fixture
def env(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    os.environ["SME_TIBI_VOICE_URL"] = "http://127.0.0.1:9"
    os.environ["SALES_GOVERNANCE_AUTO_REVIEW"] = "0"
    os.environ.pop("KP_SCOPE_EVIDENCE", None)
    os.environ["KP_SCOPE_TODAY"] = TODAY
    app = create_sales_app(tmp_path / "sales")
    hermetic(app)
    with TestClient(app) as client:
        client.headers.update({"Authorization": f"Bearer {sign_in(client, app)}"})
        assert client.post("/api/spaces", json={"name": "Acme"}).status_code == 200
        core = app.state.cores["acme"]
        hermetic(core)

        def add(name: str, text: str, approve: bool = True, **scope) -> str:
            up = client.post("/api/sources/upload", files={"file": (name, text.encode(), "text/markdown")}, headers=HEAD)
            assert up.status_code == 200, up.text
            sid = up.json()["id"] if "id" in up.json() else up.json()["source"]["id"]
            client.post(f"/api/sources/{sid}/ingest", headers=HEAD)
            if approve:
                assert client.post(f"/api/governance/sources/{sid}/approve", headers=HEAD).status_code == 200
            if scope:
                core.state.register.update(sid, **scope)
            return sid

        def ask(q: str) -> dict:
            r = client.post("/api/ask", json={"q": q}, headers=HEAD)
            assert r.status_code == 200, r.text
            return r.json()

        yield client, core, add, ask


def scope_on():
    os.environ["KP_SCOPE_EVIDENCE"] = "1"


# ---- Break 1: the retrieval index keeps the record as it was when it was built --------------------------------------

def test_scope_edit_after_index_built_still_leaks_through_retrieval(env):
    """Promise 1, retrieval path: a source's effective_to edited into the past after a first question. The index
    snapshot's fingerprint (id, version, sha, section count) ignores scope fields, so search's allow() reads the stale
    record and the out-of-force passage still answers."""
    client, core, add, ask = env
    add("lighting.md", FILLER)
    policy = add("refunds.md", "# Refund policy\n\nThe refund window for returns is ZORBLAX fourteen days.\n")
    scope_on()
    first = ask("What is the refund window for returns?")
    assert first["mode"] == "retrieval"
    assert "ZORBLAX" in first["answer"]  # in force: it answers (and the index snapshot is built)

    core.state.register.update(policy, effective_to="2025-12-31")  # no longer in force today
    second = ask("What is the refund window for returns?")
    assert "ZORBLAX" not in second["answer"], "an out-of-force source answered through retrieval"
    assert all(c["source_id"] != policy for c in second["citations"])


def test_scope_edit_via_details_api_still_leaks_through_retrieval(env):
    """Same break through the product's own route (PATCH /api/content/documents/{id}/details): it writes the register
    only and never invalidates the retrieval index."""
    client, core, add, ask = env
    add("lighting.md", FILLER)
    policy = add("refunds.md", "# Refund policy\n\nThe refund window for returns is ZORBLAX fourteen days.\n")
    scope_on()
    assert "ZORBLAX" in ask("What is the refund window for returns?")["answer"]
    r = client.patch(f"/api/content/documents/{policy}/details", json={"fields": {"effective_to": "2025-12-31"}},
                     headers=HEAD)
    assert r.status_code == 200, r.text
    assert "ZORBLAX" not in ask("What is the refund window for returns?")["answer"]


def test_site_edit_after_index_built_still_leaks_through_retrieval(env):
    """Promise 1, site: a guide edited to apply to Bristol only after a first question; a question naming Leeds (a site
    the space knows) still gets the Bristol guide, because allow() reads the snapshot's applies_to ([])."""
    client, core, add, ask = env
    add("lighting.md", FILLER)
    add("leeds.md", "# Leeds note\n\nLeeds yard gates open at six.\n", applies_to=["Leeds"])
    guide = add("refunds.md", "# Refund policy\n\nThe refund window for returns is QUOKKA ten days.\n")
    scope_on()
    assert "QUOKKA" in ask("What is the refund window for returns at Leeds?")["answer"]
    core.state.register.update(guide, applies_to=["Bristol"])
    answer = ask("What is the refund window for returns at Leeds?")
    assert "QUOKKA" not in answer["answer"], "another site's guide answered a question naming Leeds"


def test_control_rebuilt_index_keeps_out_of_force_source(env):
    """Control for break 1 (passes now): the same edit followed by an index rebuild keeps the source out, so the leak
    is the stale snapshot, not the filter's date logic."""
    client, core, add, ask = env
    add("lighting.md", FILLER)
    policy = add("refunds.md", "# Refund policy\n\nThe refund window for returns is ZORBLAX fourteen days.\n")
    scope_on()
    assert "ZORBLAX" in ask("What is the refund window for returns?")["answer"]
    core.state.register.update(policy, effective_to="2025-12-31")
    core.state.answer.retrieval.index.invalidate()
    assert "ZORBLAX" not in ask("What is the refund window for returns?")["answer"]


# ---- Break 2: an approval landing while the answer is prepared ------------------------------------------------------

def test_supersede_approved_mid_answer_lets_replaced_source_answer(env, monkeypatch):
    """Promise 1, replaced, two requests at once: the replacing source is approved after ScopeFilter is built but
    before the passages are read. superseded was computed without it, so the replaced 2025 policy answers; the
    delivery recheck (visibility and version) does not look at scope."""
    import assistant.answer.service as service
    client, core, add, ask = env
    old = add("old.md", "# Refund policy 2025\n\nThe refund window for returns is OLDWINDOW thirty days.\n")
    new = add("new.md", "# Refund policy 2026\n\nThe refund window for returns is NEWWINDOW fourteen days.\n",
              approve=False, supersedes=[old])
    scope_on()

    class Racing(service.ScopeFilter):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            core.state.register.update(new, approval_status="approved")  # the approval lands now

    monkeypatch.setattr(service, "ScopeFilter", Racing)
    answer = ask("What is the refund window for returns?")
    assert core.state.register.get(new).approval_status == "approved"
    assert "OLDWINDOW" not in answer["answer"], "a source replaced by an approved source in force answered"


# ---- Break 3: the date the question is about ------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="Stop rule (Definition of Done, 3 Oct 2026): the question's date has had faults in two "
                   "review rounds running; inferring it from free text is the design flaw. A simpler design goes to the Human "
                   "before any more patching (REF H3b #2126).")
@pytest.mark.parametrize("question", [
    "What was the refund window for returns in 2025?",          # a past year: scope uses today
    "What is the refund window for returns as of January 2027?",  # a later year without a listed cue
    "What is the refund window for returns on 2027-01-01?",
    "What is the refund window for returns in Q1 2027?",
])
def test_question_about_another_date_gets_todays_policy(env, question):
    """Promise 1, date: asked_date reads only a later year after a listed cue word; a question about 2025, or about
    2027 phrased otherwise, is treated as about today and gets the 2026 policy, which is not in force then."""
    client, core, add, ask = env
    add("y2025.md", "# Refund policy 2025\n\nThe refund window for returns is WINDOW2025 thirty days.\n",
        effective_from="2025-01-01", effective_to="2025-12-31")
    add("y2026.md", "# Refund policy 2026\n\nThe refund window for returns is WINDOW2026 fourteen days.\n",
        effective_from="2026-01-01", effective_to="2026-12-31")
    add("y2027.md", "# Refund policy 2027\n\nThe refund window for returns is WINDOW2027 seven days.\n",
        effective_from="2027-01-01")
    scope_on()
    answer = ask(question)["answer"]
    assert "WINDOW2026" not in answer, f"the 2026 policy answered a question about another year: {question}"


# ---- Break 4: nothing kept out, yet the answer differs --------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="Intended: with no site named, each passage says which site it applies to so the "
                   "answer can label both (REF H3). Promise 2 is restated: the same evidence, with those labels (REF H3b #2126).")
def test_nothing_kept_out_answer_differs_from_scope_off(env):
    """Promise 2: two in-force guides for different sites, a question naming no site, so scope keeps nothing out; the
    answer still differs from scope off, because scope prefixes "(Applies to: ...)" to each passage in the prompt."""
    client, core, add, ask = env
    add("leeds.md", "# Leeds refunds\n\nThe refund window for returns at Leeds is fourteen days.\n", applies_to=["Leeds"])
    add("bristol.md", "# Bristol refunds\n\nThe refund window for returns at Bristol is ten days.\n",
        applies_to=["Bristol"])
    off = ask("What is the refund window for returns?")
    scope_on()
    on = ask("What is the refund window for returns?")
    assert on["answer"] == off["answer"]
