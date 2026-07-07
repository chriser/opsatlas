"""Recurring question analytics tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from assistant.analytics.log import UsageEntry
from assistant.analytics.recurring import build_recurring_questions
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.sources.register import SourceRegister

PASSWORD = "recurring-test-pass"


def test_recurring_questions_groups_near_duplicates_and_trends() -> None:
    entries = [
        _entry("2026-07-01T09:00:00+00:00", "Who owns supplier ordering days?"),
        _entry("2026-07-02T09:00:00+00:00", "Which role owns supplier ordering day rules?"),
        _entry("2026-07-03T09:00:00+00:00", "Who is responsible for supplier order days?"),
        _entry("2026-07-04T09:00:00+00:00", "How do VAT invoices work?"),
        _entry("2026-07-05T09:00:00+00:00", "Who owns supplier ordering days now?", refused=True, confidence="none"),
    ]

    report = build_recurring_questions(entries, min_count=2)

    assert report["group_count"] == 1
    group = report["groups"][0]
    assert group["demand_frequency"] == 4
    assert group["first_seen"] == "2026-07-01"
    assert group["last_seen"] == "2026-07-05"
    assert group["trend"] == "steady"
    assert group["refusal_count"] == 1
    assert group["low_grounding_count"] == 1
    assert "supplier" in group["terms"]


def test_recurring_questions_endpoint_is_protected(tmp_path) -> None:
    client = TestClient(create_app(SourceRegister(tmp_path), AuthService(PASSWORD)))

    assert client.get("/api/analytics/recurring-questions").status_code == 401

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.app.state.answer.usage_log.append(_entry("2026-07-01T09:00:00+00:00", "Who owns supplier ordering days?"))
    client.app.state.answer.usage_log.append(_entry("2026-07-02T09:00:00+00:00", "Which role owns supplier ordering days?"))
    response = client.get("/api/analytics/recurring-questions", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["group_count"] == 1


def _entry(
    timestamp: str,
    question: str,
    *,
    refused: bool = False,
    confidence: str = "grounded",
) -> UsageEntry:
    return UsageEntry(
        timestamp=timestamp,
        question=question,
        mode="ask",
        answer_path="rag",
        refused=refused,
        confidence=confidence,
        citation_count=2 if not refused else 0,
    )
