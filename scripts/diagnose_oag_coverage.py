#!/usr/bin/env python3
"""Diagnose whether missed RAG-vs-OAG facts exist in the ontology store."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from assistant.eval.oag_coverage import (  # noqa: E402
    coverage_report_from_paths,
    format_oag_coverage_markdown,
    write_oag_coverage_report,
)
from assistant.eval.rag_vs_oag import DEFAULT_LABELS_PATH, DEFAULT_OUTPUT_DIR  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", help="RAG-vs-OAG benchmark JSON report to diagnose.")
    parser.add_argument("--dataset", default=str(DEFAULT_LABELS_PATH))
    parser.add_argument("--ontology-db", default="data/ontology.db")
    parser.add_argument("--config", default="oag_first")
    parser.add_argument("--split", default="holdout")
    parser.add_argument("--all-facts", action="store_true", help="Analyse all expected facts, not just missed facts.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args()

    report = coverage_report_from_paths(
        args.report,
        dataset_path=args.dataset,
        ontology_db_path=args.ontology_db,
        config=args.config,
        split=args.split,
        only_failed=not args.all_facts,
    )
    if not args.no_write:
        report["outputs"] = write_oag_coverage_report(report, args.output_dir)

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(format_oag_coverage_markdown(report))
        if not args.no_write:
            print("")
            print(f"Markdown: {report['outputs']['markdown']}")
            print(f"JSON: {report['outputs']['json']}")


if __name__ == "__main__":
    main()
