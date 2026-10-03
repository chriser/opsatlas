"""Red team, round 2, for REF S23 (the staged publish). Hermetic: temporary folders only, no network, no model.

Each break is a failing test; each control passes. The interleavings two requests would produce are emulated in one
thread at the points the code leaves open (between a reader's record read and its text read; between a swap's move
and its history), and a crash is a step that never runs (the move after the commit).
"""

from __future__ import annotations

import hashlib
import os
from types import SimpleNamespace

import pytest

from assistant.answer.service import AnswerService, Citation
from assistant.content.service import ContentService
from assistant.ingestion.service import ingest_source
from assistant.ingestion.store import SectionStore
from assistant.sources.register import ContentReplaced, SourceRegister
from assistant.sources.service import register_upload
from services.opsatlas_sales.spaces import move_document

OLD = b"# Refund policy\n\nRefunds are paid within ten days of the request.\n"
NEW = b"# Refund policy\n\nRefunds are paid within thirty days of the request.\n"
THIRD = b"# Refund policy\n\nRefunds are paid within five days of the request.\n"


def h(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(os, "environ", os.environ.copy())


def core(base):
    register, sections = SourceRegister(base), SectionStore(base)
    return register, sections, ContentService(register, sections)


def approved(register, sections, body=OLD):
    record = register_upload(register, "policy.md", body, "Refund policy")
    ingest_source(register, sections, record.id)
    return register.update(record.id, approval_status="approved")


def crash_after_commit(content):
    """The process dies right after the record's write: nothing staged is moved into place."""
    content._move_into_place = lambda source_id: None


# ---- B1: a move between spaces after a crash between the commit and the move (S2, S3) ------------------------------

def _move_case(tmp_path, crash: bool):
    reg_a, sec_a, content_a = core(tmp_path / "origin")
    reg_b, sec_b = SourceRegister(tmp_path / "target"), SectionStore(tmp_path / "target")
    record = approved(reg_a, sec_a)
    if crash:
        crash_after_commit(content_a)
    content_a._write_version(record, NEW, approve=True)
    assert reg_a.get(record.id).content_sha256 == h(NEW)  # committed: version 2 is the approved version
    move_document(record.id, (reg_a, sec_a), (reg_b, sec_b), keep_approval=True)
    return record.id, reg_b, sec_b


def test_s23_round2_control_move_after_complete_publish_keeps_new_passages(tmp_path):
    source_id, reg_b, sec_b = _move_case(tmp_path, crash=False)
    moved = reg_b.get(source_id)
    texts = " ".join(s.text for s in sec_b.list_for_source(source_id, sha=moved.content_sha256))
    assert "thirty days" in texts and "ten days" not in texts


def test_s23_round2_move_after_crash_serves_old_passages_under_new_record(tmp_path):
    # S2: after a crash between commit and move, move_document copies the live (old) file and passages, unfingerprinted,
    # under the new record; a reader holding version 2's record then gets version 1's passages ("ten days").
    source_id, reg_b, sec_b = _move_case(tmp_path, crash=True)
    moved = reg_b.get(source_id)
    assert moved.content_sha256 == h(NEW) and moved.approval_status == "approved"
    texts = " ".join(s.text for s in sec_b.list_for_source(source_id, sha=moved.content_sha256))
    assert "ten days" not in texts, "a reader holding version 2's record was given version 1's passages"


def test_s23_round2_move_after_crash_loses_the_committed_text(tmp_path):
    # S3: the committed version is not completed by the next reader: move_document drops the staged text (remove) and
    # moves the old file, so version 2's record names a text that no longer exists anywhere.
    source_id, reg_b, sec_b = _move_case(tmp_path, crash=True)
    moved = reg_b.get(source_id)
    try:
        text = reg_b.read_content(source_id, sha=moved.content_sha256)
    except ContentReplaced:
        text = None
    assert text == NEW, "version 2 is committed, but its text was lost in the move"


# ---- B2: a crash after the commit, then the next publish fails at its commit (S3) ---------------------------------

def _failed_next_publish(tmp_path, monkeypatch, crash: bool):
    register, sections, content = core(tmp_path / "core")
    record = approved(register, sections)
    if crash:
        crash_after_commit(content)
    content._write_version(record, NEW, approve=True)
    content.__dict__.pop("_move_into_place", None)  # the process restarted
    content.published_text(register.get(record.id))  # what publish() reads first: it moves the text, not the passages
    real_update = register.update

    def failing_commit(source_id, **fields):
        if fields.get("content_sha256") == h(THIRD):
            raise OSError("disk full")
        return real_update(source_id, **fields)
    monkeypatch.setattr(register, "update", failing_commit)
    with pytest.raises(Exception):
        content._write_version(register.get(record.id), THIRD, approve=True)
    live = register.get(record.id)
    assert live.content_sha256 == h(NEW)
    return " ".join(s.text for s in sections.list_for_source(record.id, sha=live.content_sha256))


def test_s23_round2_control_failed_publish_keeps_live_passages(tmp_path, monkeypatch):
    texts = _failed_next_publish(tmp_path, monkeypatch, crash=False)
    assert "thirty days" in texts


def test_s23_round2_failed_publish_after_crash_destroys_live_passages(tmp_path, monkeypatch):
    # S3: version 2's passages still sat in sections/<id>.staged.json (committed, not moved); the next publish staged
    # its own over them, failed at the commit and discarded the file, so the live version 2 has no passages at all.
    texts = _failed_next_publish(tmp_path, monkeypatch, crash=True)
    assert "thirty days" in texts, "the failed publish left the live version without its passages"


# ---- B3: a reader that read the record just before a publish (S6, S4) ----------------------------------------------

def _publish_with(content, source_id, body):
    return content._write_version(content.register.get(source_id), body, approve=True, history={"label": "approved"})


# Restated after the Human's decision on this round (versions named at commit, REF S23): the version is created inside
# the swap and written with the record; readers never look one up or add one. The races these tests drove (a reader
# between the move and the history step, the version cache) no longer have code to race, so each test now drives the
# same moments through the staged steps and checks the promise directly.

def test_s23_round2_reader_between_move_and_history_names_version_twice(tmp_path):
    """S6/S4: a reader naming the version at every moment of a publish (staged, committed, moved) never adds one: the
    new text has exactly one history number, and each reader named a version its record held."""
    register, sections, content = core(tmp_path / "core")
    record = approved(register, sections)
    content.first_version(record)
    named = []
    for step, target, name in ((0, register, "stage_content"), (1, sections, "stage_for_source"),
                               (2, register, "promote_content")):
        real = getattr(target, name)

        def hooked(*args, _real=real, **kwargs):
            out = _real(*args, **kwargs)
            named.append(content.current_version(record.id))
            return out
        setattr(target, name, hooked)
    try:
        _publish_with(content, record.id, NEW)
    finally:
        for target, name in ((register, "stage_content"), (sections, "stage_for_source"), (register, "promote_content")):
            setattr(target, name, getattr(type(target), name).__get__(target))
    rows = [r for r in content.store.versions(record.id) if r["sha"] == h(NEW)]
    assert len(rows) == 1, f"version 2's text is named {len(rows)} times"
    assert all(n["n"] in (1, rows[0]["n"]) for n in named), named


def test_s23_round2_stale_reader_poisons_version_cache_after_restore(tmp_path):
    """S6: after a restore (version 1's text published again as version 3), a citation from an answer that read the
    restored record names version 3's history number; one that read the first record names version 1's."""
    register, sections, content = core(tmp_path / "core")
    record = approved(register, sections)
    content.first_version(record)
    first = register.get(record.id)
    _publish_with(content, record.id, NEW)
    _publish_with(content, record.id, OLD)  # the restore
    live = register.get(record.id)
    assert live.content_sha256 == h(OLD) and live.history_n != first.history_n

    def stamp(read):
        return AnswerService._stamp(SimpleNamespace(version_of=content.current_version), [Citation(
            source_id=record.id, source_title="Refund policy", heading="Refund policy", ordinal=1,
            read_n=read.history_n, read_sha=read.history_sha)])[0]
    assert stamp(live).version == live.history_n and stamp(first).version == first.history_n


def test_s23_round2_restore_cites_first_version_not_register_version(tmp_path):
    """S6: after a restore, the version named is the one the register's version holds in the history."""
    register, sections, content = core(tmp_path / "core")
    record = approved(register, sections)
    content.first_version(record)
    assert content.current_version(record.id)["n"] == 1
    _publish_with(content, record.id, NEW)
    _publish_with(content, record.id, OLD)
    live = register.get(record.id)
    named = content.current_version(record.id)
    rows = {r["n"]: r for r in content.store.versions(record.id)}
    assert rows[named["n"]]["source_version"] == live.version, (
        f"the receipt names history n={named['n']} (register version {rows[named['n']]['source_version']}); "
        f"the register says version {live.version}")


# ---- B4: a file replaced on disk; the answer read the approved passages (S6, S4) ------------------------------------

def test_s23_round2_replaced_file_receipt_names_text_the_answer_did_not_read(tmp_path):
    # S6: the answer reads the passages of the record's text (v1, fingerprint matches); the file was replaced on disk.
    # The stamp names the replaced file's SHA-256, a text no passage came from, and a second "version 1" is recorded.
    register, sections, content = core(tmp_path / "core")
    record = approved(register, sections)
    content.first_version(record)
    record = register.get(record.id)  # restated (REF S23): the record names its version, which the citation carries
    register.file_path(record.id).write_bytes(THIRD)  # changed outside content management
    read = sections.list_for_source(record.id, sha=record.content_sha256)
    assert read and "ten days" in read[0].text  # what the answer read: v1's passages
    stamped = AnswerService._stamp(SimpleNamespace(version_of=content.current_version), [Citation(
        source_id=record.id, source_title="Refund policy", heading=read[0].heading, ordinal=read[0].ordinal,
        read_n=record.history_n, read_sha=record.history_sha)])[0]
    v1_rows = {r["sha"] for r in content.store.versions(record.id) if r["source_version"] == 1}
    assert stamped.sha256 == record.content_sha256, "the receipt names the replaced file's text, not the passages' text"
    assert len(v1_rows) == 1, "register version 1 now names two texts in the history"


# ---- B5: the approval's event, written but reported failed (S5) ---------------------------------------------------

def test_s23_round2_approval_event_written_twice_when_ack_is_lost(tmp_path):
    # S5: the approval's event is retried on failure, but a write that landed and then raised is written again: the
    # audit log holds two approvals of one version.
    class Events:
        def __init__(self):
            self.rows = []

        def record(self, kind, **fields):
            self.rows.append((kind, fields.get("entity_id")))
            if len(self.rows) == 1:
                raise OSError("written, but the acknowledgement was lost")
    register, sections = SourceRegister(tmp_path / "core"), SectionStore(tmp_path / "core")
    events = Events()
    content = ContentService(register, sections, events=events)
    record = approved(register, sections)
    content._write_version(record, NEW, approve=True)
    assert register.get(record.id).content_sha256 == h(NEW)
    assert len(events.rows) == 1, f"one approval, {len(events.rows)} approval events"
