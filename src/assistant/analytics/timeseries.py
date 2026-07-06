"""Regular time-series aggregation for advanced analytics and forecasting."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Literal

from .events import AnalyticsEvent
from .log import UsageEntry

Bucket = Literal["daily", "weekly"]


def build_time_series(
    usage_entries: list[UsageEntry],
    events: list[AnalyticsEvent],
    *,
    bucket: Bucket = "daily",
) -> dict:
    if bucket not in {"daily", "weekly"}:
        raise ValueError("bucket must be 'daily' or 'weekly'.")

    by_bucket: dict[str, dict[str, int]] = defaultdict(_empty_stats)
    bucket_dates: list[date] = []

    for entry in usage_entries:
        bucket_date = _bucket_date(entry.timestamp, bucket)
        if bucket_date is None:
            continue
        bucket_key = bucket_date.isoformat()
        bucket_dates.append(bucket_date)
        stats = by_bucket[bucket_key]
        stats["queries"] += 1
        if entry.refused:
            stats["refused"] += 1
        else:
            stats["answered"] += 1
            stats["citations"] += int(entry.citation_count or 0)
            if entry.confidence not in {"grounded", "high"}:
                stats["low_grounding"] += 1

    for event in events:
        if event.event_type != "governance_issue_detected":
            continue
        bucket_date = _bucket_date(event.timestamp, bucket)
        if bucket_date is None:
            continue
        bucket_key = bucket_date.isoformat()
        bucket_dates.append(bucket_date)
        by_bucket[bucket_key]["governance_issues"] += 1

    timeline = _timeline(bucket_dates, bucket)
    series = {
        "query_volume": _series(
            "query_volume",
            "Query volume",
            [(_key(day), float(by_bucket[_key(day)]["queries"])) for day in timeline],
            bucket,
        ),
        "refusal_rate": _series(
            "refusal_rate",
            "Refusal rate",
            [(_key(day), _rate(by_bucket[_key(day)]["refused"], by_bucket[_key(day)]["queries"])) for day in timeline],
            bucket,
        ),
        "low_grounding_rate": _series(
            "low_grounding_rate",
            "Low-grounding rate",
            [
                (_key(day), _rate(by_bucket[_key(day)]["low_grounding"], by_bucket[_key(day)]["queries"]))
                for day in timeline
            ],
            bucket,
        ),
        "citations_per_answer": _series(
            "citations_per_answer",
            "Citations per answer",
            [
                (_key(day), _rate(by_bucket[_key(day)]["citations"], by_bucket[_key(day)]["answered"]))
                for day in timeline
            ],
            bucket,
        ),
        "governance_issue_count": _series(
            "governance_issue_count",
            "Governance issue count",
            [(_key(day), float(by_bucket[_key(day)]["governance_issues"])) for day in timeline],
            bucket,
        ),
    }
    return {
        "bucket": bucket,
        "span": _span(timeline),
        "series_count": len(series),
        "series": series,
    }


def _empty_stats() -> dict[str, int]:
    return {
        "queries": 0,
        "refused": 0,
        "low_grounding": 0,
        "answered": 0,
        "citations": 0,
        "governance_issues": 0,
    }


def _bucket_date(timestamp: str, bucket: Bucket) -> date | None:
    if not timestamp:
        return None
    parsed = _parse_date(timestamp)
    if parsed is None:
        return None
    if bucket == "weekly":
        return parsed - timedelta(days=parsed.weekday())
    return parsed


def _parse_date(timestamp: str) -> date | None:
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(timestamp[:10])
        except ValueError:
            return None


def _timeline(bucket_dates: list[date], bucket: Bucket) -> list[date]:
    if not bucket_dates:
        return []
    step = timedelta(days=7 if bucket == "weekly" else 1)
    current = min(bucket_dates)
    end = max(bucket_dates)
    rows = []
    while current <= end:
        rows.append(current)
        current += step
    return rows


def _series(series_id: str, label: str, points: list[tuple[str, float]], bucket: Bucket) -> dict:
    rows = [{"date": item_date, "value": round(value, 4)} for item_date, value in points]
    return {
        "id": series_id,
        "label": label,
        "metadata": {
            "bucket": bucket,
            "span": _span([date.fromisoformat(row["date"]) for row in rows]),
            "n": len(rows),
        },
        "points": rows,
    }


def _span(timeline: list[date]) -> dict:
    return {
        "start": timeline[0].isoformat() if timeline else None,
        "end": timeline[-1].isoformat() if timeline else None,
    }


def _rate(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / float(denominator), 4) if denominator else 0.0


def _key(item: date) -> str:
    return item.isoformat()
