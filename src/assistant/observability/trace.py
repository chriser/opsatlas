"""Audit trace — a traceable record of how each answer was produced.

Captures the question, mode, refusal/guardrail, confidence, validation outcome,
the evidence used, the model/prompt configuration and latency, so any answer can
be explained after the fact.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path


class AuditTrace:
    def __init__(self, base_dir: str | Path) -> None:
        self.path = Path(base_dir) / "audit_trace.json"
        self._lock = threading.Lock()

    def _read(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text() or "[]")

    def append(self, record: dict) -> None:
        with self._lock:
            rows = self._read()
            rows.append(record)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(rows, indent=2))

    def recent(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._read()))[:limit]
