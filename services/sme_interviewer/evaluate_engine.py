"""Measure the Tibi engine (OBS S10, S11): routing accuracy, appropriateness, grounding precision and speed.

Runs the scripted conversations in docs/initiatives/sme-interviewer/evaluation/scenarios.json through Tibi's own
turn code (routing, the local models, the approved records) and scores every reply against the checks named for
it. The scorecard is stamped with the engine version and the knowledge it used, written to
docs/initiatives/sme-interviewer/evaluations/, and compared with the previous scorecard: each measure is improved,
the same or degraded.

    services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.evaluate_engine --runs 2 [--judge] [--replay FILE]

--judge adds a local judge's 1–5 ratings of each reply's appropriateness and naturalness (qwen2.5:14b-instruct, on
this Mac). --replay adds the speech measures (end of speech to first audio, and recognition accuracy) from a
replay_latency result. Reads the live sales workspace's approved records; changes nothing.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from services.opsatlas_sales import claims

from . import engine
from .rehearsal import RehearsalCoach
from .tibi import OLLAMA, Tibi, cited, content_words

REPO = Path(__file__).resolve().parents[2]
SCENARIOS = REPO / 'docs/initiatives/sme-interviewer/evaluation/scenarios.json'
RESULTS = REPO / 'docs/initiatives/sme-interviewer/evaluations'
KEY = REPO / '.runtime/opsatlas-sales/local-access.key'
JUDGE = 'qwen2.5:14b-instruct'
# How much a measure may move before it counts as improved or degraded.
TOLERANCE = {'routing_accuracy': 0.03, 'appropriateness': 0.03, 'grounding_precision': 0.03, 'judge_score': 0.2,
             'first_segment_p50_ms': 0.10, 'first_segment_p95_ms': 0.15, 'first_audio_p50_ms': 0.10,
             'first_audio_p95_ms': 0.15, 'recognition_accuracy': 0.02}
LOWER_IS_BETTER = {'first_segment_p50_ms', 'first_segment_p95_ms', 'first_audio_p50_ms', 'first_audio_p95_ms'}
FIRST_PERSON = re.compile(r"\b(?:I|I'm|I've|I'd|[Mm]y|[Mm]e)\b")
DECLINE = re.compile(r"\b(?:stay out|keep out|steer clear|rather not|not something I|out of date|avoid (?:politics|that))\b", re.I)
NUMBER = re.compile(r"\d[\d,.]*")


def sentences(text):
    return claims.sentences_of(text or '')


def check(name, reply, result, turn, context) -> bool:
    """Whether ``reply`` passes the check ``name``."""
    if name == 'one_question':
        return reply.count('?') <= 1
    if name == 'no_question':
        return '?' not in reply
    if name == 'capital':
        first = re.search(r'[A-Za-z]', reply)
        return bool(first) and first.group(0).isupper()
    if name == 'brief':  # a rehearsal reply: short enough to hand the floor straight back
        return len(reply) <= 300 or result.get('grounding') in ('approved_fallback', 'approved_spoken')
    if name == 'new_point':  # "what have I missed?" adds something the meeting has not said
        return len(content_words(reply) - content_words(' '.join(context.get('meeting', [])))) >= 3
    if name == 'short':
        # Approved record wording, spoken as it is when a generated answer went beyond it, may be longer.
        return len(reply) <= 400 or result.get('grounding') in ('approved_fallback', 'approved_spoken')
    if name == 'about_itself':
        return bool(FIRST_PERSON.search(reply))
    if name == 'no_product':
        # As Tibi itself judges it: an everyday price ("Milk prices can vary") is not OpsAtlas pricing.
        everyday = claims.everyday_price(claims.focus(turn['say']))
        return not any(claims.product_claim(s) and not (everyday and not claims.PRODUCT_NAMES.search(s)) for s in sentences(reply))
    if name == 'declines':
        return bool(DECLINE.search(reply))
    if name == 'grounded':
        records = result.get('evidence') or []
        if not records:
            return False
        source = ' '.join(r.get('text', '') for r in records)
        return all(n in source for n in NUMBER.findall(reply))
    if name == 'no_copy':
        words = re.findall(r"[a-z']+", reply.lower())
        guidance = ' '.join(re.findall(r"[a-z']+", context['guidance'].lower()))
        return not any(' '.join(words[i:i + 8]) in guidance for i in range(max(0, len(words) - 7)))
    if name == 'no_repeat':
        asked = [q.lower() for q in context['asked']]
        return not any(s.lower() in asked for s in sentences(reply) if s.endswith('?'))
    if name == 'mentions':
        return any(w.lower() in reply.lower() for w in turn.get('mentions', []))
    if name == 'avoids':  # whole words: "How about your run?" is not "How about you"
        return not any(re.search(r'\b' + re.escape(p) + r'\b', reply, re.I) for p in turn.get('avoids', []))
    raise ValueError(f'Unknown check: {name}')


def precision(reply, result) -> float | None:
    """Share of a product answer's sentences that an approved record it used supports."""
    records = result.get('evidence') or []
    said = [s for s in sentences(reply) if not s.endswith('?')]
    if not records or not said:
        return None
    return sum(1 for s in said if cited(s, records)) / len(said)


async def judge(client, history, reply) -> dict | None:
    prompt = ('Rate the assistant\'s last reply in this spoken sales conversation. The assistant, Tibi, is a warm, '
              'witty British voice companion that answers product questions only from approved records. Return JSON '
              '{"appropriate": 1-5, "natural": 1-5, "reason": "one short sentence"}. Appropriate: it answers what was '
              'actually said, stays on safe ground and asks at most one question. Natural: it sounds like a person.\n\n'
              + '\n'.join(f"{m['role']}: {m['content']}" for m in history) + f'\nassistant (rate this): {reply}')
    try:
        response = await client.post('/api/chat', json={'model': JUDGE, 'stream': False, 'format': 'json', 'keep_alive': '10m',
                                                        'options': {'temperature': 0}, 'messages': [{'role': 'user', 'content': prompt}]})
        data = json.loads(response.json()['message']['content'])
        return {'appropriate': float(data['appropriate']), 'natural': float(data['natural']), 'reason': str(data.get('reason', ''))[:200]}
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None


def percentile(values, q):
    if not values:
        return None
    values = sorted(values)
    return round(values[min(len(values) - 1, int(round(q / 100 * (len(values) - 1))))], 1)


async def run(args) -> dict:
    suite = json.loads(SCENARIOS.read_text())
    key = Path(args.key).read_text().strip()
    turns, digest = [], None
    async with httpx.AsyncClient(base_url=OLLAMA, timeout=120, trust_env=False) as client:
        for n in range(args.runs):
            for scenario in suite['scenarios']:
                if args.only and scenario['id'] not in args.only:
                    continue
                rehearsal = scenario.get('mode') == 'rehearsal'
                tibi = RehearsalCoach([], key, customer=scenario.get('customer', '')) if rehearsal else Tibi([], key)
                history, asked = [], []
                for index, turn in enumerate(scenario['turns']):
                    if 'hear' in turn:  # a rehearsal's meeting line: context, never answered or scored
                        tibi.observe(turn['hear'])
                        history.append({'role': 'user', 'content': f"(meeting) {turn['hear']}"})
                        continue
                    turn = {**turn, 'say': turn.get('say') or turn['ask']}
                    started = time.perf_counter()
                    live = tibi.begin(turn['say'])
                    while await live.next() is not None:
                        pass
                    result = live.result
                    reply = result['reply']
                    digest = digest or getattr(tibi.evidence, 'digest', None)
                    guidance = ' '.join(g['text'] for g in (await tibi.evidence.search(turn['say'])).get('conversation', []))
                    context = {'guidance': guidance, 'asked': asked, 'meeting': list(getattr(tibi, 'meeting', []))}
                    names = [*turn.get('checks', []), *(['mentions'] if turn.get('mentions') else []),
                             *(['avoids'] if turn.get('avoids') else [])]
                    passed = {name: check(name, reply, result, turn, context) for name in names}
                    row = {'run': n + 1, 'scenario': scenario['id'], 'turn': index, 'say': turn['say'], 'reply': reply,
                           'route': result['route'], 'route_reasons': result.get('route_reasons', []),
                           'route_ok': result['route'] in turn['route'], 'checks': passed,
                           'precision': precision(reply, result) if result['route'] in ('product', 'self', 'rehearsal') else None,
                           'first_token_ms': result['marks'].get('first_token'),
                           'first_segment_ms': result['marks'].get('first_segment'),
                           'total_ms': round((time.perf_counter() - started) * 1000, 1)}
                    history += [{'role': 'user', 'content': turn['say']}, {'role': 'assistant', 'content': reply}]
                    if args.judge:
                        row['judge'] = await judge(client, history, reply)
                    turns.append(row)
                    tibi.commit(turn['say'], reply, result['route'], result.get('clarify'))
                    asked += [s for s in sentences(reply) if s.endswith('?')]
                    print(f"{'✓' if row['route_ok'] and all(passed.values()) else '✗'} {scenario['id']}[{index}] "
                          f"{result['route']}: {reply[:110]}", flush=True)
    return score(turns, args, digest)


def score(turns, args, digest) -> dict:
    checks = [ok for t in turns for ok in t['checks'].values()]
    precisions = [t['precision'] for t in turns if t['precision'] is not None]
    firsts = [t['first_segment_ms'] for t in turns if t['first_segment_ms'] is not None]
    measures = {'routing_accuracy': round(sum(t['route_ok'] for t in turns) / len(turns), 3),
                'appropriateness': round(sum(checks) / len(checks), 3) if checks else None,
                'grounding_precision': round(statistics.mean(precisions), 3) if precisions else None,
                'first_segment_p50_ms': percentile(firsts, 50), 'first_segment_p95_ms': percentile(firsts, 95)}
    judged = [t['judge'] for t in turns if t.get('judge')]
    if judged:
        measures['judge_score'] = round(statistics.mean((j['appropriate'] + j['natural']) / 2 for j in judged), 2)
    if args.replay:
        replay = json.loads(Path(args.replay).read_text())
        first = (replay.get('summary') or {}).get('first_audio') or {}
        measures['first_audio_p50_ms'], measures['first_audio_p95_ms'] = first.get('p50'), first.get('p95')
        if (replay.get('summary') or {}).get('recognition_accuracy') is not None:
            measures['recognition_accuracy'] = replay['summary']['recognition_accuracy']
    failures = {}
    for t in turns:
        for name, ok in t['checks'].items():
            if not ok:
                failures.setdefault(name, []).append(f"{t['scenario']}[{t['turn']}]")
        if not t['route_ok']:
            failures.setdefault('route', []).append(f"{t['scenario']}[{t['turn']}] → {t['route']}")
    return {'schema': 1, 'at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'engine': engine.current(),
            'knowledge_digest': digest, 'runs': args.runs, 'turns_scored': len(turns), 'judge': JUDGE if args.judge else None,
            'measures': measures, 'failures': failures, 'turns': turns}


def compare(card: dict, previous: dict | None) -> dict:
    if not previous:
        return {}
    out = {}
    for name, value in card['measures'].items():
        before = previous['measures'].get(name)
        if value is None or before is None:
            continue
        change = (value - before) / before if name in LOWER_IS_BETTER and before else value - before
        better = -change if name in LOWER_IS_BETTER else change
        tolerance = TOLERANCE.get(name, 0.03)
        out[name] = {'before': before, 'now': value,
                     'verdict': 'improved' if better > tolerance else 'degraded' if better < -tolerance else 'same'}
    return out


def markdown(card: dict) -> str:
    e = card['engine']
    lines = [f"# Tibi engine {e['version']} scorecard", '',
             f"{card['at']} · fingerprint `{e['fingerprint']}` · models {', '.join(f'{k} {v}' for k, v in e['models'].items())} · "
             f"{card['turns_scored']} turns ({card['runs']} run{'s' if card['runs'] > 1 else ''}) · "
             f"knowledge `{card['knowledge_digest']}`", '',
             '| Measure | Now | Before | Verdict |', '|---|---|---|---|']
    for name, value in card['measures'].items():
        c = card.get('comparison', {}).get(name, {})
        lines.append(f"| {name.replace('_', ' ')} | {value} | {c.get('before', '—')} | {c.get('verdict', '—')} |")
    if card['failures']:
        lines += ['', '## What failed', '']
        lines += [f"- **{name}**: {', '.join(where)}" for name, where in sorted(card['failures'].items())]
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--runs', type=int, default=2)
    parser.add_argument('--judge', action='store_true')
    parser.add_argument('--replay', help='a replay_latency result, for the speech measures')
    parser.add_argument('--only', action='append', help='only these scenario ids')
    parser.add_argument('--no-save', action='store_true')
    parser.add_argument('--key', default=str(KEY), help='the sales workspace key (read-only use of its knowledge API)')
    parser.add_argument('--results', default=str(RESULTS), help='where scorecards are kept')
    args = parser.parse_args(argv)
    card = asyncio.run(run(args))
    results = Path(args.results)
    # Scorecards only ("<date>T<time>-engine-<version>.json"), not the wake tests or latency replays.
    scorecard = re.compile(r'\d{4}-\d\d-\d\dT\d{4}-engine-.+\.json')
    earlier = sorted(p for p in results.glob('*-engine-*.json') if scorecard.fullmatch(p.name)) if results.exists() else []
    previous = json.loads(earlier[-1].read_text()) if earlier else None
    card['compared_with'] = previous and {'engine': previous['engine']['version'], 'at': previous['at']}
    card['comparison'] = compare(card, previous)
    print(markdown(card))
    if not args.no_save and not args.only:
        results.mkdir(parents=True, exist_ok=True)
        stem = f"{card['at'][:16].replace(':', '')}-engine-{card['engine']['version']}"
        (results / f'{stem}.json').write_text(json.dumps(card, indent=1, ensure_ascii=False) + '\n')
        (results / f'{stem}.md').write_text(markdown(card))
        print(f'Saved {results / stem}.json and .md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
