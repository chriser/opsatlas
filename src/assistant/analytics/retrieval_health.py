"""Retrieval and grounding health analytics."""

from __future__ import annotations

from collections import Counter, defaultdict

from .classify import classify_topic
from .log import UsageEntry
from .recurring import build_recurring_questions

_STRONG_CONFIDENCE = {"grounded", "high"}


def build_retrieval_health(entries: list[UsageEntry]) -> dict:
    rows = [_row(entry) for entry in entries]
    totals = _totals(rows)
    by_topic = [_topic_row(topic, topic_rows) for topic, topic_rows in sorted(_group_by_topic(rows).items())]
    trend = _trend_rows(rows)
    failing_entries = [entry for entry, row in zip(entries, rows, strict=False) if row["is_failure"]]
    failing_patterns = build_recurring_questions(failing_entries, min_count=1)["groups"][:10]
    return {
        "total_queries": totals["total"],
        "rates": {
            "refusal_rate": _rate(totals["refused"], totals["total"]),
            "no_citation_rate": _rate(totals["no_citation"], totals["total"]),
            "low_grounding_rate": _rate(totals["low_grounding"], totals["total"]),
            "answered_ungrounded_rate": _rate(totals["answered_ungrounded"], totals["answered"]),
        },
        "counts": totals,
        "by_topic": by_topic,
        "trend": trend,
        "top_failing_patterns": [_pattern_row(pattern) for pattern in failing_patterns],
        "rubric": {
            "refusal_rate": "Refused rows divided by total rows.",
            "no_citation_rate": "Answered rows with zero citations divided by total rows.",
            "low_grounding_rate": "Rows whose confidence is not grounded/high divided by total rows.",
            "answered_ungrounded_rate": "Answered rows with weak confidence divided by answered rows.",
            "failure_pattern": "Refused, no-citation or low-grounding rows grouped using recurring-question lexical logic.",
        },
    }


def _row(entry: UsageEntry) -> dict:
    answered = not entry.refused
    low_grounding = entry.confidence not in _STRONG_CONFIDENCE
    no_citation = answered and int(entry.citation_count or 0) == 0
    answered_ungrounded = answered and low_grounding
    return {
        "date": entry.timestamp[:10] if entry.timestamp else "unknown",
        "topic": classify_topic(entry.question),
        "answered": answered,
        "refused": entry.refused,
        "no_citation": no_citation,
        "low_grounding": low_grounding,
        "answered_ungrounded": answered_ungrounded,
        "is_failure": entry.refused or no_citation or low_grounding,
    }


def _totals(rows: list[dict]) -> dict[str, int]:
    return {
        "total": len(rows),
        "answered": sum(1 for row in rows if row["answered"]),
        "refused": sum(1 for row in rows if row["refused"]),
        "no_citation": sum(1 for row in rows if row["no_citation"]),
        "low_grounding": sum(1 for row in rows if row["low_grounding"]),
        "answered_ungrounded": sum(1 for row in rows if row["answered_ungrounded"]),
        "failure": sum(1 for row in rows if row["is_failure"]),
    }


def _group_by_topic(rows: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["topic"]].append(row)
    return grouped


def _topic_row(topic: str, rows: list[dict]) -> dict:
    totals = _totals(rows)
    return {
        "topic": topic,
        "total_queries": totals["total"],
        "refusal_rate": _rate(totals["refused"], totals["total"]),
        "no_citation_rate": _rate(totals["no_citation"], totals["total"]),
        "low_grounding_rate": _rate(totals["low_grounding"], totals["total"]),
        "failure_count": totals["failure"],
    }


def _trend_rows(rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["date"]].append(row)
    trend = []
    for day in sorted(grouped):
        totals = _totals(grouped[day])
        trend.append(
            {
                "date": day,
                "queries": totals["total"],
                "refusal_rate": _rate(totals["refused"], totals["total"]),
                "no_citation_rate": _rate(totals["no_citation"], totals["total"]),
                "low_grounding_rate": _rate(totals["low_grounding"], totals["total"]),
                "failure_count": totals["failure"],
            }
        )
    return trend


def _pattern_row(pattern: dict) -> dict:
    reasons = Counter()
    if pattern.get("refusal_count", 0):
        reasons["refusal"] += int(pattern["refusal_count"])
    if pattern.get("low_grounding_count", 0):
        reasons["low_grounding"] += int(pattern["low_grounding_count"])
    return {
        "id": pattern["id"],
        "representative_question": pattern["representative_question"],
        "demand_frequency": pattern["demand_frequency"],
        "trend": pattern["trend"],
        "topic": pattern["topic"],
        "first_seen": pattern["first_seen"],
        "last_seen": pattern["last_seen"],
        "failure_reasons": dict(reasons) or {"retrieval_health": pattern["demand_frequency"]},
        "recommended_action": (
            "Review source coverage, answer grounding and citation support for this repeated failure pattern."
        ),
    }


def _rate(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / float(denominator), 4) if denominator else 0.0
