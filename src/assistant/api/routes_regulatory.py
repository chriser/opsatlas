"""Regulatory candidate discovery and review routes."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..external.registry import PublicContentRegistry
from ..ingestion.store import SectionStore
from ..regulatory.discovery import discover_regulatory_candidates
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

    return router
