"""S57's stated limits that can be tested, each pinned as a strict expected failure (REF S65 #2176).

A stated limit is behaviour S57 accepted and recorded instead of fixing (docs/benchmark/evidence/2026-10-04-s23-red-team.md,
"Stated limits"). Each test checks what the promise would ideally give and, where today's code does not give it, raises
LimitStillThere: the only exception its strict expected-failure mark accepts (its independent review's F2). So:
- a change that fixes the limit makes the test pass unexpectedly, which fails the gate (record the fix, remove the mark);
- any other failure fails the gate: a set-up that no longer holds (a builder's assert, an error in a fixture, which pytest
  would otherwise count against the mark), a precondition (SetupChanged), or a change that makes the limit worse.
"""
from __future__ import annotations

import pytest

from assistant.content.service import ContentError, sha
from assistant.sources.register import SourceRegister
from tests.door_helpers import as_job

TEXT = b"# Pricing\n\nAlpha is the first plan.\n"


class LimitStillThere(Exception):
    """The stated limit, observed: what the promise would ideally give is not given."""


class SetupChanged(Exception):
    """The test's set-up or precondition no longer holds: revise the test; it is not the stated limit."""


def limit(holds: bool, what: str) -> None:
    if not holds:
        raise LimitStillThere(what)


@pytest.fixture
def approved(sales_workspace):
    """An approved document in the organisation space, set up through the routes: (workspace, its source id)."""
    return sales_workspace, sales_workspace.document(TEXT)


class _PublishesLanding(SourceRegister):
    """The same register files, where a new version is published between every record read and its text read, for the
    first ``bursts`` reads; after that the record stands still, so a fix that retries until it is stable ends."""

    def __init__(self, base_dir, bursts: int = 10):
        super().__init__(base_dir)
        self.reads, self.bursts = 0, bursts

    def get(self, source_id):
        record = super().get(source_id)
        if record is None or self.reads >= self.bursts:
            return record
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


@pytest.mark.xfail(strict=True, raises=LimitStillThere,
                   reason="S57 stated limit (round 8): after three publishes inside one read, the paired read falls back "
                          "to a plain read")
def test_a_paired_read_never_gives_another_versions_text_however_many_publishes_land(approved):
    workspace, source_id = approved
    register = _PublishesLanding(workspace.core.state.register.base_dir)
    record, text = register.read_record_text(source_id)
    limit(record is None or sha(text) == record.content_sha256, "a paired read gave another version's text")  # S2


@pytest.mark.xfail(strict=True, raises=LimitStillThere,
                   reason="S57 stated limit (round 8): a reader holding the record of a source deleted meanwhile gets a "
                          "file error rather than nothing")
def test_a_reader_holding_a_deleted_sources_record_gets_nothing(approved):
    workspace, source_id = approved
    register = _DeletedMeanwhile(workspace.core.state.register.base_dir)
    try:
        read = register.read_record_text(source_id)
    except FileNotFoundError as error:
        raise LimitStillThere(f"a file error: {error}") from None
    assert read == (None, b"")  # nothing: anything else is worse than today, and fails the gate


@pytest.mark.xfail(strict=True, raises=LimitStillThere,
                   reason="S57 stated limit (round 12): a failed records step is tried again before a decision is refused "
                          "as already approved")
def test_a_decision_refused_as_already_approved_changes_nothing(approved):
    workspace, source_id = approved
    core = workspace.core
    content = core.state.content
    tried = []
    content.hooks["published"] = lambda *args: tried.append(args)  # the workspace's records step
    # No route leaves a records step failed on purpose, so the failure is recorded as the content workflow records it.
    as_job(core, content.store.set_meta, f"records_pending:{source_id}", "1")
    source = core.state.register.get(source_id)
    try:
        as_job(core, content.decide, source_id, sha(content.record_text(source)), True)
    except ContentError as refused:
        if "already approved" not in str(refused):
            raise SetupChanged(f"refused for another reason: {refused}") from None
    else:
        raise SetupChanged("the decision on an approved document was not refused")
    limit(tried == [] and bool(content.store.meta(f"records_pending:{source_id}")),
          "a refused decision tried the records step again")  # S8: refused, and nothing changed
