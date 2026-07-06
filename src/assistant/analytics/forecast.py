"""Explainable forecasting models with backtest validation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any


@dataclass(frozen=True)
class ForecastCandidate:
    model: str
    parameters: dict[str, Any]
    fitted: list[float]
    validation_forecast: list[float]
    future_forecast: list[float]


def forecast_series(
    points: list[dict],
    *,
    horizon: int = 7,
    season_length: int = 7,
    holdout: int | None = None,
) -> dict:
    values = [float(point.get("value", 0.0)) for point in points]
    if not values:
        return _empty_result(horizon)
    if len(values) < 4:
        return _short_series_result(values, horizon)

    holdout_n = holdout or min(max(3, len(values) // 4), max(1, len(values) - 3))
    holdout_n = min(holdout_n, max(1, len(values) - 3))
    train = values[:-holdout_n]
    test = values[-holdout_n:]
    candidates = _candidates(train, test, horizon, season_length)
    scored = [_score_candidate(candidate, test) for candidate in candidates]
    selected = min(scored, key=lambda item: (item["validation"]["mape"], item["validation"]["mae"], item["model_rank"]))
    residuals = [actual - predicted for actual, predicted in zip(test, selected["validation_forecast"], strict=False)]
    residual_std = pstdev(residuals) if len(residuals) > 1 else 0.0
    future_values = _refit_future(selected, values, horizon, season_length)
    forecast_rows = [
        {
            "step": index + 1,
            "value": round(value, 4),
            "lower": round(value - 1.96 * residual_std, 4),
            "upper": round(value + 1.96 * residual_std, 4),
        }
        for index, value in enumerate(future_values)
    ]
    return {
        "chosen_model": selected["model"],
        "selection_reason": "Lowest validation MAPE, with deterministic tie-break on MAE and model simplicity.",
        "parameters": selected["parameters"],
        "forecast": forecast_rows,
        "validation": {
            "holdout_n": holdout_n,
            "actual": [round(value, 4) for value in test],
            "scorecard": [
                {
                    "model": row["model"],
                    "parameters": row["parameters"],
                    "mae": row["validation"]["mae"],
                    "mape": row["validation"]["mape"],
                    "rmse": row["validation"]["rmse"],
                }
                for row in scored
            ],
            "selected": {
                "mae": selected["validation"]["mae"],
                "mape": selected["validation"]["mape"],
                "rmse": selected["validation"]["rmse"],
                "residual_std": round(residual_std, 4),
            },
        },
        "boundary": "Forecasts are diagnostic projections from historical platform telemetry, not guarantees.",
    }


def _candidates(train: list[float], test: list[float], horizon: int, season_length: int) -> list[ForecastCandidate]:
    validation_horizon = len(test)
    candidates: list[ForecastCandidate] = []
    for window in (3, 5, 7):
        if len(train) >= window:
            candidates.append(_moving_average(train, validation_horizon, horizon, window))
    candidates.append(_linear_trend(train, validation_horizon, horizon))
    for alpha in (0.2, 0.4, 0.6, 0.8):
        for beta in (0.2, 0.4, 0.6, 0.8):
            candidates.append(_holt(train, validation_horizon, horizon, alpha, beta))
    if len(train) >= season_length * 2:
        for alpha in (0.2, 0.5, 0.8):
            for beta in (0.2, 0.5, 0.8):
                for gamma in (0.2, 0.5, 0.8):
                    candidates.append(_holt_winters(train, validation_horizon, horizon, season_length, alpha, beta, gamma))
    return candidates


def _moving_average(train: list[float], validation_horizon: int, horizon: int, window: int) -> ForecastCandidate:
    value = mean(train[-window:])
    return ForecastCandidate(
        model="moving_average",
        parameters={"window": window},
        fitted=[],
        validation_forecast=[value] * validation_horizon,
        future_forecast=[value] * horizon,
    )


def _linear_trend(train: list[float], validation_horizon: int, horizon: int) -> ForecastCandidate:
    x_mean = (len(train) - 1) / 2
    y_mean = mean(train)
    denominator = sum((index - x_mean) ** 2 for index in range(len(train)))
    slope = sum((index - x_mean) * (value - y_mean) for index, value in enumerate(train)) / denominator if denominator else 0.0
    intercept = y_mean - slope * x_mean
    validation = [intercept + slope * (len(train) + step) for step in range(validation_horizon)]
    future = [intercept + slope * (len(train) + step) for step in range(horizon)]
    return ForecastCandidate(
        model="linear_trend",
        parameters={"intercept": round(intercept, 4), "slope": round(slope, 4)},
        fitted=[],
        validation_forecast=validation,
        future_forecast=future,
    )


def _holt(
    train: list[float],
    validation_horizon: int,
    horizon: int,
    alpha: float,
    beta: float,
) -> ForecastCandidate:
    level = train[0]
    trend = train[1] - train[0] if len(train) > 1 else 0.0
    for value in train[1:]:
        previous_level = level
        level = alpha * value + (1 - alpha) * (level + trend)
        trend = beta * (level - previous_level) + (1 - beta) * trend
    validation = [level + (step + 1) * trend for step in range(validation_horizon)]
    future = [level + (step + 1) * trend for step in range(horizon)]
    return ForecastCandidate(
        model="holt",
        parameters={"alpha": alpha, "beta": beta},
        fitted=[],
        validation_forecast=validation,
        future_forecast=future,
    )


def _holt_winters(
    train: list[float],
    validation_horizon: int,
    horizon: int,
    season_length: int,
    alpha: float,
    beta: float,
    gamma: float,
) -> ForecastCandidate:
    level = mean(train[:season_length])
    trend = (mean(train[season_length : 2 * season_length]) - level) / season_length
    seasonals = _initial_seasonals(train, season_length)
    for index, value in enumerate(train):
        seasonal_index = index % season_length
        previous_level = level
        level = alpha * (value - seasonals[seasonal_index]) + (1 - alpha) * (level + trend)
        trend = beta * (level - previous_level) + (1 - beta) * trend
        seasonals[seasonal_index] = gamma * (value - level) + (1 - gamma) * seasonals[seasonal_index]
    validation = [
        level + (step + 1) * trend + seasonals[(len(train) + step) % season_length]
        for step in range(validation_horizon)
    ]
    future = [level + (step + 1) * trend + seasonals[(len(train) + step) % season_length] for step in range(horizon)]
    return ForecastCandidate(
        model="holt_winters",
        parameters={"alpha": alpha, "beta": beta, "gamma": gamma, "season_length": season_length},
        fitted=[],
        validation_forecast=validation,
        future_forecast=future,
    )


def _initial_seasonals(train: list[float], season_length: int) -> list[float]:
    seasons = len(train) // season_length
    season_averages = [mean(train[index * season_length : (index + 1) * season_length]) for index in range(seasons)]
    seasonals = []
    for offset in range(season_length):
        seasonals.append(mean(train[index * season_length + offset] - season_averages[index] for index in range(seasons)))
    return seasonals


def _score_candidate(candidate: ForecastCandidate, actual: list[float]) -> dict:
    validation = _metrics(actual, candidate.validation_forecast)
    return {
        "model": candidate.model,
        "model_rank": _model_rank(candidate.model),
        "parameters": candidate.parameters,
        "validation": validation,
        "validation_forecast": [round(value, 4) for value in candidate.validation_forecast],
        "future_forecast": candidate.future_forecast,
    }


def _refit_future(selected: dict, values: list[float], horizon: int, season_length: int) -> list[float]:
    model = selected["model"]
    parameters = selected["parameters"]
    if model == "moving_average":
        return _moving_average(values, 0, horizon, int(parameters["window"])).future_forecast
    if model == "linear_trend":
        return _linear_trend(values, 0, horizon).future_forecast
    if model == "holt":
        return _holt(values, 0, horizon, float(parameters["alpha"]), float(parameters["beta"])).future_forecast
    if model == "holt_winters" and len(values) >= season_length * 2:
        return _holt_winters(
            values,
            0,
            horizon,
            int(parameters["season_length"]),
            float(parameters["alpha"]),
            float(parameters["beta"]),
            float(parameters["gamma"]),
        ).future_forecast
    return [values[-1]] * horizon


def _metrics(actual: list[float], predicted: list[float]) -> dict:
    errors = [a - p for a, p in zip(actual, predicted, strict=False)]
    abs_errors = [abs(error) for error in errors]
    pct_errors = [abs(a - p) / abs(a) for a, p in zip(actual, predicted, strict=False) if a != 0]
    return {
        "mae": round(mean(abs_errors), 4) if abs_errors else 0.0,
        "mape": round(mean(pct_errors), 4) if pct_errors else 0.0,
        "rmse": round(math.sqrt(mean([error**2 for error in errors])), 4) if errors else 0.0,
    }


def _model_rank(model: str) -> int:
    return {"moving_average": 0, "linear_trend": 1, "holt": 2, "holt_winters": 3}.get(model, 9)


def _short_series_result(values: list[float], horizon: int) -> dict:
    value = values[-1]
    return {
        "chosen_model": "naive_last_value",
        "selection_reason": "Series is too short for validated smoothing; using last observed value.",
        "parameters": {},
        "forecast": [{"step": step + 1, "value": value, "lower": value, "upper": value} for step in range(horizon)],
        "validation": {
            "holdout_n": 0,
            "actual": [],
            "scorecard": [],
            "selected": {"mae": 0.0, "mape": 0.0, "rmse": 0.0, "residual_std": 0.0},
        },
        "boundary": "Forecasts are diagnostic projections from historical platform telemetry, not guarantees.",
    }


def _empty_result(horizon: int) -> dict:
    return {
        "chosen_model": "none",
        "selection_reason": "No observations are available.",
        "parameters": {},
        "forecast": [{"step": step + 1, "value": 0.0, "lower": 0.0, "upper": 0.0} for step in range(horizon)],
        "validation": {
            "holdout_n": 0,
            "actual": [],
            "scorecard": [],
            "selected": {"mae": 0.0, "mape": 0.0, "rmse": 0.0, "residual_std": 0.0},
        },
        "boundary": "Forecasts are diagnostic projections from historical platform telemetry, not guarantees.",
    }
