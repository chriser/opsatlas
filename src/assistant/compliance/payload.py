"""Build compliance reasoning payloads from main application stores."""

from __future__ import annotations

import re
from typing import Any

from ..external.registry import PublicContentRegistry
from ..ingestion.sections import build_sections
from ..ingestion.store import SectionStore
from ..sources.register import SourceRegister

TEST_FIXTURE_SECTION_DENYLIST = {"expected governance review outcome"}
INTERNAL_REASONING_SECTION_DENYLIST = {
    "json-style learning records",
    "open questions and design decisions",
    "suggested tagging structure",
}
_NUMBERED_HEADING_PREFIX = re.compile(r"^\d+\.\s*")
_SOURCE_BASIS_LINE = re.compile(r"^(?:\*\*)?source basis:(?:\*\*)?\s*", re.I)


def build_compliance_review_payload(
    register: SourceRegister,
    section_store: SectionStore,
    public_registry: PublicContentRegistry,
    *,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a non-mutating review payload for the standalone service."""

    return {
        "review_mode": "external_vs_internal",
        "external_documents": _external_documents(public_registry),
        "internal_documents": _internal_documents(register, section_store),
        "options": options or {},
        "metadata": {
            "source": "knowledge-platform",
            "purpose": "governance-compliance-review",
        },
    }


def build_internal_source_review_payload(
    register: SourceRegister,
    section_store: SectionStore,
    *,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a pairwise internal-source review payload for the standalone service."""

    return {
        "review_mode": "internal_vs_internal",
        "external_documents": [],
        "internal_documents": _internal_documents(register, section_store),
        "options": options or {},
        "metadata": {
            "source": "knowledge-platform",
            "purpose": "governance-internal-source-review",
        },
    }


def _external_documents(public_registry: PublicContentRegistry) -> list[dict[str, Any]]:
    documents = []
    for snapshot in public_registry.list_snapshots(include_text=True):
        sections = build_sections(snapshot.id, snapshot.text)
        documents.append(
            {
                "id": snapshot.id,
                "title": snapshot.title,
                "source_type": "external",
                "url": snapshot.url,
                "version": f"v{snapshot.version}",
                "snapshot_id": snapshot.id,
                "content_sha256": snapshot.content_sha256,
                "retrieved_at": snapshot.retrieved_at,
                "sections": [
                    {
                        "id": f"{snapshot.id}-{section.ordinal}",
                        "heading": section.heading,
                        "text": section.text,
                        "citation": _external_citation(snapshot, section.heading),
                        "ordinal": section.ordinal,
                    }
                    for section in sections
                ],
                "metadata": {
                    "provider": snapshot.provider,
                    "public_body": snapshot.public_body,
                    "document_type": snapshot.document_type,
                    "update_date": snapshot.update_date,
                },
            }
        )
    return documents


def _internal_documents(register: SourceRegister, section_store: SectionStore) -> list[dict[str, Any]]:
    documents = []
    for source in register.list():
        if source.approval_status != "approved":
            continue
        is_test_fixture = _is_test_fixture_source(source)
        sections = []
        for section in section_store.list_for_source(source.id):
            if _exclude_internal_section(section.heading, is_test_fixture=is_test_fixture):
                continue
            text = _governance_section_text(section.text)
            if not text:
                continue
            sections.append((section, text))
        documents.append(
            {
                "id": source.id,
                "title": source.title,
                "source_type": "internal",
                "content_sha256": source.content_sha256,
                "sections": [
                    {
                        "id": f"{source.id}-{section.ordinal}",
                        "heading": section.heading,
                        "text": text,
                        "citation": f"{source.title} - {section.heading}",
                        "ordinal": section.ordinal,
                    }
                    for section, text in sections
                ],
                "metadata": {
                    "approval_status": source.approval_status,
                    "processing_state": source.processing_state,
                    "source_type": source.source_type,
                    "is_test_fixture": str(is_test_fixture).lower(),
                },
            }
        )
    return documents


def _is_test_fixture_source(source) -> bool:
    filename = str(getattr(source, "filename", "") or "").lower()
    title = str(getattr(source, "title", "") or "").lower()
    return "test-fixture" in filename or "synthetic" in filename or "synthetic" in title


def _exclude_internal_section(heading: str, *, is_test_fixture: bool) -> bool:
    normalized = " ".join(heading.lower().split())
    without_number = _NUMBERED_HEADING_PREFIX.sub("", normalized)
    if without_number in INTERNAL_REASONING_SECTION_DENYLIST:
        return True
    return is_test_fixture and normalized in TEST_FIXTURE_SECTION_DENYLIST


def _governance_section_text(text: str) -> str:
    """Remove provenance boilerplate while retaining substantive title-section prose."""

    kept = []
    for line in text.splitlines():
        stripped = line.strip()
        if _SOURCE_BASIS_LINE.match(stripped):
            continue
        if stripped in {"---", "***", "___"}:
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def _external_citation(snapshot, heading: str) -> str:
    parts = [snapshot.title]
    if heading and heading != "Introduction":
        parts.append(heading)
    if snapshot.version:
        parts.append(f"snapshot v{snapshot.version}")
    return " - ".join(parts)
