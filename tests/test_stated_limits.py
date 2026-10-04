"""S57's stated limits that can be tested, each pinned as a strict expected failure (REF S65 #2176).

A stated limit is behaviour S57 accepted and recorded instead of fixing (docs/benchmark/evidence/2026-10-04-s23-red-team.md,
"Stated limits"). Each test asserts what the promise would ideally give, and is a strict expected failure that raises
today's error:
- a change that fixes the limit makes the test pass unexpectedly, which fails the gate (record the fix, remove the mark);
- a change that makes it worse fails in another way, which fails the gate too.
"""
from __future__ import annotations

import pytest

from assistant.content.service import ContentError, sha
from assistant.sources.register import SourceRegister
from tests.door_helpers import as_job

TEXT = b"# Pricing\n\nAlpha is the first plan.\n"


class _PublishesLanding(SourceRegister):
    """The same register files, where a new version is published between every record read and its text read: each
    record read sees another version than the one before."""

    def __init__(self, base_dir):
        super().__init__(base_dir)
        self.reads = 0

    def get(self, source_id):
        record = super().get(source_id)
        if record is None:
            return None
        self.reads += 1
        return record.model_copy(update={"content_sha256": sha(b"version %d" % self.reads)})


class _DeletedMeanwhile(SourceRegister):
    """The same register files, where the source is deleted right after the reader takes its record."""

    deleted = False

    def get(self, source_id):
        record = super().get(source_id)
        if record is not None and not self.deleted:
            self.deleted = True
            self.remove(source_id)  # deleted between the reader's two reads
        return record


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="S57 stated limit (round 8): after three publishes inside one read, the paired read falls back "
                          "to a plain read")
def test_a_paired_read_never_gives_another_versions_text_however_many_publishes_land(sales_workspace):
    source_id = sales_workspace.document(TEXT)
    register = _PublishesLanding(sales_workspace.core.state.register.base_dir)
    record, text = register.read_record_text(source_id)
    assert record is None or sha(text) == record.content_sha256  # S2: that record's text, or none


@pytest.mark.xfail(strict=True, raises=FileNotFoundError,
                   reason="S57 stated limit (round 8): a reader holding the record of a source deleted meanwhile gets a "
                          "file error rather than nothing")
def test_a_reader_holding_a_deleted_sources_record_gets_nothing(sales_workspace):
    source_id = sales_workspace.document(TEXT)
    register = _DeletedMeanwhile(sales_workspace.core.state.register.base_dir)
    assert register.read_record_text(source_id) == (None, b"")


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="S57 stated limit (round 12): a failed records step is tried again before a decision is refused "
                          "as already approved")
def test_a_decision_refused_as_already_approved_changes_nothing(sales_workspace):
    source_id = sales_workspace.document(TEXT)  # approved
    core = sales_workspace.core
    content = core.state.content
    tried = []
    content.hooks["published"] = lambda *args: tried.append(args)  # the workspace's records step
    as_job(core, content.store.set_meta, f"records_pending:{source_id}", "1")  # failed after the last commit
    source = core.state.register.get(source_id)
    with pytest.raises(ContentError, match="already approved"):
        as_job(core, content.decide, source_id, sha(content.record_text(source)), True)
    assert tried == [] and content.store.meta(f"records_pending:{source_id}")  # S8: refused, and nothing changed
