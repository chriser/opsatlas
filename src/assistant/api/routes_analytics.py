"""Analytics route — usage scorecard and knowledge gaps."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter

from ..analytics.log import UsageLog, build_scorecard


def build_analytics_router(usage_log: UsageLog, dependencies: Sequence | None = None) -> APIRouter:
    router = APIRouter(prefix="/api/analytics", tags=["analytics"], dependencies=list(dependencies or []))

    @router.get("/scorecard")
    def scorecard() -> dict:
        return build_scorecard(usage_log.entries())

    return router
