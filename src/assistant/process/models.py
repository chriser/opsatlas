"""Process registry schema."""

from __future__ import annotations

from pydantic import BaseModel


class ProcessRule(BaseModel):
    """A single structured rule atom (from a pack's JSON-style learning records)."""

    record_id: str = ""
    topic: str = ""
    role: str = ""
    rule: str = ""
    confidence: str = ""


class ProcessRecord(BaseModel):
    """Structured knowledge about one business process, derived from one source."""

    id: str
    source_id: str
    source_title: str
    name: str
    domain: str = ""
    process: str = ""
    capabilities: list[str] = []
    roles: list[str] = []
    systems: list[str] = []
    controls: list[str] = []
    dependencies: list[str] = []
    business_rules: list[str] = []
    rules: list[ProcessRule] = []
