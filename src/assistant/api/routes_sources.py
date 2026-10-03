"""Knowledge Sources API routes (upload, list, remove)."""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Sequence

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..analytics.event_store import AnalyticsEventStore
from ..iam.context import acting_id
from ..iam.visibility import visible
from ..sources.register import SourceRegister
from ..sources.service import UploadError, register_upload
from ..storage import locked


def build_sources_router(
    register: SourceRegister,
    event_store: AnalyticsEventStore | None = None,
    dependencies: Sequence | None = None,
    ontology_rebuilder: Callable[[], object] | None = None,
    section_store=None,
    forget_content: Callable[[str, bytes], object] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/sources", tags=["sources"], dependencies=list(dependencies or []))

    @router.get("")
    def list_sources() -> list[dict]:
        return [record.model_dump() for record in register.list() if visible(record.id)]  # REF S13

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
        if record is None:
            raise HTTPException(status_code=404, detail="Source not found.")
        try:
            last_text = register.read_content(source_id)
        except OSError:
            last_text = b""
        # One at a time with a publish's swap (REF S23): a delete never leaves a staged version behind.
        index = getattr(register, "index_file", None)
        with locked(index) if index is not None else contextlib.nullcontext():
            if not register.remove(source_id):
                raise HTTPException(status_code=404, detail="Source not found.")
            # Deletion removes everything the source left (REF S4, the Human's decision of 2 October 2026): its
            # sections, and its drafts, versions, comments, activity and images no other document uses.
            if section_store is not None:
                section_store.remove_for_source(source_id)
        if forget_content is not None:
            forget_content(source_id, last_text)
        if event_store is not None:
            # The record of the deletion: who deleted which id, its version and hash, and when; never its text.
            event_store.record(
                "source_deleted",
                actor_type="operator",
                actor_id=acting_id("system"),
                entity_type="source",
                entity_id=record.id,
                source_id=record.id,
                metadata={"version": record.version, "content_sha256": record.content_sha256,
                          "approval_status": record.approval_status},
            )
        if ontology_rebuilder is not None:
            ontology_rebuilder()  # its facts leave the map with it (ARCH F2)
        return {"removed": source_id}

    return router
