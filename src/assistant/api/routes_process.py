"""Process registry routes: list and fetch structured process records."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException

from ..process.coverage import build_operating_model_coverage, build_process_gap_overlap_report
from ..process.diagram import (
    ProcessDiagramClient,
    ProcessDiagramContext,
    ProcessDiagramResolveRequest,
    ProcessDiagramServiceError,
    ProcessDiagramServiceStatus,
    build_diagram_payload,
    process_diagram_service_status,
    resolve_process_diagram,
    start_process_diagram_service,
)
from ..process.maps import ProcessMapDraft, build_process_map, build_process_maps
from ..process.registry import ProcessRegistry
from ..process.stress import build_process_stress_report
from ..sources.register import SourceRegister


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
        return [r.model_dump() for r in process_registry.derive_from_sources(register)]

    @router.get("/registry/{process_id}")
    def get_process(process_id: str) -> dict:
        record = process_registry.get(process_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Process not found.")
        return record.model_dump()

    @router.get("/maps")
    def list_process_maps() -> list[dict]:
        records = process_registry.derive_from_sources(register)
        return [draft.model_dump() for draft in build_process_maps(records)]

    @router.get("/stress-test")
    def stress_test() -> dict:
        records = process_registry.derive_from_sources(register)
        return build_process_stress_report(records).model_dump()

    @router.get("/coverage-map")
    def coverage_map() -> dict:
        records = process_registry.derive_from_sources(register)
        return build_operating_model_coverage(records).model_dump()

    @router.get("/gap-overlap")
    def gap_overlap() -> dict:
        records = process_registry.derive_from_sources(register)
        return build_process_gap_overlap_report(records).model_dump()

    @router.get("/maps/{process_id}")
    def get_process_map(process_id: str) -> dict:
        return _draft_for(process_id).model_dump()

    @router.post("/diagrams/resolve", response_model=ProcessDiagramContext)
    def resolve_diagram(body: ProcessDiagramResolveRequest) -> ProcessDiagramContext:
        records = process_registry.derive_from_sources(register)
        return resolve_process_diagram(body, records, local_diagram_client)

    @router.get("/diagrams/service/status", response_model=ProcessDiagramServiceStatus)
    def diagram_service_status() -> ProcessDiagramServiceStatus:
        return process_diagram_service_status()

    @router.post("/diagrams/service/start", response_model=ProcessDiagramServiceStatus)
    def start_diagram_service() -> ProcessDiagramServiceStatus:
        return start_process_diagram_service()

    @router.get("/diagrams/{process_id}", response_model=ProcessDiagramContext)
    def get_process_diagram(process_id: str) -> ProcessDiagramContext:
        draft = _draft_for(process_id)
        payload = build_diagram_payload(draft)
        try:
            chart = local_diagram_client.render(payload)
            svg = local_diagram_client.render_svg(payload)
        except ProcessDiagramServiceError as exc:
            return ProcessDiagramContext(
                status="unavailable",
                message=f"Local process diagram unavailable: {exc}",
                process_id=draft.process_id,
                process_name=draft.name,
                source_title=draft.source_title,
                service_url=local_diagram_client.base_url,
            )
        return ProcessDiagramContext(
            status="available",
            message="Process diagram rendered by the local diagram service.",
            process_id=draft.process_id,
            process_name=draft.name,
            source_title=draft.source_title,
            service_url=local_diagram_client.base_url,
            chart=chart,
            svg=svg,
        )

    def _draft_for(process_id: str) -> ProcessMapDraft:
        records = process_registry.derive_from_sources(register)
        record = next((item for item in records if item.id == process_id), None)
        if record is None:
            raise HTTPException(status_code=404, detail="Process not found.")
        return build_process_map(record)

    return router
