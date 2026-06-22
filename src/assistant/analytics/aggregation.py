"""Historical analytics aggregations over the event ledger.

The output shapes are intentionally chart-ready and safe for notebooks or UI
views: counts, labels and compact identifiers only. Raw prompts, source text
and generated answers stay out of the analytics layer.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from .classify import classify_topic
from .events import EVENT_GROUPS, AnalyticsEvent
from .log import UsageEntry

_LATENCY_BUCKETS = (
    ("<1s", 0, 1000),
    ("1-2s", 1000, 2000),
    ("2-4s", 2000, 4000),
    ("4-8s", 4000, 8000),
    ("8s+", 8000, 10**12),
)


def build_history(
    events: list[AnalyticsEvent],
    usage_entries: list[UsageEntry] | None = None,
    traces: list[dict] | None = None,
) -> dict:
    """Build reusable historical datasets from durable analytics facts.

    When an older dataset has usage entries but no ask_* event-ledger rows yet,
    we backfill aggregate-only ask facts from the usage log. That preserves old
    chart history without copying raw questions into the event ledger.
    """

    facts = list(events)
    if usage_entries and not any(event.event_type.startswith("ask_") for event in facts):
        facts.extend(_usage_entries_as_events(usage_entries))

    group_for_event = _group_lookup()
    by_day: dict[str, Counter] = defaultdict(Counter)
    by_type: Counter = Counter()
    by_group: Counter = Counter()
    by_outcome: Counter = Counter()
    by_topic: Counter = Counter()
    by_process: Counter = Counter()
    by_source: Counter = Counter()
    by_issue: Counter = Counter()
    by_persona: Counter = Counter()
    by_confidence: Counter = Counter()
    by_value_driver: Counter = Counter()
    value_total = 0.0
    latency_ms: list[float] = []

    for event in facts:
        day = _day(event.timestamp)
        group = group_for_event.get(event.event_type, "other")
        by_day[day]["event_count"] += 1
        by_day[day][group] += 1
        by_type[event.event_type] += 1
        by_group[group] += 1
        if event.outcome:
            by_outcome[event.outcome] += 1

        topic = _metadata_label(event, "topic")
        if topic:
            by_topic[topic] += 1
        if event.process_area:
            by_process[event.process_area] += 1
        source = _source_label(event)
        if source:
            by_source[source] += 1
        issue = _metadata_label(event, "check") or _metadata_label(event, "issue_type")
        if issue:
            by_issue[issue] += 1
        persona = event.persona or _metadata_label(event, "persona")
        if persona:
            by_persona[persona] += 1
        confidence = _metadata_label(event, "confidence")
        if confidence:
            by_confidence[confidence] += 1
        if event.value_driver:
            by_value_driver[event.value_driver] += 1
        if event.value_estimate is not None:
            value_total += event.value_estimate

        latency = event.metadata.get("latency_ms")
        if isinstance(latency, int | float):
            latency_ms.append(float(latency))

    if not latency_ms and traces:
        latency_ms = [float(t.get("latency_ms") or 0) for t in traces]

    return {
        "event_count": len(facts),
        "events_over_time": _time_rows(by_day),
        "by_event_type": _counter_rows(by_type, "event_type"),
        "by_group": _counter_rows(by_group, "group"),
        "by_outcome": _counter_rows(by_outcome, "outcome"),
        "by_topic": _counter_rows(by_topic, "topic"),
        "by_process": _counter_rows(by_process, "process_area"),
        "by_source": _counter_rows(by_source, "source"),
        "by_issue_type": _counter_rows(by_issue, "issue_type"),
        "by_persona": _counter_rows(by_persona, "persona"),
        "by_confidence": _counter_rows(by_confidence, "confidence"),
        "latency": _latency_rows(latency_ms),
        "value": {
            "total_estimate": round(value_total, 2),
            "by_driver": _counter_rows(by_value_driver, "value_driver"),
        },
    }


def _usage_entries_as_events(entries: list[UsageEntry]) -> list[AnalyticsEvent]:
    facts: list[AnalyticsEvent] = []
    for entry in entries:
        if entry.refused and entry.category:
            event_type = "ask_guardrail_blocked"
            outcome = "blocked"
        elif entry.refused:
            event_type = "ask_refused"
            outcome = "refused"
        else:
            event_type = "ask_answered"
            outcome = "answered"
        facts.append(
            AnalyticsEvent(
                event_type=event_type,
                timestamp=entry.timestamp,
                actor_type="operator",
                entity_type="ask",
                outcome=outcome,
                metadata={
                    "mode": entry.mode,
                    "category": entry.category,
                    "confidence": entry.confidence,
                    "citation_count": entry.citation_count,
                    "topic": classify_topic(entry.question),
                },
            )
        )
    return facts


def _group_lookup() -> dict[str, str]:
    return {event_type: group for group, event_types in EVENT_GROUPS.items() for event_type in event_types}


def _day(timestamp: str) -> str:
    return timestamp[:10] if timestamp else "unknown"


def _metadata_label(event: AnalyticsEvent, key: str) -> str:
    value = event.metadata.get(key)
    return str(value).replace("_", " ") if value not in (None, "") else ""


def _source_label(event: AnalyticsEvent) -> str:
    title = event.metadata.get("title") or event.metadata.get("source_title")
    if title:
        return str(title)
    return event.source_id or ""


def _counter_rows(counter: Counter, key: str) -> list[dict]:
    return [
        {key: label, "count": count}
        for label, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def _time_rows(by_day: dict[str, Counter]) -> list[dict]:
    groups = sorted(EVENT_GROUPS)
    rows: list[dict] = []
    for day in sorted(by_day):
        row = {"date": day, "event_count": by_day[day]["event_count"]}
        row.update({group: by_day[day][group] for group in groups})
        rows.append(row)
    return rows


def _latency_rows(values: list[float]) -> list[dict]:
    counts = [0] * len(_LATENCY_BUCKETS)
    for value in values:
        for index, (_, lo, hi) in enumerate(_LATENCY_BUCKETS):
            if lo <= value < hi:
                counts[index] += 1
                break
    return [{"bucket": _LATENCY_BUCKETS[index][0], "count": count} for index, count in enumerate(counts)]
