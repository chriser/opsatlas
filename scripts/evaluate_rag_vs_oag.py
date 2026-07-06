#!/usr/bin/env python3
"""Run the pre-registered RAG-vs-OAG benchmark."""

from __future__ import annotations

import argparse
import json
import sys
import time
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
    parser.add_argument("--split", choices=("all", "tuning", "holdout"), default="all")
    parser.add_argument("--rescore-existing", default="")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--progress", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    configs = tuple(item.strip() for item in args.configs.split(",") if item.strip())
    unsupported = sorted(set(configs) - set(DEFAULT_CONFIGS))
    if unsupported:
        raise SystemExit(f"Unsupported config(s): {', '.join(unsupported)}")

    dataset = load_rag_vs_oag_dataset(args.dataset)
    if args.rescore_existing:
        report = rescore_rag_vs_oag_report(json.loads(Path(args.rescore_existing).read_text()), dataset)
    else:
        progress = _progress_printer() if args.progress else None
        report = evaluate_rag_vs_oag(
            dataset,
            configs=configs,
            runs=args.runs,
            fake_generator=args.fake_generator,
            limit=args.limit,
            split=args.split,
            progress=progress,
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


def _progress_printer():
    started = time.perf_counter()

    def progress(event: dict) -> None:
        event_type = event.get("event")
        if event_type == "start":
            model = event.get("model_info", {})
            model_label = " · ".join(
                str(value)
                for value in (model.get("backend"), model.get("llm"), model.get("embed"))
                if value
            )
            print(
                "[rag-vs-oag] starting "
                f"{event.get('total', 0)} rows "
                f"({event.get('runs')} run(s), {len(event.get('configs', []))} config(s), "
                f"{event.get('questions')} question(s), split={event.get('split')}, "
                f"fake={event.get('fake_generator')}, model={model_label or 'unknown'})",
                file=sys.stderr,
                flush=True,
            )
            return
        if event_type == "row_start":
            row_number = int(event.get("completed", 0)) + 1
            total = int(event.get("total", 0))
            print(
                "[rag-vs-oag] "
                f"{row_number}/{total} start "
                f"run={event.get('run')} config={event.get('config')} "
                f"id={event.get('id')} split={event.get('split')} category={event.get('category')}",
                file=sys.stderr,
                flush=True,
            )
            return
        if event_type == "row_end":
            completed = int(event.get("completed", 0))
            total = int(event.get("total", 0))
            percent = (completed / total * 100.0) if total else 0.0
            elapsed = time.perf_counter() - started
            rate = elapsed / completed if completed else 0.0
            remaining = max(0.0, (total - completed) * rate) if rate else 0.0
            mark = "pass" if event.get("passed") else "fail"
            print(
                "[rag-vs-oag] "
                f"{completed}/{total} done ({percent:.1f}%) "
                f"run={event.get('run')} config={event.get('config')} id={event.get('id')} "
                f"path={event.get('answer_path')} result={mark} "
                f"row={float(event.get('latency_seconds', 0.0)):.1f}s "
                f"elapsed={_duration_label(elapsed)} eta={_duration_label(remaining)}",
                file=sys.stderr,
                flush=True,
            )

    return progress


def _duration_label(seconds: float) -> str:
    whole = max(0, int(round(seconds)))
    minutes, sec = divmod(whole, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{sec:02d}s"
    if minutes:
        return f"{minutes}m{sec:02d}s"
    return f"{sec}s"


if __name__ == "__main__":
    main()
