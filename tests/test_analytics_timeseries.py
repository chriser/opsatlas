"""Time-series analytics aggregation tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from assistant.analytics.events import AnalyticsEvent
from assistant.analytics.log import UsageEntry
from assistant.analytics.timeseries import build_time_series
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.sources.register import SourceRegister

PASSWORD = "timeseries-test-pass"


def test_time_series_daily_zero_fill_and_rates() -> None:
    usage = [
        UsageEntry(
            timestamp="2026-07-01T09:00:00+00:00",
            question="What is the supplier setup process?",
            mode="ask",
            answer_path="rag",
            refused=False,
            confidence="grounded",
            citation_count=2,
        ),
        UsageEntry(
            timestamp="2026-07-03T09:00:00+00:00",
            question="What is missing?",
            mode="ask",
            answer_path="rag",
            refused=True,
            confidence="none",
            citation_count=0,
        ),
        UsageEntry(
            timestamp="2026-07-03T10:00:00+00:00",
            question="Which list owner?",
            mode="ask",
            answer_path="rag",
            refused=False,
            confidence="review",
            citation_count=1,
        ),
    ]
    events = [
        AnalyticsEvent(
            event_type="governance_issue_detected",
            timestamp="2026-07-03T12:00:00+00:00",
            entity_id="issue-1",
        )
    ]

    report = build_time_series(usage, events, bucket="daily")

    assert report["span"] == {"start": "2026-07-01", "end": "2026-07-03"}
    volume = report["series"]["query_volume"]["points"]
    refusal = report["series"]["refusal_rate"]["points"]
    low_grounding = report["series"]["low_grounding_rate"]["points"]
    citations = report["series"]["citations_per_answer"]["points"]
    governance = report["series"]["governance_issue_count"]["points"]
    assert volume == [
        {"date": "2026-07-01", "value": 1.0},
        {"date": "2026-07-02", "value": 0.0},
        {"date": "2026-07-03", "value": 2.0},
    ]
    assert refusal[1]["value"] == 0.0
    assert refusal[2]["value"] == 0.5
    assert low_grounding[2]["value"] == 0.5
    assert citations[0]["value"] == 2.0
    assert citations[2]["value"] == 1.0
    assert governance[2]["value"] == 1.0
    assert report["series"]["query_volume"]["metadata"]["n"] == 3


def test_time_series_weekly_bucket_and_api_auth(tmp_path) -> None:
    usage = [
        UsageEntry(
            timestamp="2026-07-01T09:00:00+00:00",
            question="First",
            mode="ask",
            answer_path="rag",
            refused=False,
            confidence="grounded",
            citation_count=1,
        ),
        UsageEntry(
            timestamp="2026-07-08T09:00:00+00:00",
            question="Second",
            mode="ask",
            answer_path="rag",
            refused=False,
            confidence="grounded",
            citation_count=1,
        ),
    ]
    report = build_time_series(usage, [], bucket="weekly")
    assert [point["date"] for point in report["series"]["query_volume"]["points"]] == ["2026-06-29", "2026-07-06"]
    assert [point["value"] for point in report["series"]["query_volume"]["points"]] == [1.0, 1.0]

    client = TestClient(create_app(SourceRegister(tmp_path), AuthService(PASSWORD)))
    assert client.get("/api/analytics/timeseries").status_code == 401

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.app.state.answer.usage_log.append(usage[0])
    response = client.get("/api/analytics/timeseries?bucket=weekly", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["bucket"] == "weekly"
