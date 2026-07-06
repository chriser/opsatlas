"""Raw analytics dataset export helpers."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable
from dataclasses import dataclass
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
    return [event.model_dump() for event in _events(context)]


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
    return [context.ontology_store.counts()]


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


DATASET_SPECS: tuple[DatasetSpec, ...] = (
    DatasetSpec("usage_log", "Usage log", "Assistant usage events recorded by the local usage log.", _usage_rows),
    DatasetSpec("events", "Analytics events", "Append-only analytics event ledger.", _event_rows),
    DatasetSpec(
        "knowledge_gap_clusters",
        "Knowledge-gap clusters",
        "Deterministic clusters derived from refused and weakly grounded questions.",
        _knowledge_gap_rows,
    ),
    DatasetSpec("value_events", "Value events", "Operator-estimated or synthetic value telemetry events.", _value_event_rows),
    DatasetSpec(
        "value_scenarios",
        "Value scenarios",
        "Generated value scenario metrics from the assumptions ledger.",
        _value_scenario_rows,
    ),
    DatasetSpec(
        "process_complexity",
        "Process complexity",
        "Process complexity and key-person-risk rows derived from approved process records.",
        _process_complexity_rows,
    ),
    DatasetSpec("ontology_stats", "Ontology stats", "Current ontology object/link counts.", _ontology_stat_rows),
    DatasetSpec(
        "governance_history",
        "Governance history",
        "Governance issue lifecycle counts over time.",
        _governance_history_rows,
    ),
)
