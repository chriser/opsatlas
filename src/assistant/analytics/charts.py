"""Descriptive analytics datasets for the dashboard charts.

Derived from the usage log (demand, outcomes, topics) and the audit trace (latency,
cited sources). Pure aggregation — the chart shapes are ready for the frontend.
"""

from __future__ import annotations

from collections import Counter

from .classify import classify_topic
from .events import AnalyticsEvent
from .log import UsageEntry

_LATENCY_BUCKETS = [("<1s", 0, 1000), ("1-2s", 1000, 2000), ("2-4s", 2000, 4000), ("4-8s", 4000, 8000), ("8s+", 8000, 10**12)]


def build_charts(entries: list[UsageEntry], traces: list[dict], events: list[AnalyticsEvent] | None = None) -> dict:
    # Demand over time (per day) and by topic.
    by_day = Counter(e.timestamp[:10] for e in entries if e.timestamp)
    synthetic_by_day = Counter(
        event.timestamp[:10]
        for event in (events or [])
        if event.event_type.startswith("ask_") and event.metadata.get("synthetic_historical") is True and event.timestamp
    )
    volume = [
        {
            "date": day,
            "queries": by_day[day] + synthetic_by_day[day],
            "real_queries": by_day[day],
            "synthetic_queries": synthetic_by_day[day],
        }
        for day in sorted(set(by_day) | set(synthetic_by_day))
    ]
    topics = Counter(classify_topic(e.question) for e in entries)
    by_topic = [{"topic": t.replace("_", " "), "count": n} for t, n in topics.most_common(12)]

    # Outcome and confidence mix.
    answered = sum(1 for e in entries if not e.refused and not e.category)
    refused = sum(1 for e in entries if e.refused and not e.category)
    guardrail = sum(1 for e in entries if e.category)
    outcomes = [{"name": "Answered", "value": answered}, {"name": "Refused", "value": refused}, {"name": "Guardrail", "value": guardrail}]
    conf = Counter(e.confidence for e in entries if not e.refused)
    confidence = [{"name": k or "none", "value": v} for k, v in conf.items()]

    # Latency distribution and most-cited sources (from the audit trace).
    lat = [0] * len(_LATENCY_BUCKETS)
    for t in traces:
        ms = t.get("latency_ms")
        if not isinstance(ms, int | float):  # skip traces with no recorded latency (don't count them as <1s)
            continue
        for i, (_, lo, hi) in enumerate(_LATENCY_BUCKETS):
            if lo <= ms < hi:
                lat[i] += 1
                break
    latency = [{"bucket": _LATENCY_BUCKETS[i][0], "count": lat[i]} for i in range(len(_LATENCY_BUCKETS))]
    src: Counter = Counter()
    for t in traces:
        for ev in t.get("evidence", []) or []:
            title = ev.get("source_title")
            if title:
                src[title] += 1
    top_sources = [{"source": s, "citations": n} for s, n in src.most_common(8)]

    return {
        "volume_over_time": volume,
        "by_topic": by_topic,
        "outcomes": outcomes,
        "confidence": confidence,
        "latency": latency,
        "top_sources": top_sources,
    }
