"""Red team, round 7, on REF S23 (staged publish) at d6413d4: S7 (one writer per workspace; reading never waits).

Hermetic: the full Sales app on a temporary workspace, sockets refused, models faked. Every thread is a daemon thread
and every join has a timeout, so no test can hang.
"""
from __future__ import annotations

import os
import socket
import threading
import time

import pytest

from tests.iam_helpers import sign_in
from tests.test_space_leaks import hermetic, refuse

pytestmark = pytest.mark.xfail(strict=True, reason="REF S23 round 7: stop rule; awaiting the Human's design decision")


@pytest.fixture
def sales(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    os.environ["SME_TIBI_VOICE_URL"] = "http://127.0.0.1:9"
    os.environ["SALES_GOVERNANCE_AUTO_REVIEW"] = "0"
    root = tmp_path / "sales"
    app = create_sales_app(root)
    hermetic(app)
    with TestClient(app) as client:
        client.headers.update({"Authorization": f"Bearer {sign_in(client, app)}"})
        assert client.post("/api/spaces", json={"name": "Acme"}).status_code == 200
        hermetic(app.state.cores["acme"])
        yield app, client, root


def _hold_workspace_lock(root):
    """Another writer in the workspace: a daemon thread holding the workspace's one lock until released."""
    from assistant.storage import locked
    held, release = threading.Event(), threading.Event()

    def holder():
        with locked(root / "workspace"):
            held.set()
            release.wait(10)
    thread = threading.Thread(target=holder, daemon=True)
    thread.start()
    assert held.wait(5), "the holder never took the workspace lock"
    return release, thread


def _acme_document(app, text=b"# Pricing\n\nAlpha is the first plan.\n"):
    from assistant.ingestion.service import ingest_source
    from assistant.sources.service import register_upload
    core = app.state.cores["acme"]
    register, sections = core.state.register, core.state.section_store
    record = register_upload(register, "pricing.md", text, "Pricing")
    ingest_source(register, sections, record.id)
    register.update(record.id, approval_status="approved")
    return core, record.id


def test_s23_round7_reading_the_content_list_waits_for_the_workspace_lock(sales):
    """S7: "reading alone never waits". The content list (GET /api/content/documents -> suggestion_overview) takes the
    content store's lock, which since round 6 is the workspace's one lock, blocking, in every family space."""
    app, client, root = sales
    content = app.state.content  # the Product Guide's content service, with the Sales suggestion hooks
    assert content.hooks["all_suggestions"] is not None
    content.suggestion_overview()  # warm the governance scan's cache, so only the lock can make the read slow
    release, holder = _hold_workspace_lock(root)
    done = threading.Event()

    def reader():
        content.suggestion_overview()
        done.set()
    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    finished_while_held = done.wait(3)
    release.set()
    holder.join(5)
    thread.join(10)
    assert done.is_set(), "the read never finished even after the lock was released"
    assert finished_while_held, "a read of the content list waited for another writer's workspace lock"


def test_s23_round7_content_list_read_holds_the_workspace_lock_against_writers(sales):
    """S7, the other way round: while the content list is being read (its governance scan running under the lock), a
    writer in another space of the workspace (a details edit in Acme) cannot write. A read blocks writers."""
    app, client, root = sales
    core, source_id = _acme_document(app)
    content = app.state.content
    in_scan, finish_scan = threading.Event(), threading.Event()
    original = content.hooks["all_suggestions"]

    def slow_scan():  # the governance scan is slow (a dependency slow: embeddings for duplicates)
        in_scan.set()
        finish_scan.wait(10)
        return original()
    content.hooks["all_suggestions"] = slow_scan
    reader = threading.Thread(target=content.suggestion_overview, daemon=True)
    reader.start()
    assert in_scan.wait(5)
    wrote = threading.Event()

    def writer():
        from assistant.storage import locked
        with locked(root / "workspace"):  # any writer of the workspace (publish, review, ingest, move ...)
            wrote.set()
    w = threading.Thread(target=writer, daemon=True)
    w.start()
    wrote_during_read = wrote.wait(3)
    finish_scan.set()
    reader.join(10)
    w.join(10)
    content.hooks["all_suggestions"] = original
    assert wrote_during_read, "a reader of the content list held the workspace's one lock and kept every writer out"


def test_s23_round7_draft_change_is_written_while_another_writer_holds_the_lock(sales):
    """S7: "every change to the content store ... runs under the workspace's one lock". Discarding a draft writes the
    content store (documents row cleared) while another thread holds the workspace lock."""
    app, client, root = sales
    core, source_id = _acme_document(app)
    content = core.state.content
    content.save_draft(source_id, "# Pricing\n\nBeta is the first plan.\n")
    assert content.store.document(source_id)["draft_text"] is not None
    release, holder = _hold_workspace_lock(root)
    worker = threading.Thread(target=content.discard_draft, args=(source_id,), daemon=True)
    worker.start()
    changed_while_held = False
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if (content.store.document(source_id) or {}).get("draft_text") is None:
            changed_while_held = True
            break
        time.sleep(0.05)
    release.set()
    holder.join(5)
    worker.join(10)
    assert not changed_while_held, "the content store was changed while another writer held the workspace lock"


def test_s23_round7_a_draft_saved_during_a_publish_is_wiped_by_it(sales):
    """S7 consequence: an author's draft save runs outside the lock, so it lands inside an approver's publish (here
    paused on a slow event store, a dependency slow) and the publish's clear_draft then silently discards it."""
    app, client, root = sales
    core, source_id = _acme_document(app)
    content = core.state.content
    content.save_draft(source_id, "# Pricing\n\nBeta is the first plan.\n")
    content.submit(source_id)
    draft_sha = content.store.document(source_id)["draft_sha"]
    in_event, finish_event = threading.Event(), threading.Event()
    events = content.events

    class SlowEvents:
        def record(self, event_type, *args, **kwargs):
            if event_type == "source_edited" and threading.current_thread().name == "approver":
                in_event.set()
                finish_event.wait(10)
            return events.record(event_type, *args, **kwargs) if events is not None else None

        def __getattr__(self, name):
            return getattr(events, name)
    content.events = SlowEvents()
    results = {}

    def approver():
        results["publish"] = content.publish(source_id, draft_sha)
    gamma = "# Pricing\n\nGamma is the first plan.\n"
    at_write, go_write = threading.Event(), threading.Event()
    save_document = content.store.save_document

    def paced_save_document(*args, **kwargs):  # the author's request is between its log and its write
        if threading.current_thread().name == "author":
            at_write.set()
            go_write.wait(10)
        return save_document(*args, **kwargs)
    content.store.save_document = paced_save_document
    b = threading.Thread(target=content.save_draft, args=(source_id, gamma), name="author", daemon=True)
    b.start()
    assert at_write.wait(10), "the author's save never reached its write"
    a = threading.Thread(target=approver, name="approver", daemon=True)
    a.start()
    assert in_event.wait(10), "the publish never reached its edit event"
    go_write.set()  # the author's draft is written now, inside the approver's publish (it needs no lock)
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and (content.store.document(source_id) or {}).get("draft_text") != gamma:
        time.sleep(0.05)
    finish_event.set()
    a.join(10)
    b.join(10)
    content.events = events
    content.store.save_document = save_document
    assert "publish" in results, "the publish did not finish"
    assert (content.store.document(source_id) or {}).get("draft_text") == gamma, \
        "the author's draft, saved while the publish held the lock, was discarded by the publish"
