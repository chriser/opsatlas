"""Persistence for built sections (one JSON file per source).

Each file keeps, with the passages, the SHA-256 of the text they were built from (REF S23): a reader that holds a
source's record asks for the passages of that record's text and gets them or nothing, never another version's. A file
written before this carries no fingerprint and is taken as the live version's (it was built from it).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..storage import write_json
from .sections import Section


class SectionStore:
    MOVE_ON_READ = True  # a reader holding a committed version's record moves its staged passages into place (REF S23)

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
        """The source's passages; with ``sha``, only if they were built from that text (else none). Passages staged for
        that text, whose version is committed but not yet moved into place, are moved now (after a crash too)."""
        stored, rows = self._read(source_id)
        if sha is not None and stored is not None and stored != sha:
            try:
                if not self.MOVE_ON_READ or not self.promote_if_committed(source_id, sha):
                    return []
            except OSError:  # not movable just now: none for this reader; the next one tries again
                return []
            stored, rows = self._read(source_id)
            if stored != sha:
                return []
        return [Section(**row) for row in rows]

    def _staged_path(self, source_id: str) -> Path:
        return self.dir / f"{source_id}.staged.json"

    def stage_for_source(self, source_id: str, sections: list[Section], sha: str) -> None:
        """A new version's passages, beside the live ones; nothing reads them until their text's record is written."""
        self.dir.mkdir(parents=True, exist_ok=True)
        write_json(self._staged_path(source_id), {"sha": sha, "sections": [s.model_dump() for s in sections]}, indent=2)

    def promote_if_committed(self, source_id: str, sha: str) -> bool:
        """Move the staged passages into place if they were built from the text ``sha`` names; whether they were."""
        staged = self._staged_path(source_id)
        if not staged.exists() or (json.loads(staged.read_text() or "{}") or {}).get("sha") != sha:
            return False
        self.promote_for_source(source_id)
        return True

    def promote_for_source(self, source_id: str) -> None:
        try:
            os.replace(self._staged_path(source_id), self._path(source_id))
        except FileNotFoundError:
            pass

    def discard_staged_for_source(self, source_id: str) -> None:
        self._staged_path(source_id).unlink(missing_ok=True)

    def fingerprint(self, source_id: str) -> str | None:
        """The SHA-256 of the text the stored passages were built from (None: not known, or none stored)."""
        return self._read(source_id)[0]

    def count_for_source(self, source_id: str) -> int:
        return len(self.list_for_source(source_id))

    def remove_for_source(self, source_id: str) -> None:
        path = self._path(source_id)
        if path.exists():
            path.unlink()
        self._staged_path(source_id).unlink(missing_ok=True)
