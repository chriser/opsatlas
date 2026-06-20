"""Ingestion routes: build sections for a registered source and view them."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException

from ..ingestion.service import NotIngestableError, ingest_source
from ..ingestion.store import SectionStore
from ..sources.register import SourceRegister


def build_ingestion_router(
    register: SourceRegister,
    section_store: SectionStore,
    dependencies: Sequence | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/sources", tags=["ingestion"], dependencies=list(dependencies or []))

    @router.post("/{source_id}/ingest")
    def ingest(source_id: str) -> dict:
        if register.get(source_id) is None:
            raise HTTPException(status_code=404, detail="Source not found.")
        try:
            record = ingest_source(register, section_store, source_id)
        except NotIngestableError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return record.model_dump()

    @router.get("/{source_id}/sections")
    def list_sections(source_id: str) -> list[dict]:
        if register.get(source_id) is None:
            raise HTTPException(status_code=404, detail="Source not found.")
        return [section.model_dump() for section in section_store.list_for_source(source_id)]

    return router
