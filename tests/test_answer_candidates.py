"""The phase 2 candidates under test, each off by default (REF H1, H3, H4): scope decides which approved source may
answer; a multi-part question is split into its parts; an answer the grounding check marks unsupported is withheld.
These tests pin the mechanisms; whether each is adopted is decided by its registered pass mark, not here."""
from datetime import date
from types import SimpleNamespace

from assistant.answer.scope import ScopeFilter, asked_date, asked_site, parts


def source(sid, **scope):
    return SimpleNamespace(id=sid, approval_status="approved", effective_from=scope.get("start"), effective_to=scope.get("end"),
                           applies_to=scope.get("sites", []), supersedes=scope.get("replaces", []))


TODAY = date(2026, 10, 3)
SOURCES = [source("p25", start="2025-01-01", end="2025-12-31"), source("p26", start="2026-01-01", replaces=["p25"]),
           source("p27", start="2027-01-01", replaces=["p26"]), source("leeds", sites=["Leeds distribution centre"]),
           source("bristol", sites=["Bristol head office"]), source("plain")]


def allowed(question):
    scope = ScopeFilter(SOURCES, question, TODAY)
    return {s.id for s in SOURCES if scope.allow(s)}


def test_the_date_a_question_is_about():
    assert asked_date("What is the demo policy?", TODAY) == TODAY
    assert asked_date("What will the demo policy be in 2027?", TODAY) == date(2027, 1, 1)
    assert asked_date("What changes next year?", TODAY) == date(2027, 1, 1)
    assert asked_date("What did 2025 say?", TODAY) == TODAY  # a past year is not a future date to answer for


def test_scope_lets_only_sources_in_force_for_the_site_asked_answer():
    assert allowed("What is the demo policy now?") == {"p26", "leeds", "bristol", "plain"}
    assert allowed("What will the demo policy be in 2027?") == {"p27", "leeds", "bristol", "plain"}
    assert allowed("How long is onboarding at Leeds?") == {"p26", "leeds", "plain"}
    assert asked_site("Who is the contact at Bristol?", ["Bristol head office", "Leeds distribution centre"]) == "Bristol head office"
    scope = ScopeFilter(SOURCES, "How long is pilot onboarding?", TODAY)
    assert scope.note(SOURCES[3]) == "(Applies to: Leeds distribution centre.) "  # no site named: each passage says its own


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
        client.post(f"/api/governance/sources/{sid}/approve", headers=head)
        shown = client.post("/api/ask", json={"q": "Who approves refunds?"}, headers=head).json()
        assert not shown["refused"] and shown["grounding"] == "unsupported"
        os.environ["KP_WITHHOLD_UNSUPPORTED"] = "1"
        held = client.post("/api/ask", json={"q": "Who approves refunds?"}, headers=head).json()
        assert held["refused"] and WITHHELD in held["answer"] and held["citations"] == []
