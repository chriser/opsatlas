"""Atomic writes for the JSON stores (ARCH F1).

The stores under the data folder are whole files rewritten on every change. Written in place, a crash or two
overlapping requests could leave a half-written file behind, and a reader could parse one (the external
architecture review of 27 September 2026, problem 1). Every write here goes to a temporary file beside the target,
is flushed to disk, and then replaces the target in one step: a reader sees the old file or the new one, never a
partial one. Locks stay with the stores; this is about what reaches the disk, not about who writes next.
"""

from __future__ import annotations

import fcntl
import json
import os
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

NEW_FILE_MODE = 0o644  # what a plain write gave under the usual umask; an existing file keeps its own mode


def atomic_write_bytes(path: str | Path, data: bytes) -> None:
    """Write ``data`` to ``path`` so that the file on disk is always whole."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else NEW_FILE_MODE
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        with suppress(OSError):
            os.unlink(temporary)
        raise
    with suppress(OSError):  # the directory entry too, so the swap survives a power cut
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def atomic_write_text(path: str | Path, text: str, encoding: str = "utf-8") -> None:
    atomic_write_bytes(path, text.encode(encoding))


def write_json(path: str | Path, data: Any, **dumps: Any) -> None:
    """``json.dumps(data, **dumps)``, written atomically. Serialisation happens first, so a value that cannot be
    written leaves the file untouched."""
    atomic_write_text(path, json.dumps(data, **dumps))


@contextmanager
def locked(path: str | Path) -> Iterator[None]:
    """An exclusive lock on one store for a read-change-write, held across threads, store objects and processes (a
    lock file beside it). Two writers that each read, change and write the whole file would otherwise lose one
    writer's change; a lock inside one store object does not cover a second object or process (red team, REF F10)."""
    lock_path = Path(f"{path}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
