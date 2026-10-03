"""Settling a source (REF S23, a staged publish): a version whose record is written (committed) but whose staged text
and passages were not yet moved into place (a crash, a failed move) is moved first, text and passages together, before
any write to the source and when a reader finds its record and its files disagree. A staged version is moved only if
the record names it."""
from __future__ import annotations


def settle(register, section_store, source_id: str) -> None:
    record = register.get(source_id)
    if record is None:
        return
    register.promote_if_committed(source_id, record.content_sha256)
    if section_store is not None:
        section_store.promote_if_committed(source_id, record.content_sha256)
