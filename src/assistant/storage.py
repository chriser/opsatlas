"""Atomic writes for the JSON stores (ARCH F1).

The stores under the data folder are whole files rewritten on every change. Written in place, a crash or two
overlapping requests could leave a half-written file behind, and a reader could parse one (the external
architecture review of 27 September 2026, problem 1). Every write here goes to a temporary file beside the target,
is flushed to disk, and then replaces the target in one step: a reader sees the old file or the new one, never a
partial one. Who writes next is the workspace's door (REF S23, S7, below): one lock, taken once per request or job;
the stores only check it.
"""

from __future__ import annotations

import fcntl
import functools
import json
import os
import stat
import tempfile
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager, suppress
from contextvars import ContextVar
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


# The locks the current request or job holds (REF S23, S7). A context variable, not a thread-local: the door takes
# the lock where the request arrives, and the request's handler may run in a worker thread, which inherits it.
_holding: ContextVar[frozenset[str]] = ContextVar("opsatlas_locks_held", default=frozenset())


def _key(path: str | Path) -> str:
    return str(Path(f"{path}.lock"))


def holds(path: str | Path | None) -> bool:
    """Whether the current request or job holds the lock on ``path``."""
    return path is not None and _key(path) in _holding.get()


class LockBusy(OSError):
    """The lock is held elsewhere and the caller chose not to wait (a reader, REF S23)."""


class NotHolding(RuntimeError):
    """A governed store was asked to write by code that does not hold the workspace's lock (REF S23, S7). Every
    change in a workspace comes through its door, so this is a missed path, and it fails loudly instead of racing."""


@contextmanager
def locked(path: str | Path, blocking: bool = True) -> Iterator[None]:
    """The workspace's one lock (a lock file beside ``path``), held across threads, store objects and processes. Taken
    once, by the door for a request that changes something, or by a job (start-up, a background review) at its start;
    re-entrant within that request or job. With ``blocking=False`` a lock held elsewhere raises LockBusy at once: a
    reader never waits for a writer (REF S23, S7)."""
    key = _key(path)
    if key in _holding.get():
        yield
        return
    Path(key).parent.mkdir(parents=True, exist_ok=True)
    with open(key, "a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError:
            raise LockBusy(key) from None
        token = _holding.set(_holding.get() | {key})
        try:
            yield
        finally:
            _holding.reset(token)
            fcntl.flock(handle, fcntl.LOCK_UN)


@contextmanager
def if_free(path: str | Path | None) -> Iterator[bool]:
    """For a reader that would also record something (finish a committed move, note a suggestion): True with the lock
    when it is free or already held, False at once when a writer holds it. An ungoverned store (no path) is free."""
    if path is None or holds(path):
        yield True
        return
    stack = ExitStack()
    try:
        stack.enter_context(locked(path, blocking=False))
    except LockBusy:
        yield False
        return
    with stack:
        yield True


def governor(store) -> str | Path | None:
    """The lock a store's writes must hold: set by the workspace that governs it (``governed_by``), else none."""
    return getattr(store, "governed_by", None)


def require(path: str | Path | None, what: str = "a write") -> None:
    if path is not None and not holds(path):
        raise NotHolding(f"{what} without the workspace's lock (REF S23, S7)")


def writes(method):
    """Marks a governed store's write: it refuses unless the request or job holds the store's workspace lock. Stores
    never take the lock themselves; the door does (REF S23, S7)."""
    @functools.wraps(method)
    def checked(self, *args, **kwargs):
        require(governor(self), f"{type(self).__name__}.{method.__name__}")
        return method(self, *args, **kwargs)
    checked.__writes__ = True
    return checked


SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class WriteDoor:
    """The workspace's door (REF S23, S7): a request that may change something takes the workspace's one lock here,
    once, before any handler runs, and holds it until its response is sent. Requests that only read, and the routes
    named in ``passes`` (sign-in, asks, Tibi's channel: nothing they do writes a governed store, and the stores prove
    it by refusing), go through without it and never wait. The lock is tried without blocking and the request
    yields to others while it waits, so a queue of writers never ties up the server's threads."""

    def __init__(self, app, lock_path, passes: tuple[str, ...] = ()) -> None:
        self.app, self.lock_path, self.passes = app, lock_path, passes

    def opens_for(self, scope) -> str | Path | None:
        if scope["type"] != "http" or scope["method"] in SAFE_METHODS:
            return None
        path = scope["path"]
        if any(path == prefix or path.startswith(prefix + "/") for prefix in self.passes):
            return None
        return self.lock_path() if callable(self.lock_path) else self.lock_path

    async def __call__(self, scope, receive, send) -> None:
        path = self.opens_for(scope)
        if path is None or holds(path):
            await self.app(scope, receive, send)
            return
        import anyio

        stack, wait = ExitStack(), 0.002
        while True:
            try:
                stack.enter_context(locked(path, blocking=False))
                break
            except LockBusy:
                await anyio.sleep(wait)
                wait = min(wait * 2, 0.05)
        with stack:
            await self.app(scope, receive, send)
