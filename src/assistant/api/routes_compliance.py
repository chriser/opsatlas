"""Feature-flagged routes for the standalone compliance reasoning service."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..analytics.event_store import AnalyticsEventStore
from ..compliance.client import ComplianceReasoningClient, ComplianceReasoningUnavailable
from ..compliance.payload import build_compliance_review_payload
from ..compliance.resolution import ComplianceResolutionRequest, ComplianceResolutionStore, source_resolution_summary
from ..external.registry import PublicContentRegistry
from ..ingestion.store import SectionStore
from ..sources.register import SourceRegister


class ComplianceReviewOptions(BaseModel):
    include_supported_findings: bool = True
    include_unsupported_internal_claims: bool = False
    include_missing_obligations: bool = False
    include_not_related_pairs: bool = False
    min_alignment_score: float = 0.18
    min_pair_relevance_score: float = 0.12
    min_contradiction_alignment_score: float = 0.3
    max_findings: int = 50
    force_rerun: bool = False


def build_compliance_reasoning_router(
    register: SourceRegister,
    section_store: SectionStore,
    public_registry: PublicContentRegistry,
    client: ComplianceReasoningClient,
    event_store: AnalyticsEventStore | None = None,
    dependencies: Sequence | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/compliance-reasoning", tags=["compliance-reasoning"], dependencies=list(dependencies or []))
    resolution_store = ComplianceResolutionStore(register.base_dir)

    @router.get("/status")
    def status() -> dict:
        if not client.enabled:
            return {"enabled": False, "service": "compliance-reasoning", "status": "not_configured"}
        try:
            health = client.health()
        except ComplianceReasoningUnavailable as exc:
            return {"enabled": True, "service": "compliance-reasoning", "status": "unavailable", "detail": str(exc)}
        return {"enabled": True, "service": "compliance-reasoning", "status": "available", "health": health}

    @router.get("/capabilities")
    def capabilities() -> dict:
        if not client.enabled:
            raise HTTPException(status_code=503, detail="Compliance reasoning service is not configured.")
        try:
            return client.capabilities()
        except ComplianceReasoningUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @router.post("/reviews")
    def create_review(options: ComplianceReviewOptions | None = None) -> dict:
        if not client.enabled:
            raise HTTPException(status_code=503, detail="Compliance reasoning service is not configured.")
        payload = build_compliance_review_payload(
            register,
            section_store,
            public_registry,
            options=(options or ComplianceReviewOptions()).model_dump(),
        )
        try:
            result = client.create_review(payload)
        except ComplianceReasoningUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if event_store is not None:
            event_store.record(
                "compliance_reasoning_review_requested",
                actor_type="operator",
                entity_type="compliance_review",
                entity_id=result.get("status", {}).get("job_id", ""),
                outcome=result.get("status", {}).get("status", "unknown"),
                metadata={
                    "external_documents": len(payload["external_documents"]),
                    "internal_documents": len(payload["internal_documents"]),
                    "finding_count": result.get("status", {}).get("finding_count", 0),
                },
            )
        return result

    @router.get("/resolutions")
    def resolutions() -> dict:
        records = resolution_store.all()
        return {
            "records": [record.model_dump() for record in records],
            "by_finding": {finding_id: record.model_dump() for finding_id, record in resolution_store.latest_by_finding().items()},
            "source_summary": source_resolution_summary(records),
            "actions": [
                "acknowledged_supported",
                "fixed",
                "accepted_risk",
                "dismissed",
                "needs_sme_review",
            ],
        }

    @router.post("/resolutions")
    def save_resolution(request: ComplianceResolutionRequest) -> dict:
        try:
            record = resolution_store.set(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if event_store is not None:
            event_store.record(
                "compliance_finding_resolved",
                actor_type="operator",
                entity_type="compliance_finding",
                entity_id=request.finding_id,
                source_id=request.source_id or None,
                outcome=request.action,
                metadata={
                    "classification": request.classification,
                    "severity": request.severity,
                    "external_source_title": request.external_source_title,
                },
            )
        return record.model_dump()

    @router.get("/reviews/{job_id}")
    def review_status(job_id: str) -> dict:
        if not client.enabled:
            raise HTTPException(status_code=503, detail="Compliance reasoning service is not configured.")
        try:
            return client.review_status(job_id)
        except ComplianceReasoningUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @router.get("/reviews/{job_id}/findings")
    def review_findings(job_id: str) -> dict:
        if not client.enabled:
            raise HTTPException(status_code=503, detail="Compliance reasoning service is not configured.")
        try:
            return client.review_findings(job_id)
        except ComplianceReasoningUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    return router
