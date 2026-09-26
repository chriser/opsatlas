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
    python scripts/evaluate_governance_pairs.py second-opinion result-qwen2.5_14b-instruct.json qwen3.5:35b-a3b
    python scripts/evaluate_governance_pairs.py frontier claude-sonnet-5
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

sys.path.insert(0, str(ROOT / 'src'))
# The pre-registered prompt (25 September 2026) lives with the engine that uses it.
from assistant.governance.statement_judge import PROMPT, SCHEMA  # noqa: E402


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


def run_second_opinion(first_file: str, reviewer: str) -> tuple[str, list[dict]]:
    """Every case the first judge called a conflict goes to a reasoning judge (thinking on); the conflict stands only if
    the reviewer agrees, and stands too when the reviewer gives no answer (rule fixed 25 September 2026)."""
    from assistant.governance.statement_judge import OllamaJudge
    first = json.loads((OUTPUT / first_file).read_text())
    judge = OllamaJudge(reviewer, OLLAMA, timeout=600, think=True)
    cases = {i['id']: i for i in items()}
    rows = []
    for row in first['rows']:
        item = cases.get(row['id'])
        if item is None:
            continue
        out = {**row, 'first': row['predicted'], 'second': None}
        if row['predicted'] == 'conflict':
            started = time.perf_counter()
            try:
                verdict = judge.judge(item['a'], item['b'])
                out['second'] = verdict['relation']
                if verdict['relation'] != 'conflict':
                    out['predicted'] = verdict['relation']
            except Exception as exc:  # no answer: the first verdict stands
                out['second'] = 'no answer: ' + str(exc)[:80]
            out['seconds'] = round(row['seconds'] + time.perf_counter() - started, 3)
            print(item['id'], item['label'], ': first conflict, second', out['second'], flush=True)
        rows.append(out)
    return f"{first['system']} + second opinion {reviewer}+think", rows


ANTHROPIC = 'https://api.anthropic.com/v1/messages'  # explicit: never a base URL inherited from the environment


def env_key(name: str) -> str:
    for line in (ROOT / '.env').read_text().splitlines():
        if line.strip().startswith(name + '='):
            return line.split('=', 1)[1].strip()
    raise SystemExit(f'{name} is not set in .env')


def run_frontier(model: str) -> tuple[list[dict], dict]:
    """The same pre-registered prompt through Anthropic's Messages API (GOV S3, approved by the Human on 26 September
    2026). Only the benchmark pairs leave the machine; what was sent is summarised for audit.

    One method for every Claude model: the prompt's own "Return JSON" instruction, the answer parsed from the reply,
    and the model's default sampling. Newer models refuse a temperature setting (claude-sonnet-5) and a forced tool
    call (claude-opus-5-5), so neither is used for any of them.
    """
    key = env_key('ANTHROPIC_API_KEY')
    headers = {'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'}
    rows, sent_bytes, requests_sent, rejected = [], 0, 0, 0
    with httpx.Client(timeout=120, trust_env=False) as client:
        for item in items():
            body = {'model': model, 'max_tokens': 300, 'system': PROMPT,
                    'messages': [{'role': 'user', 'content': json.dumps({'statement_a': item['a'], 'statement_b': item['b']})}]}
            raw = json.dumps(body)
            assert key not in raw  # the key travels only in its header
            started = time.perf_counter()
            relation, reason, usage = 'error', '', {}
            for attempt in range(5):
                response = client.post(ANTHROPIC, headers=headers, content=raw)
                requests_sent += 1
                sent_bytes += len(raw.encode())
                if response.status_code in (429, 500, 502, 503, 529):
                    time.sleep(2 ** attempt)
                    continue
                if response.status_code != 200:
                    rejected += 1
                    reason = f'HTTP {response.status_code}: {response.text[:200]}'
                    break
                data = response.json()
                usage = data.get('usage', {})
                text = ''.join(b.get('text', '') for b in data.get('content', []) if b.get('type') == 'text')
                match = re.search(r'\{.*\}', text, re.S)
                try:
                    value = json.loads(match.group(0)) if match else {}
                except ValueError:
                    value = {}
                if value.get('relation') in ('conflict', 'duplicate', 'neither'):
                    relation, reason = value['relation'], str(value.get('reason', ''))
                else:
                    reason = 'unparsed reply: ' + text[:200]
                break
            rows.append({'id': item['id'], 'predicted': relation, 'reason': reason, 'at': round(time.time(), 1),
                         'seconds': round(time.perf_counter() - started, 3),
                         'prompt_tokens': usage.get('input_tokens'), 'output_tokens': usage.get('output_tokens')})
            print(item['id'], item['label'], '->', relation, rows[-1]['seconds'], flush=True)
    audit = {'host': 'api.anthropic.com', 'requests': requests_sent, 'rejected': rejected, 'bytes_sent': sent_bytes,
             'cases': len(rows), 'method': 'system prompt + one user message with the two statements; JSON parsed from the reply',
             'sent': 'the pre-registered system prompt and, per case, the two statements (document title, section heading, text) '
                     'from tests/evaluation/governance_pair_benchmark.json',
             'key_in_any_body': False,
             'input_tokens': sum(r['prompt_tokens'] or 0 for r in rows), 'output_tokens': sum(r['output_tokens'] or 0 for r in rows)}
    return rows, audit


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
    elif mode == 'frontier':
        rows, audit = run_frontier(sys.argv[2])
        name = sys.argv[2]
        out = OUTPUT / ('result-' + re.sub(r'[^A-Za-z0-9.+-]+', '_', name).strip('_') + '.json')
        out.write_text(json.dumps({'system': name, 'prompt': PROMPT, 'audit': audit, 'rows': rows}, indent=1))
        print('wrote', out, '| audit', audit)
        return
    elif mode == 'second-opinion':
        name, rows = run_second_opinion(sys.argv[2], sys.argv[3])
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
