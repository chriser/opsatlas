#!/usr/bin/env python3
"""Run hallucination-probe groundedness evaluation against the local app stack."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from assistant.api.app import create_app
from assistant.eval.grounding import evaluate_grounding, format_grounding_markdown


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="tests/evaluation/hallucination_probes.json")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()

    probes = json.loads(Path(args.dataset).read_text())
    app = create_app()
    report = evaluate_grounding(app.state.answer, probes)
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(format_grounding_markdown(report))


if __name__ == "__main__":
    main()
