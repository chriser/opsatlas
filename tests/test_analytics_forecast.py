"""Explainable forecast model tests."""

from __future__ import annotations

from assistant.analytics.forecast import forecast_series


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
