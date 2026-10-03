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


def stamp_unfingerprinted(register, section_store) -> int:
    """Passages stored before the staged publish carry no fingerprint; each source whose live text is its record's has
    its passages stamped with that fingerprint, once, at start-up (REF S23, red team round 4)."""
    import hashlib
    stamped = 0
    for record in register.list():
        if section_store.fingerprint(record.id) is not None:
            continue
        sections = section_store.list_for_source(record.id)
        if not sections:
            continue
        try:
            content = register.read_content(record.id)
        except OSError:
            continue
        if hashlib.sha256(content).hexdigest() == record.content_sha256:
            section_store.replace_for_source(record.id, sections, sha=record.content_sha256)
            stamped += 1
    return stamped
