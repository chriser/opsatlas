"""Persistence for built sections (one JSON file per source).

Each file keeps, with the passages, the SHA-256 of the text they were built from (REF S23): a reader that holds a
source's record asks for the passages of that record's text and gets them or nothing, never another version's. A file
written before this carries no fingerprint and is taken as the live version's (it was built from it).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..storage import LockBusy, governor, if_free, write_json, writes
from .sections import Section


class SectionStore:
    MOVE_ON_READ = True  # a reader holding a committed version's record moves its staged passages into place (REF S23)
    UNKNOWN_IS_LIVE = False  # passages without a fingerprint are the live version's only while nothing is staged

    def __init__(self, base_dir: str | Path) -> None:
        self.dir = Path(base_dir) / "sections"
        self.governed_by = None  # the workspace's lock its writes must hold, set by the workspace (REF S23, S7)
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

    @writes
    def replace_for_source(self, source_id: str, sections: list[Section], sha: str | None = None) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        write_json(self._path(source_id), {"sha": sha, "sections": [s.model_dump() for s in sections]}, indent=2)

    def list_for_source(self, source_id: str, sha: str | None = None) -> list[Section]:
        """The source's passages; with ``sha``, only if they were built from that text (else none). Passages staged for
        that text, whose version is committed but not yet moved into place, are moved now (after a crash too)."""
        stored, rows = self._read(source_id)
        # Passages from before S23 (no fingerprint) are not taken as any version's while another version is staged.
        unknown = not self.UNKNOWN_IS_LIVE and stored is None and self._staged_path(source_id).exists()
        if sha is not None and (unknown or (stored is not None and stored != sha)):
            try:
                if not self.MOVE_ON_READ or not self.promote_if_committed(source_id, sha):
                    return []
            except OSError:  # busy: passages for this text staged by a committing writer are read where they are
                return self._staged_passages(source_id, sha)
            stored, rows = self._read(source_id)
            if stored != sha:
                return []
        return [Section(**row) for row in rows]

    READ_STAGED = True  # passages of a committing version are read where they are staged (REF S23, round 6)

    def _staged_passages(self, source_id: str, sha: str) -> list[Section]:
        if not self.READ_STAGED:
            return []
        try:
            data = json.loads(self._staged_path(source_id).read_text() or "{}") or {}
        except (OSError, ValueError):
            return []
        return [Section(**row) for row in data.get("sections") or []] if data.get("sha") == sha else []

    def _staged_path(self, source_id: str) -> Path:
        return self.dir / f"{source_id}.staged.json"

    @writes
    def stage_for_source(self, source_id: str, sections: list[Section], sha: str) -> None:
        """A new version's passages, beside the live ones; nothing reads them until their text's record is written."""
        self.dir.mkdir(parents=True, exist_ok=True)
        write_json(self._staged_path(source_id), {"sha": sha, "sections": [s.model_dump() for s in sections]}, indent=2)

    def promote_if_committed(self, source_id: str, sha: str) -> bool:
        """Move the staged passages into place if they were built from the text ``sha`` names (a committed record's);
        whether they were. A writer holds the workspace's lock already; a reader only tries it (LockBusy: a writer is
        busy). Under the lock, checked again (REF S23, S7)."""
        staged = self._staged_path(source_id)
        if not staged.exists():
            return False
        with if_free(governor(self)) as free:
            if not free:
                raise LockBusy(source_id)
            if not staged.exists() or (json.loads(staged.read_text() or "{}") or {}).get("sha") != sha:
                return False
            self.promote_for_source(source_id)
            return True

    @writes
    def promote_for_source(self, source_id: str) -> None:
        try:
            os.replace(self._staged_path(source_id), self._path(source_id))
        except FileNotFoundError:
            pass

    @writes
    def discard_staged_for_source(self, source_id: str) -> None:
        self._staged_path(source_id).unlink(missing_ok=True)

    def fingerprint(self, source_id: str) -> str | None:
        """The SHA-256 of the text the stored passages were built from (None: not known, or none stored)."""
        return self._read(source_id)[0]

    def count_for_source(self, source_id: str) -> int:
        return len(self.list_for_source(source_id))

    @writes
    def remove_for_source(self, source_id: str) -> None:
        path = self._path(source_id)
        if path.exists():
            path.unlink()
        self._staged_path(source_id).unlink(missing_ok=True)
