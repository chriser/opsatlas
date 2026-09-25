#!/usr/bin/env python3
"""Run the statement-level governance review over the approved corpus (GOV S5-S7).

    python scripts/governance_statement_review.py [--judge-model qwen2.5:14b-instruct] [--workers 4]
                                                  [--second-opinion qwen3.5:35b-a3b]

Statements, embeddings and judgements are cached under <data>/governance/, so a second run over an unchanged
corpus is served from the cache and a changed document re-judges only its own pairs. The result is written to
<data>/governance/statement-review-latest.json.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from assistant.governance.statement_judge import OllamaJudge  # noqa: E402
from assistant.governance.statement_review import run_statement_review  # noqa: E402
from assistant.ingestion.store import SectionStore  # noqa: E402
from assistant.retrieval.embedder import OllamaEmbedder  # noqa: E402
from assistant.sources.register import SourceRegister  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', default=os.environ.get('KP_DATA_DIR', str(ROOT / 'data')))
    parser.add_argument('--ollama', default=os.environ.get('KP_OLLAMA_URL', 'http://127.0.0.1:11434'))
    parser.add_argument('--embed-model', default=os.environ.get('KP_EMBED_MODEL', 'nomic-embed-text'))
    parser.add_argument('--judge-model', default=os.environ.get('KP_GOVERNANCE_JUDGE_MODEL', 'qwen2.5:14b-instruct'))
    parser.add_argument('--think', action='store_true', help='let a reasoning model think before answering')
    parser.add_argument('--k', type=int, default=3)
    parser.add_argument('--k-same', type=int, default=1)
    parser.add_argument('--min-cosine', type=float, default=0.70)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--second-opinion', default='', help='a reasoning model that re-checks each conflict raised')
    args = parser.parse_args()
    data = Path(args.data)
    result = run_statement_review(
        SourceRegister(data), SectionStore(data), data, OllamaEmbedder(args.embed_model, args.ollama), args.embed_model,
        OllamaJudge(args.judge_model, args.ollama, think=args.think), args.judge_model + ('+think' if args.think else ''),
        k=args.k, k_same=args.k_same, min_cosine=args.min_cosine, workers=args.workers,
        progress=lambda done, total: print(f'  judged {done}/{total}', flush=True),
        reviewer=OllamaJudge(args.second_opinion, args.ollama, timeout=600, think=True) if args.second_opinion else None,
        reviewer_model=(args.second_opinion + '+think') if args.second_opinion else None)
    summary = {k: v for k, v in result.items() if k != 'findings'}
    for key, value in summary.items():
        print(f'{key}: {value}')


if __name__ == '__main__':
    main()
