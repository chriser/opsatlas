"""REF S23, red team round 6: the staged publish against its promises (S2, S7).

Hermetic: the full Sales app on a temporary workspace, no network, no model. Races use real threads; every thread is a
daemon and every join has a timeout, so a deadlock fails the test instead of hanging it.
"""

from __future__ import annotations

import hashlib
import os
import socket
import threading
import time

import pytest

from tests.iam_helpers import sign_in
from tests.test_space_leaks import hermetic, refuse


def _sha(data: bytes | str) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


@pytest.fixture
def sales(tmp_path, monkeypatch):
    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    os.environ["SME_TIBI_VOICE_URL"] = "http://127.0.0.1:9"
    os.environ["SALES_GOVERNANCE_AUTO_REVIEW"] = "0"
    root = tmp_path / "sales"
    app = create_sales_app(root)
    hermetic(app)
    return app, root


def _submitted_draft(content, source_id: str, extra: str) -> tuple[str, str]:
    """A submitted draft of ``source_id``: (its text, its SHA-256)."""
    published = content.document(source_id)["published"]["text"]
    text = published.rstrip("\n") + f"\n\n{extra}\n"
    doc = content.save_draft(source_id, text)
    content.submit(source_id, "for the red team")
    return text, doc["draft"]["sha"]


def _wait_until_busy(lock_base, seconds: float = 5.0) -> bool:
    """True once another thread holds the workspace lock (a non-blocking try is refused)."""
    from assistant.storage import LockBusy, locked
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with locked(lock_base, blocking=False):
                pass
        except LockBusy:
            return True
        time.sleep(0.005)
    return False


def test_s23_round6_accept_suggestion_against_publish_deadlocks_the_workspace(sales):
    """S7: "no other lock is ever taken before it". Accepting a governance suggestion takes the content store's lock
    and then (through the desk's keep) the workspace lock; a publish takes the workspace lock and then the content
    store's lock. One accept and one publish at once, in the same space, wait on each other for ever."""
    app, root = sales
    content, desk = app.state.content, app.state.governance_desk
    notes = content.suggestion_overview()["notes"]
    assert notes, "the seeded workspace raises at least one suggestion"
    suggested = next(iter(notes))
    key = content.suggestions(suggested)[0]["key"]
    other = next(s.id for s in content.register.list() if s.id != suggested and content.editable(s))
    _, draft_sha = _submitted_draft(content, other, "A line the approver read.")

    accept_holds_store_lock, publish_holds_workspace = threading.Event(), threading.Event()
    keep = desk.keep

    def keep_after_publish_started(*args, **kwargs):  # only widens the real window between the two locks
        accept_holds_store_lock.set()
        publish_holds_workspace.wait(5)
        return keep(*args, **kwargs)

    desk.keep = keep_after_publish_started
    outcome: dict = {}

    def accept():
        try:
            content.accept_suggestion(suggested, key, "kept as it is")
            outcome["accept"] = "ok"
        except Exception as exc:  # noqa: BLE001
            outcome["accept"] = repr(exc)

    def publish():
        accept_holds_store_lock.wait(5)
        try:
            content.publish(other, draft_sha)
            outcome["publish"] = "ok"
        except Exception as exc:  # noqa: BLE001
            outcome["publish"] = repr(exc)

    a = threading.Thread(target=accept, daemon=True)
    b = threading.Thread(target=publish, daemon=True)
    a.start()
    b.start()
    assert accept_holds_store_lock.wait(5)
    assert _wait_until_busy(root / "workspace"), "the publish took the workspace lock"
    publish_holds_workspace.set()
    a.join(timeout=8)
    b.join(timeout=8)
    import sys
    import traceback
    frames = sys._current_frames()
    where = {name: [f"{f.name}:{f.lineno} {f.line}" for f in traceback.extract_stack(frames[t.ident])[-2:]]
             for name, t in (("accept", a), ("publish", b)) if t.is_alive() and t.ident in frames}
    assert not a.is_alive() and not b.is_alive(), (
        f"deadlock: accept_suggestion and publish each hold one lock and wait for the other (finished: {outcome}); "
        f"blocked at {where}")


def test_s23_round6_record_reader_during_commit_gets_the_previous_versions_text(sales):
    """S2: "views and readers that pair a record with its text read them together". Between the record's write (the
    commit) and the move into place, a reader that tries the busy lock falls back to the live file: it is handed the
    new record (new SHA, new version) with the previous version's text, by the register and by the Sales source route."""
    from fastapi.testclient import TestClient
    app, root = sales
    content = app.state.content
    register = app.state.family_register
    target = next(s.id for s in content.register.list() if content.editable(s))
    before = content.register.get(target)
    old_text = content.register.read_content(target)
    new_text, draft_sha = _submitted_draft(content, target, "Version two: the approved wording.")

    committed, release = threading.Event(), threading.Event()
    commit_version = content.store.commit_version

    def commit_then_pause(source_id, n):  # the record is already written here: the version is committed
        committed.set()
        release.wait(5)
        return commit_version(source_id, n)

    content.store.commit_version = commit_then_pause
    outcome: dict = {}

    def publish():
        try:
            outcome["publish"] = content.publish(target, draft_sha)["version"]
        except Exception as exc:  # noqa: BLE001
            outcome["publish"] = repr(exc)

    with TestClient(app) as client:
        client.headers.update({"Authorization": f"Bearer {sign_in(client, app)}"})
        writer = threading.Thread(target=publish, daemon=True)
        writer.start()
        try:
            assert committed.wait(5), "the publish reached its commit"
            record, text = register.read_record_text(target)
            served = client.get(f"/api/tibi/sources/{target}")  # Tibi's reader: a record and its text, together
        finally:
            release.set()
            writer.join(timeout=10)
        assert not writer.is_alive()
    assert isinstance(outcome.get("publish"), int), outcome  # the publish itself succeeded
    assert record.content_sha256 != before.content_sha256 and record.version == before.version + 1  # the new record
    assert served.status_code == 200, served.text
    mismatched = {
        "register.read_record_text": _sha(text) != record.content_sha256,
        "GET /api/tibi/sources": _sha(served.json()["text"].encode()) != record.content_sha256,
    }
    assert not any(mismatched.values()), (
        f"record {record.version} (sha {record.content_sha256[:12]}) paired with the previous version's text: "
        f"{mismatched}; old text served: {text == old_text}")
