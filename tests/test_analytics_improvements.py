"""Analytics improvement action lifecycle tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.sources.register import SourceRegister

PASSWORD = "improvement-test-pass"


def test_improvement_action_lifecycle_is_protected_and_audited(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KP_DATA_DIR", str(tmp_path))
    client = TestClient(create_app(SourceRegister(tmp_path), AuthService(PASSWORD)))

    assert client.get("/api/analytics/improvements").status_code == 401

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})

    create_response = client.post(
        "/api/analytics/improvements",
        json={
            "trigger_type": "failed_retrieval",
            "trigger_ref": "pattern-123",
            "recommended_action": "Add clearer supplier ordering day guidance.",
            "owner_role": "Process owner",
            "review_cadence": "weekly",
            "note": "Raised from retrieval health.",
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()["action"]
    assert created["id"].startswith("imp-")
    assert created["status"] == "open"
    assert created["notes"][0]["note"] == "Raised from retrieval health."

    list_response = client.get("/api/analytics/improvements")
    assert list_response.json()["action_count"] == 1

    in_progress = client.post(
        f"/api/analytics/improvements/{created['id']}/transition",
        json={"status": "in_progress", "note": "Owner review started."},
    )
    assert in_progress.status_code == 200
    assert in_progress.json()["action"]["status"] == "in_progress"

    cannot_close = client.post(
        f"/api/analytics/improvements/{created['id']}/transition",
        json={"status": "closed", "note": "Done."},
    )
    assert cannot_close.status_code == 400
    assert "linked_source_id" in cannot_close.json()["detail"]

    closed = client.post(
        f"/api/analytics/improvements/{created['id']}/transition",
        json={"status": "closed", "linked_source_id": "src-123", "note": "Source updated."},
    )
    assert closed.status_code == 200
    action = closed.json()["action"]
    assert action["status"] == "closed"
    assert action["linked_source_id"] == "src-123"
    assert action["closed_at"]

    log = client.get("/api/ontology/actions/log").json()["executions"]
    assert [row["action"] for row in log[:4]] == [
        "transition_improvement_action",
        "transition_improvement_action",
        "transition_improvement_action",
        "create_improvement_action",
    ]
    assert log[0]["outcome"] == "ok"
    assert log[1]["outcome"] == "error"


def test_improvement_action_rejects_invalid_transition(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KP_DATA_DIR", str(tmp_path))
    client = TestClient(create_app(SourceRegister(tmp_path), AuthService(PASSWORD)))
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})

    created = client.post(
        "/api/analytics/improvements",
        json={
            "trigger_type": "recurring_question",
            "trigger_ref": "recurring-abc",
            "recommended_action": "Clarify a recurring question in the source pack.",
            "owner_role": "Knowledge owner",
            "review_cadence": "monthly",
        },
    ).json()["action"]

    response = client.post(
        f"/api/analytics/improvements/{created['id']}/transition",
        json={"status": "closed", "linked_source_id": "src-1"},
    )

    assert response.status_code == 400
    assert "Cannot transition" in response.json()["detail"]
