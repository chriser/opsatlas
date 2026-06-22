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

    def as_evidence_text(self) -> str:
        """A compact structured summary used as extra evidence when answering."""
        parts = [f"Process: {self.name}."]
        if self.roles:
            parts.append("Roles/owners: " + "; ".join(self.roles) + ".")
        if self.systems:
            parts.append("Systems involved: " + "; ".join(self.systems) + ".")
        if self.controls:
            parts.append("Controls: " + ", ".join(self.controls) + ".")
        if self.dependencies:
            parts.append("Dependencies: " + ", ".join(self.dependencies) + ".")
        if self.business_rules:
            parts.append("Key rules: " + " ".join(self.business_rules))
        return " ".join(parts)
