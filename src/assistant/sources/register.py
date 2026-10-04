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

from ..storage import LockBusy, atomic_write_bytes, governor, if_free, write_json, writes
from .models import SourceRecord


class ContentReplaced(LookupError):
    """The source's text is not the one the reader's record names: it is being replaced (REF S23)."""


class TextNotNamed(ValueError):
    """A decision on a document whose named text is not the record's, or not what is stored (REF S23, S8)."""


class ApprovalOutsideDecide(ValueError):
    """A write that would change a document's approval other than through ``decide`` or a commit (REF S23, S8)."""


class SourceRegister:
    MOVE_ON_READ = True  # a reader holding a committed version's record moves its staged text into place (REF S23)

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.files_dir = self.base_dir / "sources"
        self.index_file = self.base_dir / "source_register.json"
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.on_add: list = []  # called with each new record once it is stored (REF S18: its first version)
        self.governed_by = None  # the workspace's lock its writes must hold, set by the workspace (REF S23, S7)

    def _read_index(self) -> list[dict]:
        if not self.index_file.exists():
            return []
        text = self.index_file.read_text() or "[]"
        return json.loads(text)

    @writes
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
                    try:  # a reader never waits
                        self.promote_if_committed(source_id, record.content_sha256)
                    except OSError:  # busy: a committed version is read where it is staged, else the live file
                        committed = self._committed_staged(source_id, record.content_sha256)
                        if committed is not None:
                            return committed
            return self.file_path(source_id).read_bytes()
        content = self.file_path(source_id).read_bytes()
        if hashlib.sha256(content).hexdigest() == sha:
            return content
        if self.MOVE_ON_READ:
            try:
                moved = self.promote_if_committed(source_id, sha)
            except OSError:  # busy or not movable just now: the reader is told so, and the next one tries again
                raise ContentReplaced(source_id) from None
            if moved:
                content = self.file_path(source_id).read_bytes()
                if hashlib.sha256(content).hexdigest() == sha:
                    return content
            committed = self._committed_staged(source_id, sha)  # committed, its writer still moving it: read it there
            if committed is not None:
                return committed
        raise ContentReplaced(source_id)

    READ_STAGED = True  # a committed version not yet moved is read where it is staged (REF S23, red team round 6)

    def _committed_staged(self, source_id: str, sha: str) -> bytes | None:
        """The staged text, if it is ``sha``'s and the record names it (committed); else None. No lock: the staged file
        is written whole and only renamed, and a writer settles it before it stages another version over it."""
        if not self.READ_STAGED:
            return None
        try:
            data = self._staged_path(source_id).read_bytes()
        except OSError:
            return None
        record = self.get(source_id)
        if record is None or record.content_sha256 != sha or hashlib.sha256(data).hexdigest() != sha:
            return None
        return data

    def read_record_text(self, source_id: str) -> tuple[SourceRecord | None, bytes]:
        """A record and its text, read together (REF S23, S2): where the text does not match, the record is read
        again and the text retried (a publish landed between the two reads); only where the record has not changed is
        the file returned as it is (changed outside content management)."""
        record = self.get(source_id)
        for _ in range(3):
            if record is None:
                return None, b""
            try:
                return record, self.read_content(source_id, sha=record.content_sha256)
            except ContentReplaced:
                fresh = self.get(source_id)
                if fresh is None or fresh.content_sha256 == record.content_sha256:
                    return record, self.read_content(source_id)
                record = fresh
        return record, self.read_content(source_id)

    def promote_if_committed(self, source_id: str, sha: str) -> bool:
        """Move the staged text into place if the record names it (its SHA-256 is ``sha``); whether it was moved. A
        writer holds the workspace's lock already; a reader only tries it, and LockBusy tells it a writer is busy (REF
        S23, S7). Under the lock the record and the staged file are checked again, since a writer may have settled this
        version and staged the next one meanwhile."""
        staged = self._staged_path(source_id)
        if not staged.exists():
            return False
        with if_free(governor(self)) as free:
            if not free:
                raise LockBusy(source_id)
            record = self.get(source_id)
            if record is None or record.content_sha256 != sha or not staged.exists() \
                    or hashlib.sha256(staged.read_bytes()).hexdigest() != sha:
                return False
            self.promote_content(source_id)
            return True

    def _staged_path(self, source_id: str) -> Path:
        return self.files_dir / f"{source_id}.staged"

    @writes
    def stage_content(self, source_id: str, content: bytes) -> None:
        """A new version's text, beside the live one; nothing reads it until its record names it (REF S23)."""
        self.files_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(self._staged_path(source_id), content)

    @writes
    def promote_content(self, source_id: str) -> None:
        """Move a staged text into place (one atomic rename); nothing to do if it already was."""
        try:
            os.replace(self._staged_path(source_id), self.file_path(source_id))
        except FileNotFoundError:
            pass

    @writes
    def discard_staged_content(self, source_id: str) -> None:
        self._staged_path(source_id).unlink(missing_ok=True)

    @writes
    def write_content(self, source_id: str, content: bytes) -> None:
        with self._lock:
            self.files_dir.mkdir(parents=True, exist_ok=True)
            atomic_write_bytes(self.file_path(source_id), content)  # a reader never finds half a file (REF S23)

    # ---- approval: decided in the store (REF S23, S8, the Human's decision after round 9) ----------------------
    #
    # A document's approval changes in two ways only: ``decide``, which names the text decided on and checks that it is
    # the record's and is what is stored; and a commit, the write of a new version's record, which sets the approval in
    # the same write that names its new text. Every other write that would change it is refused.

    def names_text(self, source_id: str, sha: str | None) -> str | None:
        """Why a decision naming ``sha`` cannot be taken on this source, or None: the record must name that text, and
        that text must be what is stored (the live file, or a committed version still staged), never a file replaced
        outside content management."""
        record = self.get(source_id)
        if record is None:
            return "No such source"
        if not sha or record.content_sha256 != sha:
            return "The document changed since it was read; review the current version"
        try:
            self.read_content(source_id, sha=sha)
        except ContentReplaced:
            return "The file was changed outside content management; publish it as a new version, then review it"
        except OSError:
            return "The document's text cannot be read"
        return None

    @writes
    def decide(self, source_id: str, status: str, sha: str | None) -> SourceRecord:
        """Approve or reject the text ``sha`` names: the one way a decision changes a document's approval (S8)."""
        reason = self.names_text(source_id, sha)
        if reason is not None:
            raise TextNotNamed(reason)
        return self._update(source_id, approval_status=status)

    @writes
    def withdraw(self, source_id: str) -> SourceRecord | None:
        """The workspace's own withdrawal, when its named rejection could not be taken: fail closed, out of answers. Not
        reachable by a person (no route or action calls it)."""
        return self._update(source_id, approval_status="rejected")

    @writes
    def update(self, source_id: str, **fields) -> SourceRecord | None:
        """Any field but the approval. A write naming a new text (a commit: ``content_sha256`` with it) may set the
        approval too; any other change of approval goes through ``decide`` (REF S23, S8)."""
        if "approval_status" in fields and "content_sha256" not in fields:
            current = self.get(source_id)
            if current is not None and current.approval_status != fields["approval_status"]:
                raise ApprovalOutsideDecide("A document's approval changes only through a decision naming its text")
        return self._update(source_id, **fields)

    @writes
    def _update(self, source_id: str, **fields) -> SourceRecord | None:
        with self._lock:
            rows = self._read_index()
            for row in rows:
                if row["id"] == source_id:
                    row.update(fields)
                    self._write_index(rows)
                    return SourceRecord(**row)
            return None

    @writes
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

    @writes
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
