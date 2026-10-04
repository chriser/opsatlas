"""The workspace's door, for tests (REF S23, S7).

A request that may change something takes the workspace's one lock at the door; a governed store refuses a write from
anything that does not hold it. A test that writes to a store directly, as set-up or to act as a writer, is a job: it
holds the lock the way a request does, with ``writing``.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from assistant.storage import locked


def lock_of(app_or_core) -> Path:
    """The lock a core's door takes: the workspace's, when a workspace governs it, else the core's own. For a service
    or store used without an app (a unit test), the lock its register's door would take."""
    state = getattr(app_or_core, "state", None)
    if state is not None and getattr(state, "write_lock", None) is not None:
        return state.write_lock
    register = getattr(app_or_core, "register", app_or_core)
    return getattr(register, "governed_by", None) or register.index_file


@contextmanager
def writing(app_or_core):
    """Hold the lock this app's door takes, as a job does (set-up that writes stores directly)."""
    with locked(lock_of(app_or_core)):
        yield


def as_job(app_or_core, function, *args, **kwargs):
    """Call ``function`` as a job holding the door's lock: a direct writer, as a request would be."""
    with writing(app_or_core):
        return function(*args, **kwargs)


def decide(client, source_id: str, headers: dict | None = None, verb: str = "approve"):
    """Approve (or reject) a source through the governance route, naming the text decided on (REF S23, S8): the
    record's SHA-256, read from the sources list as a reviewer's page reads it."""
    headers = headers or {}
    rows = client.get("/api/sources", headers=headers).json()
    sha = next((r["content_sha256"] for r in rows if r["id"] == source_id), "0" * 64)
    return client.post(f"/api/governance/sources/{source_id}/{verb}", json={"sha": sha}, headers=headers)


def decided(register, source_id: str, approval_status: str | None = None, **fields):
    """Set-up that changes a document's approval: through the register's decide, naming the record's current text (REF
    S23, S8: the register refuses any other change of approval). Other fields are a plain update, written first."""
    if fields:
        register.update(source_id, **fields)
    if approval_status is not None:
        register.decide(source_id, approval_status, register.get(source_id).content_sha256)
    return register.get(source_id)
