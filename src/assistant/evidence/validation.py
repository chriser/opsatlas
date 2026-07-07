"""KSB-style traceability and validation protocol evidence."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..analytics.events import AnalyticsEvent
from ..analytics.forecast import forecast_series
from ..analytics.knowledge_gaps import build_gap_clusters
from ..analytics.log import UsageEntry
from ..analytics.timeseries import build_time_series
from ..value.ledger import build_value_report

MetricValue = str | int | float | bool | None


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    path: str
    kind: str


class OfficialKsbReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_id: str
    category: str
    framework_area: str
    mapping_status: str
    rationale: str


class EvidenceHistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_date: str
    event_type: str
    summary: str
    evidence_refs: list[EvidenceReference] = Field(default_factory=list)


class KsbTraceabilityRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ksb_id: str
    category: str
    capability: str
    evidence_claim: str
    delivered_features: list[str]
    evidence_refs: list[EvidenceReference]
    official_references: list[OfficialKsbReference] = Field(default_factory=list)
    evidence_history: list[EvidenceHistoryEntry] = Field(default_factory=list)
    validation_status: str
    next_evidence: str


class ValidationProtocolRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_id: str
    component: str
    validation_method: str
    metric: str
    acceptance_rule: str
    current_evidence: list[EvidenceReference]
    current_metrics: dict[str, MetricValue] = Field(default_factory=dict)
    status: str
    cadence: str
    boundary: str


class EthicsNote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note_id: str
    category: str
    title: str
    surface: str
    statement: str
    mitigation: str
    evidence_refs: list[EvidenceReference] = Field(default_factory=list)
    current_signal: dict[str, MetricValue] = Field(default_factory=dict)


class ValidationEvidenceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: str
    ksb_rows: list[KsbTraceabilityRow]
    validation_protocols: list[ValidationProtocolRow]
    ethics_notes: list[EthicsNote]
    summary: dict
    caveats: list[str]


def build_validation_evidence_report(
    *,
    usage_entries: list[UsageEntry] | None = None,
    events: list[AnalyticsEvent] | None = None,
    export_dictionary: dict[str, Any] | None = None,
) -> ValidationEvidenceReport:
    live_metrics = _live_validation_metrics(usage_entries or [], events or [], export_dictionary or {})
    ksb_rows = _ksb_rows()
    protocols = _validation_protocols(live_metrics)
    ethics_notes = _ethics_notes(live_metrics)
    return ValidationEvidenceReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        ksb_rows=ksb_rows,
        validation_protocols=protocols,
        ethics_notes=ethics_notes,
        summary=_summary(ksb_rows, protocols),
        caveats=[
            "Rows are project evidence mappings; replace labels with official assessment KSB IDs when the final mapping is supplied.",
            "Validation protocols evidence disciplined analytics behaviour, not legal, financial or operational certainty.",
            "Live enterprise telemetry is still required before ROI, regulatory or process-risk claims can be treated as verified.",
        ],
    )


def _ksb_rows() -> list[KsbTraceabilityRow]:
    return [
        KsbTraceabilityRow(
            ksb_id="KSB-P1",
            category="Knowledge",
            capability="Knowledge governance and approved-source control",
            evidence_claim="The platform controls what knowledge can be used before answers or analytics rely on it.",
            delivered_features=["Source register", "Ingestion state", "Governance review", "Approved-source-only answering"],
            evidence_refs=[
                EvidenceReference(label="Governance tests", path="tests/test_governance.py", kind="test"),
                EvidenceReference(label="Build governance", path="docs/ways-of-working/Build-Governance.md", kind="doc"),
            ],
            official_references=[
                _official(
                    "OFFICIAL-KNOWLEDGE-GOVERNANCE",
                    "Knowledge",
                    "Data governance, quality controls and approved-use boundaries",
                    "mapped_provisional",
                    "Maps the project governance controls to the official knowledge evidence area once final IDs are supplied.",
                )
            ],
            evidence_history=[
                _history(
                    "2026-06-20",
                    "implemented",
                    "Source lifecycle and governance review controls were added to keep unapproved material out of answers.",
                    [EvidenceReference(label="Governance tests", path="tests/test_governance.py", kind="test")],
                ),
                _history(
                    "2026-06-22",
                    "uat_evidence",
                    "Sprint 2 UAT confirmed duplicate/not-ingested remediation behaviour before ticket closure.",
                    [EvidenceReference(label="Agent handover", path="docs/ways-of-working/Agent-Handover-Log.md", kind="doc")],
                ),
            ],
            validation_status="implemented",
            next_evidence="Add screenshots from Sprint 2 UAT showing failed/not-ingested and approved source states.",
        ),
        KsbTraceabilityRow(
            ksb_id="KSB-P2",
            category="Skill",
            capability="Analytics dashboarding and evidence-led insight",
            evidence_claim="The platform turns answer, governance, simulator and process events into explainable analytics.",
            delivered_features=["Analytics scorecard", "Knowledge gaps", "Governance history", "Process complexity", "Value dashboard"],
            evidence_refs=[
                EvidenceReference(label="Analytics tests", path="tests/test_analytics_aggregation.py", kind="test"),
                EvidenceReference(label="Value hypothesis", path="docs/evidence/value-hypothesis.md", kind="doc"),
            ],
            official_references=[
                _official(
                    "OFFICIAL-SKILL-ANALYTICS",
                    "Skill",
                    "Analytics dashboarding, insight generation and evidence-led reporting",
                    "mapped_provisional",
                    "Links the analytics dashboard/reporting evidence to the official skill evidence area.",
                )
            ],
            evidence_history=[
                _history(
                    "2026-06-21",
                    "implemented",
                    "Analytics scorecard, governance history and process-complexity indicators were exposed in the UI.",
                    [EvidenceReference(label="Analytics aggregation tests", path="tests/test_analytics_aggregation.py", kind="test")],
                ),
                _history(
                    "2026-06-23",
                    "expanded",
                    "Value assumptions, exportable reports and process stress analytics strengthened the evidence spine.",
                    [EvidenceReference(label="Analytics report tests", path="tests/test_analytics_report.py", kind="test")],
                ),
            ],
            validation_status="implemented",
            next_evidence="Add UAT screenshots for Analytics page value and validation sections.",
        ),
        KsbTraceabilityRow(
            ksb_id="KSB-P3",
            category="Skill",
            capability="AI/RAG/OAG evaluation and hallucination control",
            evidence_claim=(
                "Answers are evaluated with expected behaviour classes, grounding metadata, benchmark probes and "
                "comparative architecture evidence."
            ),
            delivered_features=[
                "Grounding validation",
                "Hallucination probes",
                "Cited answers",
                "Audit traces",
                "RAG-vs-OAG comparative benchmark",
            ],
            evidence_refs=[
                EvidenceReference(label="Grounding evidence", path="docs/evidence/grounded-evidence.md", kind="doc"),
                EvidenceReference(label="Grounding tests", path="tests/test_grounding_eval.py", kind="test"),
                EvidenceReference(
                    label="RAG-vs-OAG method",
                    path="docs/benchmark/oag/oag-benchmark-method-and-decision.md",
                    kind="doc",
                ),
                EvidenceReference(
                    label="OAG-6 holdout scorecard",
                    path="docs/benchmark/oag/rag-vs-oag-rag_only-oag_first-2026-07-06T19-47-56+00-00.md",
                    kind="data",
                ),
            ],
            official_references=[
                _official(
                    "OFFICIAL-SKILL-AI-VALIDATION",
                    "Skill",
                    "AI evaluation, retrieval validation and hallucination-risk controls",
                    "mapped_provisional",
                    "Connects RAG evaluation and refusal behaviour to the official AI validation evidence area.",
                )
            ],
            evidence_history=[
                _history(
                    "2026-06-20",
                    "implemented",
                    "Benchmark probes and grounding validation were added to test answer/refusal expectations.",
                    [EvidenceReference(label="Grounding tests", path="tests/test_grounding_eval.py", kind="test")],
                ),
                _history(
                    "2026-06-22",
                    "uat_evidence",
                    "Sprint 2 UAT confirmed improved answer grounding for the tax-handling control question.",
                    [EvidenceReference(label="Grounding evidence", path="docs/evidence/grounded-evidence.md", kind="doc")],
                ),
                _history(
                    "2026-07-06",
                    "comparative_evaluation",
                    "OAG-first and RAG-only were benchmarked over the clean holdout split after OAG-6 structured routing improvements.",
                    [
                        EvidenceReference(
                            label="OAG-6 holdout scorecard",
                            path="docs/benchmark/oag/rag-vs-oag-rag_only-oag_first-2026-07-06T19-47-56+00-00.md",
                            kind="data",
                        )
                    ],
                ),
            ],
            validation_status="implemented",
            next_evidence="Keep adding fresh holdout rows before future OAG routing or ontology-content tuning.",
        ),
        KsbTraceabilityRow(
            ksb_id="KSB-P4",
            category="Knowledge",
            capability="External context and regulatory triage",
            evidence_claim="Public snapshots and candidate review provide dated context without bypassing internal approval.",
            delivered_features=["Public external-source snapshots", "Regulatory candidates", "Impact simulation"],
            evidence_refs=[
                EvidenceReference(label="Regulatory tests", path="tests/test_regulatory_candidates.py", kind="test"),
                EvidenceReference(label="Regulatory docs", path="docs/data-and-governance/regulatory-candidate-discovery.md", kind="doc"),
            ],
            official_references=[
                _official(
                    "OFFICIAL-KNOWLEDGE-EXTERNAL-CONTEXT",
                    "Knowledge",
                    "External context, regulatory scanning and change-impact triage",
                    "mapped_provisional",
                    "Maps public-source snapshots and impact simulation to the official context-analysis evidence area.",
                )
            ],
            evidence_history=[
                _history(
                    "2026-06-21",
                    "implemented",
                    "Public external-source snapshot registration and regulatory-candidate discovery were added with review status.",
                    [EvidenceReference(label="Regulatory tests", path="tests/test_regulatory_candidates.py", kind="test")],
                ),
                _history(
                    "2026-06-22",
                    "expanded",
                    "Impact simulation was added so candidate changes can be triaged against approved internal sources.",
                    [
                        EvidenceReference(
                            label="Regulatory docs",
                            path="docs/data-and-governance/regulatory-candidate-discovery.md",
                            kind="doc",
                        )
                    ],
                ),
            ],
            validation_status="implemented",
            next_evidence="Manually review at least one candidate against a real public external-source snapshot during UAT.",
        ),
        KsbTraceabilityRow(
            ksb_id="KSB-P5",
            category="Skill",
            capability="Business value modelling and assumptions governance",
            evidence_claim="The value case is represented as inspectable assumptions plus separate observed value events.",
            delivered_features=["Value assumptions ledger", "Scenario metrics", "Value event capture"],
            evidence_refs=[
                EvidenceReference(label="Value tests", path="tests/test_value_analytics.py", kind="test"),
                EvidenceReference(label="Value ledger", path="src/assistant/value/default_assumptions.json", kind="data"),
            ],
            official_references=[
                _official(
                    "OFFICIAL-SKILL-VALUE-MODELLING",
                    "Skill",
                    "Commercial value modelling, assumptions management and benefits evidence",
                    "mapped_provisional",
                    "Links the assumptions ledger and value-event telemetry to the official value-analysis evidence area.",
                )
            ],
            evidence_history=[
                _history(
                    "2026-06-22",
                    "implemented",
                    "Assumption-led value scenarios and observed value-event aggregation were added.",
                    [EvidenceReference(label="Value tests", path="tests/test_value_analytics.py", kind="test")],
                ),
                _history(
                    "2026-06-23",
                    "expanded",
                    "Exportable analytics report now carries the value scenario into downloadable evidence.",
                    [EvidenceReference(label="Analytics report tests", path="tests/test_analytics_report.py", kind="test")],
                ),
            ],
            validation_status="implemented",
            next_evidence="Replace illustrative assumptions with sponsor-approved values when available.",
        ),
        KsbTraceabilityRow(
            ksb_id="KSB-P6",
            category="Behaviour",
            capability="Ethical handling of anonymised/synthetic evidence",
            evidence_claim="The project separates anonymised learning material, synthetic simulation data and aggregate telemetry.",
            delivered_features=["Synthetic data rules", "Anonymisation rules", "Simulator synthetic-only QA metadata"],
            evidence_refs=[
                EvidenceReference(label="Synthetic rules", path="docs/data-and-governance/synthetic-data-rules.md", kind="doc"),
                EvidenceReference(label="Simulator tests", path="tests/test_simulator_runner.py", kind="test"),
            ],
            official_references=[
                _official(
                    "OFFICIAL-BEHAVIOUR-ETHICS",
                    "Behaviour",
                    "Ethical evidence handling, anonymisation and safe AI-assisted delivery",
                    "mapped_provisional",
                    "Maps anonymised/synthetic data separation and safe-use boundaries to the official behaviour evidence area.",
                )
            ],
            evidence_history=[
                _history(
                    "2026-06-20",
                    "implemented",
                    "Synthetic data rules and anonymisation boundaries were documented for safe testing.",
                    [EvidenceReference(label="Synthetic rules", path="docs/data-and-governance/synthetic-data-rules.md", kind="doc")],
                ),
                _history(
                    "2026-06-22",
                    "expanded",
                    "Synthetic pilot replay metadata was separated from real operator telemetry for analytics reporting.",
                    [EvidenceReference(label="Simulator tests", path="tests/test_simulator_runner.py", kind="test")],
                ),
            ],
            validation_status="implemented",
            next_evidence="Confirm the full 52-pack ingestion batch follows the same source-register fields.",
        ),
    ]


def _validation_protocols(metrics: dict[str, dict[str, MetricValue]]) -> list[ValidationProtocolRow]:
    return [
        ValidationProtocolRow(
            protocol_id="VAL-RAG-001",
            component="Grounded answer generation",
            validation_method="Benchmark questions, expected behaviour classes and grounding metadata.",
            metric="Answer class accuracy, grounding score, citation count and faithfulness status.",
            acceptance_rule="In-scope answers should be grounded and cited; missing evidence must refuse rather than invent.",
            current_evidence=[
                EvidenceReference(label="Evaluation runner", path="src/assistant/eval/runner.py", kind="code"),
                EvidenceReference(label="Grounding evidence", path="docs/evidence/grounded-evidence.md", kind="doc"),
            ],
            status="active",
            cadence="Run after ingestion, retrieval or prompt changes.",
            boundary="Does not prove factual completeness beyond approved source coverage.",
        ),
        ValidationProtocolRow(
            protocol_id="VAL-OAG-001",
            component="Ontology-assisted generation routing",
            validation_method=(
                "Comparative architecture evaluation over the same approved corpus using RAG-only "
                "and OAG-first routing across repeated holdout runs."
            ),
            metric=(
                "Per-category accuracy, answer-path usage, citation-type mix, latency and stability "
                "from tests/evaluation/rag_vs_oag_questions.json."
            ),
            acceptance_rule=(
                "OAG-first should improve structured entity, structured relationship and aggregate "
                "questions, preserve out-of-scope refusal and avoid material narrative degradation."
            ),
            current_evidence=[
                EvidenceReference(label="RAG-vs-OAG labels", path="tests/evaluation/rag_vs_oag_questions.json", kind="data"),
                EvidenceReference(label="RAG-vs-OAG harness", path="scripts/evaluate_rag_vs_oag.py", kind="code"),
                EvidenceReference(
                    label="RAG-vs-OAG method",
                    path="docs/benchmark/oag/oag-benchmark-method-and-decision.md",
                    kind="doc",
                ),
                EvidenceReference(
                    label="OAG-6 holdout scorecard",
                    path="docs/benchmark/oag/rag-vs-oag-rag_only-oag_first-2026-07-06T19-47-56+00-00.md",
                    kind="data",
                ),
            ],
            status="active",
            cadence="Run after ontology schema, routing, prompt or ingestion changes.",
            boundary=(
                "This isolates routing as the variable for S14/S52/S53 evidence; it does not prove "
                "complete process knowledge or legal correctness."
            ),
        ),
        ValidationProtocolRow(
            protocol_id="VAL-EAM-001",
            component="Enterprise Activity Model projection",
            validation_method=(
                "Deterministic model projection over the governed ontology, real-corpus value-chain distribution check, "
                "synthetic scale fixture and SVG render checks."
            ),
            metric=(
                "Coverage score, domain/stage coverage, gap/overlap/clash counts, evidence-confidence distribution, "
                "source provenance, APQC/SCOR value-chain classification distribution and render performance over a 60-process fixture."
            ),
            acceptance_rule=(
                "EAM must rebuild from current ontology state, keep finding output bounded/ranked, render all five views, "
                "show source provenance, keep unclassified rate below 15 percent, avoid empty value-chain columns and stay within "
                "the scale-test performance budget."
            ),
            current_evidence=[
                EvidenceReference(label="EAM projection tests", path="tests/test_eam_model.py", kind="test"),
                EvidenceReference(label="EAM API tests", path="tests/test_eam_api.py", kind="test"),
                EvidenceReference(label="EAM scale tests", path="tests/test_eam_scale.py", kind="test"),
                EvidenceReference(label="EAM dynamic update tests", path="tests/test_eam_dynamic_update.py", kind="test"),
                EvidenceReference(label="EAM architecture note", path="docs/architecture/enterprise-activity-model.md", kind="doc"),
                EvidenceReference(
                    label="EAM classification distribution",
                    path="docs/benchmark/eam/eam-classification-distribution-2026-07-07T10-24-20Z.md",
                    kind="benchmark",
                ),
            ],
            status="active",
            cadence="Run after ontology schema, projection, renderer, source-ingestion or EAM UI changes.",
            boundary=(
                "This validates deterministic visual analytics over approved ontology evidence; it does not prove live "
                "operating-model completeness or operational risk."
            ),
        ),
        ValidationProtocolRow(
            protocol_id="VAL-SIM-001",
            component="Synthetic persona simulator",
            validation_method="Seeded scenario selection, replay fingerprints and expected behaviour matching.",
            metric="Expectation match rate, replay question fingerprint and synthetic-only metadata.",
            acceptance_rule="Replay must preserve config and question set; user traffic must stay separate from persona traffic.",
            current_evidence=[
                EvidenceReference(label="Simulator tests", path="tests/test_simulator_runner.py", kind="test"),
                EvidenceReference(label="Simulator scenarios", path="docs/benchmark/simulator-scenarios.json", kind="data"),
            ],
            status="active",
            cadence="Run before UAT and after scenario catalogue changes.",
            boundary="Synthetic outcomes test behaviour boundaries, not real user adoption.",
        ),
        ValidationProtocolRow(
            protocol_id="VAL-VALUE-001",
            component="Value analytics",
            validation_method="Assumptions ledger validation and observed value-event aggregation.",
            metric="Gross benefit, net benefit, payback, NPV, IRR and observed GBP-equivalent events.",
            acceptance_rule="Assumptions must remain inspectable; observed events must be aggregate and non-negative.",
            current_evidence=[
                EvidenceReference(label="Value tests", path="tests/test_value_analytics.py", kind="test"),
                EvidenceReference(label="Value hypothesis", path="docs/evidence/value-hypothesis.md", kind="doc"),
            ],
            status="active",
            cadence="Review whenever assumptions or value-event taxonomy changes.",
            boundary="Illustrative until validated with live commercial telemetry.",
        ),
        ValidationProtocolRow(
            protocol_id="VAL-REG-001",
            component="Regulatory impact simulation",
            validation_method="Term-based deterministic impact scan over approved sources and dated public snapshots.",
            metric="Impact score, affected source count, affected process areas and external context count.",
            acceptance_rule="Must present triage evidence and next actions without claiming confirmed legal change.",
            current_evidence=[
                EvidenceReference(label="Regulatory tests", path="tests/test_regulatory_candidates.py", kind="test"),
                EvidenceReference(label="Regulatory docs", path="docs/data-and-governance/regulatory-candidate-discovery.md", kind="doc"),
            ],
            status="active",
            cadence="Run when candidate terms, public snapshots or source packs change.",
            boundary="Not legal advice and not proof that an operating procedure changed.",
        ),
        ValidationProtocolRow(
            protocol_id="VAL-PROC-001",
            component="Process analytics",
            validation_method="Deterministic parsing, process registry extraction and complexity rubric tests.",
            metric="Process count, complexity score, key-person-risk score and rubric coverage.",
            acceptance_rule="Scores must expose signals and caveats; capped scores need signal-level review.",
            current_evidence=[
                EvidenceReference(label="Process tests", path="tests/test_process_complexity.py", kind="test"),
                EvidenceReference(label="Process registry tests", path="tests/test_process_registry.py", kind="test"),
            ],
            status="active",
            cadence="Run after pack ingestion or parser/rubric changes.",
            boundary="Diagnostic indicator only, not operational risk proof.",
        ),
        ValidationProtocolRow(
            protocol_id="VAL-ANL-FORECAST-001",
            component="Analytics forecasting",
            validation_method="Rolling-origin backtest over telemetry series with deterministic model selection.",
            metric="Selected model, holdout count, MAE, MAPE and RMSE for query-volume forecasting.",
            acceptance_rule="Forecasts must show selected model, backtest error and diagnostic boundary before use.",
            current_evidence=[
                EvidenceReference(label="Forecast engine", path="src/assistant/analytics/forecast.py", kind="code"),
                EvidenceReference(label="Forecast tests", path="tests/test_analytics_timeseries.py", kind="test"),
            ],
            current_metrics=metrics.get("analytics_forecast", {}),
            status="active",
            cadence="Run after time-series, forecast or telemetry changes.",
            boundary="Forecasts are diagnostics from local telemetry and not operational demand guarantees.",
        ),
        ValidationProtocolRow(
            protocol_id="VAL-ANL-CLUSTER-001",
            component="Knowledge-gap clustering",
            validation_method="Deterministic lexical clustering with silhouette-style separation reporting.",
            metric="Candidate count, cluster count and silhouette score from current usage data.",
            acceptance_rule="Clusters must expose representative questions, terms, confidence and source-gap wording.",
            current_evidence=[
                EvidenceReference(label="Knowledge-gap clustering", path="src/assistant/analytics/knowledge_gaps.py", kind="code"),
                EvidenceReference(label="Knowledge-gap tests", path="tests/test_analytics_aggregation.py", kind="test"),
            ],
            current_metrics=metrics.get("analytics_cluster", {}),
            status="active",
            cadence="Run after retrieval, confidence or usage-log changes.",
            boundary="Lexical grouping can merge or split themes incorrectly; human review remains required.",
        ),
        ValidationProtocolRow(
            protocol_id="VAL-ANL-EXPORT-001",
            component="Analytics export and reproducibility pack",
            validation_method="Generated data dictionary coverage and export bundle round-trip checks.",
            metric="Dataset count, active field count and undocumented active field count.",
            acceptance_rule="Exports must include a dictionary, safe aggregate fields and no raw prompts/source text.",
            current_evidence=[
                EvidenceReference(label="Export helpers", path="src/assistant/analytics/export.py", kind="code"),
                EvidenceReference(label="Export tests", path="tests/test_analytics_export.py", kind="test"),
            ],
            current_metrics=metrics.get("analytics_export", {}),
            status="active",
            cadence="Run after analytics dataset or export schema changes.",
            boundary="Exports are aggregate analytics metadata only and exclude raw source content and generated answers.",
        ),
        ValidationProtocolRow(
            protocol_id="VAL-ANL-VALUE-001",
            component="Value analytics sensitivity",
            validation_method="Versioned assumptions ledger, scenario spread and observed value-event separation.",
            metric="Scenario count, base NPV/payback and observed value-event count.",
            acceptance_rule="Value claims must keep assumptions, synthetic telemetry and observed events separate.",
            current_evidence=[
                EvidenceReference(label="Value ledger", path="src/assistant/value/default_assumptions.json", kind="data"),
                EvidenceReference(label="Value tests", path="tests/test_value_analytics.py", kind="test"),
            ],
            current_metrics=metrics.get("analytics_value_sensitivity", {}),
            status="active",
            cadence="Run when assumptions, value drivers or telemetry sources change.",
            boundary="Commercial figures remain illustrative until sponsor-approved values and live evidence replace assumptions.",
        ),
    ]


def _live_validation_metrics(
    usage_entries: list[UsageEntry],
    events: list[AnalyticsEvent],
    export_dictionary: dict[str, Any],
) -> dict[str, dict[str, MetricValue]]:
    time_series = build_time_series(usage_entries, events, bucket="daily")
    query_points = time_series.get("series", {}).get("query_volume", {}).get("points", [])
    forecast = forecast_series(query_points, horizon=7)
    forecast_selected = forecast.get("validation", {}).get("selected", {})
    clusters = build_gap_clusters(usage_entries)
    datasets = export_dictionary.get("datasets", []) if isinstance(export_dictionary, dict) else []
    undocumented_fields = sum(len(dataset.get("undocumented_active_columns", [])) for dataset in datasets if isinstance(dataset, dict))
    active_fields = sum(len(dataset.get("active_columns", [])) for dataset in datasets if isinstance(dataset, dict))
    value_report = build_value_report(events).model_dump()
    base_metric = next((row for row in value_report.get("metrics", []) if row.get("scenario_id") == "base"), {})
    value_telemetry = value_report.get("telemetry", {})
    return {
        "analytics_forecast": {
            "series_points": len(query_points),
            "chosen_model": forecast.get("chosen_model", ""),
            "holdout_n": forecast.get("validation", {}).get("holdout_n", 0),
            "mae": forecast_selected.get("mae"),
            "mape": forecast_selected.get("mape"),
            "rmse": forecast_selected.get("rmse"),
        },
        "analytics_cluster": {
            "total_candidates": clusters.get("total_candidates", 0),
            "cluster_count": clusters.get("cluster_count", 0),
            "silhouette_score": clusters.get("silhouette_score", 0),
        },
        "analytics_export": {
            "dataset_count": len(datasets),
            "active_field_count": active_fields,
            "undocumented_active_field_count": undocumented_fields,
            "ethics_boundary_present": bool(export_dictionary.get("ethics_boundary")),
        },
        "analytics_value_sensitivity": {
            "scenario_count": len(value_report.get("scenarios", [])),
            "base_npv_gbp": base_metric.get("npv_gbp"),
            "base_simple_payback_years": base_metric.get("simple_payback_years"),
            "observed_value_event_count": value_telemetry.get("event_count", 0),
            "synthetic_value_event_count": value_telemetry.get("synthetic_event_count", 0),
        },
        "ethics": {
            "usage_rows": len(usage_entries),
            "export_dataset_count": len(datasets),
            "synthetic_value_event_count": value_telemetry.get("synthetic_event_count", 0),
            "observed_value_event_count": value_telemetry.get("event_count", 0),
        },
    }


def _ethics_notes(metrics: dict[str, dict[str, MetricValue]]) -> list[EthicsNote]:
    ethics = metrics.get("ethics", {})
    return [
        EthicsNote(
            note_id="ETH-GDPR-001",
            category="GDPR and data protection",
            title="Data minimisation and export safety",
            surface="Analytics export, reproducibility pack and validation report",
            statement=(
                "Analytics exports contain operational metadata and aggregate indicators only; raw source text, "
                "full prompts and generated answers are intentionally excluded."
            ),
            mitigation=(
                "Keep source documents in governed stores, preserve anonymisation rules, and treat screenshots "
                "or exported artefacts as submission evidence rather than production personal-data extracts."
            ),
            evidence_refs=[
                EvidenceReference(label="Synthetic data rules", path="docs/data-and-governance/synthetic-data-rules.md", kind="doc"),
                EvidenceReference(label="Anonymisation rules", path="docs/data-and-governance/anonymisation-rules.md", kind="doc"),
                EvidenceReference(label="Export helpers", path="src/assistant/analytics/export.py", kind="code"),
            ],
            current_signal={
                "export_dataset_count": ethics.get("export_dataset_count", 0),
                "usage_rows": ethics.get("usage_rows", 0),
            },
        ),
        EthicsNote(
            note_id="ETH-BIAS-001",
            category="Bias and analytical limitation",
            title="Lexical and benchmark classifiers can mis-assign themes",
            surface="Knowledge gaps, recurring questions, precision metrics and RAG-vs-OAG benchmark views",
            statement=(
                "Several analytics use deterministic keyword, lexical or labelled benchmark rules. These are "
                "review aids and can over-group, under-group or reflect the limits of the labelled set."
            ),
            mitigation=(
                "Show rubrics and boundaries, preserve holdout discipline, route candidate actions through "
                "human-owned improvement review, and avoid treating one score as operational truth."
            ),
            evidence_refs=[
                EvidenceReference(label="OAG benchmark method", path="docs/benchmark/oag/oag-benchmark-method-and-decision.md", kind="doc"),
                EvidenceReference(label="Knowledge-gap clustering", path="src/assistant/analytics/knowledge_gaps.py", kind="code"),
            ],
            current_signal={
                "cluster_count": metrics.get("analytics_cluster", {}).get("cluster_count", 0),
                "silhouette_score": metrics.get("analytics_cluster", {}).get("silhouette_score", 0),
            },
        ),
        EthicsNote(
            note_id="ETH-SUSTAIN-001",
            category="Sustainability and compute footprint",
            title="Local compute is bounded and benchmark-heavy runs are separated",
            surface="Forecast, governance review, OAG benchmark and export evidence",
            statement=(
                "The platform favours deterministic local analytics for routine operation. Heavy model benchmarks "
                "are explicit validation activities, not background page-load work."
            ),
            mitigation=(
                "Use quick deterministic views by default, keep benchmark runs manual and evidence-led, and record "
                "when synthetic or benchmark telemetry is separate from real operator activity."
            ),
            evidence_refs=[
                EvidenceReference(
                    label="Governance review simplification",
                    path="docs/data-and-governance/governance-review-mode-simplification-2026-07-05.md",
                    kind="doc",
                ),
                EvidenceReference(
                    label="OAG benchmark method",
                    path="docs/benchmark/oag/oag-benchmark-method-and-decision.md",
                    kind="doc",
                ),
            ],
            current_signal={
                "synthetic_value_event_count": ethics.get("synthetic_value_event_count", 0),
                "observed_value_event_count": ethics.get("observed_value_event_count", 0),
            },
        ),
    ]


def _official(reference_id: str, category: str, framework_area: str, mapping_status: str, rationale: str) -> OfficialKsbReference:
    return OfficialKsbReference(
        reference_id=reference_id,
        category=category,
        framework_area=framework_area,
        mapping_status=mapping_status,
        rationale=rationale,
    )


def _history(
    event_date: str,
    event_type: str,
    summary: str,
    evidence_refs: list[EvidenceReference],
) -> EvidenceHistoryEntry:
    return EvidenceHistoryEntry(
        event_date=event_date,
        event_type=event_type,
        summary=summary,
        evidence_refs=evidence_refs,
    )


def _summary(ksb_rows: list[KsbTraceabilityRow], protocols: list[ValidationProtocolRow]) -> dict:
    ksb_status = Counter(row.validation_status for row in ksb_rows)
    protocol_status = Counter(row.status for row in protocols)
    official_status = Counter(ref.mapping_status for row in ksb_rows for ref in row.official_references)
    return {
        "ksb_count": len(ksb_rows),
        "validation_protocol_count": len(protocols),
        "ksb_by_status": dict(sorted(ksb_status.items())),
        "protocols_by_status": dict(sorted(protocol_status.items())),
        "official_reference_count": sum(len(row.official_references) for row in ksb_rows),
        "official_references_by_status": dict(sorted(official_status.items())),
        "evidence_history_event_count": sum(len(row.evidence_history) for row in ksb_rows),
        "evidence_reference_count": sum(len(row.evidence_refs) for row in ksb_rows)
        + sum(len(row.current_evidence) for row in protocols)
        + sum(len(entry.evidence_refs) for row in ksb_rows for entry in row.evidence_history),
    }
