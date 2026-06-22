"""Historical analytics aggregation tests."""

from fastapi.testclient import TestClient

from assistant.analytics.aggregation import build_history
from assistant.analytics.event_store import AnalyticsEventStore
from assistant.analytics.events import AnalyticsEvent
from assistant.analytics.log import UsageEntry
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.sources.register import SourceRegister

PASSWORD = "test-pass"


def test_build_history_empty_is_safe():
    out = build_history([])

    assert out["event_count"] == 0
    assert out["events_over_time"] == []
    assert out["by_event_type"] == []
    assert out["value"]["total_estimate"] == 0
    assert [row["count"] for row in out["latency"]] == [0, 0, 0, 0, 0]


def test_build_history_aggregates_mixed_ledger_events():
    events = [
        AnalyticsEvent(
            event_type="source_uploaded",
            timestamp="2026-06-22T09:00:00Z",
            source_id="s1",
            metadata={"title": "Supplier pack"},
        ),
        AnalyticsEvent(
            event_type="ask_answered",
            timestamp="2026-06-22T10:00:00Z",
            outcome="answered",
            process_area="supplier setup",
            metadata={"topic": "checks", "confidence": "grounded", "latency_ms": 850},
        ),
        AnalyticsEvent(
            event_type="ask_refused",
            timestamp="2026-06-23T10:00:00Z",
            outcome="refused",
            metadata={"topic": "finance_mapping", "confidence": "none", "latency_ms": 2200},
        ),
        AnalyticsEvent(
            event_type="governance_issue_accepted",
            timestamp="2026-06-23T11:00:00Z",
            source_id="s1",
            outcome="accepted",
            metadata={"check": "duplicate"},
        ),
        AnalyticsEvent(
            event_type="simulation_run_completed",
            timestamp="2026-06-23T12:00:00Z",
            persona="new starter",
            outcome="completed",
        ),
        AnalyticsEvent(
            event_type="value_event_recorded",
            timestamp="2026-06-23T13:00:00Z",
            value_driver="time_saved",
            value_estimate=12.5,
        ),
    ]

    out = build_history(events)

    assert out["event_count"] == 6
    assert out["events_over_time"] == [
        {
            "date": "2026-06-22",
            "event_count": 2,
            "assistant_usage": 1,
            "external_context": 0,
            "governance": 0,
            "simulation": 0,
            "source_lifecycle": 1,
            "value": 0,
        },
        {
            "date": "2026-06-23",
            "event_count": 4,
            "assistant_usage": 1,
            "external_context": 0,
            "governance": 1,
            "simulation": 1,
            "source_lifecycle": 0,
            "value": 1,
        },
    ]
    assert {"group": "assistant_usage", "count": 2} in out["by_group"]
    assert {"event_type": "ask_answered", "count": 1} in out["by_event_type"]
    assert {"topic": "checks", "count": 1} in out["by_topic"]
    assert {"process_area": "supplier setup", "count": 1} in out["by_process"]
    assert {"source": "Supplier pack", "count": 1} in out["by_source"]
    assert {"issue_type": "duplicate", "count": 1} in out["by_issue_type"]
    assert {"persona": "new starter", "count": 1} in out["by_persona"]
    assert out["latency"][0] == {"bucket": "<1s", "count": 1}
    assert out["latency"][2] == {"bucket": "2-4s", "count": 1}
    assert out["value"]["total_estimate"] == 12.5
    assert out["value"]["by_driver"] == [{"value_driver": "time_saved", "count": 1}]


def test_build_history_backfills_legacy_usage_when_ask_events_absent():
    entries = [
        UsageEntry(
            timestamp="2026-06-22T10:00:00Z",
            question="Are credit checks mandatory?",
            mode="retrieval",
            refused=False,
            confidence="grounded",
            citation_count=2,
        ),
        UsageEntry(
            timestamp="2026-06-22T11:00:00Z",
            question="What is the VAT number?",
            mode="empty",
            refused=True,
        ),
    ]

    out = build_history([], usage_entries=entries, traces=[{"latency_ms": 1500}])

    assert out["event_count"] == 2
    assert {"outcome": "answered", "count": 1} in out["by_outcome"]
    assert {"outcome": "refused", "count": 1} in out["by_outcome"]
    assert {"topic": "checks", "count": 1} in out["by_topic"]
    assert out["latency"][1] == {"bucket": "1-2s", "count": 1}


def test_history_endpoint_reads_event_ledger(tmp_path):
    register = SourceRegister(tmp_path)
    events = AnalyticsEventStore(register.base_dir)
    events.record(
        "ask_answered",
        timestamp="2026-06-22T10:00:00Z",
        outcome="answered",
        metadata={"topic": "checks", "confidence": "grounded"},
    )
    client = TestClient(create_app(register, AuthService(PASSWORD)))
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})

    out = client.get("/api/analytics/history").json()

    assert out["event_count"] == 1
    assert out["events_over_time"][0]["assistant_usage"] == 1
    assert {"topic": "checks", "count": 1} in out["by_topic"]
