"""Raw analytics dataset export helpers."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ..ontology import OntologyStore
from ..process.registry import ProcessRegistry
from ..sources.register import SourceRegister
from ..value.ledger import build_value_report
from .event_store import AnalyticsEventStore
from .events import AnalyticsEvent
from .governance_history import build_governance_history
from .knowledge_gaps import build_gap_clusters
from .log import UsageLog
from .process_complexity import build_process_complexity

Scalar = str | int | float | bool | None
FlatRow = dict[str, Scalar]


@dataclass(frozen=True)
class AnalyticsExportContext:
    usage_log: UsageLog
    event_store: AnalyticsEventStore | None = None
    process_registry: ProcessRegistry | None = None
    register: SourceRegister | None = None
    ontology_store: OntologyStore | None = None


@dataclass(frozen=True)
class DatasetSpec:
    dataset: str
    label: str
    description: str
    builder: Callable[[AnalyticsExportContext], list[dict[str, Any]]]
    fields: tuple["FieldSpec", ...]


@dataclass(frozen=True)
class FieldSpec:
    field: str
    type: str
    unit: str
    description: str
    source_module: str

    def as_json(self, *, currently_exported: bool) -> dict:
        return {
            "field": self.field,
            "type": self.type,
            "unit": self.unit,
            "description": self.description,
            "source_module": self.source_module,
            "currently_exported": currently_exported,
        }


@dataclass(frozen=True)
class ExportDataset:
    dataset: str
    label: str
    description: str
    rows: list[FlatRow]
    columns: list[str]
    row_count: int
    last_updated: str | None

    def as_json(self) -> dict:
        return {
            "dataset": self.dataset,
            "label": self.label,
            "description": self.description,
            "row_count": self.row_count,
            "last_updated": self.last_updated,
            "columns": self.columns,
            "rows": self.rows,
        }


def export_index(context: AnalyticsExportContext) -> dict:
    datasets = []
    for spec in DATASET_SPECS:
        dataset = build_export_dataset(context, spec.dataset)
        datasets.append(
            {
                "dataset": dataset.dataset,
                "label": dataset.label,
                "description": dataset.description,
                "row_count": dataset.row_count,
                "last_updated": dataset.last_updated,
                "formats": ["csv", "json"],
            }
        )
    return {
        "datasets": datasets,
        "dataset_count": len(datasets),
        "ethics_boundary": (
            "Exports contain operational analytics metadata only; raw prompts, generated answers and source text are excluded."
        ),
    }


def build_data_dictionary(context: AnalyticsExportContext) -> dict:
    datasets = []
    for spec in DATASET_SPECS:
        export = build_export_dataset(context, spec.dataset)
        declared_fields = {field.field for field in spec.fields}
        active_columns = set(export.columns)
        datasets.append(
            {
                "dataset": spec.dataset,
                "label": spec.label,
                "description": spec.description,
                "row_count": export.row_count,
                "active_columns": export.columns,
                "field_count": len(spec.fields),
                "undocumented_active_columns": sorted(active_columns - declared_fields),
                "fields": [
                    field.as_json(currently_exported=field.field in active_columns)
                    for field in spec.fields
                ],
            }
        )
    return {
        "title": "OpsAtlas Analytics Data Dictionary",
        "dataset_count": len(datasets),
        "datasets": datasets,
        "ethics_boundary": (
            "Exports contain operational analytics metadata only; raw prompts, generated answers and source text are excluded."
        ),
    }


def data_dictionary_markdown(dictionary: dict) -> str:
    lines = [
        "# OpsAtlas Analytics Data Dictionary",
        "",
        dictionary.get("ethics_boundary", ""),
        "",
    ]
    for dataset in dictionary.get("datasets", []):
        lines.extend(
            [
                f"## {dataset.get('label', dataset.get('dataset', 'Dataset'))}",
                "",
                str(dataset.get("description", "")),
                "",
                f"- Dataset: `{dataset.get('dataset', '')}`",
                f"- Rows at generation time: `{dataset.get('row_count', 0)}`",
                f"- Active columns: `{len(dataset.get('active_columns', []))}`",
                "",
                "| Field | Type | Unit | Description | Source module |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for field in dataset.get("fields", []):
            lines.append(
                "| "
                + " | ".join(
                    _md_cell(field.get(key, ""))
                    for key in ("field", "type", "unit", "description", "source_module")
                )
                + " |"
            )
        undocumented = dataset.get("undocumented_active_columns") or []
        if undocumented:
            lines.extend(["", f"Undocumented active columns: `{', '.join(undocumented)}`"])
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_reproducibility_bundle(context: AnalyticsExportContext) -> bytes:
    dictionary = build_data_dictionary(context)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.md", reproducibility_readme(dictionary))
        archive.writestr("data-dictionary.json", json.dumps(dictionary, indent=2, sort_keys=True))
        archive.writestr("data-dictionary.md", data_dictionary_markdown(dictionary))
        archive.writestr("methodology-catalogue.md", methodology_catalogue_markdown())
        for dataset in available_dataset_names():
            export = build_export_dataset(context, dataset)
            archive.writestr(f"datasets/{dataset}.json", json.dumps(export.as_json(), indent=2, sort_keys=True))
            archive.writestr(f"datasets/{dataset}.csv", export_csv(export))
    return buffer.getvalue()


def reproducibility_readme(dictionary: dict) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    dataset_rows = [
        f"- `{dataset['dataset']}`: {dataset['row_count']} rows, {len(dataset['active_columns'])} active columns"
        for dataset in dictionary.get("datasets", [])
    ]
    lines = [
        "# OpsAtlas Analytics Reproducibility Pack",
        "",
        f"Generated: `{generated_at}`",
        "",
        "## Contents",
        "",
        "- `datasets/*.csv` and `datasets/*.json`: raw analytics export datasets.",
        "- `data-dictionary.json` and `data-dictionary.md`: generated field-level dictionary.",
        "- `methodology-catalogue.md`: deterministic method notes for headline analytics.",
        "- `README.md`: this file.",
        "",
        "## Dataset Snapshot",
        "",
        *dataset_rows,
        "",
        "## Recompute Notes",
        "",
        "- Coverage score: use `usage_log`; answer rate is non-refused rows divided by total rows, "
        "and grounded rate is grounded non-refused rows divided by total rows.",
        "- Silhouette: rebuild knowledge-gap candidates from `usage_log`, then apply the deterministic lexical "
        "token-set distance method described in `methodology-catalogue.md`.",
        "- NPV/IRR and payback: use `value_scenarios`; formula fields document gross annual benefit, then compare "
        "`one_off_capex_gbp`, `annual_opex_gbp`, `net_annual_benefit_gbp`, `npv_gbp` and `irr`.",
        "- Forecast value: use `value_events` for observed or synthetic telemetry and `value_scenarios` for the "
        "assumptions-led forecast; keep synthetic and observed rows separate.",
        "- Friction score: use `knowledge_gap_clusters.friction_score`; it is a deterministic indicator derived "
        "from coverage-gap and weak-evidence counts.",
        "- Governance open issues: use the latest `governance_history.open` value after sorting by date.",
        "- Process complexity: use `process_complexity` scores and signal columns; scores are triage indicators, "
        "not proof of operational risk.",
        "",
        "## Boundary",
        "",
        dictionary.get("ethics_boundary", ""),
        "The pack is designed for offline validation of aggregate analytics. It intentionally excludes raw source "
        "content, generated answers and full prompt/answer traces.",
    ]
    return "\n".join(lines).strip() + "\n"


def methodology_catalogue_markdown() -> str:
    lines = [
        "# OpsAtlas Analytics Methodology Catalogue",
        "",
        "## Usage Coverage",
        "",
        "- Source dataset: `usage_log`.",
        "- Answer rate: answered rows / total rows, where answered means `refused=false`.",
        "- Grounded rate: grounded answered rows / total rows.",
        "- Citation average: mean `citation_count` over answered rows.",
        "",
        "## Knowledge-Gap Clustering",
        "",
        "- Source dataset: `usage_log`.",
        "- Candidate rule: refused rows without a guardrail category plus answered rows with weak confidence.",
        "- Topic rule: deterministic lexical topic classification.",
        "- Friction score: coverage gaps are weighted higher than weak-evidence rows and capped at 100.",
        "- Silhouette: deterministic lexical token-set distance over candidate questions; values below 0.2 need review.",
        "",
        "## Governance History",
        "",
        "- Source dataset: `governance_history`.",
        "- Each row is a daily lifecycle aggregate for detected, accepted, resolved and open governance issues.",
        "",
        "## Value Analytics",
        "",
        "- Source datasets: `value_events` and `value_scenarios`.",
        "- Gross annual benefit formula: annual workstreams x affected share x delay months saved x monthly value.",
        "- Net annual benefit: gross annual benefit minus annual opex.",
        "- Payback, NPV and IRR are assumptions-led until validated with enterprise telemetry.",
        "",
        "## Process Complexity",
        "",
        "- Source dataset: `process_complexity`.",
        "- Scores combine counts of roles, systems, dependencies, controls, hand-offs, exception wording and rules.",
        "- Key-person-risk scores combine ownership concentration, unclear ownership and exception wording.",
        "- Scores are diagnostic triage indicators, not operational risk proof.",
    ]
    return "\n".join(lines).strip() + "\n"


def build_export_dataset(context: AnalyticsExportContext, dataset: str) -> ExportDataset:
    spec = _spec(dataset)
    raw_rows = spec.builder(context)
    rows = [_flatten(row) for row in raw_rows]
    columns = _columns(rows)
    normalised_rows = [{column: row.get(column) for column in columns} for row in rows]
    return ExportDataset(
        dataset=spec.dataset,
        label=spec.label,
        description=spec.description,
        rows=normalised_rows,
        columns=columns,
        row_count=len(normalised_rows),
        last_updated=_last_updated(normalised_rows),
    )


def export_csv(dataset: ExportDataset) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=dataset.columns, extrasaction="ignore")
    writer.writeheader()
    for row in dataset.rows:
        writer.writerow({column: _csv_value(row.get(column)) for column in dataset.columns})
    return output.getvalue()


def available_dataset_names() -> list[str]:
    return [spec.dataset for spec in DATASET_SPECS]


def _spec(dataset: str) -> DatasetSpec:
    for spec in DATASET_SPECS:
        if spec.dataset == dataset:
            return spec
    raise KeyError(dataset)


def _usage_rows(context: AnalyticsExportContext) -> list[dict[str, Any]]:
    return [entry.model_dump() for entry in context.usage_log.entries()]


def _event_rows(context: AnalyticsExportContext) -> list[dict[str, Any]]:
    rows = []
    for event in _events(context):
        row = event.model_dump()
        row["metadata"] = json.dumps(row.get("metadata") or {}, sort_keys=True)
        rows.append(row)
    return rows


def _knowledge_gap_rows(context: AnalyticsExportContext) -> list[dict[str, Any]]:
    return list(build_gap_clusters(context.usage_log.entries()).get("clusters", []))


def _value_event_rows(context: AnalyticsExportContext) -> list[dict[str, Any]]:
    return [
        {
            "event_id": event.event_id,
            "timestamp": event.timestamp,
            "label": event.metadata.get("label") or "Value event",
            "value_driver": event.value_driver,
            "value_estimate": event.value_estimate,
            "process_area": event.process_area,
            "scenario_id": event.metadata.get("scenario_id"),
            "unit": event.metadata.get("unit") or "GBP",
            "confidence": event.metadata.get("confidence") or "review",
            "evidence_type": event.metadata.get("evidence_type") or "operator_estimate",
            "synthetic_historical": event.metadata.get("synthetic_historical") is True,
            "run_id": event.metadata.get("run_id"),
        }
        for event in _events(context)
        if event.event_type == "value_event_recorded"
    ]


def _value_scenario_rows(context: AnalyticsExportContext) -> list[dict[str, Any]]:
    return list(build_value_report(_events(context)).model_dump().get("metrics", []))


def _process_complexity_rows(context: AnalyticsExportContext) -> list[dict[str, Any]]:
    records = []
    if context.process_registry is not None:
        records = (
            context.process_registry.derive_from_sources(context.register)
            if context.register is not None
            else context.process_registry.list()
        )
    return list(build_process_complexity(records).get("processes", []))


def _ontology_stat_rows(context: AnalyticsExportContext) -> list[dict[str, Any]]:
    if context.ontology_store is None:
        return []
    counts = context.ontology_store.counts()
    return [
        {
            "object_counts": json.dumps(counts.get("objects", {}), sort_keys=True),
            "link_counts": json.dumps(counts.get("links", {}), sort_keys=True),
            "total_objects": counts.get("total_objects", 0),
            "total_links": counts.get("total_links", 0),
        }
    ]


def _governance_history_rows(context: AnalyticsExportContext) -> list[dict[str, Any]]:
    return list(build_governance_history(_events(context)).get("issue_events_over_time", []))


def _events(context: AnalyticsExportContext) -> list[AnalyticsEvent]:
    return context.event_store.events() if context.event_store is not None else []


def _flatten(row: dict[str, Any], prefix: str = "") -> FlatRow:
    output: FlatRow = {}
    for key, value in row.items():
        flat_key = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            output.update(_flatten(value, flat_key))
        elif isinstance(value, list):
            output[flat_key] = json.dumps(value, sort_keys=True)
        elif value is None or isinstance(value, (str, int, float, bool)):
            output[flat_key] = value
        else:
            output[flat_key] = str(value)
    return output


def _columns(rows: list[FlatRow]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        for column in row:
            if column not in columns:
                columns.append(column)
    return columns


def _last_updated(rows: list[FlatRow]) -> str | None:
    values = [str(row.get("timestamp") or row.get("date") or "") for row in rows]
    dated = [value for value in values if value]
    return max(dated) if dated else None


def _csv_value(value: Scalar) -> str | int | float:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "/").replace("\n", " ").strip()


def _field(field: str, type_: str, unit: str, description: str, source_module: str) -> FieldSpec:
    return FieldSpec(
        field=field,
        type=type_,
        unit=unit,
        description=description,
        source_module=source_module,
    )


DATASET_SPECS: tuple[DatasetSpec, ...] = (
    DatasetSpec(
        "usage_log",
        "Usage log",
        "Assistant usage events recorded by the local usage log.",
        _usage_rows,
        (
            _field("timestamp", "datetime", "ISO-8601", "Time the usage event was recorded.", "analytics.log.UsageEntry"),
            _field("question", "string", "n/a", "User question text captured for aggregate usage analysis.", "analytics.log.UsageEntry"),
            _field("mode", "string", "n/a", "Interface or assistant mode used for the request.", "analytics.log.UsageEntry"),
            _field("answer_path", "string", "n/a", "Answering path such as rag or oag.", "analytics.log.UsageEntry"),
            _field("refused", "boolean", "n/a", "Whether the assistant refused or could not answer.", "analytics.log.UsageEntry"),
            _field("category", "string", "n/a", "Guardrail or refusal category when present.", "analytics.log.UsageEntry"),
            _field("confidence", "string", "n/a", "Answer confidence label recorded by the platform.", "analytics.log.UsageEntry"),
            _field("citation_count", "integer", "count", "Number of citations attached to the answer.", "analytics.log.UsageEntry"),
        ),
    ),
    DatasetSpec(
        "events",
        "Analytics events",
        "Append-only analytics event ledger.",
        _event_rows,
        (
            _field("event_id", "string", "n/a", "Stable event identifier.", "analytics.events.AnalyticsEvent"),
            _field("event_type", "string", "n/a", "Controlled analytics event type.", "analytics.events.AnalyticsEvent"),
            _field("timestamp", "datetime", "ISO-8601", "Time the event was recorded.", "analytics.events.AnalyticsEvent"),
            _field("actor_type", "string", "n/a", "Actor category: system, operator, persona or agent.", "analytics.events.AnalyticsEvent"),
            _field("actor_id", "string", "n/a", "Optional actor identifier.", "analytics.events.AnalyticsEvent"),
            _field("entity_type", "string", "n/a", "Type of entity affected by the event.", "analytics.events.AnalyticsEvent"),
            _field("entity_id", "string", "n/a", "Identifier of the entity affected by the event.", "analytics.events.AnalyticsEvent"),
            _field("source_id", "string", "n/a", "Optional source identifier linked to the event.", "analytics.events.AnalyticsEvent"),
            _field("process_area", "string", "n/a", "Optional process area linked to the event.", "analytics.events.AnalyticsEvent"),
            _field("persona", "string", "n/a", "Optional synthetic persona linked to the event.", "analytics.events.AnalyticsEvent"),
            _field("outcome", "string", "n/a", "Outcome label recorded for the event.", "analytics.events.AnalyticsEvent"),
            _field(
                "value_driver",
                "string",
                "n/a",
                "Value driver when the event records value telemetry.",
                "analytics.events.AnalyticsEvent",
            ),
            _field("value_estimate", "number", "GBP-equivalent", "Value estimate when present.", "analytics.events.AnalyticsEvent"),
            _field(
                "metadata",
                "json",
                "n/a",
                "Flat safe metadata serialised as JSON to keep columns stable.",
                "analytics.events.AnalyticsEvent",
            ),
        ),
    ),
    DatasetSpec(
        "knowledge_gap_clusters",
        "Knowledge-gap clusters",
        "Deterministic clusters derived from refused and weakly grounded questions.",
        _knowledge_gap_rows,
        (
            _field("id", "string", "n/a", "Stable cluster identifier.", "analytics.knowledge_gaps"),
            _field("label", "string", "n/a", "Human-readable cluster label.", "analytics.knowledge_gaps"),
            _field("topic", "string", "n/a", "Deterministic topic classification.", "analytics.knowledge_gaps"),
            _field("process_area", "string", "n/a", "Likely process area affected by the gap.", "analytics.knowledge_gaps"),
            _field("source_gap", "string", "n/a", "Explanation of the source coverage gap.", "analytics.knowledge_gaps"),
            _field("question_count", "integer", "count", "Number of questions in the cluster.", "analytics.knowledge_gaps"),
            _field("representative_questions", "json", "n/a", "Representative questions serialised as JSON.", "analytics.knowledge_gaps"),
            _field("terms", "json", "n/a", "Top lexical terms serialised as JSON.", "analytics.knowledge_gaps"),
            _field("friction_score", "integer", "0-100", "Deterministic friction indicator for the cluster.", "analytics.knowledge_gaps"),
            _field("confidence", "string", "n/a", "Cluster confidence label.", "analytics.knowledge_gaps"),
        ),
    ),
    DatasetSpec(
        "value_events",
        "Value events",
        "Operator-estimated or synthetic value telemetry events.",
        _value_event_rows,
        (
            _field("event_id", "string", "n/a", "Source analytics event identifier.", "analytics.export._value_event_rows"),
            _field("timestamp", "datetime", "ISO-8601", "Time the value event was recorded.", "analytics.export._value_event_rows"),
            _field("label", "string", "n/a", "Human-readable value event label.", "analytics.export._value_event_rows"),
            _field("value_driver", "string", "n/a", "Benefit or value driver category.", "analytics.export._value_event_rows"),
            _field("value_estimate", "number", "GBP-equivalent", "Recorded value estimate.", "analytics.export._value_event_rows"),
            _field("process_area", "string", "n/a", "Process area associated with the value event.", "analytics.export._value_event_rows"),
            _field("scenario_id", "string", "n/a", "Value scenario associated with the event.", "analytics.export._value_event_rows"),
            _field("unit", "string", "n/a", "Unit recorded for the value estimate.", "analytics.export._value_event_rows"),
            _field("confidence", "string", "n/a", "Confidence label for the estimate.", "analytics.export._value_event_rows"),
            _field("evidence_type", "string", "n/a", "Evidence type behind the estimate.", "analytics.export._value_event_rows"),
            _field(
                "synthetic_historical",
                "boolean",
                "n/a",
                "Whether the event came from synthetic replay.",
                "analytics.export._value_event_rows",
            ),
            _field("run_id", "string", "n/a", "Synthetic run identifier when present.", "analytics.export._value_event_rows"),
        ),
    ),
    DatasetSpec(
        "value_scenarios",
        "Value scenarios",
        "Generated value scenario metrics from the assumptions ledger.",
        _value_scenario_rows,
        (
            _field("scenario_id", "string", "n/a", "Scenario identifier from the assumptions ledger.", "value.ledger.ValueScenarioMetric"),
            _field("label", "string", "n/a", "Scenario label.", "value.ledger.ValueScenarioMetric"),
            _field("confidence", "string", "n/a", "Scenario confidence label.", "value.ledger.ValueScenarioMetric"),
            _field("gross_annual_benefit_gbp", "number", "GBP/year", "Gross annual benefit estimate.", "value.ledger.ValueScenarioMetric"),
            _field("annual_opex_gbp", "number", "GBP/year", "Annual operating cost estimate.", "value.ledger.ValueScenarioMetric"),
            _field("net_annual_benefit_gbp", "number", "GBP/year", "Gross benefit less annual opex.", "value.ledger.ValueScenarioMetric"),
            _field("one_off_capex_gbp", "number", "GBP", "One-off implementation cost estimate.", "value.ledger.ValueScenarioMetric"),
            _field(
                "simple_payback_years",
                "number",
                "years",
                "Simple payback period, or blank when not positive.",
                "value.ledger.ValueScenarioMetric",
            ),
            _field("npv_gbp", "number", "GBP", "Net present value over the scenario horizon.", "value.ledger.ValueScenarioMetric"),
            _field("irr", "number", "ratio", "Internal rate of return, or blank when not computable.", "value.ledger.ValueScenarioMetric"),
            _field("horizon_years", "integer", "years", "Scenario evaluation horizon.", "value.ledger.ValueScenarioMetric"),
            _field("formula", "string", "n/a", "Formula used for the gross benefit calculation.", "value.ledger.ValueScenarioMetric"),
        ),
    ),
    DatasetSpec(
        "process_complexity",
        "Process complexity",
        "Process complexity and key-person-risk rows derived from approved process records.",
        _process_complexity_rows,
        (
            _field("id", "string", "n/a", "Process identifier.", "analytics.process_complexity"),
            _field("name", "string", "n/a", "Process name.", "analytics.process_complexity"),
            _field("source_title", "string", "n/a", "Source document title.", "analytics.process_complexity"),
            _field("domain", "string", "n/a", "Process domain label.", "analytics.process_complexity"),
            _field("process", "string", "n/a", "Process family label.", "analytics.process_complexity"),
            _field("complexity_score", "integer", "0-100", "Capped process complexity indicator.", "analytics.process_complexity"),
            _field("complexity_band", "string", "n/a", "Low, medium or high complexity band.", "analytics.process_complexity"),
            _field("key_person_risk_score", "integer", "0-100", "Capped key-person-risk indicator.", "analytics.process_complexity"),
            _field("key_person_risk_band", "string", "n/a", "Low, medium or high key-person-risk band.", "analytics.process_complexity"),
            _field("dominant_role", "string", "n/a", "Most common attributed rule owner.", "analytics.process_complexity"),
            _field("signals.roles", "integer", "count", "Number of roles identified in the process.", "analytics.process_complexity"),
            _field("signals.systems", "integer", "count", "Number of systems identified in the process.", "analytics.process_complexity"),
            _field("signals.dependencies", "integer", "count", "Number of process dependencies.", "analytics.process_complexity"),
            _field("signals.controls", "integer", "count", "Number of controls identified.", "analytics.process_complexity"),
            _field("signals.handoffs", "integer", "count", "Role hand-off count.", "analytics.process_complexity"),
            _field(
                "signals.exception_terms",
                "integer",
                "count",
                "Exception or manual-work wording count.",
                "analytics.process_complexity",
            ),
            _field(
                "signals.unclear_ownership",
                "integer",
                "count",
                "Rules or wording with unclear ownership.",
                "analytics.process_complexity",
            ),
            _field("signals.rules", "integer", "count", "Business rule count.", "analytics.process_complexity"),
            _field(
                "signals.dominant_role_share",
                "number",
                "ratio",
                "Share of attributed rules owned by the dominant role.",
                "analytics.process_complexity",
            ),
            _field("indicators", "json", "n/a", "Top explanatory indicators serialised as JSON.", "analytics.process_complexity"),
            _field("explanation", "string", "n/a", "Boundary note explaining the indicator limits.", "analytics.process_complexity"),
        ),
    ),
    DatasetSpec(
        "ontology_stats",
        "Ontology stats",
        "Current ontology object/link counts.",
        _ontology_stat_rows,
        (
            _field("object_counts", "json", "count", "Object counts by ontology object type.", "ontology.store.OntologyStore.counts"),
            _field("link_counts", "json", "count", "Link counts by ontology link type.", "ontology.store.OntologyStore.counts"),
            _field("total_objects", "integer", "count", "Total ontology object count.", "ontology.store.OntologyStore.counts"),
            _field("total_links", "integer", "count", "Total ontology link count.", "ontology.store.OntologyStore.counts"),
        ),
    ),
    DatasetSpec(
        "governance_history",
        "Governance history",
        "Governance issue lifecycle counts over time.",
        _governance_history_rows,
        (
            _field("date", "date", "YYYY-MM-DD", "Governance event day.", "analytics.governance_history"),
            _field("detected", "integer", "count", "Issues detected on the day.", "analytics.governance_history"),
            _field("accepted", "integer", "count", "Issues accepted on the day.", "analytics.governance_history"),
            _field("resolved", "integer", "count", "Issues resolved on the day.", "analytics.governance_history"),
            _field("open", "integer", "count", "Open detected issues after processing that day.", "analytics.governance_history"),
        ),
    ),
)
