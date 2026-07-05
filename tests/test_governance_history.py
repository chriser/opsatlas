"""Governance lifecycle analytics tests."""

from fastapi.testclient import TestClient

from assistant.analytics.event_store import AnalyticsEventStore
from assistant.analytics.governance_history import build_governance_history, record_governance_snapshot
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.ingestion.store import SectionStore
from assistant.retrieval.service import RetrievalService
from assistant.sources.register import SourceRegister

PASSWORD = "test-pass"


def _report(detail: str = "Needs action.") -> dict:
    return {
        "issues": {
            "compliance": [
                {
                    "check": "metadata_title",
                    "severity": "low",
                    "source_id": "src-1",
                    "source_title": "Source One",
                    "detail": detail,
                }
            ],
            "consistency": [],
            "correctness": [],
        }
    }


def test_snapshot_records_detected_once_per_day_and_resolves_missing_issue(tmp_path):
    store = AnalyticsEventStore(tmp_path)

    record_governance_snapshot(_report(), store, timestamp="2026-06-22T09:00:00Z")
    record_governance_snapshot(_report(), store, timestamp="2026-06-22T10:00:00Z")
    record_governance_snapshot(
        {"issues": {"compliance": [], "consistency": [], "correctness": []}},
        store,
        timestamp="2026-06-23T09:00:00Z",
    )

    events = store.events()
    assert [event.event_type for event in events] == [
        "governance_issue_detected",
        "governance_issue_resolved",
    ]
    assert events[0].metadata == {
        "category": "compliance",
        "check": "metadata_title",
        "severity": "low",
        "source_title": "Source One",
    }
    assert events[1].entity_id == events[0].entity_id


def test_governance_history_builds_burndown_and_resolution_metrics(tmp_path):
    store = AnalyticsEventStore(tmp_path)
    record_governance_snapshot(_report(), store, timestamp="2026-06-22T09:00:00Z")
    record_governance_snapshot(_report(), store, timestamp="2026-06-23T09:00:00Z")
    record_governance_snapshot(
        {"issues": {"compliance": [], "consistency": [], "correctness": []}},
        store,
        timestamp="2026-06-24T09:00:00Z",
    )

    out = build_governance_history(store.events())

    assert out["issue_events_over_time"] == [
        {"date": "2026-06-22", "detected": 1, "accepted": 0, "resolved": 0, "open": 1},
        {"date": "2026-06-23", "detected": 1, "accepted": 0, "resolved": 0, "open": 1},
        {"date": "2026-06-24", "detected": 0, "accepted": 0, "resolved": 1, "open": 0},
    ]
    assert out["mean_time_to_resolve_hours"] == 48.0
    assert out["resolved_count"] == 1
    assert out["open_count"] == 0
    assert out["recurring_issues"][0]["detections"] == 2
    assert out["recurring_issues"][0]["state"] == "resolved"


def test_governance_history_endpoint_records_overview_events(tmp_path):
    register = SourceRegister(tmp_path)
    store = SectionStore(register.base_dir)
    retrieval = RetrievalService(register, store)
    client = TestClient(create_app(register, AuthService(PASSWORD), retrieval=retrieval))
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    client.post(
        "/api/sources/upload",
        files={"file": ("plain.md", b"Plain body without a custom title.", "text/markdown")},
        data={"title": "plain"},
    )

    # GET is read-only; capturing a snapshot is an explicit POST.
    assert client.get("/api/analytics/governance-history").json()["open_count"] == 0
    history = client.post("/api/analytics/governance-history/snapshot").json()

    assert history["open_count"] >= 1
    assert any(row["detected"] >= 1 for row in history["issue_events_over_time"])
    audit = client.get("/api/ontology/actions/log").json()["executions"][0]
    assert audit["action"] == "capture_governance_snapshot"
    assert audit["actor"]["type"] == "operator"
    assert audit["outcome"] == "ok"
