"""Append-only analytics event ledger."""

from __future__ import annotations

import threading
from pathlib import Path

from .events import AnalyticsEvent, EventType


class AnalyticsEventStore:
    """File-backed JSONL store for immutable analytics facts."""

    def __init__(self, base_dir: str | Path, filename: str = "analytics_events.jsonl") -> None:
        self.path = Path(base_dir) / filename
        self._lock = threading.Lock()

    def append(self, event: AnalyticsEvent) -> AnalyticsEvent:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(event.model_dump_json())
                handle.write("\n")
        return event

    def record(self, event_type: EventType, **kwargs) -> AnalyticsEvent:
        event = AnalyticsEvent(event_type=event_type, **kwargs)
        return self.append(event)

    def events(self, event_type: EventType | None = None, source_id: str | None = None) -> list[AnalyticsEvent]:
        if not self.path.exists():
            return []

        rows: list[AnalyticsEvent] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = AnalyticsEvent.model_validate_json(line)
            if event_type is not None and event.event_type != event_type:
                continue
            if source_id is not None and event.source_id != source_id:
                continue
            rows.append(event)
        return rows

    def recent(self, limit: int = 50) -> list[AnalyticsEvent]:
        safe_limit = max(1, min(limit, 500))
        return list(reversed(self.events()))[:safe_limit]
