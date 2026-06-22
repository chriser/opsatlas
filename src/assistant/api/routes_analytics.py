"""Analytics route — usage scorecard and knowledge gaps."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter

from ..analytics.aggregation import build_history
from ..analytics.charts import build_charts
from ..analytics.event_store import AnalyticsEventStore
from ..analytics.governance_history import build_governance_history, record_governance_snapshot
from ..analytics.knowledge_gaps import build_gap_clusters
from ..analytics.log import UsageLog, build_scorecard
from ..analytics.process_complexity import build_process_complexity
from ..governance.intelligence import KnowledgeIntelligence
from ..observability.trace import AuditTrace
from ..process.registry import ProcessRegistry
from ..sources.register import SourceRegister


def build_analytics_router(
    usage_log: UsageLog,
    audit_trace: AuditTrace | None = None,
    event_store: AnalyticsEventStore | None = None,
    intelligence: KnowledgeIntelligence | None = None,
    process_registry: ProcessRegistry | None = None,
    register: SourceRegister | None = None,
    dependencies: Sequence | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/analytics", tags=["analytics"], dependencies=list(dependencies or []))

    @router.get("/scorecard")
    def scorecard() -> dict:
        return build_scorecard(usage_log.entries())

    @router.get("/charts")
    def charts() -> dict:
        traces = audit_trace.recent(1000) if audit_trace is not None else []
        return build_charts(usage_log.entries(), traces)

    @router.get("/history")
    def history() -> dict:
        events = event_store.events() if event_store is not None else []
        traces = audit_trace.recent(1000) if audit_trace is not None else []
        return build_history(events, usage_entries=usage_log.entries(), traces=traces)

    @router.get("/governance-history")
    def governance_history() -> dict:
        events = event_store.events() if event_store is not None else []
        if event_store is not None and intelligence is not None:
            record_governance_snapshot(intelligence.run(), event_store)
            events = event_store.events()
        return build_governance_history(events)

    @router.get("/knowledge-gaps")
    def knowledge_gaps() -> dict:
        return build_gap_clusters(usage_log.entries())

    @router.get("/process-complexity")
    def process_complexity() -> dict:
        records = []
        if process_registry is not None:
            records = process_registry.build_from_sources(register) if register is not None else process_registry.list()
        return build_process_complexity(records)

    return router
