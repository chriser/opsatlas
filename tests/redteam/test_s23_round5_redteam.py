"""Red team, round 5, on REF S23 (staged publish, one writer per space). Each test states the promise it holds the
code to; a failing test is a break. Hermetic: no network, no live service, no model."""
from __future__ import annotations

import hashlib
import os
import socket
import threading
import time

import pytest

from tests.door_helpers import as_job, writing
from tests.iam_helpers import sign_in
from tests.test_space_leaks import hermetic, refuse

# A low-severity break kept as a stated limit (the Human's exit rule, 3 October 2026): it needs two faults and a stale
# reader of the same text. Strict, so a fix shows up as an unexpected pass.
STATED_LIMIT = pytest.mark.xfail(strict=True, reason="REF S23 stated limit (low): staged passages moved against the reader's fingerprint")

JOIN = 8  # seconds: no thread in this file may hang the run


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
    app = create_sales_app(tmp_path / "sales")
    hermetic(app)
    return app


def _run(name, target, errors):
    def body():
        try:
            target()
        except BaseException as exc:  # noqa: BLE001 - recorded for the assertion message
            errors[name] = repr(exc)
    thread = threading.Thread(target=body, name=name, daemon=True)
    thread.start()
    return thread


# ---- S7: the space lock is always taken first; a Sales review and a Sales settle deadlock -------------------------

def test_s23_round5_sales_review_and_dispute_settle_deadlock(sales, monkeypatch):
    """S7 (space lock always taken first; the space never stops accepting writes). The Sales review (`decide`) takes
    the space lock, then the Sales store's lock; `settle` (and `propose`, `resolve`) take the store's lock, then reach
    the space lock through `_withdraw` -> reject_source -> `_set_status`. Two real requests at once deadlock.
    Restated for the door (REF S23, the Human's decision after round 7): the space lock is gone; the review and the
    settle are each a job holding the workspace's one lock, as their requests would be, so while the review is paused
    inside the Sales store's lock the settle waits at the workspace's lock (it never reaches the store's), and both
    finish once the review is done."""
    knowledge, family = sales.state.sales, sales.state.family_register
    rows = [r for r in knowledge.records()
            if family.get(r["source_id"]) is not None and family.get(r["source_id"]).approval_status != "rejected"]
    assert len(rows) >= 2, "the seeded Sales records are needed"
    target, other = rows[0], rows[1]

    review_has_store_lock, settle_has_store_lock, release = threading.Event(), threading.Event(), threading.Event()
    original_records = knowledge.records

    def records():  # widens the window only: called inside `with self.lock`
        rows_now = original_records()
        if threading.current_thread().name == "review" and not review_has_store_lock.is_set():
            review_has_store_lock.set()
            release.wait(JOIN)
        if threading.current_thread().name == "settle":
            settle_has_store_lock.set()
        return rows_now

    monkeypatch.setattr(knowledge, "records", records)
    errors: dict = {}
    review = _run("review", lambda: as_job(sales, knowledge.decide, target["id"], target["sha256"], True), errors)
    assert review_has_store_lock.wait(JOIN)
    settle = _run("settle", lambda: as_job(sales, knowledge.settle,
        [{"source_id": target["source_id"]}, {"source_id": other["source_id"]}], {"decision": "dispute"},
        "red team"), errors)
    time.sleep(0.3)
    assert not settle_has_store_lock.is_set(), "the settle reached the Sales store while the review held the lock"
    release.set()
    review.join(JOIN)
    settle.join(JOIN)
    assert not review.is_alive() and not settle.is_alive(), (
        f"deadlock: review alive={review.is_alive()}, settle alive={settle.is_alive()}, errors={errors}; "
        f"review waits in {_where(review)}; settle waits in {_where(settle)}")


def _where(thread) -> list[str]:
    """The innermost frames a blocked thread sits in (evidence of what it waits on)."""
    import sys
    import traceback
    frame = sys._current_frames().get(thread.ident)
    return [f"{f.name}@{os.path.basename(f.filename)}:{f.lineno}" for f in traceback.extract_stack(frame)[-4:]] if frame else []


# ---- S3/S5: a publish action that fails after its swap committed ---------------------------------------------------

def test_s23_round5_publish_reported_failed_but_live_when_audit_write_fails(sales, monkeypatch):
    """S5 and S3. The publish_version action's audit write (`action_log.append`) runs after its handler committed the
    swap; when that write failed, the publish raised, yet the new version was live and approved. Restated for the
    door (REF S23, the Human's decision after round 7): the direct set-up writes and the publish are jobs holding the
    workspace's lock, as a request would."""
    from fastapi.testclient import TestClient

    from assistant.ingestion.service import ingest_source
    with TestClient(sales) as client:
        client.headers.update({"Authorization": f"Bearer {sign_in(client, sales)}"})
        assert client.post("/api/spaces", json={"name": "Acme"}).status_code == 200
        core = sales.state.cores["acme"]
        hermetic(core)
        up = client.post("/api/sources/upload", files={"file": ("policy.md", b"# Policy\n\nVersion one text.\n",
                                                                  "text/markdown")}, headers={"X-OpsAtlas-Space": "acme"})
        assert up.status_code == 200, up.text
        sid = up.json()["id"]
        register, sections, content = core.state.register, core.state.section_store, core.state.content
        new_text = "# Policy\n\nVersion two text, not live until published.\n"
        with writing(core):
            ingest_source(register, sections, sid)
            register.update(sid, approval_status="approved")
            content.save_draft(sid, new_text)
            content.submit(sid)
        before = register.get(sid)

        log = core.state.actions.action_log
        original_append = log.append

        def append(execution):
            if execution.action == "publish_version":
                raise OSError(28, "No space left on device")
            return original_append(execution)

        monkeypatch.setattr(log, "append", append)
        try:
            as_job(core, content.publish, sid, _sha(new_text))
            raised = None
        except Exception as exc:  # noqa: BLE001
            raised = exc
        after = register.get(sid)
        live = register.read_content(sid)
    # Restated to the Human's decision on this round (S5, 4 October 2026): a publish whose record names its version entry
    # is published, whatever fails after it, the audit write included. What must never happen is the two disagreeing:
    # a publish reported as failed while its version is live (or reported as published while it is not).
    assert raised is None, f"the version is live, yet the publish was reported as failed: {raised!r}"
    assert after.version == before.version + 1 and after.approval_status == "approved" and live == new_text.encode()


# ---- S2: a reader holding a record gets that record's text or none ------------------------------------------------

def test_s23_round5_document_view_pairs_old_record_with_new_text(tmp_path):
    """S2 (a reader holding a record gets that record's text or none, never another version's). The content view
    reads the record, then the text by fingerprint; when a publish lands in between, the fallback to a plain read
    returns the new text under the old record: version 1, its SHA and approval, shown with version 2's text."""
    from assistant.content.service import ContentService
    from assistant.ingestion.service import ingest_source
    from assistant.ingestion.store import SectionStore
    from assistant.sources.register import SourceRegister
    from assistant.sources.service import register_upload

    register = SourceRegister(tmp_path)
    sections = SectionStore(tmp_path)
    content = ContentService(register, sections)
    register.on_add.append(content.first_version)
    record = register_upload(register, "policy.md", b"# Policy\n\nVersion one text.\n", "Policy")
    ingest_source(register, sections, record.id)
    new_text = "# Policy\n\nVersion two text.\n"
    content.save_draft(record.id, new_text)
    content.submit(record.id)

    got_record, published = threading.Event(), threading.Event()
    original_get = register.get

    def get(source_id):  # widens the window only (restated: the view now reads its record through the register)
        found = original_get(source_id)
        if threading.current_thread().name == "reader" and not got_record.is_set():
            got_record.set()
            published.wait(JOIN)
        return found

    register.get = get
    errors: dict = {}
    seen: dict = {}
    reader = _run("reader", lambda: seen.update(doc=content.document(record.id)), errors)
    assert got_record.wait(JOIN)
    writer = _run("writer", lambda: content.publish(record.id, _sha(new_text)), errors)
    writer.join(JOIN)
    published.set()
    reader.join(JOIN)
    assert not reader.is_alive() and not writer.is_alive() and not errors, errors
    doc = seen["doc"]
    shown = doc["published"]["text"].encode()
    assert _sha(shown) == doc["source"]["content_sha256"], (
        f"the view names version {doc['source']['version']} (sha {doc['source']['content_sha256'][:12]}) "
        f"but shows {shown!r}, the text of version {register.get(record.id).version}")


# ---- S7: moves between spaces take only the origin's lock first ---------------------------------------------------

def test_s23_round5_opposite_moves_deadlock_on_unversioned_documents(tmp_path, monkeypatch):
    """S7 (one writer per space, the lock taken first; the space never stops accepting writes). A move takes the
    origin's lock only, then adds to the target, whose first_version takes the target's lock. Two moves in opposite
    directions, each of a document with no version yet (an unreadable PDF), hold one lock each and wait for the other."""
    from assistant.content.service import ContentService
    from assistant.ingestion.store import SectionStore
    from assistant.sources.register import SourceRegister
    from assistant.sources.service import register_upload
    from services.opsatlas_sales import spaces

    pairs = {}
    for name in ("a", "b"):
        register = SourceRegister(tmp_path / name)
        sections = SectionStore(register.base_dir)
        content = ContentService(register, sections)
        register.on_add.append(content.first_version)  # as create_app wires it (REF S18)
        pairs[name] = (register, sections)
    doc_a = register_upload(pairs["a"][0], "scan-a.pdf", b"%PDF-1.4 damaged scan a", "Scan A")
    doc_b = register_upload(pairs["b"][0], "scan-b.pdf", b"%PDF-1.4 damaged scan b", "Scan B")
    assert pairs["a"][0].get(doc_a.id).history_n is None and pairs["b"][0].get(doc_b.id).history_n is None

    both_hold_origin = threading.Barrier(2, timeout=JOIN)
    original_settle = spaces.settling.settle

    def settle(register, section_store, source_id):  # widens the window only: called under the origin's lock
        original_settle(register, section_store, source_id)
        try:
            both_hold_origin.wait()
        except threading.BrokenBarrierError:
            pass

    monkeypatch.setattr(spaces.settling, "settle", settle)
    errors: dict = {}
    one = _run("a-to-b", lambda: spaces.move_document(doc_a.id, pairs["a"], pairs["b"], keep_approval=False), errors)
    two = _run("b-to-a", lambda: spaces.move_document(doc_b.id, pairs["b"], pairs["a"], keep_approval=False), errors)
    one.join(JOIN + 2)
    two.join(JOIN + 2)
    assert not one.is_alive() and not two.is_alive(), (
        f"deadlock: a-to-b waits in {_where(one)}; b-to-a waits in {_where(two)}; errors={errors}")


# ---- S3: staged passages are moved by a reader whose record does not name them ------------------------------------

@STATED_LIMIT
def test_s23_round5_staged_passages_moved_without_their_record(tmp_path):
    """S3 (a staged version is moved only if its record names it; the live version stays whole). SectionStore's move
    checks the staged file against the sha the caller passes, never against the record: after a failed publish whose
    discard also failed, a reader holding an older record of the same text moves the uncommitted passages over the live
    ones, and the live record's passages are gone."""
    from assistant.content.service import ContentService
    from assistant.ingestion.service import ingest_source
    from assistant.ingestion.store import SectionStore
    from assistant.sources.register import SourceRegister
    from assistant.sources.service import register_upload

    register = SourceRegister(tmp_path)
    sections = SectionStore(tmp_path)
    content = ContentService(register, sections)
    register.on_add.append(content.first_version)
    text_a = "# Policy\n\nThe original wording.\n"
    record = register_upload(register, "policy.md", text_a.encode(), "Policy")
    ingest_source(register, sections, record.id)
    held = register.get(record.id)  # an answer in flight holds version 1's record (text A)
    for text in ("# Policy\n\nThe corrected wording.\n",):
        content.save_draft(record.id, text)
        content.submit(record.id)
        content.publish(record.id, _sha(text))
    live = register.get(record.id)
    assert live.content_sha256 != held.content_sha256 and sections.list_for_source(record.id, sha=live.content_sha256)

    # A revert to the original wording fails at its commit, and discarding its staged passages fails too.
    content.save_draft(record.id, text_a)
    content.submit(record.id)
    original_update, original_discard = register.update, sections.discard_staged_for_source

    def update(source_id, **fields):
        if "history_n" in fields:
            raise OSError(5, "Input/output error")
        return original_update(source_id, **fields)

    def discard(source_id):
        raise OSError(16, "Resource busy")

    register.update, sections.discard_staged_for_source = update, discard
    with pytest.raises(Exception):
        content.publish(record.id, _sha(text_a))
    register.update, sections.discard_staged_for_source = original_update, original_discard
    assert register.get(record.id).content_sha256 == live.content_sha256  # the live record stands

    sections.list_for_source(record.id, sha=held.content_sha256)  # the in-flight reader asks for its record's passages
    assert sections.list_for_source(record.id, sha=live.content_sha256), (
        "the live record's passages were replaced by an uncommitted version's that no record names: "
        f"stored fingerprint {sections.fingerprint(record.id)[:12]}, record {live.content_sha256[:12]}")
