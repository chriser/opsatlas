"""Source register data model."""

from __future__ import annotations

from pydantic import BaseModel, Field

# Document types accepted into the knowledge base (anonymised material only).
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".json"}

# Governance vocabulary kept deliberately small for the proof of concept.
SENSITIVITY_VALUES = ("anonymised", "synthetic")
PROCESSING_STATES = ("registered", "ingested", "indexed", "failed")
APPROVAL_STATES = ("pending", "approved", "rejected")


class SourceRecord(BaseModel):
    """One catalogued source document and its governance status."""

    id: str
    filename: str
    title: str
    source_type: str = "document"
    sensitivity: str = "anonymised"
    version: int = 1
    processing_state: str = "registered"
    approval_status: str = "pending"
    section_count: int = 0
    size_bytes: int
    content_sha256: str
    created_at: str
    # Scope and lifecycle (GOV S8), all optional: when the source is in force (ISO dates), the phase it describes
    # (assistant.governance.scope.PHASES), the sites or networks it applies to, and the sources it replaces.
    effective_from: str | None = None
    effective_to: str | None = None
    phases: list[str] = Field(default_factory=list)
    applies_to: list[str] = Field(default_factory=list)
    supersedes: list[str] = Field(default_factory=list)
