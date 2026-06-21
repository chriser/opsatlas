"""Automated evaluation harness.

Loads one or more knowledge packs, runs a question set through the full assistant
stack, scores against the rubric, and writes a report. Repeatable for the real
packs and for A/B-ing models.

Usage:
  PYTHONPATH=src .venv/bin/python automation/evaluate.py \
      --pack docs/benchmark/supplier-setup-pack.md \
      --questions docs/benchmark/questions.json \
      [--llm qwen3:30b-a3b] [--no-rewrite] [--no-rerank] [--out report.json]
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", nargs="+", default=["docs/benchmark/supplier-setup-pack.md"])
    ap.add_argument("--questions", default="docs/benchmark/questions.json")
    ap.add_argument("--out", default=None)
    ap.add_argument("--llm", default=None)
    ap.add_argument("--embed", default=None)
    ap.add_argument("--no-rewrite", action="store_true")
    ap.add_argument("--no-rerank", action="store_true")
    args = ap.parse_args()

    if args.llm:
        os.environ["KP_LLM_MODEL"] = args.llm
    if args.embed:
        os.environ["KP_EMBED_MODEL"] = args.embed

    from assistant.answer.service import AnswerService
    from assistant.eval.runner import format_markdown, run_eval
    from assistant.ingestion.service import ingest_source
    from assistant.ingestion.store import SectionStore
    from assistant.models.provider import provider_from_env
    from assistant.retrieval.embedder import EmbeddingCache
    from assistant.retrieval.rerank import LLMReranker
    from assistant.retrieval.rewrite import QueryRewriter
    from assistant.retrieval.service import RetrievalService
    from assistant.sources.register import SourceRegister
    from assistant.sources.service import register_upload

    data_dir = tempfile.mkdtemp(prefix="kp-eval-")
    register = SourceRegister(data_dir)
    store = SectionStore(register.base_dir)
    for pack in args.pack:
        path = Path(pack)
        record = register_upload(register, path.name, path.read_bytes(), title=path.stem)
        ingest_source(register, store, record.id)
        register.update(record.id, approval_status="approved")

    provider = provider_from_env()
    retrieval = RetrievalService(
        register, store, embedder=provider, cache=EmbeddingCache(register.base_dir),
        rewriter=None if args.no_rewrite else QueryRewriter(provider),
        reranker=None if args.no_rerank else LLMReranker(provider),
    )
    answer = AnswerService(retrieval, provider)

    questions = json.loads(Path(args.questions).read_text())
    print(f"Running {len(questions)} questions against {provider.info()} …\n")
    report = run_eval(answer, questions)
    report["models"] = provider.info()
    print(format_markdown(report))
    print(f"\nAccuracy: {report['summary']['accuracy']:.0%}  ({report['summary']['passed']}/{report['summary']['total']})")

    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2))
        print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
