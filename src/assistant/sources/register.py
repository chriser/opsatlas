"""Source register persistence.

A small, file-backed catalogue of source documents. Stores each uploaded file
by id and keeps an index JSON describing every registered source. This is the
controlled store the rest of the platform reads from; it deliberately does no
ingestion, retrieval or answer generation.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path

from ..storage import atomic_write_bytes, locked, write_json
from .models import SourceRecord


class ContentReplaced(LookupError):
    """The source's text is not the one the reader's record names: it is being replaced (REF S23)."""


class SourceRegister:
    MOVE_ON_READ = True  # a reader holding a committed version's record moves its staged text into place (REF S23)

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.files_dir = self.base_dir / "sources"
        self.index_file = self.base_dir / "source_register.json"
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.on_add: list = []  # called with each new record once it is stored (REF S18: its first version)

    def _read_index(self) -> list[dict]:
        if not self.index_file.exists():
            return []
        text = self.index_file.read_text() or "[]"
        return json.loads(text)

    def _write_index(self, rows: list[dict]) -> None:
        write_json(self.index_file, rows, indent=2)

    def list(self) -> list[SourceRecord]:
        return [SourceRecord(**row) for row in self._read_index()]

    def get(self, source_id: str) -> SourceRecord | None:
        for row in self._read_index():
            if row["id"] == source_id:
                return SourceRecord(**row)
        return None

    def file_path(self, source_id: str) -> Path:
        return self.files_dir / source_id

    def read_content(self, source_id: str, sha: str | None = None) -> bytes:
        """The source's text; with ``sha``, only if it is that text (REF S23): a reader that holds a record gets that
        record's text or ContentReplaced, never another version's. A version staged and committed (its record written)
        but not yet moved into place is moved now, by whichever reader comes first, after a crash or restart too."""
        if sha is None:  # a plain read settles a committed version first (REF S23, S2 coverage)
            if self.MOVE_ON_READ and self._staged_path(source_id).exists():
                record = self.get(source_id)
                if record is not None:
                    try:
                        self.promote_if_committed(source_id, record.content_sha256)
                    except OSError:
                        pass
            return self.file_path(source_id).read_bytes()
        content = self.file_path(source_id).read_bytes()
        if hashlib.sha256(content).hexdigest() == sha:
            return content
        if self.MOVE_ON_READ:
            try:
                moved = self.promote_if_committed(source_id, sha)
            except OSError:  # not movable just now: the reader is told so, and the next one tries again
                raise ContentReplaced(source_id) from None
            if moved:
                content = self.file_path(source_id).read_bytes()
                if hashlib.sha256(content).hexdigest() == sha:
                    return content
        raise ContentReplaced(source_id)

    def promote_if_committed(self, source_id: str, sha: str) -> bool:
        """Move the staged text into place if the record names it (its SHA-256 is ``sha``); whether it was moved. One
        writer per space (REF S23, S7): under the space's lock, the record and the staged file are checked again, since a
        writer may have settled this version and staged the next one meanwhile."""
        staged = self._staged_path(source_id)
        if not staged.exists():
            return False
        with locked(self.index_file):
            record = self.get(source_id)
            if record is None or record.content_sha256 != sha or not staged.exists() \
                    or hashlib.sha256(staged.read_bytes()).hexdigest() != sha:
                return False
            self.promote_content(source_id)
            return True

    def _staged_path(self, source_id: str) -> Path:
        return self.files_dir / f"{source_id}.staged"

    def stage_content(self, source_id: str, content: bytes) -> None:
        """A new version's text, beside the live one; nothing reads it until its record names it (REF S23)."""
        self.files_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(self._staged_path(source_id), content)

    def promote_content(self, source_id: str) -> None:
        """Move a staged text into place (one atomic rename); nothing to do if it already was."""
        try:
            os.replace(self._staged_path(source_id), self.file_path(source_id))
        except FileNotFoundError:
            pass

    def discard_staged_content(self, source_id: str) -> None:
        self._staged_path(source_id).unlink(missing_ok=True)

    def write_content(self, source_id: str, content: bytes) -> None:
        with self._lock:
            self.files_dir.mkdir(parents=True, exist_ok=True)
            atomic_write_bytes(self.file_path(source_id), content)  # a reader never finds half a file (REF S23)

    def update(self, source_id: str, **fields) -> SourceRecord | None:
        with self._lock:
            rows = self._read_index()
            for row in rows:
                if row["id"] == source_id:
                    row.update(fields)
                    self._write_index(rows)
                    return SourceRecord(**row)
            return None

    def add(self, record: SourceRecord, content: bytes) -> SourceRecord:
        with self._lock:
            self.files_dir.mkdir(parents=True, exist_ok=True)  # resilient if storage was cleared
            rows = self._read_index()
            (self.files_dir / record.id).write_bytes(content)
            rows.append(record.model_dump())
            self._write_index(rows)
        for listener in self.on_add:
            listener(record)
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
            self._staged_path(source_id).unlink(missing_ok=True)  # and any version staged for it (REF S23)
            return True
