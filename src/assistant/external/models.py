"""Schemas for public external-content sources and snapshots."""

from __future__ import annotations

from pydantic import BaseModel


class PublicContentSource(BaseModel):
    """One selected public source URL that may be refreshed into snapshots."""

    id: str
    provider: str = "govuk"
    url: str
    title: str = ""
    public_body: str = ""
    topics: list[str] = []
    licence: str = "Open Government Licence v3.0"
    update_cadence: str = "manual"
    created_at: str
    updated_at: str
    snapshot_count: int = 0
    latest_snapshot_id: str = ""
    latest_snapshot_date: str = ""
    latest_update_date: str = ""
    last_error: str = ""


class FetchedPublicContent(BaseModel):
    """Content fetched from a public provider before it is versioned locally."""

    provider: str = "govuk"
    url: str
    title: str
    public_body: str = ""
    content_id: str = ""
    document_type: str = ""
    locale: str = ""
    update_date: str = ""
    retrieved_at: str
    text: str
    metadata: dict[str, str] = {}


class PublicContentSnapshot(BaseModel):
    """A versioned local snapshot of one public source."""

    id: str
    source_id: str
    provider: str = "govuk"
    version: int
    url: str
    title: str
    public_body: str = ""
    content_id: str = ""
    document_type: str = ""
    locale: str = ""
    update_date: str = ""
    retrieved_at: str
    snapshot_date: str
    content_sha256: str
    text: str
    metadata: dict[str, str] = {}
