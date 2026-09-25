"""Statement-level governance review: statements, candidates, one judgement each (GOV S5-S7).

    statements = StatementStore(...).sync(register, section_store)       # extracted once per source version
    candidates = StatementIndex(...).candidates(statements)              # nearest statements, not document pairs
    judgements = judge_candidates(candidates, judge, cache)              # one cached judgement per pair

A finding quotes both statements with their sources. Conflicts are raised across documents and between
sections of one document (a document contradicting itself). Duplicates are raised only across documents: a
document restating itself, as an overview restates its rules, is recorded but not raised.

Second opinion (optional; rule fixed 25 September 2026 before its test): each conflict the judge raises is put to
a second, reasoning judge. The conflict is raised only if the second judge also calls it a conflict; if the
second judge gives no answer, the first verdict stands, so a true conflict is never lost to a timeout. Dismissed
conflicts stay in the result, with both verdicts, for audit.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .statement_index import StatementIndex
from .statement_judge import PROMPT_VERSION, JudgementCache, judge_candidates
from .statements import StatementStore


def finding_key(a_id: str, b_id: str) -> str:
    return hashlib.sha256(('statement-pair\u0000' + '\u0000'.join(sorted((a_id, b_id)))).encode()).hexdigest()[:16]


def run_statement_review(register, section_store, base_dir: str | Path, embedder, embed_model: str, judge, judge_model: str, *,
                         k: int = 3, k_same: int = 1, min_cosine: float = 0.70, exclude_sources: set[str] = frozenset(),
                         workers: int = 4, progress=None, reviewer=None, reviewer_model: str | None = None) -> dict:
    base_dir = Path(base_dir)
    started = time.perf_counter()
    statements, sync = StatementStore(base_dir).sync(register, section_store)
    index = StatementIndex(base_dir, embedder, embed_model)
    candidates, index_stats = index.candidates(statements, k=k, k_same=k_same, min_cosine=min_cosine, exclude_sources=exclude_sources)
    indexed = time.perf_counter() - started
    judgements, judge_stats = judge_candidates(candidates, judge, JudgementCache(base_dir), judge_model, workers=workers, progress=progress)
    findings, restated = [], 0
    for candidate, judgement in zip(candidates, judgements):
        if not judgement or judgement['relation'] == 'neither':
            continue
        if judgement['relation'] == 'duplicate' and candidate.same_document:
            restated += 1
            continue
        findings.append({'key': finding_key(candidate.a.id, candidate.b.id), 'relation': judgement['relation'],
                         'reason': judgement['reason'], 'cosine': candidate.cosine, 'same_document': candidate.same_document,
                         'statements': [asdict(candidate.a), asdict(candidate.b)]})
    dismissed, second = [], None
    if reviewer is not None:
        by_key = {finding_key(c.a.id, c.b.id): c for c in candidates}
        pairs = [(by_key[f['key']], f) for f in findings if f['relation'] == 'conflict']
        verdicts, second = judge_candidates([c for c, _ in pairs], reviewer, JudgementCache(base_dir), reviewer_model, workers=1)
        for (_, finding), verdict in zip(pairs, verdicts):
            finding['second_opinion'] = verdict and {k: verdict[k] for k in ('relation', 'reason', 'model')}
            if verdict and verdict['relation'] != 'conflict':
                dismissed.append(finding)
        findings = [f for f in findings if f not in dismissed]
    findings.sort(key=lambda f: (f['relation'] != 'conflict', -f['cosine']))
    result = {
        'engine': 'statement-review', 'prompt_version': PROMPT_VERSION, 'judge_model': judge_model, 'embed_model': embed_model,
        'finished_at': datetime.now(timezone.utc).isoformat(), 'settings': {'k': k, 'k_same': k_same, 'min_cosine': min_cosine,
                                                                            'excluded_sources': sorted(exclude_sources)},
        'statements': len(statements), 'sync': sync, 'index': index_stats, 'judging': judge_stats,
        'index_seconds': round(indexed, 1), 'total_seconds': round(time.perf_counter() - started, 1),
        'raised': {r: sum(1 for f in findings if f['relation'] == r) for r in ('conflict', 'duplicate')},
        'restated_within_a_document': restated, 'second_opinion': second and {**second, 'model': reviewer_model,
                                                                              'dismissed': len(dismissed)},
        'dismissed_by_second_opinion': dismissed, 'findings': findings,
    }
    path = base_dir / 'governance' / 'statement-review-latest.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=1))
    return result
