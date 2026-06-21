"""Governance routes: knowledge-intelligence overview and the approval gate."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException

from ..governance.intelligence import KnowledgeIntelligence
from ..sources.register import SourceRegister


def build_governance_router(
    register: SourceRegister,
    intelligence: KnowledgeIntelligence,
    dependencies: Sequence | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/governance", tags=["governance"], dependencies=list(dependencies or []))

    @router.get("/intelligence")
    def overview() -> dict:
        return intelligence.run()

    @router.post("/sources/{source_id}/approve")
    def approve(source_id: str) -> dict:
        return _set_status(register, source_id, "approved")

    @router.post("/sources/{source_id}/reject")
    def reject(source_id: str) -> dict:
        return _set_status(register, source_id, "rejected")

    return router


def _set_status(register: SourceRegister, source_id: str, status: str) -> dict:
    record = register.update(source_id, approval_status=status)
    if record is None:
        raise HTTPException(status_code=404, detail="Source not found.")
    return record.model_dump()
