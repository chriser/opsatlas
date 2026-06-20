"""Knowledge Sources API routes (upload, list, remove)."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..sources.register import SourceRegister
from ..sources.service import UploadError, register_upload


def build_sources_router(register: SourceRegister) -> APIRouter:
    router = APIRouter(prefix="/api/sources", tags=["sources"])

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
        return record.model_dump()

    @router.delete("/{source_id}")
    def remove_source(source_id: str) -> dict:
        if not register.remove(source_id):
            raise HTTPException(status_code=404, detail="Source not found.")
        return {"removed": source_id}

    return router
