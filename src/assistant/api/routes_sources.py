"""Knowledge Sources API routes (upload, list, remove)."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..analytics.event_store import AnalyticsEventStore
from ..sources.register import SourceRegister
from ..sources.service import UploadError, register_upload


def build_sources_router(
    register: SourceRegister,
    event_store: AnalyticsEventStore | None = None,
    dependencies: Sequence | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/sources", tags=["sources"], dependencies=list(dependencies or []))

    @router.get("")
    def list_sources() -> list[dict]:
        return [record.model_dump() for record in register.list()]

    @router.post("/upload")
    async def upload_source(
        file: UploadFile = File(...),
        title: str | None = Form(default=None),
    ) -> dict:
        content = await file.read()
        try:
            record = register_upload(register, file.filename or "upload", content, title)
        except UploadError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if event_store is not None:
            event_store.record(
                "source_uploaded",
                actor_type="operator",
                entity_type="source",
                entity_id=record.id,
                source_id=record.id,
                metadata={
                    "filename": record.filename,
                    "title": record.title,
                    "size_bytes": record.size_bytes,
                    "sensitivity": record.sensitivity,
                    "processing_state": record.processing_state,
                    "approval_status": record.approval_status,
                },
            )
        return record.model_dump()

    @router.delete("/{source_id}")
    def remove_source(source_id: str) -> dict:
        record = register.get(source_id)
        if record is None or not register.remove(source_id):
            raise HTTPException(status_code=404, detail="Source not found.")
        if event_store is not None:
            event_store.record(
                "source_deleted",
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
        return {"removed": source_id}

    return router
