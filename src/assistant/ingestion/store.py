"""Persistence for built sections (one JSON file per source)."""

from __future__ import annotations

import json
from pathlib import Path

from .sections import Section


class SectionStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.dir = Path(base_dir) / "sections"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, source_id: str) -> Path:
        return self.dir / f"{source_id}.json"

    def replace_for_source(self, source_id: str, sections: list[Section]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self._path(source_id).write_text(json.dumps([s.model_dump() for s in sections], indent=2))

    def list_for_source(self, source_id: str) -> list[Section]:
        path = self._path(source_id)
        if not path.exists():
            return []
        return [Section(**row) for row in json.loads(path.read_text() or "[]")]

    def count_for_source(self, source_id: str) -> int:
        return len(self.list_for_source(source_id))

    def remove_for_source(self, source_id: str) -> None:
        path = self._path(source_id)
        if path.exists():
            path.unlink()
