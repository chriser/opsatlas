"""Ontology agent proposal API tests."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.sources.register import SourceRegister

PASSWORD = "test-pass"


class ScriptedGenerator:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses

    def generate(self, prompt: str) -> str:
        if not self.responses:
            return '{"final_answer":"done"}'
        return self.responses.pop(0)


def test_agent_run_persists_proposal_and_approve_executes_once(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KP_DATA_DIR", str(tmp_path))
    client = _client(tmp_path)
    rec = client.post("/api/sources/upload", files={"file": ("a.txt", b"hello", "text/plain")}, data={"title": "a"}).json()
    client.app.state.ontology_agent.generator = ScriptedGenerator([
        json.dumps({
            "tool": "propose_action",
            "args": {
                "action": "accept_issue",
                "params": {"source_id": rec["id"], "check": "not_ingested", "detail": "Accepted by agent proposal."},
                "rationale": "The operator should accept this known issue.",
            },
        }),
        json.dumps({"final_answer": "I proposed accepting the issue."}),
    ])

    run = client.post("/api/ontology/agent/runs", json={"question": "Investigate this issue"}).json()

    assert run["final_answer"] == "I proposed accepting the issue."
    proposal = run["persisted_proposals"][0]
    assert proposal["status"] == "pending"
    assert proposal["action"] == "accept_issue"
    assert client.get("/api/ontology/proposals").json()["count"] == 1

    approved = client.post(f"/api/ontology/proposals/{proposal['proposal_id']}/approve").json()

    assert approved["proposal"]["status"] == "approved"
    assert approved["proposal"]["execution_id"] == approved["execution"]["execution_id"]
    assert approved["execution"]["outcome"] == "ok"
    action_log = client.get("/api/ontology/actions/log").json()["executions"]
    assert [row["action"] for row in action_log] == ["accept_issue"]
    assert action_log[0]["actor"]["type"] == "agent"
    assert action_log[0]["actor"]["approved_by"] == "operator"

    second = client.post(f"/api/ontology/proposals/{proposal['proposal_id']}/approve").json()

    assert second["already_approved"] is True
    assert len(client.get("/api/ontology/actions/log").json()["executions"]) == 1
    event_types = _ontology_event_types(client)
    assert event_types == [
        "agent_run_completed",
        "action_proposed",
        "governance_issue_accepted",
        "action_approved",
    ]


def test_declined_proposal_cannot_execute(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KP_DATA_DIR", str(tmp_path))
    client = _client(tmp_path)
    rec = client.post("/api/sources/upload", files={"file": ("a.txt", b"hello", "text/plain")}, data={"title": "a"}).json()
    client.app.state.ontology_agent.generator = ScriptedGenerator([
        json.dumps({
            "tool": "propose_action",
            "args": {
                "action": "accept_issue",
                "params": {"source_id": rec["id"], "check": "not_ingested", "detail": "Decline this."},
                "rationale": "This one should be declined.",
            },
        }),
        json.dumps({"final_answer": "I proposed an action."}),
    ])
    run = client.post("/api/ontology/agent/runs", json={"question": "Investigate"}).json()
    proposal_id = run["persisted_proposals"][0]["proposal_id"]

    declined = client.post(f"/api/ontology/proposals/{proposal_id}/decline", json={"reason": "Not needed."}).json()

    assert declined["proposal"]["status"] == "declined"
    assert declined["proposal"]["declined_reason"] == "Not needed."
    assert client.post(f"/api/ontology/proposals/{proposal_id}/approve").status_code == 409
    assert client.get("/api/ontology/actions/log").json()["count"] == 0
    event_types = _ontology_event_types(client)
    assert event_types == ["agent_run_completed", "action_proposed", "action_declined"]


def _client(tmp_path) -> TestClient:
    client = TestClient(create_app(SourceRegister(tmp_path), AuthService(PASSWORD)))
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def _ontology_event_types(client: TestClient) -> list[str]:
    relevant = {"agent_run_completed", "action_proposed", "governance_issue_accepted", "action_approved", "action_declined"}
    return [event.event_type for event in client.app.state.analytics_events.events() if event.event_type in relevant]
