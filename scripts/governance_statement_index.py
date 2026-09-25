#!/usr/bin/env python3
"""Statement-index candidate generation for governance checks, measured against the current document-pair design.

Every bullet, table row and sentence of the approved corpus (data/) is a statement. Each statement is embedded once
with the platform's embedding model; a statement's candidates are its k nearest statements in other documents.
The planted conflicts and duplicates of tests/evaluation/governance_pair_benchmark.json are inserted into their
documents to measure recall, and the 31 human-dismissed real findings to measure how much noise is still put forward.
The current Full Governance Review extractor is run on the same corpus to show which statements it can see.

This script is the review's measurement tool (25 September 2026). The engine built from it is
assistant.governance.statement_review (scripts/governance_statement_review.py).

    python scripts/governance_statement_index.py
    python scripts/governance_statement_index.py --trial qwen2.5:14b-instruct   # the whole pipeline on the real corpus
    python scripts/governance_statement_index.py --filter docs/benchmark/governance/pipeline-trial-qwen2.5_14b-instruct.json
"""
from __future__ import annotations

import collections
import json
import math
import os
import re
import sys
import time
from pathlib import Path

import httpx
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / 'src'):
    sys.path.insert(0, str(path))
from services.compliance_reasoning.engine import extract_internal_claims  # noqa: E402
from services.compliance_reasoning.models import EvidenceDocument, EvidenceSection  # noqa: E402

DATA = Path(os.environ.get('KP_DATA_DIR', ROOT / 'data'))
OUTPUT = Path(os.environ.get('GOVERNANCE_BENCHMARK_OUTPUT', ROOT / 'docs/benchmark/governance'))
CACHE = ROOT / '.runtime/governance-benchmark/embed-cache.json'
OLLAMA = os.environ.get('KP_OLLAMA_URL', 'http://127.0.0.1:11434')
MODEL = os.environ.get('KP_EMBED_MODEL', 'nomic-embed-text')
# Sections the Full Governance Review payload also leaves out.
SKIP = ('json-style learning records', 'open questions and design decisions', 'suggested tagging structure')
HEADER_CELLS = ('role', 'step', 'system', 'question', '#', 'no.', 'system / data', 'dependency')


def corpus():
    register = json.loads((DATA / 'source_register.json').read_text())
    rows = register if isinstance(register, list) else register.get('sources', register)
    rows = rows if isinstance(rows, list) else list(rows.values())
    docs = {}
    for row in rows:
        if row.get('approval_status') != 'approved':
            continue
        sections = json.loads((DATA / f"sections/{row['id']}.json").read_text())
        sections = sections if isinstance(sections, list) else sections.get('sections', [])
        docs[row['title']] = [(s['heading'], s['text']) for s in sections if not any(k in s['heading'].lower() for k in SKIP)]
    return docs


def units(text):
    """Every bullet, table row and sentence, whatever its grammar."""
    out = []
    for line in (raw.strip() for raw in text.splitlines()):
        if not line or line.startswith('#') or re.fullmatch(r'\|?[\s:|-]+\|?', line):
            continue
        if line.startswith('|'):
            cells = [c.strip() for c in line.strip('|').split('|')]
            if cells and cells[0].lower() not in HEADER_CELLS:
                out.append(' | '.join(cells))
            continue
        line = re.sub(r'^[-*•]\s+|^\d+[.)]\s+', '', line)
        out.extend(s for s in re.split(r'(?<=[.!?])\s+(?=[A-Z])', line) if len(s.split()) >= 5)
    return out


def embed(texts):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    key = lambda t: MODEL + '\u0000' + t  # noqa: E731 - vectors from different models never mix
    todo = [t for t in dict.fromkeys(texts) if key(t) not in cache]
    with httpx.Client(timeout=60, trust_env=False) as client:
        for i in range(0, len(todo), 64):
            batch = todo[i:i + 64]
            vectors = client.post(f'{OLLAMA}/api/embed', json={'model': MODEL, 'input': batch}).json()['embeddings']
            cache.update((key(t), v) for t, v in zip(batch, vectors))
    CACHE.write_text(json.dumps(cache))
    out = []
    for t in texts:
        v = cache[key(t)]
        n = math.sqrt(sum(x * x for x in v)) or 1
        out.append([x / n for x in v])
    return np.array(out)


def trial(model: str, k: int = 3, threshold: float = 0.7, workers: int = 4) -> None:
    """Run the proposed pipeline over the real corpus (no planted items): index, candidates, one judge call each.

    The 2026-07-18 Full Governance Review of this corpus took 35 h 23 m and a person found no material contradiction,
    so every conflict raised here is either a genuine miss of that review or a false alarm, and is listed for review.
    """
    from concurrent.futures import ThreadPoolExecutor
    sys.path.insert(0, str(ROOT / 'scripts'))
    from evaluate_governance_pairs import PROMPT, SCHEMA

    docs = corpus()
    started = time.perf_counter()
    rows = [(title, heading, u) for title, sections in docs.items() for heading, text in sections for u in units(text)]
    M = embed([u for _, _, u in rows])
    owner = np.array([t for t, _, _ in rows])
    sims = M @ M.T
    sims[np.equal.outer(owner, owner)] = -1
    top = np.argsort(-sims, axis=1)[:, :k]
    candidates = sorted({tuple(sorted((a, int(b)))) for a in range(len(rows)) for b in top[a] if sims[a, b] >= threshold})
    indexed = time.perf_counter() - started

    def judge(pair):
        a, b = pair
        body = {'statement_a': {'document': rows[a][0], 'section': rows[a][1], 'text': rows[a][2]},
                'statement_b': {'document': rows[b][0], 'section': rows[b][1], 'text': rows[b][2]}}
        with httpx.Client(timeout=300, trust_env=False) as client:
            data = client.post(f'{OLLAMA}/api/chat', json={
                'model': model, 'stream': False, 'keep_alive': '10m', 'format': SCHEMA, 'think': False,
                'options': {'temperature': 0, 'num_ctx': 4096, 'num_predict': 160},
                'messages': [{'role': 'system', 'content': PROMPT}, {'role': 'user', 'content': json.dumps(body)}]}).json()
        value = json.loads(data['message']['content'])
        return {**body, 'relation': value.get('relation'), 'reason': value.get('reason'), 'cosine': round(float(sims[a, b]), 3)}

    started = time.perf_counter()
    with ThreadPoolExecutor(workers) as pool:
        judged = list(pool.map(judge, candidates))
    judged_seconds = time.perf_counter() - started
    raised = [j for j in judged if j['relation'] in ('conflict', 'duplicate')]
    out = {'model': model, 'k': k, 'min_cosine': threshold, 'workers': workers, 'documents': len(docs), 'statements': len(rows),
           'candidates': len(candidates), 'index_seconds': round(indexed, 1), 'judge_seconds': round(judged_seconds, 1),
           'raised': collections.Counter(j['relation'] for j in raised), 'findings': raised}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / f"pipeline-trial-{model.replace(':', '_')}.json").write_text(json.dumps(out, indent=1))
    print({k: v for k, v in out.items() if k != 'findings'})


def normalised(text):
    return re.sub(r'[*_`]', '', text).strip().lower()


def derived(side):
    """Restatements, not knowledge: a pack's Realistic Q&A pairs, and the preamble before its numbered sections."""
    return 'q&a' in side['section'].lower() or not re.match(r'^\d+\.', side['section'])


def filter_findings(path: Path) -> None:
    """Two generic filters, chosen after the first trial and reported as such. They mirror existing platform rules
    (Quick Scan drops text repeated across sources; the review payload drops derived sections) and are checked
    against the benchmark: neither may remove a planted conflict or duplicate."""
    trial_run = json.loads(path.read_text())
    spread = collections.defaultdict(set)
    for title, sections in corpus().items():
        for _, text in sections:
            for u in units(text):
                spread[normalised(u)].add(title)
    template = {t for t, where in spread.items() if len(where) >= 3}

    def noise(side):
        return derived(side) or normalised(side['text']) in template
    kept = [f for f in trial_run['findings'] if not (noise(f['statement_a']) or noise(f['statement_b']))]
    bench = json.loads((ROOT / 'tests/evaluation/governance_pair_benchmark.json').read_text())['items']
    removed = [i['id'] for i in bench if i['label'] != 'neither' and (noise(i['a']) or noise(i['b']))]
    out = {'source': path.name, 'template_lines': len(template),
           'filters': ["statements in derived sections: a pack's Realistic Q&A pairs and the preamble before its numbered sections",
                       'statements repeated verbatim in 3 or more documents (template text)'],
           'benchmark_positives_removed': removed,
           'raised_before': collections.Counter(f['relation'] for f in trial_run['findings']),
           'raised_after': collections.Counter(f['relation'] for f in kept), 'findings': kept}
    target = path.with_name(path.stem + '-filtered.json')
    target.write_text(json.dumps(out, indent=1))
    print({k: v for k, v in out.items() if k != 'findings'})


def main() -> None:
    if len(sys.argv) > 2 and sys.argv[1] == '--trial':
        trial(sys.argv[2])
        return
    if len(sys.argv) > 2 and sys.argv[1] == '--filter':
        filter_findings(Path(sys.argv[2]))
        return
    bench = json.loads((ROOT / 'tests/evaluation/governance_pair_benchmark.json').read_text())['items']
    planted = [i for i in bench if i['kind'] in ('conflict', 'duplicate')]
    real = [i for i in bench if i['kind'] == 'real_finding' and not i.get('exclude')]
    docs = corpus()
    extra = collections.defaultdict(list)
    for item in planted:
        for side in ('a', 'b'):
            extra[item[side]['document']].append((item[side]['section'], item[side]['text']))

    statements = [(title, u) for title, sections in docs.items() for _, text in sections for u in units(text)]
    with_planted = [(title, u) for title, sections in docs.items() for _, text in [*sections, *extra.get(title, [])]
                    for u in units(text)]
    engine_texts = set()
    for title, sections in docs.items():
        doc = EvidenceDocument(id=title, title=title, source_type='internal', sections=[
            EvidenceSection(id=f'{title}-{n}', heading=h, text=t) for n, (h, t) in enumerate([*sections, *extra.get(title, [])])])
        engine_texts |= {c.evidence.text for c in extract_internal_claims([doc])}
    engine_sees = sum(1 for i in planted if i['a']['text'] in engine_texts and i['b']['text'] in engine_texts)

    started = time.perf_counter()
    M = embed([t for _, t in with_planted])
    embed_seconds = time.perf_counter() - started
    owner = [d for d, _ in with_planted]
    where = collections.defaultdict(list)
    for n, (_, t) in enumerate(with_planted):
        where[t].append(n)
    sims = M @ M.T
    sims[np.equal.outer(np.array(owner), np.array(owner))] = -1  # candidates come from other documents

    def pairs(k, threshold=None):
        top = np.argsort(-sims, axis=1)[:, :k]
        return {tuple(sorted((a, int(b)))) for a in range(len(owner)) for b in top[a]
                if threshold is None or sims[a, b] >= threshold}

    def found(candidates, item):
        return any(tuple(sorted((x, y))) in candidates for x in where[item['a']['text']] for y in where[item['b']['text']])

    Qa, Qb = embed([i['a']['text'] for i in real]), embed([i['b']['text'] for i in real])

    def real_put_forward(candidates):
        count = 0
        for item, va, vb in zip(real, Qa, Qb):
            ia = [n for n in range(len(owner)) if owner[n] == item['a']['document']]
            ib = [n for n in range(len(owner)) if owner[n] == item['b']['document']]
            if ia and ib:
                na, nb = max(ia, key=lambda n: float(M[n] @ va)), max(ib, key=lambda n: float(M[n] @ vb))
                count += tuple(sorted((na, nb))) in candidates
        return count

    per_doc = collections.Counter(d for d, _ in statements)
    names = list(per_doc)
    result = {
        'documents': len(docs), 'statements': len(statements), 'embedding_model': MODEL,
        'embedding_seconds_all_statements': round(embed_seconds, 1),
        'document_pairs': len(docs) * (len(docs) - 1) // 2,
        'cross_document_statement_pairs': sum(per_doc[a] * per_doc[b] for i, a in enumerate(names) for b in names[i + 1:]),
        'planted_conflicts_and_duplicates': len(planted),
        'planted_within_one_document': sum(1 for i in planted if i['a']['document'] == i['b']['document']),
        'current_extractor_sees_both_sides': engine_sees,
        'real_dismissed_findings': len(real),
        'index': [],
    }
    for k, threshold in ((3, None), (5, None), (10, None), (3, 0.7), (3, 0.75), (3, 0.8)):
        candidates = pairs(k, threshold)
        result['index'].append({'k': k, 'min_cosine': threshold, 'candidate_pairs': len(candidates),
                                'planted_found': sum(found(candidates, i) for i in planted),
                                'real_dismissed_put_forward': real_put_forward(candidates)})
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / 'statement-index.json').write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1))


if __name__ == '__main__':
    main()
