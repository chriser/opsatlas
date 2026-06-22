"""Ingestion routes: build sections for a registered source and view them."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException

from ..analytics.event_store import AnalyticsEventStore
from ..ingestion.service import NotIngestableError, ingest_source
from ..ingestion.store import SectionStore
from ..sources.register import SourceRegister


def build_ingestion_router(
    register: SourceRegister,
    section_store: SectionStore,
    event_store: AnalyticsEventStore | None = None,
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
        if event_store is not None:
            event_store.record(
                "source_ingested",
                actor_type="operator",
                entity_type="source",
                entity_id=record.id,
                source_id=record.id,
                metadata={
                    "title": record.title,
                    "section_count": record.section_count,
                    "processing_state": record.processing_state,
                    "approval_status": record.approval_status,
                },
            )
        return record.model_dump()

    @router.get("/{source_id}/sections")
    def list_sections(source_id: str) -> list[dict]:
        if register.get(source_id) is None:
            raise HTTPException(status_code=404, detail="Source not found.")
        return [section.model_dump() for section in section_store.list_for_source(source_id)]

    return router
