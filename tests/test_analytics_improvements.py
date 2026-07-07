"""Analytics improvement action lifecycle tests."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from assistant.analytics.improvement import ImprovementAction, build_improvement_loop_metrics
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
    metrics = client.get("/api/analytics/improvements/metrics").json()
    assert metrics["action_count"] == 1
    assert metrics["status_counts"]["closed"] == 1
    assert metrics["rates"]["actioned_rate"] == 1.0


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


def test_improvement_loop_metrics_measure_age_due_and_repeat_triggers() -> None:
    now = datetime(2026, 7, 7, tzinfo=timezone.utc)
    actions = [
        ImprovementAction(
            id="imp-open",
            trigger_type="failed_retrieval",
            trigger_ref="pattern-1",
            recommended_action="Add ordering day guidance.",
            owner_role="Knowledge owner",
            review_cadence="weekly",
            status="open",
            created_at="2026-06-20T00:00:00+00:00",
            updated_at="2026-06-25T00:00:00+00:00",
        ),
        ImprovementAction(
            id="imp-actioned",
            trigger_type="failed_retrieval",
            trigger_ref="pattern-1",
            recommended_action="Update the same source section.",
            owner_role="Knowledge owner",
            review_cadence="monthly",
            status="actioned",
            created_at="2026-07-01T00:00:00+00:00",
            updated_at="2026-07-02T00:00:00+00:00",
        ),
        ImprovementAction(
            id="imp-closed",
            trigger_type="recurring_question",
            trigger_ref="recurring-1",
            recommended_action="Clarify RACI wording.",
            owner_role="Process owner",
            review_cadence="weekly",
            status="closed",
            linked_source_id="src-1",
            created_at="2026-06-01T00:00:00+00:00",
            updated_at="2026-06-06T00:00:00+00:00",
            closed_at="2026-06-06T00:00:00+00:00",
        ),
        ImprovementAction(
            id="imp-wont",
            trigger_type="knowledge_gap",
            trigger_ref="gap-1",
            recommended_action="No change required after review.",
            owner_role="Governance owner",
            review_cadence="ad_hoc",
            status="wont_fix",
            created_at="2026-07-01T00:00:00+00:00",
            updated_at="2026-07-01T00:00:00+00:00",
            closed_at="2026-07-01T00:00:00+00:00",
        ),
    ]

    metrics = build_improvement_loop_metrics(actions, now=now)

    assert metrics["action_count"] == 4
    assert metrics["status_counts"] == {
        "open": 1,
        "in_progress": 0,
        "actioned": 1,
        "closed": 1,
        "wont_fix": 1,
    }
    assert metrics["rates"]["actioned_rate"] == 0.5
    assert metrics["rates"]["repeat_trigger_rate"] == 0.25
    assert metrics["age"]["oldest_open_age_days"] == 17.0
    assert metrics["age"]["mean_time_to_close_days"] == 5.0
    assert metrics["review_due_count"] == 1
    assert metrics["review_due"][0]["id"] == "imp-open"
    assert metrics["owner_workload"] == [{"owner_role": "Knowledge owner", "open_actions": 2}]
