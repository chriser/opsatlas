"""Analytics event schema and taxonomy.

The event ledger is the durable fact stream behind governance trends, simulated
pilot usage, value telemetry and future notebooks. Events intentionally carry
small, safe metadata only; source text, prompts and generated answers stay in
their specialist stores.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

MetadataValue = str | int | float | bool | None

EventType = Literal[
    "source_uploaded",
    "source_deleted",
    "source_ingested",
    "source_approved",
    "source_rejected",
    "source_edited",
    "governance_issue_detected",
    "governance_issue_accepted",
    "governance_issue_resolved",
    "ask_answered",
    "ask_refused",
    "ask_guardrail_blocked",
    "simulation_run_started",
    "simulation_run_completed",
    "value_event_recorded",
    "external_snapshot_recorded",
    "external_change_flagged",
    "regulatory_impact_simulated",
]

EVENT_TYPES: tuple[str, ...] = (
    "source_uploaded",
    "source_deleted",
    "source_ingested",
    "source_approved",
    "source_rejected",
    "source_edited",
    "governance_issue_detected",
    "governance_issue_accepted",
    "governance_issue_resolved",
    "ask_answered",
    "ask_refused",
    "ask_guardrail_blocked",
    "simulation_run_started",
    "simulation_run_completed",
    "value_event_recorded",
    "external_snapshot_recorded",
    "external_change_flagged",
    "regulatory_impact_simulated",
)

EVENT_GROUPS: dict[str, tuple[str, ...]] = {
    "source_lifecycle": (
        "source_uploaded",
        "source_deleted",
        "source_ingested",
        "source_approved",
        "source_rejected",
        "source_edited",
    ),
    "governance": (
        "governance_issue_detected",
        "governance_issue_accepted",
        "governance_issue_resolved",
    ),
    "assistant_usage": (
        "ask_answered",
        "ask_refused",
        "ask_guardrail_blocked",
    ),
    "simulation": (
        "simulation_run_started",
        "simulation_run_completed",
    ),
    "value": (
        "value_event_recorded",
    ),
    "external_context": (
        "external_snapshot_recorded",
        "external_change_flagged",
        "regulatory_impact_simulated",
    ),
}

ActorType = Literal["system", "operator", "persona", "agent"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AnalyticsEvent(BaseModel):
    """A single append-only analytics fact.

    Use entity fields for joins and compact metadata for chart dimensions. Do not
    store raw document text, raw prompts, generated answers, personal data or
    commercially sensitive content here.
    """

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: uuid4().hex)
    event_type: EventType
    timestamp: str = Field(default_factory=now_iso)
    actor_type: ActorType = "system"
    actor_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    source_id: str | None = None
    process_area: str | None = None
    persona: str | None = None
    outcome: str | None = None
    value_driver: str | None = None
    value_estimate: float | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def metadata_is_flat(cls, value: dict[str, MetadataValue]) -> dict[str, MetadataValue]:
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError("metadata keys must be non-empty strings")
            if item is not None and not isinstance(item, (str, int, float, bool)):
                raise ValueError("metadata values must be scalar and safe to aggregate")
        return value

    @field_validator("value_estimate")
    @classmethod
    def value_estimate_is_non_negative(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            raise ValueError("value_estimate must be non-negative")
        return value
