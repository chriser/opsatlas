"""Red team, round 7, on REF S23 (staged publish) at d6413d4: S7 (one writer per workspace; reading never waits).

The stop rule applied after this round; the Human chose the door (lock at the door, check in the stores). These tests
now pass as written or restated for it (each restatement says so).

Hermetic: the full Sales app on a temporary workspace, sockets refused, models faked. Every thread is a daemon thread
and every join has a timeout, so no test can hang.
"""
from __future__ import annotations

import os
import socket
import threading
import time

import pytest

from tests.door_helpers import as_job, decided, writing
from tests.iam_helpers import sign_in
from tests.test_space_leaks import hermetic, refuse


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
    with writing(core):  # set-up is a job (REF S23, the door)
        record = register_upload(register, "pricing.md", text, "Pricing")
        ingest_source(register, sections, record.id)
        decided(register, record.id, approval_status="approved")
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
    """S7: "every change to the content store ... runs under the workspace's one lock". Restated for the door (REF S23,
    the Human's decision after round 7): discarding a draft is a request; it waits at the door while another writer
    holds the workspace's lock, and goes in once the lock is free."""
    app, client, root = sales
    core, source_id = _acme_document(app)
    content = core.state.content
    with writing(core):
        content.save_draft(source_id, "# Pricing\n\nBeta is the first plan.\n")
    assert content.store.document(source_id)["draft_text"] is not None
    release, holder = _hold_workspace_lock(root)
    out = {}
    worker = threading.Thread(target=lambda: out.setdefault(
        "status", client.delete(f"/api/content/documents/{source_id}/draft", headers={"X-OpsAtlas-Space": "acme"}).status_code),
        daemon=True)
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
    assert out.get("status") == 200 and (content.store.document(source_id) or {}).get("draft_text") is None


def test_s23_round7_a_draft_saved_during_a_publish_is_wiped_by_it(sales):
    """S7 consequence: an author's draft save landed inside an approver's publish and the publish's clear_draft then
    silently discarded it. Restated for the door (REF S23): the author's save is a request and the publish a job, so
    one runs after the other. Whichever goes first, the author's draft is never silently lost: either it is kept (the
    publish refuses a draft returned to editing) or the publish names the draft it published."""
    app, client, root = sales
    core, source_id = _acme_document(app)
    content = core.state.content
    with writing(core):
        content.save_draft(source_id, "# Pricing\n\nBeta is the first plan.\n")
        content.submit(source_id)
    draft_sha = content.store.document(source_id)["draft_sha"]
    gamma = "# Pricing\n\nGamma is the first plan.\n"
    at_write, go_write = threading.Event(), threading.Event()
    save_document = content.store.save_document

    def paced_save_document(*args, **kwargs):  # the author's request is between its log and its write
        if kwargs.get("draft_text") == gamma:
            at_write.set()
            go_write.wait(10)
        return save_document(*args, **kwargs)
    content.store.save_document = paced_save_document
    results = {}
    author = threading.Thread(target=lambda: results.setdefault("author", client.put(
        f"/api/content/documents/{source_id}/draft", json={"text": gamma}, headers={"X-OpsAtlas-Space": "acme"}).status_code),
        daemon=True)
    author.start()
    assert at_write.wait(10), "the author's save never reached its write"

    def approver():
        try:
            results["publish"] = as_job(core, content.publish, source_id, draft_sha)
        except Exception as error:  # refused: the draft it was asked to publish is no longer the submitted one
            results["refused"] = str(error)
    a = threading.Thread(target=approver, daemon=True)
    a.start()
    time.sleep(0.5)
    assert "publish" not in results and "refused" not in results, "the publish ran inside the author's request"
    go_write.set()
    author.join(10)
    a.join(10)
    content.store.save_document = save_document
    assert results.get("author") == 200
    state = content.store.document(source_id) or {}
    published = content.published_text(core.state.register.get(source_id))
    assert state.get("draft_text") == gamma or published == gamma, \
        "the author's draft, saved while the publish waited, was discarded by the publish"
