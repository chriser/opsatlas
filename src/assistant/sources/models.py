"""Source register data model."""

from __future__ import annotations

from pydantic import BaseModel

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
    size_bytes: int
    content_sha256: str
    created_at: str
