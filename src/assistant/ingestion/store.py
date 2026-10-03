"""Persistence for built sections (one JSON file per source).

Each file keeps, with the passages, the SHA-256 of the text they were built from (REF S23): a reader that holds a
source's record asks for the passages of that record's text and gets them or nothing, never another version's. A file
written before this carries no fingerprint and is taken as the live version's (it was built from it).
"""

from __future__ import annotations

import json
from pathlib import Path

from ..storage import write_json
from .sections import Section


class SectionStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.dir = Path(base_dir) / "sections"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, source_id: str) -> Path:
        return self.dir / f"{source_id}.json"

    def _read(self, source_id: str) -> tuple[str | None, list[dict]]:
        path = self._path(source_id)
        if not path.exists():
            return None, []
        data = json.loads(path.read_text() or "[]")
        if isinstance(data, dict):
            return data.get("sha"), data.get("sections") or []
        return None, data

    def replace_for_source(self, source_id: str, sections: list[Section], sha: str | None = None) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        write_json(self._path(source_id), {"sha": sha, "sections": [s.model_dump() for s in sections]}, indent=2)

    def list_for_source(self, source_id: str, sha: str | None = None) -> list[Section]:
        """The source's passages; with ``sha``, only if they were built from that text (else none)."""
        stored, rows = self._read(source_id)
        if sha is not None and stored is not None and stored != sha:
            return []
        return [Section(**row) for row in rows]

    def fingerprint(self, source_id: str) -> str | None:
        """The SHA-256 of the text the stored passages were built from (None: not known, or none stored)."""
        return self._read(source_id)[0]

    def count_for_source(self, source_id: str) -> int:
        return len(self.list_for_source(source_id))

    def remove_for_source(self, source_id: str) -> None:
        path = self._path(source_id)
        if path.exists():
            path.unlink()
