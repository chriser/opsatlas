"""Governance routes: knowledge-intelligence overview and the approval gate."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..governance.intelligence import KnowledgeIntelligence
from ..ingestion.service import ingest_source
from ..ingestion.store import SectionStore
from ..sources.register import SourceRegister


class DocumentEdit(BaseModel):
    text: str


def build_governance_router(
    register: SourceRegister,
    intelligence: KnowledgeIntelligence,
    section_store: SectionStore | None = None,
    dependencies: Sequence | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/governance", tags=["governance"], dependencies=list(dependencies or []))

    @router.get("/intelligence")
    def overview() -> dict:
        return intelligence.run()

    @router.get("/sources/{source_id}/document")
    def get_document(source_id: str) -> dict:
        record = register.get(source_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Source not found.")
        return {"id": record.id, "title": record.title, "text": register.read_content(source_id).decode("utf-8", "replace")}

    @router.put("/sources/{source_id}/document")
    def save_document(source_id: str, edit: DocumentEdit) -> dict:
        record = register.get(source_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Source not found.")
        if section_store is None:
            raise HTTPException(status_code=500, detail="Editing is not available.")
        register.write_content(source_id, edit.text.encode("utf-8"))
        updated = ingest_source(register, section_store, source_id)  # rebuild sections from edited content
        return {"id": updated.id, "title": updated.title, "section_count": updated.section_count}

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
