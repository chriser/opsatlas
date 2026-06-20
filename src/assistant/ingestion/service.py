"""Ingestion service: extract text from a registered source and build sections."""

from __future__ import annotations

from pathlib import Path

from ..sources.models import SourceRecord
from ..sources.register import SourceRegister
from .sections import build_sections
from .store import SectionStore

# Text extraction supported for these now; PDF/DOCX parsing arrives in a later slice.
TEXT_EXTENSIONS = {".txt", ".md"}


class NotIngestableError(ValueError):
    """Raised when a source cannot be ingested (unsupported type, missing, etc.)."""


def extract_text(filename: str, content: bytes) -> str:
    extension = Path(filename).suffix.lower()
    if extension in TEXT_EXTENSIONS:
        return content.decode("utf-8", errors="replace")
    raise NotIngestableError(
        f"Text extraction for '{extension or filename}' is not supported yet (only .txt and .md)."
    )


def ingest_source(
    register: SourceRegister,
    section_store: SectionStore,
    source_id: str,
) -> SourceRecord:
    record = register.get(source_id)
    if record is None:
        raise NotIngestableError("Source not found.")

    text = extract_text(record.filename, register.read_content(source_id))
    sections = build_sections(source_id, text)
    section_store.replace_for_source(source_id, sections)

    updated = register.update(
        source_id, processing_state="ingested", section_count=len(sections)
    )
    assert updated is not None  # the record existed a moment ago
    return updated
