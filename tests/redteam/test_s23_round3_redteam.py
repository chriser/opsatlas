"""Red team, round 3, on REF S23 (staged publish, versions named at commit). Hermetic: a bare SourceRegister,
SectionStore and ContentService over tmp_path; no network, no live service, no model. Each test is a break (it fails
on 1de8b05) unless its name ends in ``_control``."""
from __future__ import annotations

import hashlib
import logging
import sqlite3
import threading
from types import SimpleNamespace

import pytest

from assistant.answer.service import AnswerService, Citation
from assistant.content.service import ContentService, Operator, sha
from assistant.ingestion.service import ingest_source
from assistant.ingestion.store import SectionStore
from assistant.sources.register import ContentReplaced, SourceRegister
from assistant.sources.service import register_upload

BODY = "The supervisor signs the handover log at 06:00 each day and checks the gate seals.\n"
A = "# Shift handover\n\n" + BODY
B = "# Shift handover\n\nThe supervisor signs the handover log at 07:00 each day and checks the gate seals.\n"
C = "# Shift handover\n\nThe duty manager signs the handover log at 08:00 each day and checks the gate seals.\n"


def _setup(tmp_path, *, approve=True, events=None, fail_first_history_write=False):
    reg = SourceRegister(tmp_path)
    sections = SectionStore(tmp_path)
    content = ContentService(reg, sections, operator=Operator("Red Team", "Editor"), events=events)
    reg.on_add.append(content.first_version)
    if fail_first_history_write:
        original = content.store.add_version
        state = {"failed": False}

        def fails_once(*a, **k):
            if not state["failed"]:
                state["failed"] = True
                raise sqlite3.OperationalError("database is locked")
            return original(*a, **k)

        content.store.add_version = fails_once
        with pytest.raises(sqlite3.OperationalError):
            register_upload(reg, "handover.md", A.encode())  # the upload reports failure; the record is stored
        content.store.add_version = original
        record = reg.list()[0]
    else:
        record = register_upload(reg, "handover.md", A.encode())
    ingest_source(reg, sections, record.id)
    if approve:
        reg.update(record.id, approval_status="approved")
    return reg, sections, content, record.id


def _publish(content, sid, text):
    content.save_draft(sid, text)
    content.submit(sid)
    return content.publish(sid, sha(text))


def _source_versions(content, sid):
    # Restated after the Human's decision on this round (REF S23): an uncommitted entry names nothing and is never shown,
    # so the promise "a version number names one text" is about the committed entries.
    return sorted(v["source_version"] for v in content.store.versions(sid) if v.get("committed", 1))


# ---- the history entry: written but reported failed; its removal failing ---------------------------------------


def test_s23_round3_history_entry_lands_but_reports_failure(tmp_path, monkeypatch):
    """S3/S6/S4: add_version commits its row and then raises. _swap does not catch it, so the staged text and passages
    are left on disk and the history keeps a version (labelled approved) that was never committed; the next publish
    is then given the same source version number, so version 2 names two texts."""
    reg, sections, content, sid = _setup(tmp_path)
    before = [v["sha"] for v in content.versions(sid)]
    original = content.store.add_version

    def lands_then_fails(*a, **k):
        original(*a, **k)
        raise sqlite3.OperationalError("disk I/O error")  # the row is written; the caller is told it was not

    monkeypatch.setattr(content.store, "add_version", lands_then_fails)
    with pytest.raises(Exception):
        _publish(content, sid, B)
    monkeypatch.setattr(content.store, "add_version", original)

    problems = []
    if reg.get(sid).content_sha256 != sha(A.encode()):
        problems.append("the live record changed")
    if (tmp_path / "sources" / f"{sid}.staged").exists() or (tmp_path / "sections" / f"{sid}.staged.json").exists():
        problems.append("S3: what was staged was not discarded")
    if [v["sha"] for v in content.versions(sid)] != before:
        problems.append("S6/S1: the history shows a version that was never committed")
    _publish(content, sid, C)
    numbers = _source_versions(content, sid)
    if len(numbers) != len(set(numbers)):
        problems.append(f"S4: a source version number names two texts in the history: {numbers}")
    assert not problems, problems


def test_s23_round3_record_write_fails_and_history_removal_fails(tmp_path, monkeypatch):
    """S6/S4: the record's write fails cleanly. (Restated: the entry made for it is not removed, so there is no removal
    to fail; it stays uncommitted and invisible.) It must not show in the history, and no number may name two texts."""
    reg, sections, content, sid = _setup(tmp_path)
    original_update = reg.update

    def commit_fails(source_id, **fields):
        if "history_n" in fields:
            raise OSError("No space left on device")
        return original_update(source_id, **fields)

    def removal_fails(*a, **k):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(reg, "update", commit_fails)
    assert removal_fails  # kept from the red team's draft; the design has no removal step to fail
    with pytest.raises(Exception):
        _publish(content, sid, B)
    monkeypatch.setattr(reg, "update", original_update)

    problems = []
    if any(v["sha"] == sha(B) for v in content.versions(sid)):
        problems.append("S6: the version created for a commit that failed is still in the history")
    _publish(content, sid, C)
    numbers = _source_versions(content, sid)
    if len(numbers) != len(set(numbers)):
        problems.append(f"S4: a source version number names two texts in the history: {numbers}")
    assert not problems, problems


# ---- a reader in the middle of the swap -----------------------------------------------------------------------


def test_s23_round3_versions_view_sees_uncommitted_version_and_its_number_is_reused(tmp_path, monkeypatch):
    """S1/S4: between the history entry and the record's write, the content views' versions list and version(n) show
    the new text (labelled approved) though nothing is committed; the commit then fails, the entry is removed, and
    number n is handed to a different text by the next publish."""
    reg, sections, content, sid = _setup(tmp_path)
    original_update = reg.update
    seen = {}

    def commit_fails_after_a_reader(source_id, **fields):
        if "history_n" in fields and not seen:
            seen["shas"] = [v["sha"] for v in content.versions(sid)]  # another request's content view, at this moment
            seen["n"] = fields["history_n"]
            try:
                seen["text"] = content.version(sid, fields["history_n"])["text"]
            except Exception:  # restated (REF S23): an uncommitted entry is not shown
                seen["text"] = None
            raise OSError("No space left on device")
        return original_update(source_id, **fields)

    monkeypatch.setattr(reg, "update", commit_fails_after_a_reader)
    with pytest.raises(OSError):
        _publish(content, sid, B)
    monkeypatch.setattr(reg, "update", original_update)

    problems = []
    if sha(B) in seen["shas"]:
        problems.append("S1: a content view listed the new version before its record was written (it never was)")
    if seen["text"] is not None:
        problems.append("S1: a content view showed the uncommitted version")
    _publish(content, sid, C)
    try:
        later = content.version(sid, seen["n"])["text"]
    except Exception:
        later = None
    if later is not None:
        problems.append(f"S4: number {seen['n']}, made for a commit that failed, now names a text")
    assert not problems, problems


# ---- duplicate input: a publish of the live text whose record write fails --------------------------------------


def test_s23_round3_same_text_publish_with_failed_commit_reports_success(tmp_path, monkeypatch):
    """S3/S6/S4: a draft that differs from the live text only by its final newline is published as the live bytes.
    The record's write fails without landing, but _swap sees the record already has that SHA, takes it as committed,
    and the publish reports success: the approval is never written, the version made for it stays in the history,
    and the next publish reuses its source version number."""
    reg, sections, content, sid = _setup(tmp_path, approve=False)
    original_update = reg.update

    def commit_fails(source_id, **fields):
        if "history_n" in fields:
            raise OSError("No space left on device")
        return original_update(source_id, **fields)

    monkeypatch.setattr(reg, "update", commit_fails)
    problems = []
    try:
        result = _publish(content, sid, A.rstrip("\n"))
        problems.append(f"S3: the publish reported success (version {result['version']}) though its record was not written")
    except Exception:
        pass
    monkeypatch.setattr(reg, "update", original_update)
    if reg.get(sid).approval_status != "approved" and not problems:
        pass  # failed and said so: fine
    elif reg.get(sid).approval_status != "approved":
        problems.append("S3: the document is still pending after a publish that reported success")
    if len([v for v in content.store.versions(sid) if v.get("committed", 1)]) != 1:  # restated: uncommitted names nothing
        problems.append("S6: the version created for the failed write is visible")
    content.store.clear_draft(sid)
    _publish(content, sid, C)
    numbers = _source_versions(content, sid)
    if len(numbers) != len(set(numbers)):
        problems.append(f"S4: a source version number names two texts in the history: {numbers}")
    assert not problems, problems


# ---- a reader that adds the first version, racing a publish ----------------------------------------------------


def test_s23_round3_reader_first_version_overwrites_committed_record(tmp_path, monkeypatch):
    """S6/S2: the upload's history write failed, so the record names no version. A content view (a reader) then adds
    one and writes history_n/history_sha without the lock and without checking the record's text; a publish that
    commits meanwhile is overwritten, so the record's text is B but it names version (and SHA) A, and every citation
    of B's passages, and the delivery recheck, carry A's version."""
    reg, sections, content, sid = _setup(tmp_path, fail_first_history_write=True)
    assert reg.get(sid).history_n is None
    original = content.store.add_version
    state = {"raced": False, "error": None}

    def publish_meanwhile(*a, **k):
        if not state["raced"]:
            state["raced"] = True

            def run():
                try:
                    _publish(content, sid, B)
                except Exception as exc:  # pragma: no cover - reported below
                    state["error"] = exc

            state["worker"] = threading.Thread(target=run)
            state["worker"].start()  # restated (REF S23, S7): the publish waits for the reader's lock, not the reverse
        return original(*a, **k)

    monkeypatch.setattr(content.store, "add_version", publish_meanwhile)
    content.versions(sid)  # a reader opens the document's history
    state["worker"].join(20)
    monkeypatch.setattr(content.store, "add_version", original)
    assert state["error"] is None, state["error"]

    record = reg.get(sid)
    live = reg.read_content(sid, sha=record.content_sha256).decode()
    named = content.store.version(sid, record.history_n)
    assert record.content_sha256 == sha(B.encode())
    assert record.history_sha == sha(live) and named["sha"] == sha(live), (
        f"S6: the record's text is version B but it names version {record.history_n}, whose text is A")


# ---- decide (approve) racing a new version written without approval ---------------------------------------------


def test_s23_round3_approval_of_read_version_lands_on_newer_unapproved_version(tmp_path, monkeypatch):
    """S1 (and the rule that a version written without approval is not approved): decide checks the SHA the Human
    read, then approves the record with no lock; a rename that writes an unapproved version in between is approved by
    it, so every reader sees as approved a text nobody approved."""
    reg, sections, content, sid = _setup(tmp_path, approve=False)
    content.hooks["retitle"] = lambda source, title: f"# {title}\n\n{BODY}"  # a document whose title is its heading
    expected = content.document(sid)["published"]["sha"]
    original_approve = content._approve

    def rename_meanwhile(source_id):
        worker = threading.Thread(target=lambda: content.rename(sid, "Gate handover"))
        worker.start()
        worker.join(20)
        return original_approve(source_id)

    monkeypatch.setattr(content, "_approve", rename_meanwhile)
    content.decide(sid, expected, approve=True)
    record = reg.get(sid)
    assert record.version == 2  # the rename's version is live
    assert record.approval_status != "approved" or sha(content.published_text(record)) == expected, (
        "an approval given to the text the Human read was written on a newer version nobody approved")


# ---- the event store down after a publish ----------------------------------------------------------------------


class _DownEvents:
    def record(self, *a, **k):
        raise OSError("event store unavailable")


def test_s23_round3_event_store_down_fails_a_committed_publish(tmp_path):
    """S5/S3: with the event store down, the approval event is swallowed, but publish() then writes source_edited
    unguarded and raises: the version is live but the publish reports failure, the draft stays submitted and the
    'approved and published' entry is never written; publishing again is refused (the base changed)."""
    reg, sections, content, sid = _setup(tmp_path, events=_DownEvents())
    problems = []
    try:
        _publish(content, sid, B)
    except Exception as exc:
        problems.append(f"S5: the publish failed on an event write: {exc!r}")
    if reg.get(sid).content_sha256 == sha(B.encode()) and problems:
        problems.append("S3: ... although the version was committed and is live")
    if (content.store.document(sid) or {}).get("draft_text") is not None:
        problems.append("the published draft is still waiting for approval")
    assert not problems, problems


class _ApprovalEventLost:
    def __init__(self):
        self.rows = []

    def record(self, kind, **k):
        if kind == "source_approved":
            raise OSError("event store unavailable")
        self.rows.append(kind)


def test_s23_round3_lost_approval_event_is_not_noted(tmp_path, caplog):
    """S5: 'a lost one is noted': _after_publish swallows the approval event's failure with a bare except/continue;
    nothing is logged and nothing is written to the document's activity, so the loss is invisible."""
    events = _ApprovalEventLost()
    reg, sections, content, sid = _setup(tmp_path, events=events)
    caplog.set_level(logging.DEBUG)
    _publish(content, sid, B)
    assert reg.get(sid).content_sha256 == sha(B.encode())
    logged = [r for r in caplog.records if r.levelno >= logging.WARNING and ("event" in r.getMessage().lower()
                                                                              or "approv" in r.getMessage().lower())]
    noted = [a for a in content.store.activity(sid) if "event" in (a["detail"] or "").lower() + a["action"].lower()]
    assert logged or noted, "S5: the lost approval event was not noted anywhere"


# ---- the stamp looks a version up when the record named none ---------------------------------------------------


def test_s23_round3_stamp_looks_up_current_version_for_unnumbered_record(tmp_path):
    """S6: a citation read from a record that named no version (the upload's history write failed) is stamped by
    looking up the version live at the end of the answer. A publish meanwhile makes A's passage cite version B, and
    the delivery recheck (cited SHA vs the record's) then passes."""
    reg, sections, content, sid = _setup(tmp_path, fail_first_history_write=True)
    read = reg.get(sid)  # the answer reads the record: history_n None
    passage = sections.list_for_source(sid, sha=read.content_sha256)[0]
    citation = Citation(source_id=sid, source_title=read.title, heading=passage.heading, ordinal=passage.ordinal,
                        read_n=read.history_n, read_sha=read.history_sha)
    _publish(content, sid, B)  # meanwhile
    stamped = AnswerService._stamp(SimpleNamespace(version_of=content.current_version), [citation])[0]
    assert stamped.sha256 in (None, sha(A)), (
        f"S6: a passage read from text A is cited as version {stamped.version} (text B)")


# ---- a reader's move racing a writer's staging -----------------------------------------------------------------


def test_s23_round3_reader_move_puts_writers_uncommitted_staged_text_live(tmp_path, monkeypatch):
    """S1/S3/S2: a reader holding committed record B checks the staged file is B, then (no lock, no re-check) renames
    it; a writer meanwhile settles B itself and stages C. The reader's rename puts C live before C's record is
    written. C's commit then fails: the record says B, B's text is gone from disk (readers holding B get nothing), and
    the content views show C, which was never committed."""
    reg, sections, content, sid = _setup(tmp_path)
    with monkeypatch.context() as m:  # B committed, not yet moved (a crash after the record's write)
        m.setattr(content, "_move_into_place", lambda source_id: None)
        content._write_version(reg.get(sid), B.encode(), approve=True, history={"label": "approved", "note": None})
    assert reg.get(sid).content_sha256 == sha(B.encode())
    assert (tmp_path / "sources" / f"{sid}.staged").read_bytes() == B.encode()

    reader_ready, writer_staged, reader_done = threading.Event(), threading.Event(), threading.Event()
    original_promote, original_update = reg.promote_content, reg.update
    out = {}

    def promote(source_id):
        if threading.current_thread().name == "reader":
            reader_ready.set()
            writer_staged.wait(10)
        return original_promote(source_id)

    def update(source_id, **fields):
        if threading.current_thread().name == "writer" and "history_n" in fields:
            writer_staged.set()
            reader_done.wait(10)
            out["during"] = content.published_text(reg.get(sid))  # a content view, before C is committed
            raise OSError("No space left on device")
        return original_update(source_id, **fields)

    monkeypatch.setattr(reg, "promote_content", promote)
    monkeypatch.setattr(reg, "update", update)

    def read():
        try:
            out["read"] = reg.read_content(sid, sha=sha(B.encode()))
        except ContentReplaced:
            out["read"] = None
        finally:
            reader_done.set()

    def write():
        reader_ready.wait(10)
        try:
            content._write_version(reg.get(sid), C.encode(), approve=True, history={"label": "approved", "note": None})
        except OSError:
            out["write_failed"] = True

    threads = [threading.Thread(target=read, name="reader"), threading.Thread(target=write, name="writer")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(20)
    monkeypatch.setattr(reg, "promote_content", original_promote)
    monkeypatch.setattr(reg, "update", original_update)

    record = reg.get(sid)
    problems = []
    assert out.get("write_failed") and record.content_sha256 == sha(B.encode())
    if out.get("during") == C:
        problems.append("S1: a content view showed C before its record was written")
    try:
        reg.read_content(sid, sha=record.content_sha256)
    except ContentReplaced:
        problems.append("S3/S2: after C's failed publish the live version B is gone; readers holding B get nothing")
    if content.published_text(record) == C:
        problems.append("S1/S3: the content views show C, which was never committed")
    assert not problems, problems


def test_s23_round3_committed_unmoved_version_is_settled_by_reader_control(tmp_path, monkeypatch):
    """Control: with no writer in between, a reader holding committed record B moves B's text and passages."""
    reg, sections, content, sid = _setup(tmp_path)
    with monkeypatch.context() as m:
        m.setattr(content, "_move_into_place", lambda source_id: None)
        content._write_version(reg.get(sid), B.encode(), approve=True, history={"label": "approved", "note": None})
    record = reg.get(sid)
    assert reg.read_content(sid, sha=record.content_sha256) == B.encode()
    assert sections.list_for_source(sid, sha=record.content_sha256)
    assert hashlib.sha256((tmp_path / "sources" / sid).read_bytes()).hexdigest() == record.content_sha256


# ---- the governance desk reads passages without the record's SHA -------------------------------------------------


def test_s23_round3_governance_statements_cache_previous_text_under_committed_version(tmp_path, monkeypatch):
    """S2/S1: with B committed but not yet moved (a crash after the record's write), the governance desk's statement
    sync reads passages without the record's SHA, so it extracts A's statements and files them under B's fingerprint
    (sha B, version 2). The fingerprint never changes again, so after B is moved the desk keeps A's wording for
    version B for good."""
    from assistant.governance.statements import StatementStore

    reg, sections, content, sid = _setup(tmp_path)
    with monkeypatch.context() as m:  # B committed, not yet moved
        m.setattr(content, "_move_into_place", lambda source_id: None)
        content._write_version(reg.get(sid), B.encode(), approve=True, history={"label": "approved", "note": None})
    desk = StatementStore(tmp_path)
    desk.sync(reg, sections)  # the governance desk's refresh, before any other reader came by
    record = reg.get(sid)
    assert reg.read_content(sid, sha=record.content_sha256) == B.encode()  # a reader moves B's text in
    assert sections.list_for_source(sid, sha=record.content_sha256)  # and its passages: B is wholly live now
    statements, _ = desk.sync(reg, sections)  # the next refresh
    words = " ".join(s.text for s in statements if s.source_id == sid)
    assert "06:00" not in words and "07:00" in words, (
        f"S2: the governance desk's statements for version {record.version} (text B) are A's: {words!r}")
