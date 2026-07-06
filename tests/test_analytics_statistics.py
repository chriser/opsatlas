"""Descriptive statistics and anomaly detection tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from assistant.analytics.log import UsageEntry
from assistant.analytics.statistics import analyse_points, build_series_statistics
from assistant.analytics.timeseries import build_time_series
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.sources.register import SourceRegister

PASSWORD = "stats-test-pass"


def test_analyse_points_flags_planted_spike() -> None:
    points = [
        {"date": f"2026-07-{index + 1:02d}", "value": value}
        for index, value in enumerate([10, 10, 10, 10, 10, 35, 11])
    ]

    stats = analyse_points(points, z_threshold=2.0, window=5)

    assert stats["n"] == 7
    assert stats["max"] == 35
    assert stats["anomalies"]
    assert stats["anomalies"][0]["date"] == "2026-07-06"
    assert stats["anomalies"][0]["z_score"] >= 2.0
    assert stats["boundary"].startswith("Diagnostic")


def test_build_series_statistics_and_endpoint(tmp_path) -> None:
    usage = [
        UsageEntry(
            timestamp=f"2026-07-{day:02d}T09:00:00+00:00",
            question=f"Question {day}",
            mode="ask",
            answer_path="rag",
            refused=False,
            confidence="grounded",
            citation_count=1,
        )
        for day in (1, 2, 3, 4, 5, 6)
    ]
    report = build_series_statistics(build_time_series(usage, []))

    assert report["series_count"] == 5
    assert "query_volume" in report["statistics"]
    assert report["statistics"]["query_volume"]["mean"] == 1.0

    client = TestClient(create_app(SourceRegister(tmp_path), AuthService(PASSWORD)))
    assert client.get("/api/analytics/timeseries/stats").status_code == 401

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.app.state.answer.usage_log.append(usage[0])
    response = client.get("/api/analytics/timeseries/stats", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["statistics"]["query_volume"]["n"] == 1
