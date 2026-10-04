"""Red team, round 4, REF S23 (staged publish, one writer per space). Each test is a break: it fails on d317389.

Hermetic: services built directly over tmp_path; no network, no live services, no model.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from assistant.content.service import ContentError, ContentService, Operator
from assistant.ingestion.service import ingest_source
from assistant.ingestion.store import SectionStore
from assistant.retrieval.index import CorpusIndex
from assistant.sources.models import SourceRecord
from assistant.sources.register import SourceRegister
from tests.door_helpers import as_job, decided

V1 = "# Refund policy\n\nRefunds are paid within thirty days of the request.\n"
V2 = "# Refund policy\n\nRefunds are paid within fourteen days of the request.\n"


def sha(value: str | bytes) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def build(tmp_path, text: str = V1, approved: bool = True, actions=None):
    register = SourceRegister(tmp_path)
    sections = SectionStore(tmp_path)
    svc = ContentService(register, sections, actions=actions, operator=Operator("Ann", "Approver"))
    register.on_add.append(svc.first_version)  # as the app wires it
    content = text.encode()
    record = SourceRecord(id="doc1", filename="policy.md", title="Refund policy", size_bytes=len(content),
                          content_sha256=sha(content), created_at=datetime.now(timezone.utc).isoformat())
    register.add(record, content)
    ingest_source(register, sections, "doc1")
    if approved:
        decided(register, "doc1", approval_status="approved")
    return register, sections, svc


def run(name: str, target, results: dict) -> threading.Thread:
    def body():
        try:
            results[name] = ("ok", target())
        except BaseException as exc:  # noqa: BLE001
            results[name] = ("error", exc)
    thread = threading.Thread(target=body, name=name, daemon=True)
    thread.start()
    return thread


# ---------------------------------------------------------------------------------------------------------------------
# Break 1 (S7, S3): two locks taken in opposite orders. publish() and rename() hold the content store's lock and then
# take the space's lock (in _swap); update_details (and first_version, _swap itself) hold the space's lock and then take
# the content store's lock (store.log / store.add_version). One approval and one details edit at once deadlock: both
# requests hang for ever, and every later writer in the space (and every reader that meets a staged file) hangs too.
# ---------------------------------------------------------------------------------------------------------------------

def test_s23_round4_publish_and_details_edit_at_once_deadlock(tmp_path):
    register, sections, svc = build(tmp_path)
    svc.save_draft("doc1", V2)
    svc.submit("doc1")
    a_holds_store_lock, b_holds_space_lock = threading.Event(), threading.Event()

    def prepare(source, text):  # runs inside publish(), under the content store's lock (a widened window, no I/O)
        if threading.current_thread().name == "approver":
            a_holds_store_lock.set()
            b_holds_space_lock.wait(3)
        return (text if text.endswith("\n") else text + "\n").encode(), None

    def describe(source):  # runs inside update_details, under the space's lock (a widened window, no I/O)
        if threading.current_thread().name == "editor" and not b_holds_space_lock.is_set():
            b_holds_space_lock.set()
            a_holds_store_lock.wait(3)
        return {}

    svc.hooks["prepare"], svc.hooks["describe"] = prepare, describe
    results: dict = {}
    approver = run("approver", lambda: svc.publish("doc1", sha(V2)), results)
    editor = run("editor", lambda: svc.update_details("doc1", {"effective_from": "2026-01-01"}), results)
    approver.join(8)
    editor.join(8)
    assert not approver.is_alive() and not editor.is_alive(), \
        "an approval and a details edit at once deadlocked (store lock -> space lock vs space lock -> store lock)"


def test_s23_round4_publish_and_new_upload_at_once_deadlock(tmp_path):
    """The same inversion through an upload: register.add -> on_add -> first_version holds the space's lock and then
    store.add_version takes the content store's lock, while a publish holds the store's lock and waits for the space's."""
    register, sections, svc = build(tmp_path)
    svc.save_draft("doc1", V2)
    svc.submit("doc1")
    a_holds_store_lock, b_holds_space_lock = threading.Event(), threading.Event()

    def prepare(source, text):
        if threading.current_thread().name == "approver":
            a_holds_store_lock.set()
            b_holds_space_lock.wait(3)
        return (text if text.endswith("\n") else text + "\n").encode(), None

    versions = svc.store.versions

    def paused_versions(source_id):  # first_version reads the history under the space's lock, then adds a version
        if threading.current_thread().name == "uploader" and not b_holds_space_lock.is_set():
            b_holds_space_lock.set()
            a_holds_store_lock.wait(3)
        return versions(source_id)

    svc.hooks["prepare"] = prepare
    svc.store.versions = paused_versions
    content = b"# Delivery\n\nParcels ship within two days.\n"
    upload = SourceRecord(id="doc2", filename="delivery.md", title="Delivery", size_bytes=len(content),
                          content_sha256=sha(content), created_at=datetime.now(timezone.utc).isoformat())
    results: dict = {}
    approver = run("approver", lambda: svc.publish("doc1", sha(V2)), results)
    uploader = run("uploader", lambda: register.add(upload, content), results)
    approver.join(8)
    uploader.join(8)
    assert not approver.is_alive() and not uploader.is_alive(), \
        "an approval and an upload at once deadlocked (store lock -> space lock vs space lock -> store lock)"


# ---------------------------------------------------------------------------------------------------------------------
# Break 2 (S7, S1): rename reads the approval it "keeps" before it takes the space's lock. A reviewer's rejection that
# lands in between (decide(), itself under the space's lock) is overwritten: the withdrawn document's next version is
# written approved, nobody having approved it, and readers search it again.
# ---------------------------------------------------------------------------------------------------------------------

def test_s23_round4_rename_reapproves_a_document_rejected_meanwhile(tmp_path):
    """Restated for the door (REF S23, the Human's decision after round 7): the rename and the rejection are each a job
    holding the door's lock, as their requests would be (no service lock remains). While the rename is paused preparing
    its text, the rejection waits at the lock; once the rename is done, the rejection meets the new version and is
    refused, so it can never be accepted and then overwritten by the rename's approval."""
    register, sections, svc = build(tmp_path)
    svc.document("doc1")
    published = svc.published_text(register.get("doc1"))
    preparing, go = threading.Event(), threading.Event()

    def retitle(source, title):  # the workspace's retitle hook (a record's title is its first heading)
        if threading.current_thread().name == "renamer":
            preparing.set()  # the reviewer's rejection arrives while the rename is preparing its text
            go.wait(8)
        return source and V1.replace("# Refund policy", f"# {title}")

    svc.hooks["retitle"] = retitle
    results: dict = {}
    renamer = run("renamer", lambda: as_job(svc, svc.rename, "doc1", "Refunds"), results)
    assert preparing.wait(8)
    reviewer = run("reviewer", lambda: as_job(svc, svc.decide, "doc1", sha(published), approve=False), results)
    time.sleep(0.3)
    assert "reviewer" not in results and register.get("doc1").approval_status == "approved", \
        "the rejection went in while the rename held the lock"
    go.set()
    renamer.join(8)
    reviewer.join(8)
    assert results["renamer"][0] == "ok", results["renamer"]
    record = register.get("doc1")
    searchable = [s.text for _, s in CorpusIndex(register, sections).current().items]
    # Restated after the fix (one writer per space, REF S23): the rename holds the space lock, so the rejection either
    # lands first or is refused because the version it was given is no longer live ("review it again"). What must
    # never happen is a rejection accepted and the document approved by the rename that raced it.
    if results["reviewer"][0] == "ok":
        assert record.approval_status != "approved" and not searchable, (
            f"the reviewer rejected the document, yet the concurrent rename wrote its next version as "
            f"{record.approval_status!r} and readers search it: {searchable}")
    else:
        assert "changed since you opened it" in str(results["reviewer"][1]), results["reviewer"]


# ---------------------------------------------------------------------------------------------------------------------
# Break 3 (S2, S6, S3): passages written before S23 carry no fingerprint and are "taken as the live version's" by every
# reader, whatever SHA it asks for. One failed move after a commit (or a crash between the record's write and the move)
# then serves the previous version's passages under the new record, cited as the new version. The reader never moves
# them (it returns early), and the retrieval snapshot keeps them even after a writer settles (the fingerprint is
# unchanged).
# ---------------------------------------------------------------------------------------------------------------------

def test_s23_round4_unfingerprinted_passages_served_as_the_new_version_after_a_failed_move(tmp_path):
    register, sections, svc = build(tmp_path)
    path = tmp_path / "sections" / "doc1.json"
    legacy = json.loads(path.read_text())["sections"]
    path.write_text(json.dumps(legacy))  # a passages file as written before this change (no fingerprint)

    move = sections.promote_for_source
    failed = {"n": 0}

    def failing_move(source_id):  # one failed rename after the commit (EBUSY, EACCES, a crash at this step)
        if failed["n"] == 0:
            failed["n"] += 1
            raise OSError("rename failed")
        return move(source_id)

    sections.promote_for_source = failing_move
    svc.save_draft("doc1", V2)
    svc.submit("doc1")
    result = svc.publish("doc1", sha(V2))
    record = register.get("doc1")
    assert record.content_sha256 == sha(V2) and record.history_n == result["version"]

    index = CorpusIndex(register, sections)
    served = [(r.history_n, s.text) for r, s in index.current().items]
    ingest_source(register, sections, "doc1")  # a later writer settles the source on disk
    served_after_settle = [(r.history_n, s.text) for r, s in index.current().items]
    stale = [(n, t) for n, t in served + served_after_settle if "thirty" in t]
    assert not stale, (f"version {record.history_n}'s record is served with version 1's passages "
                       f"(cited as version {record.history_n}): {stale}")


# ---------------------------------------------------------------------------------------------------------------------
# Break 4 (S6): a commit is recognised by its text after a failed publish action. With the actions engine wired, a
# publish whose record write failed is taken as committed when the record's SHA equals the new text's (a draft that only
# drops the trailing newline, or a re-approval of the same text). The approver is told "approved and published" with
# the previous version's number; the record is not approved; the draft is cleared.
# ---------------------------------------------------------------------------------------------------------------------

@dataclass
class _Result:
    outcome: str
    message: str | None = None


class _Actions:
    """The engine's contract as content management uses it: a handler's error becomes outcome "error"."""

    def __init__(self):
        self.handlers = {}

    def register_handler(self, name, handler):
        self.handlers[name] = handler

    def execute(self, name, params, person):
        context = type("Context", (), {"params": params})()
        try:
            self.handlers[name](context)
            return _Result("ok")
        except Exception as exc:  # noqa: BLE001
            return _Result("error", str(exc))


def test_s23_round4_failed_publish_of_the_same_text_reported_as_published(tmp_path, monkeypatch):
    register, sections, svc = build(tmp_path, approved=False, actions=_Actions())
    decided(register, "doc1", approval_status="rejected")
    before = register.get("doc1")
    svc.save_draft("doc1", V1.rstrip("\n"))  # the same text bar the newline the publish adds back
    svc.submit("doc1")

    update = register.update

    def failing_update(source_id, **fields):  # the commit's write fails (disk full); nothing lands
        if "history_n" in fields:
            raise OSError("No space left on device")
        return update(source_id, **fields)

    monkeypatch.setattr(register, "update", failing_update)
    try:
        result = svc.publish("doc1", sha(V1.rstrip("\n")))
    except ContentError:
        return  # the failure reported: no break
    after = register.get("doc1")
    assert after.approval_status == "approved", (
        f"the publish failed (record not written, still {after.approval_status!r}, version {after.history_n} = "
        f"{before.history_n}) but was reported as published version {result['version']}")
