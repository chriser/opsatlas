"""Analytics route — usage scorecard and knowledge gaps."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import PlainTextResponse

from ..analytics.aggregation import build_history
from ..analytics.charts import build_charts
from ..analytics.event_store import AnalyticsEventStore
from ..analytics.governance_history import build_governance_history, record_governance_snapshot
from ..analytics.knowledge_gaps import build_gap_clusters
from ..analytics.log import UsageLog, build_scorecard
from ..analytics.pdf_report import build_analytics_report_pdf
from ..analytics.process_complexity import build_process_complexity
from ..analytics.report import build_analytics_report
from ..evidence.validation import build_validation_evidence_report
from ..governance.intelligence import KnowledgeIntelligence
from ..observability.trace import AuditTrace
from ..ontology import OntologyStore
from ..process.registry import ProcessRegistry
from ..sources.register import SourceRegister
from ..value.ledger import ValueEventInput, build_value_report


def build_analytics_router(
    usage_log: UsageLog,
    audit_trace: AuditTrace | None = None,
    event_store: AnalyticsEventStore | None = None,
    intelligence: KnowledgeIntelligence | None = None,
    process_registry: ProcessRegistry | None = None,
    register: SourceRegister | None = None,
    ontology_store: OntologyStore | None = None,
    dependencies: Sequence | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/analytics", tags=["analytics"], dependencies=list(dependencies or []))

    @router.get("/scorecard")
    def scorecard() -> dict:
        return build_scorecard(usage_log.entries())

    @router.get("/charts")
    def charts() -> dict:
        traces = audit_trace.recent(1000) if audit_trace is not None else []
        events = event_store.events() if event_store is not None else []
        return build_charts(usage_log.entries(), traces, events=events)

    @router.get("/history")
    def history() -> dict:
        events = event_store.events() if event_store is not None else []
        traces = audit_trace.recent(1000) if audit_trace is not None else []
        return build_history(events, usage_entries=usage_log.entries(), traces=traces)

    @router.get("/governance-history")
    def governance_history() -> dict:
        # Read-only: returns previously captured snapshots. Capturing a new snapshot
        # is an explicit POST (it runs the heavy intelligence scan and writes an event),
        # so refreshing the dashboard never mutates state or incurs that cost.
        events = event_store.events() if event_store is not None else []
        return build_governance_history(events)

    @router.post("/governance-history/snapshot")
    def capture_governance_snapshot() -> dict:
        if event_store is None or intelligence is None:
            raise HTTPException(status_code=503, detail="Governance snapshots are not configured.")
        record_governance_snapshot(intelligence.run(), event_store)
        return build_governance_history(event_store.events())

    @router.get("/knowledge-gaps")
    def knowledge_gaps() -> dict:
        return build_gap_clusters(usage_log.entries())

    @router.get("/process-complexity")
    def process_complexity() -> dict:
        records = []
        if process_registry is not None:
            records = process_registry.derive_from_sources(register) if register is not None else process_registry.list()
        return build_process_complexity(records)

    @router.get("/ontology-stats")
    def ontology_stats() -> dict:
        if ontology_store is None:
            raise HTTPException(status_code=503, detail="Ontology stats are not configured.")
        return ontology_store.counts()

    @router.get("/value")
    def value_report() -> dict:
        events = event_store.events() if event_store is not None else []
        return build_value_report(events).model_dump()

    @router.get("/validation-evidence")
    def validation_evidence() -> dict:
        return build_validation_evidence_report().model_dump()

    @router.get("/report.md", response_class=PlainTextResponse)
    def analytics_report() -> PlainTextResponse:
        report = _build_report_markdown()
        return PlainTextResponse(
            report,
            media_type="text/markdown",
            headers={"Content-Disposition": 'attachment; filename="analytics-evidence-report.md"'},
        )

    @router.get("/report.pdf")
    def analytics_report_pdf() -> Response:
        report = _build_report_markdown()
        return Response(
            build_analytics_report_pdf(report),
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="analytics-evidence-report.pdf"'},
        )

    def _build_report_markdown() -> str:
        events = event_store.events() if event_store is not None else []
        traces = audit_trace.recent(1000) if audit_trace is not None else []
        records = []
        if process_registry is not None:
            records = process_registry.derive_from_sources(register) if register is not None else process_registry.list()
        return build_analytics_report(
            scorecard=build_scorecard(usage_log.entries()),
            history=build_history(events, usage_entries=usage_log.entries(), traces=traces),
            governance=build_governance_history(events),
            gaps=build_gap_clusters(usage_log.entries()),
            complexity=build_process_complexity(records),
            value=build_value_report(events).model_dump(),
            validation=build_validation_evidence_report().model_dump(),
        )

    @router.post("/value/events")
    def record_value_event(payload: ValueEventInput) -> dict:
        if event_store is None:
            raise HTTPException(status_code=503, detail="Value event ledger is not configured.")
        event_store.record(
            "value_event_recorded",
            actor_type="operator",
            entity_type="value_event",
            entity_id=f"value-{uuid4().hex}",
            process_area=payload.process_area.strip() or None,
            outcome="recorded",
            value_driver=payload.value_driver.strip(),
            value_estimate=payload.value_estimate,
            metadata={
                "label": payload.label.strip(),
                "scenario_id": payload.scenario_id.strip(),
                "unit": payload.unit.strip() or "GBP",
                "confidence": payload.confidence.strip() or "review",
                "evidence_type": payload.evidence_type.strip() or "operator_estimate",
            },
        )
        return build_value_report(event_store.events()).model_dump()

    return router
