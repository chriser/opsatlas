"""Retrieval-health analytics tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from assistant.analytics.log import UsageEntry
from assistant.analytics.retrieval_health import build_retrieval_health
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.sources.register import SourceRegister

PASSWORD = "retrieval-health-test-pass"


def test_retrieval_health_rates_topics_and_failing_patterns() -> None:
    entries = [
        _entry("2026-07-01T09:00:00+00:00", "Who owns supplier ordering days?", confidence="grounded", citations=2),
        _entry("2026-07-02T09:00:00+00:00", "Who owns supplier ordering days?", refused=True, confidence="none", citations=0),
        _entry("2026-07-03T09:00:00+00:00", "Who owns supplier ordering day rules?", confidence="review", citations=0),
        _entry("2026-07-04T09:00:00+00:00", "How do invoices map?", confidence="review", citations=1),
    ]

    report = build_retrieval_health(entries)

    assert report["total_queries"] == 4
    assert report["counts"]["refused"] == 1
    assert report["counts"]["no_citation"] == 1
    assert report["counts"]["low_grounding"] == 3
    assert report["rates"]["refusal_rate"] == 0.25
    assert report["rates"]["no_citation_rate"] == 0.25
    assert report["rates"]["low_grounding_rate"] == 0.75
    assert report["rates"]["answered_ungrounded_rate"] == 0.6667
    assert any(row["topic"] == "roles" and row["failure_count"] == 2 for row in report["by_topic"])
    assert report["trend"][1]["refusal_rate"] == 1.0
    assert report["top_failing_patterns"][0]["demand_frequency"] == 2
    assert report["top_failing_patterns"][0]["recommended_action"].startswith("Review source coverage")


def test_retrieval_health_endpoint_is_protected(tmp_path) -> None:
    client = TestClient(create_app(SourceRegister(tmp_path), AuthService(PASSWORD)))

    assert client.get("/api/analytics/retrieval-health").status_code == 401

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.app.state.answer.usage_log.append(
        _entry("2026-07-01T09:00:00+00:00", "Who owns supplier ordering days?", confidence="review", citations=0)
    )
    response = client.get("/api/analytics/retrieval-health", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["counts"]["failure"] == 1


def _entry(
    timestamp: str,
    question: str,
    *,
    refused: bool = False,
    confidence: str = "grounded",
    citations: int = 1,
) -> UsageEntry:
    return UsageEntry(
        timestamp=timestamp,
        question=question,
        mode="ask",
        answer_path="rag",
        refused=refused,
        confidence=confidence,
        citation_count=citations,
    )
