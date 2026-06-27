"""Build compliance reasoning payloads from main application stores."""

from __future__ import annotations

from typing import Any

from ..external.registry import PublicContentRegistry
from ..ingestion.sections import build_sections
from ..ingestion.store import SectionStore
from ..sources.register import SourceRegister


def build_compliance_review_payload(
    register: SourceRegister,
    section_store: SectionStore,
    public_registry: PublicContentRegistry,
    *,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a non-mutating review payload for the standalone service."""

    return {
        "external_documents": _external_documents(public_registry),
        "internal_documents": _internal_documents(register, section_store),
        "options": options or {},
        "metadata": {
            "source": "knowledge-platform",
            "purpose": "governance-compliance-review",
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
        sections = section_store.list_for_source(source.id)
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
                        "text": section.text,
                        "citation": f"{source.title} - {section.heading}",
                        "ordinal": section.ordinal,
                    }
                    for section in sections
                ],
                "metadata": {
                    "approval_status": source.approval_status,
                    "processing_state": source.processing_state,
                    "source_type": source.source_type,
                },
            }
        )
    return documents


def _external_citation(snapshot, heading: str) -> str:
    parts = [snapshot.title]
    if heading and heading != "Introduction":
        parts.append(heading)
    if snapshot.version:
        parts.append(f"snapshot v{snapshot.version}")
    return " - ".join(parts)
