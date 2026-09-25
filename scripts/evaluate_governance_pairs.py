#!/usr/bin/env python3
"""Governance pair benchmark: can a system tell a conflict or a duplicate from two statements that merely look alike?

Dataset: tests/evaluation/governance_pair_benchmark.json (labels written before any model ran). It holds the 31
human-reviewed findings of the 2026-07-18 Full Governance Review (none was a contradiction or a duplicate) and
planted conflicts, duplicates, scoped variants and complementary pairs written from the learning packs' own wording.

    engine   the current Full Governance Review pair path (deep profile, guards on); each item is wrapped as two
             one-section documents, with the pair-relevance gate at 0 because whole template documents always pass it
    model    one model, the pre-registered generic prompt below, JSON output, temperature 0, no guards
    score    score every result file in the output directory

    python scripts/evaluate_governance_pairs.py engine
    python scripts/evaluate_governance_pairs.py model qwen2.5:14b-instruct [--think] [--kinds=scoped,complementary]
    python scripts/evaluate_governance_pairs.py nli MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli
    python scripts/evaluate_governance_pairs.py score

    nli      a specialist natural-language-inference model (requirements-nli.txt), run in both directions. Decision rule,
             fixed 2026-09-25 before the first run: conflict when the contradiction probability is at least 0.5 in either
             direction; otherwise duplicate when the entailment probability is at least 0.5 in both directions; else neither.
"""
from __future__ import annotations

import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / 'tests/evaluation/governance_pair_benchmark.json'
OUTPUT = Path(os.environ.get('GOVERNANCE_BENCHMARK_OUTPUT', ROOT / 'docs/benchmark/governance'))
OLLAMA = os.environ.get('KP_OLLAMA_URL', 'http://127.0.0.1:11434')

# Pre-registered 2026-09-25 before any model run. Not tuned to the benchmark.
PROMPT = """You review an organisation's governed process documents for knowledge-governance issues.
You are given two statements, each from a different document or section. Classify their relationship:
- "conflict": they cannot both be followed or both be true for the same subject, scope and time, for example
  different values, owners, order of steps or methods, or one requires what the other rules out.
- "duplicate": they give the same substantive guidance, so one could replace the other.
- "neither": anything else: they are about different subjects, processes, item types, phases, sites or dates;
  one is an exception to, or a later phase of, the other; or they add different, compatible information.
Judge only what the statements say. Different wording alone is not a conflict.
Return JSON: {"relation": "conflict" | "duplicate" | "neither", "reason": "<one sentence>"}"""
SCHEMA = {'type': 'object', 'properties': {'relation': {'type': 'string', 'enum': ['conflict', 'duplicate', 'neither']},
                                           'reason': {'type': 'string'}},
          'required': ['relation', 'reason']}


def items():
    rows = json.loads(DATASET.read_text())['items']
    kinds = [a.split('=', 1)[1].split(',') for a in sys.argv if a.startswith('--kinds=')]
    return [i for i in rows if i['kind'] in kinds[0]] if kinds else rows


def run_model(model: str, think: bool = False) -> list[dict]:
    rows = []
    with httpx.Client(timeout=300, trust_env=False) as client:
        client.post(f'{OLLAMA}/api/chat', json={'model': model, 'stream': False, 'keep_alive': '10m', 'think': False,
                                                'messages': [{'role': 'user', 'content': 'Hello'}],
                                                'options': {'num_predict': 1}})  # load before timing
        for item in items():
            payload = {'model': model, 'stream': False, 'keep_alive': '10m', 'format': SCHEMA, 'think': think,
                       'options': {'temperature': 0, 'num_ctx': 4096, 'num_predict': 4096 if think else 160},
                       'messages': [{'role': 'system', 'content': PROMPT},
                                    {'role': 'user', 'content': json.dumps({'statement_a': item['a'], 'statement_b': item['b']})}]}
            started = time.perf_counter()
            try:
                data = client.post(f'{OLLAMA}/api/chat', json=payload).json()
                value = json.loads(data['message']['content'])
                relation, reason = value.get('relation', 'error'), value.get('reason', '')
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                relation, reason, data = 'error', str(exc), {}
            rows.append({'id': item['id'], 'predicted': relation, 'reason': reason, 'at': round(time.time(), 1),
                         'seconds': round(time.perf_counter() - started, 3),
                         'prompt_tokens': data.get('prompt_eval_count'), 'output_tokens': data.get('eval_count')})
            print(item['id'], item['label'], '->', relation, rows[-1]['seconds'], flush=True)
    return rows


def run_engine() -> list[dict]:
    for path in (ROOT, ROOT / 'src'):
        sys.path.insert(0, str(path))
    os.environ['KP_COMPLIANCE_AGENT_ENABLED'] = '1'
    from services.compliance_reasoning.app import _engine_from_env
    from services.compliance_reasoning.models import ComplianceReviewRequest, EvidenceDocument, EvidenceSection, ReviewOptions
    engine = _engine_from_env()
    options = ReviewOptions(include_supported_findings=False, include_unsupported_internal_claims=False,
                            include_missing_obligations=False, include_not_related_pairs=False, min_alignment_score=0.18,
                            min_pair_relevance_score=0.0, min_contradiction_alignment_score=0.3, max_findings=100,
                            review_depth='deep', max_agent_calls_per_pair=0)

    def doc(key, side):
        return EvidenceDocument(id=key, title=side['document'], source_type='internal', version='1',
                                sections=[EvidenceSection(id=f'{key}-0', heading=side['section'], text=side['text'],
                                                          citation=f"{side['document']} - {side['section']}")])
    rows = []
    for item in items():
        a, b = doc(item['id'] + '-a', item['a']), doc(item['id'] + '-b', item['b'])
        request = ComplianceReviewRequest(review_mode='internal_vs_internal', internal_documents=[a, b], options=options)
        started = time.perf_counter()
        try:
            result = engine.review_internal_document_pair(a, b, request)
            classes = [f.classification for f in result['findings']]
            calls = (result.get('diagnostics') or {}).get('llm_call_count')
        except Exception as exc:  # recorded, never hidden
            classes, calls = ['error: ' + str(exc)[:120]], None
        predicted = 'conflict' if 'contradiction' in classes else 'duplicate' if 'duplicate' in classes else 'neither'
        rows.append({'id': item['id'], 'predicted': predicted, 'engine_classes': classes, 'flagged': bool(classes),
                     'at': round(time.time(), 1), 'llm_calls': calls, 'seconds': round(time.perf_counter() - started, 3)})
        print(item['id'], item['label'], '->', predicted, classes, rows[-1]['seconds'], flush=True)
    return rows


NLI_MODELS = ROOT / '.runtime/governance-benchmark/models'


class NLI:
    """A natural-language-inference cross-encoder: P(entailment | neutral | contradiction) for premise -> hypothesis."""

    def __init__(self, name: str):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        self.torch = torch
        self.device = 'mps' if torch.backends.mps.is_available() else 'cpu'
        self.tokenizer = AutoTokenizer.from_pretrained(name, cache_dir=NLI_MODELS)
        self.model = AutoModelForSequenceClassification.from_pretrained(name, cache_dir=NLI_MODELS).to(self.device).eval()
        labels = {v.lower(): int(k) for k, v in self.model.config.id2label.items()}
        self.index = {key: next(i for label, i in labels.items() if label.startswith(key)) for key in ('entail', 'contradict')}

    def probabilities(self, premises, hypotheses):
        with self.torch.no_grad():
            batch = self.tokenizer(premises, hypotheses, truncation=True, padding=True, return_tensors='pt').to(self.device)
            probs = self.model(**batch).logits.softmax(-1).cpu()
        return [{'entailment': float(p[self.index['entail']]), 'contradiction': float(p[self.index['contradict']])} for p in probs]

    def relation(self, a: str, b: str) -> tuple[str, dict]:
        forward, backward = self.probabilities([a, b], [b, a])
        contradiction = max(forward['contradiction'], backward['contradiction'])
        entailment = min(forward['entailment'], backward['entailment'])
        relation = 'conflict' if contradiction >= 0.5 else 'duplicate' if entailment >= 0.5 else 'neither'
        return relation, {'contradiction': round(contradiction, 3), 'entailment_both_ways': round(entailment, 3)}


def run_nli(name: str) -> list[dict]:
    nli = NLI(name)
    nli.relation('warm up', 'warm up')
    rows = []
    for item in items():
        started = time.perf_counter()
        relation, scores = nli.relation(item['a']['text'], item['b']['text'])
        rows.append({'id': item['id'], 'predicted': relation, 'reason': json.dumps(scores), 'at': round(time.time(), 1),
                     'seconds': round(time.perf_counter() - started, 4)})
        print(item['id'], item['label'], '->', relation, scores, flush=True)
    return rows


def prf(rows, gold, label):
    tp = sum(1 for r in rows if r['predicted'] == label and gold[r['id']]['label'] == label)
    fp = sum(1 for r in rows if r['predicted'] == label and gold[r['id']]['label'] != label)
    fn = sum(1 for r in rows if r['predicted'] != label and gold[r['id']]['label'] == label)
    return {'precision': tp / (tp + fp) if tp + fp else None, 'recall': tp / (tp + fn) if tp + fn else None,
            'tp': tp, 'fp': fp, 'fn': fn}


def score(path: Path) -> dict:
    gold = {i['id']: i for i in items() if not i.get('exclude')}
    data = json.loads(path.read_text())
    rows = [r for r in data['rows'] if r['id'] in gold]
    correct = lambda part: sum(r['predicted'] == gold[r['id']]['label'] for r in part)  # noqa: E731
    planted = [r for r in rows if gold[r['id']]['kind'] != 'real_finding']
    real = [r for r in rows if gold[r['id']]['kind'] == 'real_finding']
    negatives = [r for r in rows if gold[r['id']]['label'] == 'neither']
    secs = sorted(r['seconds'] for r in rows)
    out = {'system': data['system'], 'n': len(rows), 'accuracy': correct(rows) / len(rows),
           **{f'accuracy_{s}': correct(p) / len(p) for s in ('dev', 'holdout')
              if (p := [r for r in planted if gold[r['id']]['split'] == s])},
           'conflict': prf(rows, gold, 'conflict'), 'duplicate': prf(rows, gold, 'duplicate'),
           # A false alarm: anything but "neither" on a human-dismissed finding (for the engine, any finding at all).
           'real_false_alarms': sum(1 for r in real if r['predicted'] != 'neither' or r.get('flagged')), 'real_n': len(real),
           'neither_flagged': sum(1 for r in negatives if r['predicted'] != 'neither' or r.get('flagged')),
           'neither_n': len(negatives), 'errors': sum(1 for r in rows if r['predicted'] == 'error'),
           'median_seconds': statistics.median(secs), 'p95_seconds': secs[int(0.95 * (len(secs) - 1))]}
    by_kind = {}
    for r in rows:
        k = gold[r['id']]['kind']
        by_kind.setdefault(k, [0, 0])
        by_kind[k][0] += r['predicted'] == gold[r['id']]['label']
        by_kind[k][1] += 1
    out['by_kind'] = {k: f'{a}/{b}' for k, (a, b) in by_kind.items()}
    if any(r.get('llm_calls') is not None for r in rows):
        out['median_llm_calls'] = statistics.median(r['llm_calls'] for r in rows if r.get('llm_calls') is not None)
    return out


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else 'score'
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if mode == 'score':
        results = [score(p) for p in sorted(OUTPUT.glob('result-*.json'))]
        (OUTPUT / 'scorecard.json').write_text(json.dumps(results, indent=1))
        pct = lambda x: '—' if x is None else f'{100 * x:.0f}%'  # noqa: E731
        for o in results:
            print(f"{o['system']:30} acc {pct(o['accuracy'])} | conflict P {pct(o['conflict']['precision'])} "
                  f"R {pct(o['conflict']['recall'])} | duplicate P {pct(o['duplicate']['precision'])} "
                  f"R {pct(o['duplicate']['recall'])} | real false alarms {o['real_false_alarms']}/{o['real_n']} | "
                  f"median {o['median_seconds']:.2f}s")
        return
    if mode == 'engine':
        name, rows = 'engine-v8.10', run_engine()
    elif mode == 'nli':
        name, rows = 'nli-' + sys.argv[2].rsplit('/', 1)[-1], run_nli(sys.argv[2])
    else:
        think = '--think' in sys.argv
        subset = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--kinds=')), None)
        name = sys.argv[2] + ('+think' if think else '') + (f' ({subset} only)' if subset else '')
        rows = run_model(sys.argv[2], think)
    out = OUTPUT / ('result-' + re.sub(r'[^A-Za-z0-9.+-]+', '_', name).strip('_') + '.json')
    out.write_text(json.dumps({'system': name, 'prompt': None if mode == 'engine' else PROMPT, 'rows': rows}, indent=1))
    print('wrote', out)


if __name__ == '__main__':
    main()
