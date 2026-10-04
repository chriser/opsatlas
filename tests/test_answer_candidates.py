"""The phase 2 candidates under test, each off by default (REF H1, H3, H4): scope decides which approved source may
answer; a multi-part question is split into its parts; an answer the grounding check marks unsupported is withheld.
These tests pin the mechanisms; whether each is adopted is decided by its registered pass mark, not here."""
from datetime import date
from types import SimpleNamespace

from assistant.answer.scope import UNREADABLE, ScopeFilter, parts, read_date
from tests.door_helpers import decide


def source(sid, **scope):
    return SimpleNamespace(id=sid, approval_status="approved", effective_from=scope.get("start"), effective_to=scope.get("end"),
                           applies_to=scope.get("sites", []), supersedes=scope.get("replaces", []))


TODAY = date(2026, 10, 3)
SOURCES = [source("p25", start="2025-01-01", end="2025-12-31"), source("p26", start="2026-01-01", replaces=["p25"]),
           source("p27", start="2027-01-01", replaces=["p26"]), source("leeds", sites=["Leeds distribution centre"]),
           source("bristol", sites=["Bristol head office"]), source("plain")]


def test_scope_judges_by_today_and_labels_what_comes_later():
    """The Human's decisions after the stop rule (3 Oct 2026): nothing is read from the question, neither date nor site."""
    scope = ScopeFilter(SOURCES, TODAY)
    assert {s.id for s in SOURCES if scope.allow(s)} == {"p26", "p27", "leeds", "bristol", "plain"}
    assert scope.note(SOURCES[2]) == "(In force from 1 January 2027.) "
    assert not scope.allow(SOURCES[0])  # expired: left out (so its passages never reach the evidence)


def test_scope_labels_every_site_specific_passage_and_closes_the_facts():
    scope = ScopeFilter(SOURCES, TODAY)
    assert scope.note(SOURCES[3]) == "(Applies to: Leeds distribution centre.) "
    assert scope.note(SOURCES[4]) == "(Applies to: Bristol head office.) "
    assert scope.note(SOURCES[5]) == ""
    assert scope.closes_facts(SOURCES)  # something left out or labelled: no facts map, no process registry
    assert not ScopeFilter([SOURCES[5]], TODAY).closes_facts([SOURCES[5]])


def test_scope_reads_dates_one_way_as_the_details_editor_does():
    assert read_date("20261231") == read_date("2026-12-31") == date(2026, 12, 31)
    assert read_date(date(2027, 1, 1)) == date(2027, 1, 1)
    assert read_date(None) is None and read_date("") is None
    for bad in ("2026-12-311", "2027-1-1", " 2027-01-01", "31/12/2026", 20261231):
        assert read_date(bad) is UNREADABLE, bad


def test_a_multi_part_question_is_split_into_its_parts():
    assert parts("What did the evaluation find, and what limits how far it generalises?") == [
        "What did the evaluation find", "what limits how far it generalises"]
    assert parts("Who owns the ledger? Which system records the release?") == [
        "Who owns the ledger", "Which system records the release"]
    assert parts("Who approves refunds and returns?") == ["Who approves refunds and returns?"]


def test_an_unsupported_answer_is_withheld_only_when_the_candidate_is_on(tmp_path, monkeypatch):
    import os
    import socket

    from fastapi.testclient import TestClient
    from iam_helpers import sign_in
    from test_space_leaks import hermetic, refuse

    from assistant.answer.service import WITHHELD
    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    os.environ.update({"SME_TIBI_VOICE_URL": "http://127.0.0.1:9", "SALES_GOVERNANCE_AUTO_REVIEW": "0"})
    app = create_sales_app(tmp_path / "sales")
    hermetic(app)
    app.state.answer.validator = SimpleNamespace(validate=lambda answer, texts: "unsupported")
    with TestClient(app) as client:
        head = {"Authorization": f"Bearer {sign_in(client, app)}"}
        up = client.post("/api/sources/upload", files={"file": ("r.md", b"# Returns\n\nThe store manager approves refunds.\n",
                                                                 "text/markdown")}, headers=head).json()
        sid = up["id"] if "id" in up else up["source"]["id"]
        client.post(f"/api/sources/{sid}/ingest", headers=head)
        decide(client, sid, headers=head)
        shown = client.post("/api/ask", json={"q": "Who approves refunds?"}, headers=head).json()
        assert not shown["refused"] and shown["grounding"] == "unsupported"
        os.environ["KP_WITHHOLD_UNSUPPORTED"] = "1"
        held = client.post("/api/ask", json={"q": "Who approves refunds?"}, headers=head).json()
        assert held["refused"] and WITHHELD in held["answer"] and held["citations"] == []
