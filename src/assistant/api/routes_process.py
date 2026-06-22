"""Process registry routes: list and fetch structured process records."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException

from ..process.maps import build_process_map, build_process_maps
from ..process.registry import ProcessRegistry
from ..process.stress import build_process_stress_report
from ..sources.register import SourceRegister


def build_process_router(
    register: SourceRegister,
    process_registry: ProcessRegistry,
    dependencies: Sequence | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/process", tags=["process"], dependencies=list(dependencies or []))

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

    @router.get("/maps/{process_id}")
    def get_process_map(process_id: str) -> dict:
        records = process_registry.build_from_sources(register)
        record = next((item for item in records if item.id == process_id), None)
        if record is None:
            raise HTTPException(status_code=404, detail="Process not found.")
        return build_process_map(record).model_dump()

    return router
