#!/usr/bin/env python3
"""Run compliance-reasoning evaluation against labelled evidence pairs."""

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

from assistant.eval.compliance_reasoning import (  # noqa: E402
    DEFAULT_LABELS_PATH,
    DEFAULT_OUTPUT_DIR,
    evaluate_compliance_reasoning,
    format_compliance_markdown,
    load_compliance_labels,
    write_compliance_scorecard,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(DEFAULT_LABELS_PATH))
    parser.add_argument("--depth", choices=("fast", "balanced", "deep"), default="deep")
    parser.add_argument("--model", default="")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--fake-generator", action="store_true")
    parser.add_argument("--throttle-deep", action="store_true")
    parser.add_argument("--disable-safety-gates", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()

    labels = load_compliance_labels(args.dataset)
    if args.limit > 0:
        labels = labels[: args.limit]
    report = evaluate_compliance_reasoning(
        labels,
        depth=args.depth,
        model=args.model,
        runs=args.runs,
        fake_generator=args.fake_generator,
        throttle_deep=args.throttle_deep,
        disable_safety_gates=args.disable_safety_gates,
    )
    if not args.no_write:
        paths = write_compliance_scorecard(report, args.output_dir)
        report["outputs"] = paths
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(format_compliance_markdown(report))
        if not args.no_write:
            print("")
            print(f"Markdown: {report['outputs']['markdown']}")
            print(f"JSON: {report['outputs']['json']}")


if __name__ == "__main__":
    main()
