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
    "superseded_by_source_edit",
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


class ComplianceFindingReconcileItem(BaseModel):
    finding_id: str
    source_id: str = ""
    source_title: str = ""
    classification: str = ""
    severity: str = ""
    external_source_title: str = ""
    internal_evidence_text: str = ""
    proposed_internal_text: str = ""


class ComplianceFindingReconcileRequest(BaseModel):
    findings: list[ComplianceFindingReconcileItem] = Field(default_factory=list)
    persist_superseded: bool = False


class ComplianceFindingCurrentStatus(BaseModel):
    finding_id: str
    source_id: str = ""
    source_status: str = "no_internal_evidence"
    related_key: str = ""
    related_count: int = 0
    current_source_hash: str = ""
    message: str = ""


class ComplianceFindingGroup(BaseModel):
    related_key: str
    source_id: str = ""
    finding_ids: list[str] = Field(default_factory=list)
    original_text_hash: str = ""


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
            {
                "resolved": 0,
                "fixed": 0,
                "accepted_risk": 0,
                "dismissed": 0,
                "needs_sme_review": 0,
                "superseded_by_source_edit": 0,
                "latest_resolved_at": "",
            },
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


def reconcile_current_source_status(
    *,
    request: ComplianceFindingReconcileRequest,
    read_source_text,
    existing: dict[str, ComplianceResolution] | None = None,
    persist=None,
) -> dict:
    """Compare finding evidence with current source text and optionally persist superseded findings."""

    existing = existing or {}
    statuses: dict[str, ComplianceFindingCurrentStatus] = {}
    groups = _finding_groups(request.findings)
    source_text_cache: dict[str, str] = {}
    source_hash_cache: dict[str, str] = {}
    superseded_records: list[ComplianceResolution] = []

    for item in request.findings:
        group = groups.get(_related_key(item))
        status = _current_status(item, read_source_text, source_text_cache, source_hash_cache)
        status.related_count = len(group.finding_ids) if group is not None else 0
        statuses[item.finding_id] = status

    if request.persist_superseded and persist is not None:
        for item in request.findings:
            status = statuses[item.finding_id]
            if status.source_status != "already_changed" or item.finding_id in existing:
                continue
            record = persist(
                ComplianceResolutionRequest(
                    finding_id=item.finding_id,
                    action="superseded_by_source_edit",
                    note="Original wording is no longer present in the current source after another edit.",
                    source_id=item.source_id,
                    source_title=item.source_title,
                    classification=item.classification,
                    severity=item.severity,
                    external_source_title=item.external_source_title,
                    internal_evidence_text=item.internal_evidence_text,
                    proposed_internal_text=item.proposed_internal_text,
                )
            )
            superseded_records.append(record)
            existing[item.finding_id] = record

    return {
        "by_finding": {finding_id: status.model_dump() for finding_id, status in statuses.items()},
        "groups": [group.model_dump() for group in groups.values() if len(group.finding_ids) > 1],
        "superseded_records": [record.model_dump() for record in superseded_records],
    }


def _current_status(
    item: ComplianceFindingReconcileItem,
    read_source_text,
    source_text_cache: dict[str, str],
    source_hash_cache: dict[str, str],
) -> ComplianceFindingCurrentStatus:
    if not item.internal_evidence_text.strip() or not item.source_id:
        return ComplianceFindingCurrentStatus(
            finding_id=item.finding_id,
            source_id=item.source_id,
            source_status="no_internal_evidence",
            related_key=_related_key(item),
            message="No internal wording was attached to this finding.",
        )
    if item.source_id not in source_text_cache:
        try:
            source_text = read_source_text(item.source_id)
        except FileNotFoundError:
            return ComplianceFindingCurrentStatus(
                finding_id=item.finding_id,
                source_id=item.source_id,
                source_status="source_missing",
                related_key=_related_key(item),
                message="The source is no longer available.",
            )
        source_text_cache[item.source_id] = source_text
        source_hash_cache[item.source_id] = _text_hash(source_text)
    source_text = source_text_cache[item.source_id]
    source_status = "still_present" if _contains_text(source_text, item.internal_evidence_text) else "already_changed"
    message = (
        "Original wording is still present in the current source."
        if source_status == "still_present"
        else "Original wording is no longer present in the current source."
    )
    return ComplianceFindingCurrentStatus(
        finding_id=item.finding_id,
        source_id=item.source_id,
        source_status=source_status,
        related_key=_related_key(item),
        current_source_hash=source_hash_cache[item.source_id],
        message=message,
    )


def _finding_groups(items: list[ComplianceFindingReconcileItem]) -> dict[str, ComplianceFindingGroup]:
    groups: dict[str, ComplianceFindingGroup] = {}
    for item in items:
        key = _related_key(item)
        if not key:
            continue
        group = groups.setdefault(
            key,
            ComplianceFindingGroup(
                related_key=key,
                source_id=item.source_id,
                original_text_hash=_text_hash(_normalise_text(item.internal_evidence_text)),
            ),
        )
        group.finding_ids.append(item.finding_id)
    return groups


def _related_key(item: ComplianceFindingReconcileItem) -> str:
    normalised = _normalise_text(item.internal_evidence_text)
    if not item.source_id or not normalised:
        return ""
    return f"{item.source_id}:{_text_hash(normalised)[:16]}"


def _contains_text(haystack: str, needle: str) -> bool:
    normalised_haystack = _normalise_text(haystack)
    normalised_needle = _normalise_text(needle)
    if not normalised_needle:
        return False
    return normalised_needle in normalised_haystack


def _normalise_text(value: str) -> str:
    return " ".join(value.strip().lower().split())
