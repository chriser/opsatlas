"""Red team for REF H3b (scope on the written answer path). Hermetic: no network, no model; the model echoes its prompt,
so any evidence it was given appears in the answer."""
from __future__ import annotations

import os
import socket

import pytest

from tests.door_helpers import as_job, decide, decided, writing
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
                assert decide(client, sid, headers=HEAD).status_code == 200
            if scope:
                with writing(core):  # set-up is a job (REF S23, the door)
                    decided(core.state.register, sid, **scope)
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
    record and the out-of-force passage still answers. Restated for the door (REF S23, the Human's decision after
    round 7): the edit is a job holding the workspace's lock, as the details request would."""
    client, core, add, ask = env
    add("lighting.md", FILLER)
    policy = add("refunds.md", "# Refund policy\n\nThe refund window for returns is ZORBLAX fourteen days.\n")
    scope_on()
    first = ask("What is the refund window for returns?")
    assert first["mode"] == "retrieval"
    assert "ZORBLAX" in first["answer"]  # in force: it answers (and the index snapshot is built)

    with writing(core):
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
    """Promise 2, site: a guide edited to apply to Bristol only after a first question. Restated after the second stop
    rule (no site guessing): the guide still answers, and its passage says Bristol, read from the register as it is now,
    not from the search index's copy (which still has no site). Restated for the door (REF S23, the Human's decision
    after round 7): the edit is a job holding the workspace's lock, as the details request would."""
    client, core, add, ask = env
    add("lighting.md", FILLER)
    add("leeds.md", "# Leeds note\n\nLeeds yard gates open at six.\n", applies_to=["Leeds"])
    guide = add("refunds.md", "# Refund policy\n\nThe refund window for returns is QUOKKA ten days.\n")
    scope_on()
    assert "QUOKKA" in ask("What is the refund window for returns at Leeds?")["answer"]
    with writing(core):
        core.state.register.update(guide, applies_to=["Bristol"])
    answer = ask("What is the refund window for returns at Leeds?")["answer"]
    assert "(Applies to: Bristol.) " in answer and "QUOKKA" in answer, "the site edit did not reach the passage's label"


def test_control_rebuilt_index_keeps_out_of_force_source(env):
    """Control for break 1 (passes now): the same edit followed by an index rebuild keeps the source out, so the leak
    is the stale snapshot, not the filter's date logic. Restated for the door (REF S23, the Human's decision after
    round 7): the edit is a job holding the workspace's lock, as the details request would."""
    client, core, add, ask = env
    add("lighting.md", FILLER)
    policy = add("refunds.md", "# Refund policy\n\nThe refund window for returns is ZORBLAX fourteen days.\n")
    scope_on()
    assert "ZORBLAX" in ask("What is the refund window for returns?")["answer"]
    with writing(core):
        core.state.register.update(policy, effective_to="2025-12-31")
    core.state.answer.retrieval.index.invalidate()
    assert "ZORBLAX" not in ask("What is the refund window for returns?")["answer"]


# ---- Break 2: an approval landing while the answer is prepared ------------------------------------------------------

def test_supersede_approved_mid_answer_lets_replaced_source_answer(env, monkeypatch):
    """Promise 1, replaced, two requests at once: the replacing source is approved after ScopeFilter is built. Restated
    after round 3 (the Human's decision: one reading per answer, no mid-answer recheck): this answer is judged on the
    reading taken as it began, so the 2025 policy answers once; the next answer has only the 2026 policy. Restated for
    the door (REF S23, the Human's decision after round 7): the approval is a job holding the workspace's lock, as its
    request would; the ask passes the door and does not wait, so the approval still lands mid-answer."""
    import assistant.answer.service as service
    client, core, add, ask = env
    old = add("old.md", "# Refund policy 2025\n\nThe refund window for returns is OLDWINDOW thirty days.\n")
    new = add("new.md", "# Refund policy 2026\n\nThe refund window for returns is NEWWINDOW fourteen days.\n",
              approve=False, supersedes=[old])
    scope_on()

    class Racing(service.ScopeFilter):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            as_job(core, decided, core.state.register, new, approval_status="approved")  # the approval lands now

    monkeypatch.setattr(service, "ScopeFilter", Racing)
    answer = ask("What is the refund window for returns?")
    assert core.state.register.get(new).approval_status == "approved"
    assert "OLDWINDOW" in answer["answer"] and "NEWWINDOW" not in answer["answer"]  # the reading as it began
    answer = ask("What is the refund window for returns?")
    assert "OLDWINDOW" not in answer["answer"], "a source replaced by an approved source in force answered"
    assert "NEWWINDOW" in answer["answer"]


# ---- Break 3: the date the question is about ------------------------------------------------------------------------
# After the stop rule the Human chose "today, future rules labelled" (3 Oct 2026): scope never guesses the date a question
# is about. These tests now hold the restated promise: whatever date the question mentions, the evidence is what is in
# force today plus what is approved for later, labelled with its start; an expired source never.

@pytest.mark.parametrize("question", [
    "What was the refund window for returns in 2025?",
    "What is the refund window for returns as of January 2027?",
    "What is the refund window for returns on 2027-01-01?",
    "What is the refund window for returns in Q1 2027?",
    "What is the refund window for returns?",
])
def test_whatever_date_is_asked_today_and_labelled_later_rules_answer(env, question):
    client, core, add, ask = env
    add("y2025.md", "# Refund policy 2025\n\nThe refund window for returns is WINDOW2025 thirty days.\n",
        effective_from="2025-01-01", effective_to="2025-12-31")
    add("y2026.md", "# Refund policy 2026\n\nThe refund window for returns is WINDOW2026 fourteen days.\n",
        effective_from="2026-01-01", effective_to="2026-12-31")
    add("y2027.md", "# Refund policy 2027\n\nThe refund window for returns is WINDOW2027 seven days.\n",
        effective_from="2027-01-01")
    scope_on()
    answer = ask(question)["answer"]  # the echo model repeats its evidence
    assert "WINDOW2025" not in answer, question
    assert "WINDOW2026" in answer and "In force until 31 December 2026" in answer, question
    assert "WINDOW2027" in answer and "In force from 1 January 2027" in answer, question


# ---- Break 4: nothing left out or labelled -------------------------------------------------------------------------

def test_nothing_left_out_or_labelled_answers_as_scope_off(env):
    """Promise restated: with scope on and nothing left out or labelled, the evidence, and so the answer, is the same."""
    client, core, add, ask = env
    add("a.md", "# Refunds\n\nThe refund window for returns is fourteen days.\n")
    add("b.md", "# Exchanges\n\nExchanges are accepted within thirty days.\n")
    off = ask("What is the refund window for returns?")
    scope_on()
    on = ask("What is the refund window for returns?")
    assert on["answer"] == off["answer"]


def test_with_no_site_named_each_site_passage_says_its_site(env):
    client, core, add, ask = env
    add("leeds.md", "# Leeds refunds\n\nThe refund window for returns at Leeds is fourteen days.\n", applies_to=["Leeds"])
    add("bristol.md", "# Bristol refunds\n\nThe refund window for returns at Bristol is ten days.\n",
        applies_to=["Bristol"])
    scope_on()
    answer = ask("What is the refund window for returns?")["answer"]
    assert "Applies to: Leeds" in answer and "Applies to: Bristol" in answer
