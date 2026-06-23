"""Process registry routes: list and fetch structured process records."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from ..process.coverage import build_operating_model_coverage
from ..process.diagram import (
    ProcessDiagramClient,
    ProcessDiagramContext,
    ProcessDiagramResolveRequest,
    resolve_process_diagram,
)
from ..process.lucid import (
    LUCID_IMPORT_CONTENT_TYPE,
    LucidCreateError,
    build_lucid_archive,
    create_lucid_document,
    lucid_settings_from_env,
    safe_lucid_filename,
)
from ..process.maps import ProcessMapDraft, build_process_map, build_process_maps
from ..process.registry import ProcessRegistry
from ..process.stress import build_process_stress_report
from ..sources.register import SourceRegister


class LucidConfigResponse(BaseModel):
    provider: str = "lucidchart"
    configured: bool
    missing: list[str]
    product: str
    api_key_hint: str = ""
    parent_folder_id_hint: str = ""


class LucidCreateResponse(BaseModel):
    provider: str = "lucidchart"
    document_id: str = ""
    edit_url: str = ""
    view_url: str = ""
    raw: dict = Field(default_factory=dict)


def build_process_router(
    register: SourceRegister,
    process_registry: ProcessRegistry,
    diagram_client: ProcessDiagramClient | None = None,
    dependencies: Sequence | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/process", tags=["process"], dependencies=list(dependencies or []))
    local_diagram_client = diagram_client or ProcessDiagramClient.from_env()

    @router.get("/registry")
    def list_processes() -> list[dict]:
        # Rebuild from current approved sources so the registry always reflects edits.
        return [r.model_dump() for r in process_registry.build_from_sources(register)]

    @router.get("/registry/{process_id}")
    def get_process(process_id: str) -> dict:
        record = process_registry.get(process_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Process not found.")
        return record.model_dump()

    @router.get("/maps")
    def list_process_maps() -> list[dict]:
        records = process_registry.build_from_sources(register)
        return [draft.model_dump() for draft in build_process_maps(records)]

    @router.get("/stress-test")
    def stress_test() -> dict:
        records = process_registry.build_from_sources(register)
        return build_process_stress_report(records).model_dump()

    @router.get("/coverage-map")
    def coverage_map() -> dict:
        records = process_registry.build_from_sources(register)
        return build_operating_model_coverage(records).model_dump()

    @router.get("/maps/{process_id}")
    def get_process_map(process_id: str) -> dict:
        return _draft_for(process_id).model_dump()

    @router.post("/diagrams/resolve", response_model=ProcessDiagramContext)
    def resolve_diagram(body: ProcessDiagramResolveRequest) -> ProcessDiagramContext:
        records = process_registry.build_from_sources(register)
        return resolve_process_diagram(body, records, local_diagram_client)

    @router.get("/lucid/config", response_model=LucidConfigResponse)
    def lucid_config() -> LucidConfigResponse:
        settings = lucid_settings_from_env()
        missing = settings.missing
        return LucidConfigResponse(
            configured=not missing,
            missing=missing,
            product=settings.product,
            api_key_hint=_hint(settings.api_key),
            parent_folder_id_hint=_hint(settings.parent_folder_id),
        )

    @router.get("/maps/{process_id}/lucid-import")
    def get_lucid_import(process_id: str) -> Response:
        draft = _draft_for(process_id)
        filename = safe_lucid_filename(draft)
        return Response(
            content=build_lucid_archive(draft),
            media_type=LUCID_IMPORT_CONTENT_TYPE,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.post("/maps/{process_id}/lucid", response_model=LucidCreateResponse)
    def create_lucid(process_id: str) -> LucidCreateResponse:
        draft = _draft_for(process_id)
        settings = lucid_settings_from_env()
        if settings.missing:
            raise HTTPException(status_code=503, detail=f"Missing Lucid configuration: {', '.join(settings.missing)}")
        try:
            result = create_lucid_document(draft, settings)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except LucidCreateError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return LucidCreateResponse(**result)

    def _draft_for(process_id: str) -> ProcessMapDraft:
        records = process_registry.build_from_sources(register)
        record = next((item for item in records if item.id == process_id), None)
        if record is None:
            raise HTTPException(status_code=404, detail="Process not found.")
        return build_process_map(record)

    return router


def _hint(value: str) -> str:
    return f"{value[:6]}..." if value else ""
