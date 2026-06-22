"""Governance issue lifecycle analytics."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

from ..governance.accepted import issue_key
from .event_store import AnalyticsEventStore
from .events import AnalyticsEvent, now_iso

_GOVERNANCE_EVENTS = {
    "governance_issue_detected": "detected",
    "governance_issue_accepted": "accepted",
    "governance_issue_resolved": "resolved",
}


def record_governance_snapshot(report: dict, event_store: AnalyticsEventStore, timestamp: str | None = None) -> None:
    """Append lifecycle events for the current governance report.

    Active issue detections are recorded once per issue per day. Issues that were
    previously detected but are no longer active are recorded as resolved.
    """

    ts = timestamp or now_iso()
    today = _day(ts)
    events = [event for event in event_store.events() if event.event_type in _GOVERNANCE_EVENTS]
    current = _current_issues(report)
    current_ids = set(current)
    detected_today = {
        (event.entity_id, _day(event.timestamp))
        for event in events
        if event.event_type == "governance_issue_detected" and event.entity_id
    }

    for entity_id, issue in sorted(current.items()):
        if (entity_id, today) in detected_today:
            continue
        event_store.record(
            "governance_issue_detected",
            timestamp=ts,
            actor_type="system",
            entity_type="governance_issue",
            entity_id=entity_id,
            source_id=issue["source_id"],
            outcome="detected",
            metadata={
                "category": issue["category"],
                "check": issue["check"],
                "severity": issue["severity"],
                "source_title": issue["source_title"],
            },
        )

    latest = _latest_state(events)
    for entity_id, state in sorted(latest.items()):
        if state != "detected" or entity_id in current_ids:
            continue
        event_store.record(
            "governance_issue_resolved",
            timestamp=ts,
            actor_type="system",
            entity_type="governance_issue",
            entity_id=entity_id,
            outcome="resolved",
            metadata=_last_metadata(events, entity_id),
        )


def build_governance_history(events: list[AnalyticsEvent]) -> dict:
    governance_events = [event for event in events if event.event_type in _GOVERNANCE_EVENTS and event.entity_id]
    by_day: dict[str, list[AnalyticsEvent]] = defaultdict(list)
    for event in governance_events:
        by_day[_day(event.timestamp)].append(event)

    state: dict[str, str] = {}
    event_rows: list[dict] = []
    for day in sorted(by_day):
        counts = Counter(_GOVERNANCE_EVENTS[event.event_type] for event in by_day[day])
        for event in sorted(by_day[day], key=lambda item: item.timestamp):
            state[event.entity_id or ""] = _GOVERNANCE_EVENTS[event.event_type]
        event_rows.append({
            "date": day,
            "detected": counts["detected"],
            "accepted": counts["accepted"],
            "resolved": counts["resolved"],
            "open": sum(1 for value in state.values() if value == "detected"),
        })

    latest_events = _latest_events(governance_events)
    detections: dict[str, list[AnalyticsEvent]] = defaultdict(list)
    first_detected: dict[str, AnalyticsEvent] = {}
    terminal: dict[str, AnalyticsEvent] = {}
    for event in sorted(governance_events, key=lambda item: item.timestamp):
        entity_id = event.entity_id or ""
        if event.event_type == "governance_issue_detected":
            detections[entity_id].append(event)
            first_detected.setdefault(entity_id, event)
        elif event.event_type in {"governance_issue_accepted", "governance_issue_resolved"} and entity_id not in terminal:
            terminal[entity_id] = event

    durations = []
    for entity_id, start in first_detected.items():
        if entity_id not in terminal:
            continue
        hours = (_parse_dt(terminal[entity_id].timestamp) - _parse_dt(start.timestamp)).total_seconds() / 3600
        if hours >= 0:
            durations.append(hours)

    state_mix = Counter(_GOVERNANCE_EVENTS[event.event_type] for event in latest_events.values())
    issue_type_mix = Counter(_metadata(event, "check") for event in governance_events if _metadata(event, "check"))
    source_mix = Counter(
        _metadata(event, "source_title") or event.source_id
        for event in governance_events
        if _metadata(event, "source_title") or event.source_id
    )

    return {
        "issue_events_over_time": event_rows,
        "issue_state_mix": _rows(state_mix, "state"),
        "issue_type_mix": _rows(issue_type_mix, "issue_type"),
        "source_issue_counts": _rows(source_mix, "source"),
        "mean_time_to_resolve_hours": round(sum(durations) / len(durations), 2) if durations else 0.0,
        "resolved_count": len(durations),
        "open_count": state_mix.get("detected", 0),
        "recurring_issues": _recurring_rows(detections, latest_events),
    }


def _current_issues(report: dict) -> dict[str, dict]:
    current: dict[str, dict] = {}
    for category, issues in (report.get("issues") or {}).items():
        for issue in issues:
            entity_id = issue_key(issue["source_id"], issue["check"], issue["detail"])
            current[entity_id] = {
                "category": category,
                "check": issue["check"],
                "severity": issue["severity"],
                "source_id": issue["source_id"],
                "source_title": issue["source_title"],
            }
    return current


def _latest_state(events: list[AnalyticsEvent]) -> dict[str, str]:
    return {
        event.entity_id or "": _GOVERNANCE_EVENTS[event.event_type]
        for event in sorted(events, key=lambda item: item.timestamp)
        if event.entity_id
    }


def _latest_events(events: list[AnalyticsEvent]) -> dict[str, AnalyticsEvent]:
    return {
        event.entity_id or "": event
        for event in sorted(events, key=lambda item: item.timestamp)
        if event.entity_id
    }


def _last_metadata(events: list[AnalyticsEvent], entity_id: str) -> dict:
    for event in sorted(events, key=lambda item: item.timestamp, reverse=True):
        if event.entity_id == entity_id:
            return dict(event.metadata)
    return {}


def _recurring_rows(
    detections: dict[str, list[AnalyticsEvent]],
    latest_events: dict[str, AnalyticsEvent],
) -> list[dict]:
    rows = []
    for entity_id, items in detections.items():
        if len(items) < 2:
            continue
        latest = latest_events.get(entity_id, items[-1])
        rows.append({
            "issue_id": entity_id,
            "issue_type": _metadata(latest, "check") or "unknown",
            "source": _metadata(latest, "source_title") or latest.source_id or "unknown",
            "detections": len(items),
            "first_seen": min(item.timestamp for item in items)[:10],
            "last_seen": max(item.timestamp for item in items)[:10],
            "state": _GOVERNANCE_EVENTS.get(latest.event_type, "unknown"),
        })
    return sorted(rows, key=lambda row: (-row["detections"], row["issue_type"], row["source"]))


def _rows(counter: Counter, key: str) -> list[dict]:
    return [
        {key: label, "count": count}
        for label, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def _metadata(event: AnalyticsEvent, key: str) -> str:
    value = event.metadata.get(key)
    return str(value).replace("_", " ") if value not in (None, "") else ""


def _day(timestamp: str) -> str:
    return timestamp[:10] if timestamp else "unknown"


def _parse_dt(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
