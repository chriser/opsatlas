"""Analytics route — usage scorecard and knowledge gaps."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter

from ..analytics.charts import build_charts
from ..analytics.log import UsageLog, build_scorecard
from ..observability.trace import AuditTrace


def build_analytics_router(usage_log: UsageLog, audit_trace: AuditTrace | None = None, dependencies: Sequence | None = None) -> APIRouter:
    router = APIRouter(prefix="/api/analytics", tags=["analytics"], dependencies=list(dependencies or []))

    @router.get("/scorecard")
    def scorecard() -> dict:
        return build_scorecard(usage_log.entries())

    @router.get("/charts")
    def charts() -> dict:
        traces = audit_trace.recent(1000) if audit_trace is not None else []
        return build_charts(usage_log.entries(), traces)

    return router
