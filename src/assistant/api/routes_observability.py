"""Observability route — recent audit traces."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter

from ..observability.trace import AuditTrace


def build_observability_router(audit_trace: AuditTrace, dependencies: Sequence | None = None) -> APIRouter:
    router = APIRouter(prefix="/api/observability", tags=["observability"], dependencies=list(dependencies or []))

    @router.get("/traces")
    def traces(limit: int = 50) -> list[dict]:
        return audit_trace.recent(max(1, min(limit, 200)))

    return router
