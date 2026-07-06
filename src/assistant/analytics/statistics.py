"""Descriptive statistics and anomaly flags for analytics time series."""

from __future__ import annotations

from statistics import mean, pstdev


def analyse_points(points: list[dict], *, z_threshold: float = 2.0, window: int = 5) -> dict:
    values = [float(point.get("value", 0.0)) for point in points]
    if not values:
        return _empty_stats(z_threshold, window)
    deltas = [values[index] - values[index - 1] for index in range(1, len(values))]
    slope = _linear_slope(values)
    anomalies = _rolling_anomalies(points, z_threshold=z_threshold, window=window)
    return {
        "n": len(values),
        "mean": round(mean(values), 4),
        "std": round(pstdev(values), 4) if len(values) > 1 else 0.0,
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "latest_delta": round(deltas[-1], 4) if deltas else 0.0,
        "trend_slope": round(slope, 4),
        "trend_direction": _trend_direction(slope),
        "anomaly_threshold": z_threshold,
        "anomalies": anomalies,
        "boundary": "Diagnostic descriptive statistics only; anomaly flags are not inferential proof.",
    }


def build_series_statistics(time_series_report: dict, *, z_threshold: float = 2.0, window: int = 5) -> dict:
    series = time_series_report.get("series", {})
    stats = {
        series_id: analyse_points(payload.get("points", []), z_threshold=z_threshold, window=window)
        for series_id, payload in series.items()
    }
    return {
        "bucket": time_series_report.get("bucket", "daily"),
        "span": time_series_report.get("span", {"start": None, "end": None}),
        "series_count": len(stats),
        "statistics": stats,
        "boundary": "Diagnostic descriptive statistics only; anomaly flags are not inferential proof.",
    }


def _rolling_anomalies(points: list[dict], *, z_threshold: float, window: int) -> list[dict]:
    rows = []
    values = [float(point.get("value", 0.0)) for point in points]
    for index, value in enumerate(values):
        if index < window:
            continue
        previous = values[index - window : index]
        previous_mean = mean(previous)
        previous_std = pstdev(previous)
        if previous_std == 0:
            z_score = 999.0 if value != previous_mean else 0.0
        else:
            z_score = (value - previous_mean) / previous_std
        if abs(z_score) >= z_threshold:
            rows.append(
                {
                    "date": points[index].get("date"),
                    "value": round(value, 4),
                    "z_score": round(z_score, 4),
                    "baseline_mean": round(previous_mean, 4),
                    "baseline_std": round(previous_std, 4),
                }
            )
    return rows


def _linear_slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    x_mean = (len(values) - 1) / 2
    y_mean = mean(values)
    denominator = sum((index - x_mean) ** 2 for index in range(len(values)))
    if denominator == 0:
        return 0.0
    return sum((index - x_mean) * (value - y_mean) for index, value in enumerate(values)) / denominator


def _trend_direction(slope: float) -> str:
    if slope > 0.05:
        return "increasing"
    if slope < -0.05:
        return "decreasing"
    return "flat"


def _empty_stats(z_threshold: float, window: int) -> dict:
    return {
        "n": 0,
        "mean": 0.0,
        "std": 0.0,
        "min": 0.0,
        "max": 0.0,
        "latest_delta": 0.0,
        "trend_slope": 0.0,
        "trend_direction": "flat",
        "anomaly_threshold": z_threshold,
        "anomalies": [],
        "boundary": "Diagnostic descriptive statistics only; anomaly flags are not inferential proof.",
    }
