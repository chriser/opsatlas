"""Regulatory candidate discovery and review routes."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..analytics.event_store import AnalyticsEventStore
from ..external.registry import PublicContentRegistry
from ..ingestion.store import SectionStore
from ..regulatory.discovery import discover_regulatory_candidates
from ..regulatory.impact import simulate_regulatory_impact
from ..regulatory.review import REVIEW_STATUSES, RegulatoryReviewStore
from ..sources.register import SourceRegister


class RegulatoryReviewRequest(BaseModel):
    status: str
    note: str = ""


def build_regulatory_router(
    register: SourceRegister,
    section_store: SectionStore,
    review_store: RegulatoryReviewStore,
    public_registry: PublicContentRegistry | None = None,
    event_store: AnalyticsEventStore | None = None,
    dependencies: Sequence | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/regulatory", tags=["regulatory"], dependencies=list(dependencies or []))

    @router.get("/candidates")
    def candidates() -> dict:
        return discover_regulatory_candidates(register, section_store, review_store, public_registry)

    @router.post("/candidates/{candidate_id}/review")
    def review_candidate(candidate_id: str, review: RegulatoryReviewRequest) -> dict:
        if review.status not in REVIEW_STATUSES or review.status == "unreviewed":
            allowed = ", ".join(status for status in REVIEW_STATUSES if status != "unreviewed")
            raise HTTPException(status_code=400, detail=f"Status must be one of: {allowed}.")
        saved = review_store.set(candidate_id, review.status, note=review.note)
        return saved.model_dump()

    @router.post("/candidates/{candidate_id}/impact-simulation")
    def impact_simulation(candidate_id: str) -> dict:
        try:
            simulation = simulate_regulatory_impact(register, section_store, review_store, public_registry, candidate_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if event_store is not None:
            event_store.record(
                "regulatory_impact_simulated",
                actor_type="operator",
                entity_type="regulatory_candidate",
                entity_id=simulation.candidate_id,
                source_id=simulation.source_id,
                process_area="; ".join(simulation.affected_process_areas[:3]),
                outcome="simulated",
                metadata={
                    "theme": simulation.theme,
                    "label": simulation.label,
                    "impact_score": simulation.impact_score,
                    "impact_band": simulation.impact_band,
                    "affected_source_count": simulation.affected_source_count,
                    "external_context_count": simulation.external_context_count,
                },
            )
        return simulation.model_dump()

    return router
