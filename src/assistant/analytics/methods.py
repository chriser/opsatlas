"""Structured analytics methods and models catalogue."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

KNOWLEDGE_GAP_CANDIDATE_RULE = "Refused knowledge gaps plus answered questions with weak confidence."
KNOWLEDGE_GAP_QUALITY_RULE = "Silhouette is calculated over deterministic lexical token sets; <0.2 requires manual review."
PROCESS_COMPLEXITY_BOUNDARY = "These scores are diagnostic triage signals, not operational risk proof."


class MethodReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    path: str
    kind: str


class AnalyticsMethod(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    status: str = "implemented"
    technique: str
    model_family: str
    formula: str
    parameters: dict[str, str] = Field(default_factory=dict)
    inputs: list[str]
    assumptions: list[str]
    boundaries: list[str]
    validation_metric: str
    references: list[MethodReference]


class AnalyticsMethodsCatalogue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: str
    methods: list[AnalyticsMethod]
    summary: dict[str, int]


def build_methods_catalogue() -> AnalyticsMethodsCatalogue:
    methods = _methods()
    return AnalyticsMethodsCatalogue(
        generated_at=datetime.now(timezone.utc).isoformat(),
        methods=methods,
        summary={
            "method_count": len(methods),
            "implemented_count": sum(1 for method in methods if method.status == "implemented"),
            "planned_count": sum(1 for method in methods if method.status == "planned"),
        },
    )


def methodology_catalogue_markdown(catalogue: AnalyticsMethodsCatalogue | None = None) -> str:
    report = catalogue or build_methods_catalogue()
    lines = [
        "# OpsAtlas Analytics Methodology Catalogue",
        "",
        f"Generated: `{report.generated_at}`",
        "",
    ]
    for method in report.methods:
        lines.extend(
            [
                f"## {method.name}",
                "",
                f"- Method id: `{method.id}`",
                f"- Status: `{method.status}`",
                f"- Technique: {method.technique}",
                f"- Model family: {method.model_family}",
                f"- Formula: `{method.formula}`",
                f"- Validation metric: {method.validation_metric}",
                "",
                "Inputs:",
                *[f"- `{item}`" for item in method.inputs],
                "",
                "Parameters:",
                *[f"- `{key}`: {value}" for key, value in method.parameters.items()],
                "",
                "Assumptions:",
                *[f"- {item}" for item in method.assumptions],
                "",
                "Boundaries:",
                *[f"- {item}" for item in method.boundaries],
                "",
                "References:",
                *[f"- {reference.label}: `{reference.path}` ({reference.kind})" for reference in method.references],
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _ref(label: str, path: str, kind: str = "code") -> MethodReference:
    return MethodReference(label=label, path=path, kind=kind)


def _methods() -> list[AnalyticsMethod]:
    return [
        AnalyticsMethod(
            id="coverage_score",
            name="Coverage and Grounding Scorecard",
            technique="Descriptive ratio analytics",
            model_family="Deterministic aggregation",
            formula="answer_rate = answered / total; grounded_rate = grounded_answered / total",
            parameters={"grounded_confidence_label": "grounded", "answered_rule": "refused=false"},
            inputs=["usage_log.timestamp", "usage_log.refused", "usage_log.confidence", "usage_log.citation_count"],
            assumptions=[
                "Usage log rows are already filtered to approved platform interactions.",
                "Grounded confidence is a proxy for evidence quality, not proof of correctness.",
            ],
            boundaries=[
                "High answer rate is only useful when grounded rate and citation count remain healthy.",
                "The scorecard does not inspect the semantic correctness of each answer.",
            ],
            validation_metric="Unit tests assert scorecard counts, rates and average citation behaviour.",
            references=[
                _ref("Scorecard builder", "src/assistant/analytics/log.py"),
                _ref("Analytics tests", "tests/test_analytics.py", "test"),
            ],
        ),
        AnalyticsMethod(
            id="knowledge_gap_clustering",
            name="Knowledge-Gap Clustering",
            technique="Lexical clustering with deterministic topic classification",
            model_family="Rule-based NLP",
            formula="friction = min(100, coverage_gaps*25 + weak_evidence*15 + repeated_rows*5)",
            parameters={
                "candidate_rule": KNOWLEDGE_GAP_CANDIDATE_RULE,
                "quality_rule": KNOWLEDGE_GAP_QUALITY_RULE,
                "silhouette_distance": "1 - token_intersection / token_union",
            },
            inputs=["usage_log.question", "usage_log.refused", "usage_log.category", "usage_log.confidence"],
            assumptions=[
                "Repeated lexical themes are useful triage signals for documentation gaps.",
                "Weakly grounded answers can indicate source coverage weakness even when not refused.",
            ],
            boundaries=[
                "Clusters are triage prompts, not definitive root-cause analysis.",
                "Short or highly similar questions can inflate lexical similarity.",
            ],
            validation_metric="Silhouette coefficient over deterministic token sets; values below 0.2 require manual review.",
            references=[
                _ref("Knowledge gap analytics", "src/assistant/analytics/knowledge_gaps.py"),
                _ref("Knowledge gap tests", "tests/test_knowledge_gaps.py", "test"),
            ],
        ),
        AnalyticsMethod(
            id="value_dcf",
            name="Value Model: DCF, NPV, IRR and Payback",
            technique="Discounted cash-flow scenario modelling",
            model_family="Financial analytics",
            formula=(
                "gross = annual_workstreams * affected_share * delay_reduction_months * monthly_delay_value_gbp; "
                "net = gross - annual_opex_gbp"
            ),
            parameters={"discount_rate": "scenario assumption", "horizon_years": "scenario assumption"},
            inputs=["value_scenarios.*", "value_events.value_estimate", "value_events.synthetic_historical"],
            assumptions=[
                "Scenario assumptions are illustrative until validated with enterprise telemetry.",
                "Synthetic pilot events must remain separate from observed operator evidence.",
            ],
            boundaries=[
                "NPV, IRR and payback are business-case estimates, not audited financial outcomes.",
                "Negative or zero net benefit cannot produce a meaningful simple payback.",
            ],
            validation_metric="Tests validate value formulas, telemetry separation and assumptions-led report output.",
            references=[
                _ref("Value ledger", "src/assistant/value/ledger.py"),
                _ref("Value analytics tests", "tests/test_value_analytics.py", "test"),
            ],
        ),
        AnalyticsMethod(
            id="process_complexity_index",
            name="Process Complexity Index",
            technique="Weighted deterministic process indicator",
            model_family="Rule-based scoring",
            formula="min(100, roles*7 + systems*9 + dependencies*10 + controls*5 + handoffs*7 + exceptions*8 + rules*3)",
            parameters={"score_cap": "100", "banding": "low<34; medium 34-66; high>=67"},
            inputs=[
                "process_complexity.signals.roles",
                "process_complexity.signals.systems",
                "process_complexity.signals.dependencies",
                "process_complexity.signals.controls",
                "process_complexity.signals.handoffs",
                "process_complexity.signals.exception_terms",
            ],
            assumptions=[
                "Higher counts of roles, systems, dependencies and exception wording indicate more complex operational change.",
            ],
            boundaries=[PROCESS_COMPLEXITY_BOUNDARY, "Scores are capped; compare signals for capped processes."],
            validation_metric="Tests assert scoring, cap behaviour, bands and rubric coverage.",
            references=[
                _ref("Process complexity", "src/assistant/analytics/process_complexity.py"),
                _ref("Process complexity tests", "tests/test_process_complexity.py", "test"),
            ],
        ),
        AnalyticsMethod(
            id="key_person_risk_index",
            name="Key-Person-Risk Index",
            technique="Ownership concentration and unclear ownership indicator",
            model_family="Rule-based scoring",
            formula=(
                "min(100, dominant_role_share*40 + single_role_bonus + unclear_ownership*18 + "
                "concentration_bonus + exception_bonus + rule_role_imbalance)"
            ),
            parameters={"score_cap": "100", "dominant_share_threshold": "0.7", "banding": "low<34; medium 34-66; high>=67"},
            inputs=[
                "process_complexity.signals.dominant_role_share",
                "process_complexity.signals.unclear_ownership",
                "process_complexity.signals.exception_terms",
                "process_complexity.signals.rules",
            ],
            assumptions=[
                "Concentrated rule ownership and unclear owners are useful early-warning indicators for knowledge concentration.",
            ],
            boundaries=[PROCESS_COMPLEXITY_BOUNDARY, "The indicator does not prove individual dependency or operational fragility."],
            validation_metric="Tests assert concentration, unclear-owner and band behaviour.",
            references=[
                _ref("Process complexity", "src/assistant/analytics/process_complexity.py"),
                _ref("Process complexity tests", "tests/test_process_complexity.py", "test"),
            ],
        ),
        AnalyticsMethod(
            id="forecasting",
            name="Time-Series Forecasting",
            status="planned",
            technique="Rolling-window baseline with backtest validation",
            model_family="Classical time-series analytics",
            formula="forecast_t+n = validated baseline trend plus seasonality/residual checks",
            parameters={"minimum_history": "ANL-3 will define", "backtest_window": "ANL-3 will define"},
            inputs=["usage_log.timestamp", "analytics_events.timestamp", "value_events.timestamp"],
            assumptions=["Forecasts are only shown when enough history exists for backtest evidence."],
            boundaries=["Forecasts will be scenario support, not demand guarantees."],
            validation_metric="Planned: backtest error and coverage intervals.",
            references=[_ref("Advanced analytics backlog", "ADO #1210-#1214", "ado")],
        ),
        AnalyticsMethod(
            id="recurring_questions",
            name="Recurring Questions Analytic",
            status="planned",
            technique="Question normalisation and recurrence counting",
            model_family="Deterministic text analytics",
            formula="recurrence_count = count(normalised_question_key) over selected period",
            parameters={"normalisation": "lowercase, punctuation trim, whitespace collapse"},
            inputs=["usage_log.question", "usage_log.timestamp", "usage_log.answer_path"],
            assumptions=["Repeated questions can indicate unmet documentation or navigation needs."],
            boundaries=["Semantically similar but differently worded questions may need later embedding support."],
            validation_metric="Planned: tests for normalisation and repeat detection.",
            references=[_ref("Advanced analytics backlog", "ADO #1215-#1218", "ado")],
        ),
        AnalyticsMethod(
            id="failed_retrieval",
            name="Failed Retrieval and Low-Grounding Analytic",
            status="planned",
            technique="Low-confidence and zero-citation signal aggregation",
            model_family="Deterministic retrieval-quality analytics",
            formula="failed_retrieval = refused_without_guardrail OR (confidence not high/grounded AND citation_count=0)",
            parameters={"strong_confidence_labels": "grounded, high", "minimum_citations": "1"},
            inputs=["usage_log.refused", "usage_log.category", "usage_log.confidence", "usage_log.citation_count"],
            assumptions=["Low grounding and zero-citation answers are useful retrieval-quality triage signals."],
            boundaries=["This analytic flags likely retrieval weakness, not the precise missing source passage."],
            validation_metric="Planned: tests for refused, weak-confidence and zero-citation cases.",
            references=[_ref("Advanced analytics backlog", "ADO #1215-#1218", "ado")],
        ),
    ]
