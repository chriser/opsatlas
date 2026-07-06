"""Ontology coverage diagnostics for RAG-vs-OAG benchmark failures."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from assistant.ontology.query import OntologyQueryService
from assistant.ontology.store import OntologyStore

from .rag_vs_oag import (
    DEFAULT_LABELS_PATH,
    DEFAULT_OUTPUT_DIR,
    ExpectedFact,
    RagVsOagDataset,
    _best_fact_match,
    _content_tokens,
    _normalise_text,
    load_rag_vs_oag_dataset,
)

CoverageStatus = Literal["present", "partial", "absent"]


@dataclass(frozen=True)
class OntologyCandidate:
    object_id: str
    object_type: str
    candidate_type: str
    label: str
    text: str


def build_oag_coverage_report(
    benchmark_report: dict[str, Any],
    dataset: RagVsOagDataset,
    query: OntologyQueryService,
    *,
    config: str = "oag_first",
    split: str = "holdout",
    only_failed: bool = True,
) -> dict[str, Any]:
    """Compare missed benchmark facts with ontology object/link content."""

    labels = {label.id: label for label in dataset.questions}
    candidates = _ontology_candidates(query)
    source_rows = [
        row
        for row in benchmark_report.get("rows", [])
        if row.get("config") == config
        and row.get("split") == split
        and (not only_failed or not row.get("passed", False))
    ]
    coverage_rows: list[dict[str, Any]] = []
    for row in source_rows:
        label = labels.get(str(row.get("id", "")))
        if label is None:
            continue
        missed = set(row.get("facts_missed") or [])
        facts = _facts_for_row(label.expected_answer_facts, missed, only_failed=only_failed)
        for fact in facts:
            coverage_rows.append(
                {
                    "id": label.id,
                    "category": label.category,
                    "question": label.question,
                    "config": row.get("config", ""),
                    "answer_path": row.get("answer_path", ""),
                    "expected_fact": fact.text,
                    **_best_ontology_coverage(fact, candidates),
                }
            )

    counts = Counter(row["coverage_status"] for row in coverage_rows)
    return {
        "summary": {
            "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "benchmark_generated_at": benchmark_report.get("summary", {}).get("generated_at", ""),
            "benchmark_dataset_version": benchmark_report.get("summary", {}).get("dataset_version", ""),
            "benchmark_code_state": benchmark_report.get("summary", {}).get("code_state", {}),
            "config_filter": config,
            "split_filter": split,
            "only_failed": only_failed,
            "analysed_fact_count": len(coverage_rows),
            "coverage_counts": dict(sorted(counts.items())),
            "ontology_candidate_count": len(candidates),
            "diagnostic_purpose": "content coverage: decide whether OAG misses are ontology content gaps or retrieval/routing gaps",
        },
        "rows": coverage_rows,
    }


def load_ontology_query(db_path: str | Path = "data/ontology.db") -> OntologyQueryService:
    """Load the read-only query service used by the coverage diagnostic."""

    return OntologyQueryService(OntologyStore(db_path))


def format_oag_coverage_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    counts = summary.get("coverage_counts", {})
    lines = [
        "# OAG Ontology Coverage Diagnostic",
        "",
        f"Generated: {summary['generated_at']}",
        f"Benchmark generated: {summary.get('benchmark_generated_at') or 'n/a'}",
        f"Dataset: {summary.get('benchmark_dataset_version') or 'n/a'}",
        f"Config filter: {summary['config_filter']}",
        f"Split filter: {summary['split_filter']}",
        f"Only failed rows: {summary['only_failed']}",
        f"Analysed facts: {summary['analysed_fact_count']}",
        "Coverage counts: "
        + ", ".join(f"{name}={counts[name]}" for name in sorted(counts))
        if counts
        else "Coverage counts: none",
        f"Ontology candidates inspected: {summary['ontology_candidate_count']}",
        "",
        "## Coverage Table",
        "",
        "| ID | Category | Status | Coverage | Missing Tokens | Best Ontology Candidate | Expected Fact |",
        "|---|---|---|---:|---|---|---|",
    ]
    for row in report["rows"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["id"],
                    row["category"],
                    row["coverage_status"],
                    f"{row['token_coverage']:.0%}",
                    _cell(", ".join(row.get("missing_tokens", [])) or "n/a"),
                    _cell(row.get("best_candidate_label") or "n/a"),
                    _cell(row["expected_fact"]),
                ]
            )
            + " |"
        )
    if not report["rows"]:
        lines.append("| n/a | n/a | n/a | 0% | n/a | n/a | No rows matched the diagnostic filters. |")
    lines.extend(
        [
            "",
            "## How To Read This",
            "",
            "- `present` means the expected fact text or an alias was found directly in ontology object/link text.",
            "- `partial` means related ontology text exists, but key tokens are missing; this usually points to a content enrichment gap.",
            "- `absent` means the diagnostic could not find enough ontology content to support the expected fact.",
            "- If most misses are `partial` or `absent`, prioritise ontology sync/schema enrichment before routing changes.",
        ]
    )
    return "\n".join(lines)


def write_oag_coverage_report(
    report: dict[str, Any],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stamp = report["summary"]["generated_at"].replace(":", "-")
    base = output / f"oag-coverage-diagnostic-{stamp}"
    json_path = base.with_suffix(".json")
    md_path = base.with_suffix(".md")
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(format_oag_coverage_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def coverage_report_from_paths(
    benchmark_report_path: str | Path,
    *,
    dataset_path: str | Path = DEFAULT_LABELS_PATH,
    ontology_db_path: str | Path = "data/ontology.db",
    config: str = "oag_first",
    split: str = "holdout",
    only_failed: bool = True,
) -> dict[str, Any]:
    benchmark_report = json.loads(Path(benchmark_report_path).read_text(encoding="utf-8"))
    dataset = load_rag_vs_oag_dataset(dataset_path)
    query = load_ontology_query(ontology_db_path)
    return build_oag_coverage_report(
        benchmark_report,
        dataset,
        query,
        config=config,
        split=split,
        only_failed=only_failed,
    )


def _facts_for_row(
    facts: list[ExpectedFact],
    missed: set[str],
    *,
    only_failed: bool,
) -> list[ExpectedFact]:
    if only_failed and missed:
        return [fact for fact in facts if fact.text in missed]
    return list(facts)


def _best_ontology_coverage(fact: ExpectedFact, candidates: list[OntologyCandidate]) -> dict[str, Any]:
    best: dict[str, Any] = {
        "coverage_status": "absent",
        "match_method": "none",
        "token_coverage": 0.0,
        "missing_tokens": _content_tokens(fact.text),
        "matched_variant": "",
        "best_candidate_id": "",
        "best_candidate_type": "",
        "best_candidate_label": "",
        "best_candidate_text": "",
    }
    for candidate in candidates:
        match = _best_fact_match([fact.text, *fact.aliases], _normalise_text(candidate.text), set(_content_tokens(candidate.text)))
        if _is_better_match(match, best):
            status: CoverageStatus
            if match["match_method"] == "exact" or (
                match["token_coverage"] >= 1.0 and not match["missing_tokens"]
            ):
                status = "present"
            elif match["hit"] or match["token_coverage"] >= 0.5:
                status = "partial"
            else:
                status = "absent"
            best = {
                "coverage_status": status,
                "match_method": match["match_method"],
                "token_coverage": match["token_coverage"],
                "missing_tokens": match["missing_tokens"],
                "matched_variant": match["matched_variant"],
                "best_candidate_id": candidate.object_id,
                "best_candidate_type": candidate.candidate_type,
                "best_candidate_label": f"{candidate.object_type}/{candidate.label}",
                "best_candidate_text": candidate.text[:500],
            }
    return best


def _is_better_match(match: dict[str, Any], best: dict[str, Any]) -> bool:
    if match["hit"] and not best.get("match_method") == "exact":
        return True
    if match["match_method"] == "exact" and best.get("match_method") != "exact":
        return True
    return float(match["token_coverage"]) > float(best.get("token_coverage", 0.0))


def _ontology_candidates(query: OntologyQueryService) -> list[OntologyCandidate]:
    candidates: list[OntologyCandidate] = []
    for object_def in query.schema().get("object_types", []):
        object_type = str(object_def.get("api_name") or "")
        if not object_type:
            continue
        for item in query.find_objects(object_type):
            detail = query.get_object(item["id"]) or item
            label = _label(detail)
            candidates.append(
                OntologyCandidate(
                    object_id=detail["id"],
                    object_type=object_type,
                    candidate_type="object_properties",
                    label=label,
                    text=_object_text(detail),
                )
            )
            candidates.extend(_link_candidates(detail, label))
    return candidates


def _link_candidates(item: dict[str, Any], label: str) -> list[OntologyCandidate]:
    candidates: list[OntologyCandidate] = []
    neighbors = item.get("neighbors")
    if not isinstance(neighbors, dict):
        return candidates
    for link_type, grouped in neighbors.items():
        if not isinstance(grouped, dict):
            continue
        for direction, values in grouped.items():
            if not isinstance(values, list):
                continue
            for neighbor in values:
                if not isinstance(neighbor, dict):
                    continue
                neighbor_label = _label(neighbor)
                candidates.append(
                    OntologyCandidate(
                        object_id=item["id"],
                        object_type=item["object_type"],
                        candidate_type=f"link_{direction}",
                        label=f"{label} {link_type} {neighbor_label}",
                        text=f"{label} {link_type} {neighbor_label}. {_object_text(item)} {_object_text(neighbor)}",
                    )
                )
    return candidates


def _object_text(item: dict[str, Any]) -> str:
    values = [str(item.get("primary_key_value", "")), str(item.get("citation", ""))]
    for value in item.get("properties", {}).values():
        if isinstance(value, list):
            values.extend(str(child) for child in value)
        else:
            values.append(str(value))
    return " ".join(values)


def _label(item: dict[str, Any]) -> str:
    properties = item.get("properties", {})
    return str(properties.get("name") or properties.get("title") or item.get("primary_key_value") or item["id"])


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()
