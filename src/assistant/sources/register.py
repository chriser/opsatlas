"""Source register persistence.

A small, file-backed catalogue of source documents. Stores each uploaded file
by id and keeps an index JSON describing every registered source. This is the
controlled store the rest of the platform reads from; it deliberately does no
ingestion, retrieval or answer generation.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from .models import SourceRecord


class SourceRegister:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.files_dir = self.base_dir / "sources"
        self.index_file = self.base_dir / "source_register.json"
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _read_index(self) -> list[dict]:
        if not self.index_file.exists():
            return []
        text = self.index_file.read_text() or "[]"
        return json.loads(text)

    def _write_index(self, rows: list[dict]) -> None:
        self.index_file.write_text(json.dumps(rows, indent=2))

    def list(self) -> list[SourceRecord]:
        return [SourceRecord(**row) for row in self._read_index()]

    def get(self, source_id: str) -> SourceRecord | None:
        for row in self._read_index():
            if row["id"] == source_id:
                return SourceRecord(**row)
        return None

    def add(self, record: SourceRecord, content: bytes) -> SourceRecord:
        with self._lock:
            rows = self._read_index()
            (self.files_dir / record.id).write_bytes(content)
            rows.append(record.model_dump())
            self._write_index(rows)
        return record

    def remove(self, source_id: str) -> bool:
        with self._lock:
            rows = self._read_index()
            kept = [r for r in rows if r["id"] != source_id]
            if len(kept) == len(rows):
                return False
            self._write_index(kept)
            stored = self.files_dir / source_id
            if stored.exists():
                stored.unlink()
            return True
