"""File-backed process registry, populated from approved sources."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from ..sources.register import SourceRegister
from .models import ProcessRecord
from .parser import parse_process


class ProcessRegistry:
    def __init__(self, base_dir: str | Path) -> None:
        self.path = Path(base_dir) / "process_registry.json"
        self._lock = threading.Lock()

    def list(self) -> list[ProcessRecord]:
        if not self.path.exists():
            return []
        return [ProcessRecord(**r) for r in json.loads(self.path.read_text() or "[]")]

    def get(self, process_id: str) -> ProcessRecord | None:
        return next((r for r in self.list() if r.id == process_id), None)

    def replace_all(self, records: list[ProcessRecord]) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps([r.model_dump() for r in records], indent=2))

    def derive_from_sources(self, register: SourceRegister) -> list[ProcessRecord]:
        """Parse approved sources into process records WITHOUT persisting (pure read).

        Use this on read paths so a GET never writes the registry file.
        """
        records: list[ProcessRecord] = []
        for source in register.list():
            if source.approval_status != "approved":
                continue
            text = register.read_content(source.id).decode("utf-8", "replace")
            records.append(parse_process(source.id, source.title, text))
        return records

    def build_from_sources(self, register: SourceRegister) -> list[ProcessRecord]:
        """Derive and persist the record set (use on ingest/approve or explicit rebuild)."""
        records = self.derive_from_sources(register)
        self.replace_all(records)
        return records
