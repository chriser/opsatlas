#!/usr/bin/env python3
"""Run the pre-registered RAG-vs-OAG benchmark."""

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

from assistant.eval.rag_vs_oag import (  # noqa: E402
    DEFAULT_CONFIGS,
    DEFAULT_LABELS_PATH,
    DEFAULT_OUTPUT_DIR,
    evaluate_rag_vs_oag,
    format_rag_vs_oag_markdown,
    load_rag_vs_oag_dataset,
    rescore_rag_vs_oag_report,
    write_rag_vs_oag_scorecard,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(DEFAULT_LABELS_PATH))
    parser.add_argument("--configs", default=",".join(DEFAULT_CONFIGS))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--fake-generator", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--rescore-existing", default="")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args()

    configs = tuple(item.strip() for item in args.configs.split(",") if item.strip())
    unsupported = sorted(set(configs) - set(DEFAULT_CONFIGS))
    if unsupported:
        raise SystemExit(f"Unsupported config(s): {', '.join(unsupported)}")

    dataset = load_rag_vs_oag_dataset(args.dataset)
    if args.rescore_existing:
        report = rescore_rag_vs_oag_report(json.loads(Path(args.rescore_existing).read_text()), dataset)
    else:
        report = evaluate_rag_vs_oag(
            dataset,
            configs=configs,
            runs=args.runs,
            fake_generator=args.fake_generator,
            limit=args.limit,
        )
    if not args.no_write:
        report["outputs"] = write_rag_vs_oag_scorecard(report, args.output_dir)

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(format_rag_vs_oag_markdown(report))
        if not args.no_write:
            print("")
            print(f"Markdown: {report['outputs']['markdown']}")
            print(f"JSON: {report['outputs']['json']}")


if __name__ == "__main__":
    main()
