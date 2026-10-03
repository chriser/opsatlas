"""REF S20: Tibi's turns in the usage analytics, by channel; a Tibi turn without approved evidence as a knowledge gap;
good, odd and wrong on written answers, and an improvement action from a wrong mark, on an answer or a Tibi turn.

Hermetic: the Tibi service address goes nowhere, every outbound connection is refused, and the Product Guide answers
with a model that echoes its prompt."""
import os
import socket
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from iam_helpers import sign_in
from test_space_leaks import hermetic, refuse

from assistant.analytics.feedback import AnswerFeedbackStore

PW = "walnut harbour lantern seventeen"


def turn(session, n, heard, route, grounding, records=(), mode="chat", typed=False, outcome="completed"):
    return {"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z"), "session": session, "turn": n,
            "mode": mode, "typed": typed, "heard": heard, "reply": "A reply.", "route": route, "grounding": grounding,
            "records": list(records), "outcome": outcome}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    from assistant.iam.service import Actor
    from services.opsatlas_sales import conversations
    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    os.environ.update({"SME_TIBI_VOICE_URL": "http://127.0.0.1:9", "SALES_GOVERNANCE_AUTO_REVIEW": "0"})
    root = tmp_path / "sales"
    app = create_sales_app(root)
    hermetic(app)
    for row in (
        turn("v-1", 0, "Hello Tibi, how are you?", "conversation", "conversation"),
        turn("v-1", 1, "Does OpsAtlas export the process map to Visio?", "product", "no_approved_evidence"),
        turn("v-1", 2, "What does OpsAtlas do?", "product", "grounded_synthesis", ["opsatlas-overview"]),
        turn("v-1", 3, "", "conversation", "conversation"),  # heard nothing: not usage
        turn("t-1", 0, "Which languages does the voice support?", "product", "approved_fallback", ["voice"], typed=True),
        turn("t-1", 1, "Tell me about yourself", "self", "approved_spoken", ["tiberius"], typed=True),
        turn("d-1", 0, "Can OpsAtlas run offline?", "product", "no_approved_evidence", mode="digital_sme", typed=True),
        turn("d-1", 1, "Thanks, that's all", "conversation", "conversation", mode="digital_sme", typed=True),
    ):
        conversations.append(root, row)
    with TestClient(app) as client:
        admin = {"Authorization": f"Bearer {sign_in(client, app)}"}
        iam = app.state.auth.iam
        admin_id = iam.store.one("SELECT id FROM users WHERE login = ?", ("operator@example.test",))["id"]
        app.state.tibi_owners.record("v-1", admin_id, "voice")
        invited = iam.invite(Actor(admin_id, fresh=True), email="sam@example.test", display_name="Sam",
                             role_id="sales_user", space_id="product-guide")
        iam.accept_invitation(invited["token"], PW)
        sam = {"Authorization": f"Bearer {sign_in(client, app, 'sam@example.test', PW)}"}
        yield client, app, admin, sam, admin_id


def test_tibi_turns_count_in_the_scorecard_by_channel(workspace):
    client, app, admin, _, admin_id = workspace
    card = client.get("/api/analytics/scorecard", headers=admin)
    assert card.status_code == 200, card.text
    card = card.json()
    channels = card["by_channel"]
    assert channels["voice"]["queries"] == 3 and channels["voice"]["refused"] == 1
    assert channels["typed"]["queries"] == 2 and channels["typed"]["refused"] == 0
    assert channels["digital_sme"] == {"queries": 2, "answered": 1, "refused": 1, "answer_rate": 0.5, "refusal_rate": 0.5}
    # The totals are every channel, each turn once; nothing was copied into the core's usage log.
    assert card["total_queries"] == sum(c["queries"] for c in channels.values()) == 7
    assert not (app.state.register.base_dir / "usage_log.json").exists()
    assert "Does OpsAtlas export the process map to Visio?" in card["knowledge_gaps"]
    assert "Hello Tibi, how are you?" not in card["knowledge_gaps"]
    # Who asked: the conversation's owner, where the gateway recorded one.
    tibi = {e.question: e for e in app.state.usage_log.entries()}
    assert tibi["What does OpsAtlas do?"].actor_id == admin_id and tibi["What does OpsAtlas do?"].confidence == "grounded"
    assert tibi["Can OpsAtlas run offline?"].actor_id is None and tibi["Can OpsAtlas run offline?"].space == "product-guide"
    # The time series behind the forecasts read Tibi's times, written with an offset and no colon, as well.
    for path in ("/api/analytics/timeseries", "/api/analytics/retrieval-health", "/api/analytics/charts"):
        assert client.get(path, headers=admin).status_code == 200, path


def test_how_a_turn_is_read():
    from services.opsatlas_sales.tibi_usage import entry
    row = entry({"at": "2026-10-03T09:30:00+0100", "session": "s", "turn": 4, "heard": "Is there an API?", "route": "product",
                 "grounding": "no_approved_evidence", "records": [], "mode": "rehearsal"}, "person-1")
    assert row.id == "tibi:s:4" and row.timestamp == "2026-10-03T09:30:00+01:00" and row.channel == "voice"
    assert row.refused and row.gap_eligible and row.actor_id == "person-1" and row.answer_path == "tibi"
    assert entry({"at": "yesterday", "heard": "Hello"}) is None
    failed = entry({"at": "2026-10-03T09:30:00+0100", "heard": "Is there an API?", "route": None, "outcome": "failed"})
    assert failed.refused and not failed.gap_eligible
    interview = entry({"at": "2026-10-03T09:30:00+0100", "heard": "We approve it in SAP.", "mode": "process_interview",
                       "grounding": "no_product_claim"})
    assert not interview.refused and not interview.gap_eligible


def test_a_tibi_turn_without_approved_evidence_is_a_knowledge_gap_and_chit_chat_is_not(workspace):
    client, _, admin, sam, _ = workspace
    gaps = client.get("/api/analytics/knowledge-gaps", headers=admin)
    assert gaps.status_code == 200, gaps.text
    questions = [q for c in gaps.json()["clusters"] for q in c["representative_questions"]]
    assert "Does OpsAtlas export the process map to Visio?" in questions
    assert "Can OpsAtlas run offline?" in questions
    assert "Which languages does the voice support?" in questions  # answered with fallback wording: weak evidence
    assert gaps.json()["total_candidates"] == 3
    for social in ("Hello Tibi, how are you?", "Thanks, that's all", "Tell me about yourself", "What does OpsAtlas do?"):
        assert social not in questions
    assert client.get("/api/analytics/knowledge-gaps", headers=sam).status_code == 403


def test_a_written_answer_is_rated_and_a_wrong_mark_raises_an_improvement_action(workspace):
    client, _, admin, sam, admin_id = workspace
    answer = client.post("/api/ask", json={"q": "What does OpsAtlas do?"}, headers=admin)
    assert answer.status_code == 200, answer.text
    answer_id = answer.json()["usage_id"]
    assert answer_id.startswith("ans-")
    good = client.post(f"/api/answers/{answer_id}/feedback", json={"verdict": "good"}, headers=admin)
    assert good.status_code == 200 and good.json()["action_id"] is None
    wrong = client.post(f"/api/answers/{answer_id}/feedback",
                        json={"verdict": "wrong", "note": "It left out the governance review.", "raise_action": True},
                        headers=admin)
    assert wrong.status_code == 200, wrong.text
    saved = wrong.json()
    assert saved["feedback"]["verdict"] == "wrong" and saved["feedback"]["actor_id"] == admin_id
    actions = client.get("/api/analytics/improvements", headers=admin).json()["actions"]
    raised = [a for a in actions if a["id"] == saved["action_id"]]
    assert raised and raised[0]["trigger_type"] == "answer_feedback" and raised[0]["trigger_ref"] == answer_id
    assert raised[0]["recommended_action"] == "It left out the governance review."
    # Marking it again does not raise a second action while the first is open.
    again = client.post(f"/api/answers/{answer_id}/feedback", json={"verdict": "wrong", "raise_action": True}, headers=admin)
    assert again.json()["action_id"] == saved["action_id"]
    assert client.post(f"/api/answers/{answer_id}/feedback", json={"verdict": "good", "raise_action": True},
                       headers=admin).status_code == 400
    assert client.post(f"/api/answers/{answer_id}/feedback", json={"verdict": "meh"}, headers=admin).status_code == 422
    assert client.post("/api/answers/ans-000000000000/feedback", json={"verdict": "odd"}, headers=admin).status_code == 404
    # Another person's answer is not theirs to rate: 404, as one that does not exist.
    assert client.post(f"/api/answers/{answer_id}/feedback", json={"verdict": "odd"}, headers=sam).status_code == 404


def test_rating_needs_the_right_to_ask_and_raising_needs_the_right_to_create_actions(workspace):
    client, app, admin, sam, admin_id = workspace
    mine = client.post("/api/ask", json={"q": "What does OpsAtlas do?"}, headers=sam)
    assert mine.status_code == 200, mine.text
    sam_answer = mine.json()["usage_id"]
    assert client.post(f"/api/answers/{sam_answer}/feedback", json={"verdict": "odd", "note": "Vague."},
                       headers=sam).status_code == 200
    # A sales user may not raise improvement actions: refused, and nothing is stored or created.
    refused = client.post(f"/api/answers/{sam_answer}/feedback", json={"verdict": "wrong", "raise_action": True}, headers=sam)
    assert refused.status_code == 403
    assert client.get("/api/analytics/improvements", headers=admin).json()["actions"] == []
    # Without knowledge.ask, no feedback at all: signed out, or with asking denied to the person in the space.
    assert client.post(f"/api/answers/{sam_answer}/feedback", json={"verdict": "good"}).status_code == 401
    from assistant.iam.service import Actor
    iam = app.state.auth.iam
    sam_id = iam.store.one("SELECT id FROM users WHERE login = ?", ("sam@example.test",))["id"]
    iam.deny(Actor(admin_id, fresh=True), subject_id=sam_id, permission="knowledge.ask", scope_type="space",
             scope_id="product-guide", reason="test")
    assert client.post("/api/ask", json={"q": "What does OpsAtlas do?"}, headers=sam).status_code == 403
    assert client.post(f"/api/answers/{sam_answer}/feedback", json={"verdict": "good"}, headers=sam).status_code == 403
    stored = AnswerFeedbackStore(app.state.register.base_dir).latest().values()
    assert [(r["actor_id"], r["verdict"]) for r in stored] == [(sam_id, "odd")]  # the refused marks were not kept


def test_a_wrong_tibi_turn_raises_an_improvement_action_for_who_may_create_them(workspace):
    client, _, admin, sam, _ = workspace
    path = "/api/conversations/v-1/turns/1"
    assert client.post(f"{path}/improvement", headers=admin).status_code == 400  # not marked yet
    marked = client.put(f"{path}/review", json={"verdict": "wrong", "note": "Say plainly that Visio export is not offered."},
                        headers=admin)
    assert marked.status_code == 200, marked.text
    raised = client.post(f"{path}/improvement", headers=admin)
    assert raised.status_code == 200, raised.text
    action = raised.json()["action"]
    assert action["trigger_type"] == "answer_feedback" and action["trigger_ref"] == "tibi:v-1:1"
    assert action["recommended_action"] == "Say plainly that Visio export is not offered."
    listed = client.get("/api/analytics/improvements", headers=admin).json()["actions"]
    assert [a["id"] for a in listed] == [action["id"]]
    assert client.post(f"{path}/improvement", headers=sam).status_code == 403
    assert client.post("/api/conversations/v-1/turns/9/improvement", headers=admin).status_code == 404
