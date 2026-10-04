"""Analytics route — usage scorecard and knowledge gaps."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse, StreamingResponse

from ..analytics.aggregation import build_history
from ..analytics.charts import build_charts
from ..analytics.event_store import AnalyticsEventStore
from ..analytics.explain import build_computation_traces, find_computation_trace
from ..analytics.export import (
    AnalyticsExportContext,
    available_dataset_names,
    build_data_dictionary,
    build_export_dataset,
    build_reproducibility_bundle,
    data_dictionary_markdown,
    export_csv,
    export_index,
)
from ..analytics.forecast import forecast_series
from ..analytics.governance_history import build_governance_history, record_governance_snapshot
from ..analytics.improvement import (
    ImprovementActionCreate,
    ImprovementActionStore,
    ImprovementActionTransition,
    build_improvement_loop_metrics,
)
from ..analytics.knowledge_gaps import build_gap_clusters
from ..analytics.log import UsageLog, build_scorecard
from ..analytics.methods import build_methods_catalogue
from ..analytics.oag_benchmark import build_oag_benchmark_report
from ..analytics.oag_operations import build_oag_operations_report
from ..analytics.pdf_report import build_analytics_report_pdf
from ..analytics.process_complexity import build_process_complexity
from ..analytics.recurring import build_recurring_questions
from ..analytics.report import build_analytics_report
from ..analytics.retrieval_health import build_retrieval_health
from ..analytics.statistics import analyse_points, build_series_statistics
from ..analytics.timeseries import build_time_series
from ..evidence.validation import build_validation_evidence_report
from ..governance.intelligence import KnowledgeIntelligence
from ..observability.trace import AuditTrace
from ..ontology import OntologyStore
from ..ontology.actions import ActionContext, ActionsEngine, acting_person
from ..process.registry import ProcessRegistry
from ..sources.register import SourceRegister
from .access import derived_guard, need

# Views, exports and reports that name documents or processes are built from every approved document of the space, so,
# like the facts map, they are withheld from a person some of those documents are hidden from (REF S13, S16). Counts,
# rates and the usage log are not: the planted-sentence sweep (tests/test_leak_sweep.py) finds no document in them.
NAMED = [Depends(derived_guard)]
NAMED_DATASETS = {"events", "process_complexity"}


def build_analytics_router(
    usage_log: UsageLog,
    audit_trace: AuditTrace | None = None,
    event_store: AnalyticsEventStore | None = None,
    intelligence: KnowledgeIntelligence | None = None,
    process_registry: ProcessRegistry | None = None,
    register: SourceRegister | None = None,
    ontology_store: OntologyStore | None = None,
    actions: ActionsEngine | None = None,
    dependencies: Sequence | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/analytics", tags=["analytics"], dependencies=list(dependencies or []))
    improvement_store = ImprovementActionStore(register.base_dir) if register is not None else None

    def _capture_governance_snapshot_action(context: ActionContext) -> dict:
        if intelligence is None:
            raise RuntimeError("Governance snapshots are not configured.")
        return {"governance_report": intelligence.run()}

    def _create_improvement_action(context: ActionContext) -> dict:
        if improvement_store is None:
            raise RuntimeError("Improvement actions are not configured.")
        payload = ImprovementActionCreate.model_validate(context.params)
        action = improvement_store.create(payload)
        return {
            "action": action.model_dump(),
            "analytics_event": {
                "event_type": "improvement_action_created",
                "actor_type": context.actor.type,
                "entity_type": "improvement_action",
                "entity_id": action.id,
                "outcome": "created",
                "metadata": {
                    "trigger_type": action.trigger_type,
                    "trigger_ref": action.trigger_ref,
                    "owner_role": action.owner_role,
                    "review_cadence": action.review_cadence,
                    "status": action.status,
                },
            },
        }

    def _transition_improvement_action(context: ActionContext) -> dict:
        if improvement_store is None:
            raise RuntimeError("Improvement actions are not configured.")
        payload = ImprovementActionTransition.model_validate({
            "status": context.params["status"],
            "linked_source_id": context.params.get("linked_source_id") or "",
            "note": context.params.get("note") or "",
        })
        action = improvement_store.transition(context.params["action_id"], payload)
        return {
            "action": action.model_dump(),
            "analytics_event": {
                "event_type": "improvement_action_transitioned",
                "actor_type": context.actor.type,
                "entity_type": "improvement_action",
                "entity_id": action.id,
                "outcome": action.status,
                "metadata": {
                    "trigger_type": action.trigger_type,
                    "trigger_ref": action.trigger_ref,
                    "linked_source_id": action.linked_source_id,
                    "status": action.status,
                },
            },
        }

    if actions is not None and event_store is not None and intelligence is not None:
        actions.register_handler("capture_governance_snapshot", _capture_governance_snapshot_action)
    if actions is not None and improvement_store is not None:
        actions.register_handler("create_improvement_action", _create_improvement_action)
        actions.register_handler("transition_improvement_action", _transition_improvement_action)

    @router.get("/scorecard")
    def scorecard() -> dict:
        return build_scorecard(usage_log.entries())

    @router.get("/charts", dependencies=NAMED)
    def charts() -> dict:
        traces = audit_trace.recent(1000) if audit_trace is not None else []
        events = event_store.events() if event_store is not None else []
        return build_charts(usage_log.entries(), traces, events=events)

    @router.get("/history", dependencies=NAMED)
    def history() -> dict:
        events = event_store.events() if event_store is not None else []
        traces = audit_trace.recent(1000) if audit_trace is not None else []
        return build_history(events, usage_entries=usage_log.entries(), traces=traces)

    @router.get("/timeseries")
    def time_series(bucket: str = Query(default="daily", pattern="^(daily|weekly)$")) -> dict:
        events = event_store.events() if event_store is not None else []
        bucket_value = "weekly" if bucket == "weekly" else "daily"
        return build_time_series(usage_log.entries(), events, bucket=bucket_value)

    @router.get("/timeseries/stats")
    def time_series_stats(bucket: str = Query(default="daily", pattern="^(daily|weekly)$")) -> dict:
        events = event_store.events() if event_store is not None else []
        bucket_value = "weekly" if bucket == "weekly" else "daily"
        return build_series_statistics(build_time_series(usage_log.entries(), events, bucket=bucket_value))

    @router.get("/forecast/{series_id}")
    def analytics_forecast(
        series_id: str,
        bucket: str = Query(default="daily", pattern="^(daily|weekly)$"),
        horizon: int = Query(default=7, ge=1, le=30),
    ) -> dict:
        events = event_store.events() if event_store is not None else []
        bucket_value = "weekly" if bucket == "weekly" else "daily"
        time_series = build_time_series(usage_log.entries(), events, bucket=bucket_value)
        series = time_series["series"].get(series_id)
        if series is None:
            raise HTTPException(status_code=404, detail=f"Unknown analytics series: {series_id}")
        season_length = 7 if bucket_value == "daily" else 4
        forecast = forecast_series(series["points"], horizon=horizon, season_length=season_length)
        return {
            "series_id": series_id,
            "label": series["label"],
            "bucket": bucket_value,
            "actuals": series["points"],
            "statistics": analyse_points(series["points"]),
            "chosen_model": forecast["chosen_model"],
            "selection_reason": forecast["selection_reason"],
            "parameters": forecast["parameters"],
            "forecast": forecast["forecast"],
            "validation": forecast["validation"],
            "method_id": "forecasting",
            "boundary": forecast["boundary"],
        }

    @router.get("/governance-history")
    def governance_history() -> dict:
        # Read-only: returns previously captured snapshots. Capturing a new snapshot
        # is an explicit POST (it runs the heavy intelligence scan and writes an event),
        # so refreshing the dashboard never mutates state or incurs that cost.
        events = event_store.events() if event_store is not None else []
        return build_governance_history(events)

    @router.post("/governance-history/snapshot", dependencies=[need("analytics.improvements.manage")])
    def capture_governance_snapshot() -> dict:
        if event_store is None or intelligence is None:
            raise HTTPException(status_code=503, detail="Governance snapshots are not configured.")
        if actions is not None:
            result = actions.execute("capture_governance_snapshot", {}, acting_person())
            if result.outcome != "ok":
                raise HTTPException(status_code=500, detail=result.message or "Governance snapshot action failed.")
            side_effects = result.result.get("side_effects", {})
            analytics_result = side_effects.get("record_analytics_event", {}) if isinstance(side_effects, dict) else {}
            history = analytics_result.get("history") if isinstance(analytics_result, dict) else None
            return history if isinstance(history, dict) else build_governance_history(event_store.events())
        record_governance_snapshot(intelligence.run(), event_store)
        return build_governance_history(event_store.events())

    @router.get("/knowledge-gaps", dependencies=[need("analytics.raw.read")])
    def knowledge_gaps() -> dict:
        return build_gap_clusters(usage_log.entries())

    @router.get("/recurring-questions", dependencies=[need("analytics.raw.read")])
    def recurring_questions() -> dict:
        return build_recurring_questions(usage_log.entries())

    @router.get("/retrieval-health")
    def retrieval_health() -> dict:
        return build_retrieval_health(usage_log.entries())

    @router.get("/improvements")
    def improvement_actions() -> dict:
        if improvement_store is None:
            raise HTTPException(status_code=503, detail="Improvement actions are not configured.")
        actions_list = [action.model_dump() for action in improvement_store.list()]
        return {"action_count": len(actions_list), "actions": actions_list}

    @router.get("/improvements/metrics")
    def improvement_metrics() -> dict:
        if improvement_store is None:
            raise HTTPException(status_code=503, detail="Improvement actions are not configured.")
        return build_improvement_loop_metrics(improvement_store.list())

    @router.post("/improvements", dependencies=[need("analytics.improvements.create")])
    def create_improvement_action(payload: ImprovementActionCreate) -> dict:
        if improvement_store is None:
            raise HTTPException(status_code=503, detail="Improvement actions are not configured.")
        if actions is None:
            action = improvement_store.create(payload)
            return {"action": action.model_dump(), "execution": None}
        result = actions.execute(
            "create_improvement_action",
            payload.model_dump(),
            acting_person(),
        )
        if result.outcome != "ok":
            raise HTTPException(status_code=400, detail=result.message or "Improvement action was not created.")
        return {"action": result.result["handler"]["action"], "execution": result.model_dump()}

    @router.post("/improvements/{action_id}/transition", dependencies=[need("analytics.improvements.manage")])
    def transition_improvement_action(action_id: str, payload: ImprovementActionTransition) -> dict:
        if improvement_store is None:
            raise HTTPException(status_code=503, detail="Improvement actions are not configured.")
        if actions is None:
            try:
                action = improvement_store.transition(action_id, payload)
            except (KeyError, ValueError) as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return {"action": action.model_dump(), "execution": None}
        result = actions.execute(
            "transition_improvement_action",
            {"action_id": action_id, **payload.model_dump()},
            acting_person(),
        )
        if result.outcome != "ok":
            raise HTTPException(status_code=400, detail=result.message or "Improvement action was not transitioned.")
        return {"action": result.result["handler"]["action"], "execution": result.model_dump()}

    @router.get("/process-complexity", dependencies=NAMED)
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

    @router.get("/oag-benchmark")
    def oag_benchmark() -> dict:
        return build_oag_benchmark_report()

    @router.get("/oag-operations")
    def oag_operations() -> dict:
        traces = audit_trace.recent(1000) if audit_trace is not None else []
        return build_oag_operations_report(usage_log.entries(), traces)

    @router.get("/validation-evidence")
    def validation_evidence() -> dict:
        events = event_store.events() if event_store is not None else []
        return build_validation_evidence_report(
            usage_entries=usage_log.entries(),
            events=events,
            export_dictionary=build_data_dictionary(_export_context()),
        ).model_dump()

    @router.get("/methods")
    def analytics_methods() -> dict:
        return build_methods_catalogue().model_dump()

    @router.get("/explain", dependencies=NAMED)
    def analytics_explain() -> dict:
        return build_computation_traces(_export_context()).model_dump()

    @router.get("/explain/{metric_id}", dependencies=NAMED)
    def analytics_explain_metric(metric_id: str) -> dict:
        trace = find_computation_trace(_export_context(), metric_id)
        if trace is None:
            raise HTTPException(status_code=404, detail=f"Unknown analytics metric: {metric_id}")
        return trace.model_dump()

    @router.get("/export", dependencies=[need("analytics.export")])
    def analytics_export_index() -> dict:
        return export_index(_export_context())

    @router.get("/export/dictionary", dependencies=[need("analytics.export")])
    def analytics_export_dictionary(format: str = Query(default="json", pattern="^(md|json)$")):
        dictionary = build_data_dictionary(_export_context())
        if format == "md":
            return PlainTextResponse(
                data_dictionary_markdown(dictionary),
                media_type="text/markdown",
                headers={"Content-Disposition": 'attachment; filename="opsatlas-analytics-data-dictionary.md"'},
            )
        return dictionary

    @router.get("/export/reproducibility-pack", dependencies=[need("analytics.export"), *NAMED])
    def analytics_reproducibility_pack() -> Response:
        return Response(
            build_reproducibility_bundle(_export_context()),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="opsatlas-analytics-reproducibility-pack.zip"'},
        )

    @router.get("/export/{dataset}", dependencies=[need("analytics.export")])
    def analytics_export_dataset(request: Request, dataset: str, format: str = Query(default="json", pattern="^(csv|json)$")):
        if dataset not in available_dataset_names():
            raise HTTPException(status_code=404, detail=f"Unknown analytics export dataset: {dataset}")
        if dataset in NAMED_DATASETS:
            derived_guard(request)
        export = build_export_dataset(_export_context(), dataset)
        if format == "csv":
            filename = f"opsatlas-{dataset}.csv"
            return StreamingResponse(
                iter([export_csv(export)]),
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        return export.as_json()

    @router.get("/report.md", response_class=PlainTextResponse, dependencies=[need("analytics.export"), *NAMED])
    def analytics_report() -> PlainTextResponse:
        report = _build_report_markdown()
        return PlainTextResponse(
            report,
            media_type="text/markdown",
            headers={"Content-Disposition": 'attachment; filename="analytics-evidence-report.md"'},
        )

    @router.get("/report.pdf", dependencies=[need("analytics.export"), *NAMED])
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
        report = build_analytics_report(
            scorecard=build_scorecard(usage_log.entries()),
            history=build_history(events, usage_entries=usage_log.entries(), traces=traces),
            governance=build_governance_history(events),
            gaps=build_gap_clusters(usage_log.entries()),
            complexity=build_process_complexity(records),
            validation=build_validation_evidence_report().model_dump(),
        )
        return report + "\n" + data_dictionary_markdown(build_data_dictionary(_export_context()))

    def _export_context() -> AnalyticsExportContext:
        return AnalyticsExportContext(
            usage_log=usage_log,
            event_store=event_store,
            process_registry=process_registry,
            register=register,
            ontology_store=ontology_store,
        )

    return router
