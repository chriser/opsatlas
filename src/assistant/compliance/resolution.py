"""Human resolution records for compliance reasoning findings."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

RESOLUTION_ACTIONS = {
    "acknowledged_supported",
    "fixed",
    "accepted_risk",
    "dismissed",
    "needs_sme_review",
}


class ComplianceResolution(BaseModel):
    finding_id: str
    action: str
    note: str = ""
    source_id: str = ""
    source_title: str = ""
    classification: str = ""
    severity: str = ""
    external_source_title: str = ""
    internal_evidence_hash: str = ""
    proposed_text_hash: str = ""
    resolved_at: str = ""


class ComplianceResolutionRequest(BaseModel):
    finding_id: str
    action: str
    note: str = ""
    source_id: str = ""
    source_title: str = ""
    classification: str = ""
    severity: str = ""
    external_source_title: str = ""
    internal_evidence_text: str = Field(default="", exclude=True)
    proposed_internal_text: str = Field(default="", exclude=True)


class ComplianceResolutionStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.path = Path(base_dir) / "compliance_resolutions.json"
        self._lock = threading.Lock()

    def all(self) -> list[ComplianceResolution]:
        return [ComplianceResolution(**row) for row in self._read()]

    def latest_by_finding(self) -> dict[str, ComplianceResolution]:
        out: dict[str, ComplianceResolution] = {}
        for record in self.all():
            out[record.finding_id] = record
        return out

    def set(self, request: ComplianceResolutionRequest) -> ComplianceResolution:
        if request.action not in RESOLUTION_ACTIONS:
            allowed = ", ".join(sorted(RESOLUTION_ACTIONS))
            raise ValueError(f"Unsupported compliance resolution action '{request.action}'. Allowed: {allowed}.")
        record = ComplianceResolution(
            finding_id=request.finding_id,
            action=request.action,
            note=request.note,
            source_id=request.source_id,
            source_title=request.source_title,
            classification=request.classification,
            severity=request.severity,
            external_source_title=request.external_source_title,
            internal_evidence_hash=_text_hash(request.internal_evidence_text),
            proposed_text_hash=_text_hash(request.proposed_internal_text),
            resolved_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            rows = [row for row in self._read() if row.get("finding_id") != request.finding_id]
            rows.append(record.model_dump())
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(rows[-500:], indent=2), encoding="utf-8")
        return record

    def _read(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            rows = json.loads(self.path.read_text(encoding="utf-8") or "[]")
        except (OSError, json.JSONDecodeError):
            return []
        return rows if isinstance(rows, list) else []


def source_resolution_summary(records: list[ComplianceResolution]) -> dict[str, dict]:
    summary: dict[str, dict] = {}
    for record in records:
        if not record.source_id:
            continue
        row = summary.setdefault(
            record.source_id,
            {"resolved": 0, "fixed": 0, "accepted_risk": 0, "dismissed": 0, "needs_sme_review": 0, "latest_resolved_at": ""},
        )
        row["resolved"] += 1
        if record.action in row:
            row[record.action] += 1
        if record.resolved_at > row["latest_resolved_at"]:
            row["latest_resolved_at"] = record.resolved_at
    return summary


def _text_hash(value: str) -> str:
    if not value:
        return ""
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()
