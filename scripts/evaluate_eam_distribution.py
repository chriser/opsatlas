#!/usr/bin/env python3
"""Produce an EAM classification distribution report for the active ontology."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from assistant.eam import TaxonomyConfig, build_eam_model  # noqa: E402
from assistant.ontology import OntologyStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data", help="Directory containing ontology.db")
    parser.add_argument("--output-dir", default="docs/benchmark/eam", help="Directory for markdown/json reports")
    parser.add_argument("--unclassified-threshold", type=float, default=0.15)
    parser.add_argument("--dominant-column-threshold", type=float, default=0.65)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when guardrails fail")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    taxonomy = TaxonomyConfig.load()
    model = build_eam_model(OntologyStore(data_dir / "ontology.db"), taxonomy)
    report = build_distribution_report(
        model=model.model_dump(),
        taxonomy=taxonomy.model_dump(),
        unclassified_threshold=args.unclassified_threshold,
        dominant_column_threshold=args.dominant_column_threshold,
    )

    timestamp = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    safe_timestamp = timestamp.replace(":", "-")
    json_path = output_dir / f"eam-classification-distribution-{safe_timestamp}.json"
    md_path = output_dir / f"eam-classification-distribution-{safe_timestamp}.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    if args.strict and not report["passes"]:
        return 1
    return 0


def build_distribution_report(
    *,
    model: dict,
    taxonomy: dict,
    unclassified_threshold: float,
    dominant_column_threshold: float,
) -> dict:
    nodes = list(model["nodes"])
    process_count = len(nodes)
    stage_labels = {stage["id"]: stage["label"] for stage in taxonomy["lifecycle_stages"]}
    domain_labels = {domain["id"]: domain["label"] for domain in taxonomy["domains"]}
    stage_counts = Counter(node["lifecycle_id"] for node in nodes)
    domain_counts = Counter(node["domain_id"] for node in nodes)
    cell_counts = Counter((node["domain_id"], node["lifecycle_id"]) for node in nodes)
    unclassified_count = sum(1 for node in nodes if node["domain_id"] == "unclassified" or node["lifecycle_id"] == "unclassified")
    unclassified_rate = (unclassified_count / process_count) if process_count else 0.0
    empty_columns = [stage["id"] for stage in taxonomy["lifecycle_stages"] if stage_counts[stage["id"]] == 0]
    dominant_stage_id, dominant_stage_count = _most_common(stage_counts)
    dominant_column_share = (dominant_stage_count / process_count) if process_count else 0.0
    guards = {
        "unclassified_below_threshold": unclassified_rate < unclassified_threshold,
        "no_empty_columns": not empty_columns,
        "no_dominant_column": dominant_column_share <= dominant_column_threshold,
    }
    return {
        "schema": "eam-classification-distribution.v1",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "taxonomy_version": taxonomy["version"],
        "taxonomy_provenance": taxonomy.get("provenance", ""),
        "process_count": process_count,
        "guardrails": {
            "unclassified_threshold": unclassified_threshold,
            "dominant_column_threshold": dominant_column_threshold,
            **guards,
        },
        "passes": all(guards.values()),
        "unclassified_count": unclassified_count,
        "unclassified_rate": round(unclassified_rate, 4),
        "empty_columns": [{"id": stage_id, "label": stage_labels.get(stage_id, stage_id)} for stage_id in empty_columns],
        "dominant_column": {
            "id": dominant_stage_id,
            "label": stage_labels.get(dominant_stage_id, dominant_stage_id),
            "count": dominant_stage_count,
            "share": round(dominant_column_share, 4),
        },
        "stage_distribution": [
            {"id": stage["id"], "label": stage["label"], "count": stage_counts[stage["id"]]}
            for stage in taxonomy["lifecycle_stages"]
        ],
        "domain_distribution": [
            {"id": domain["id"], "label": domain["label"], "count": domain_counts[domain["id"]]}
            for domain in taxonomy["domains"]
        ],
        "cell_distribution": [
            {
                "domain_id": domain_id,
                "domain_label": domain_labels.get(domain_id, domain_id),
                "stage_id": stage_id,
                "stage_label": stage_labels.get(stage_id, stage_id),
                "count": count,
            }
            for (domain_id, stage_id), count in sorted(cell_counts.items(), key=lambda row: (-row[1], row[0][0], row[0][1]))
        ],
    }


def render_markdown(report: dict) -> str:
    outcome = "PASS" if report["passes"] else "REVIEW"
    lines = [
        "# EAM Classification Distribution",
        "",
        f"Generated: {report['generated_at']}",
        f"Taxonomy: {report['taxonomy_version']}",
        f"Outcome: **{outcome}**",
        "",
        report["taxonomy_provenance"],
        "",
        "## Guardrails",
        "",
        f"- Process count: {report['process_count']}",
        f"- Unclassified: {report['unclassified_count']} ({report['unclassified_rate']:.1%})",
        f"- Dominant column: {report['dominant_column']['label']} ({report['dominant_column']['share']:.1%})",
        f"- Empty columns: {', '.join(item['label'] for item in report['empty_columns']) or 'None'}",
        "",
        "## Stage Distribution",
        "",
        "| Stage | Count |",
        "|---|---:|",
    ]
    lines.extend(f"| {row['label']} | {row['count']} |" for row in report["stage_distribution"])
    lines.extend(["", "## Domain Distribution", "", "| Domain | Count |", "|---|---:|"])
    lines.extend(f"| {row['label']} | {row['count']} |" for row in report["domain_distribution"])
    lines.extend(["", "## Populated Cells", "", "| Domain | Stage | Count |", "|---|---|---:|"])
    lines.extend(
        f"| {row['domain_label']} | {row['stage_label']} | {row['count']} |"
        for row in report["cell_distribution"]
    )
    lines.append("")
    return "\n".join(lines)


def _most_common(counter: Counter) -> tuple[str, int]:
    if not counter:
        return "", 0
    return max(counter.items(), key=lambda row: (row[1], row[0]))


if __name__ == "__main__":
    raise SystemExit(main())
