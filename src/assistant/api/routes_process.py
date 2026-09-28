"""Process registry routes: list and fetch structured process records."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..process.coverage import build_operating_model_coverage, build_process_gap_overlap_report
from ..process.diagram import (
    ProcessDiagramClient,
    ProcessDiagramContext,
    ProcessDiagramResolveRequest,
    ProcessDiagramServiceError,
    ProcessDiagramServiceStatus,
    payload_for,
    process_diagram_service_status,
    resolve_process_diagram,
    start_process_diagram_service,
)
from ..process.interview_map import capture_markdown, diagram_payload
from ..process.maps import ProcessMapDraft, build_process_map, build_process_maps
from ..process.models import ProcessRecord
from ..process.registry import ProcessRegistry
from ..process.stress import build_process_stress_report
from ..sources.register import SourceRegister
from ..sources.service import UploadError, register_upload

MAX_MODEL_BYTES = 1_000_000


class InterviewMapRequest(BaseModel):
    """A process interview's working model (TIBI E5), and which of its processes to draw (default: the one in focus)."""

    process_model: dict
    process: str | None = None


class CaptureRequest(BaseModel):
    """One process of a process interview, to be saved to this space as a governed document."""

    process_model: dict
    process: str = Field(min_length=1, max_length=16)
    interview: str = Field(min_length=1, max_length=64)
    organisation: str = Field(min_length=1, max_length=60)


def _small(model: dict) -> dict:
    if len(json.dumps(model)) > MAX_MODEL_BYTES:
        raise HTTPException(status_code=413, detail="The process model is too large.")
    return model


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
        record = _record_for(process_id)
        draft = build_process_map(record)
        payload = payload_for(record, draft)
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

    @router.post("/interview-map")
    def interview_map(body: InterviewMapRequest) -> dict:
        """The live map of a process interview (TIBI E5, PI F5): its working model, drawn by the diagram service."""
        try:
            payload = diagram_payload(_small(body.process_model), body.process)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc) or "The process model cannot be drawn.") from exc
        title = payload["process_model"]["title"]
        try:
            chart = local_diagram_client.render(payload)
        except ProcessDiagramServiceError as exc:
            return {"status": "unavailable", "process_name": title,
                    "message": f"The process diagram service is not answering ({exc}). Start it from Status."}
        return {"status": "available", "process_name": title, "chart": chart}

    @router.post("/captures")
    def save_capture(body: CaptureRequest) -> dict:
        """Save one interviewed process to this space (PI F6): a readable document with its model, waiting for the
        Human's approval in Governance Review. Approved, it feeds this space's registry, ontology, EAM and maps."""
        try:
            title, text = capture_markdown(_small(body.process_model), body.process, organisation=body.organisation.strip(),
                                           interview=body.interview, captured=datetime.now().strftime("%-d %B %Y"))
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc) or "The process cannot be saved.") from exc
        filename = (re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")[:60] or "process") + ".md"
        try:
            record = register_upload(register, filename, text.encode("utf-8"), title)
        except UploadError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"source_id": record.id, "title": record.title, "approval_status": record.approval_status}

    def _record_for(process_id: str) -> ProcessRecord:
        records = process_registry.derive_from_sources(register)
        record = next((item for item in records if item.id == process_id), None)
        if record is None:
            raise HTTPException(status_code=404, detail="Process not found.")
        return record

    def _draft_for(process_id: str) -> ProcessMapDraft:
        return build_process_map(_record_for(process_id))

    return router
