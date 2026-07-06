"""Explainable forecast model tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from assistant.analytics.forecast import forecast_series
from assistant.analytics.log import UsageEntry
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.sources.register import SourceRegister

PASSWORD = "forecast-test-pass"


def test_forecast_series_backtests_and_selects_model_on_seasonal_data() -> None:
    seasonal = [0, 2, 4, 3, 1, -1, -2]
    points = [
        {"date": f"2026-07-{(index % 28) + 1:02d}", "value": 20 + index * 0.4 + seasonal[index % 7]}
        for index in range(42)
    ]

    result = forecast_series(points, horizon=7, season_length=7)

    assert result["chosen_model"] in {"moving_average", "linear_trend", "holt", "holt_winters"}
    assert len(result["forecast"]) == 7
    assert result["validation"]["holdout_n"] >= 3
    assert result["validation"]["scorecard"]
    assert all({"mae", "mape", "rmse"} <= set(row) for row in result["validation"]["scorecard"])
    assert result["validation"]["selected"]["mae"] >= 0
    assert result["validation"]["selected"]["mape"] >= 0
    assert result["validation"]["selected"]["rmse"] >= 0
    assert result["forecast"][0]["lower"] <= result["forecast"][0]["value"] <= result["forecast"][0]["upper"]


def test_forecast_series_uses_short_series_fallback() -> None:
    result = forecast_series(
        [
            {"date": "2026-07-01", "value": 3},
            {"date": "2026-07-02", "value": 5},
            {"date": "2026-07-03", "value": 8},
        ],
        horizon=3,
    )

    assert result["chosen_model"] == "naive_last_value"
    assert [point["value"] for point in result["forecast"]] == [8.0, 8.0, 8.0]
    assert result["validation"]["holdout_n"] == 0


def test_forecast_series_handles_empty_points() -> None:
    result = forecast_series([], horizon=2)

    assert result["chosen_model"] == "none"
    assert [point["value"] for point in result["forecast"]] == [0.0, 0.0]


def test_forecast_endpoint_returns_actuals_forecast_and_validation(tmp_path) -> None:
    client = TestClient(create_app(SourceRegister(tmp_path), AuthService(PASSWORD)))
    assert client.get("/api/analytics/forecast/query_volume").status_code == 401

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    for day in range(1, 10):
        client.app.state.answer.usage_log.append(
            UsageEntry(
                timestamp=f"2026-07-{day:02d}T09:00:00+00:00",
                question=f"Question {day}",
                mode="ask",
                answer_path="rag",
                refused=day % 4 == 0,
                confidence="grounded",
                citation_count=2,
            )
        )

    response = client.get("/api/analytics/forecast/query_volume?horizon=3", headers=headers)
    refusal = client.get("/api/analytics/forecast/refusal_rate?horizon=3", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["series_id"] == "query_volume"
    assert len(body["actuals"]) == 9
    assert len(body["forecast"]) == 3
    assert body["validation"]["selected"]["mape"] >= 0
    assert body["method_id"] == "forecasting"
    assert refusal.status_code == 200
    assert client.get("/api/analytics/forecast/not-a-series", headers=headers).status_code == 404
