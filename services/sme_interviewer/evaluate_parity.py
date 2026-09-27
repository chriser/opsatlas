"""Same answers from Tibi's voice and the Digital SME (DSME S3).

Asks the latency replay's 20 questions, as one conversation each time, three ways:

* twice through Tibi's engine as the voice uses it (the companion the voice builds, turn by turn, without audio);
* once through the Tibi service's text channel, as the Ask Digital SME page does.

The two voice runs give the engine's own run-to-run variation (the model samples its wording). The Digital SME run
should agree with the voice as closely as the voice agrees with itself: the same route, the same records, and
wording within the same similarity. Run it against a disposable copy of the sales workspace, never the live one:

    services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.evaluate_parity \\
        --core http://127.0.0.1:8794 --tibi http://127.0.0.1:8795 --workspace <copy of the sales workspace>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from statistics import mean

import httpx

from .engine import current
from .replay_latency import QUESTIONS
from .tibi import Tibi

REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / 'docs/initiatives/sme-interviewer/evaluations'


def outcome(result: dict) -> dict:
    records = result.get('records') if 'records' in result else result.get('evidence')
    return {'route': result.get('route'), 'grounding': result.get('grounding'), 'reply': result.get('reply', ''),
            'records': sorted(r['id'] for r in records or [] if isinstance(r, dict))}


async def voice_run(credential: str, core: str) -> list[dict]:
    """The questions through Tibi's engine exactly as the voice companion runs a turn, minus the audio."""
    tibi = Tibi([], credential, core)
    await tibi.warm()
    out = []
    for question in QUESTIONS:
        turn = tibi.begin(question)
        while await turn.next() is not None:
            pass
        await turn.task
        result = turn.result
        tibi.commit(question, result['reply'], result['route'], result.get('clarify'))
        out.append(outcome(result))
    return out


async def text_run(service: str) -> list[dict]:
    """The questions through the Tibi service's text channel, as the Ask Digital SME page asks them."""
    async with httpx.AsyncClient(base_url=service, timeout=60, trust_env=False) as client:
        token = (await client.get('/api/bootstrap')).json()['token']
        headers = {'x-sme-token': token}
        opened = (await client.post('/api/text/sessions', json={'channel': 'digital_sme'}, headers=headers)).json()
        out = []
        try:
            for question in QUESTIONS:
                response = await client.post(f"/api/text/sessions/{opened['id']}/turns", json={'text': question}, headers=headers)
                response.raise_for_status()
                out.append(outcome(response.json()))
        finally:
            await client.post(f"/api/text/sessions/{opened['id']}/close", json={}, headers=headers)
    return out


def compare(a: list[dict], b: list[dict]) -> dict:
    pairs = list(zip(a, b))
    same_route = [x['route'] == y['route'] for x, y in pairs]
    same_records = [x['records'] == y['records'] for x, y in pairs]
    wording = [SequenceMatcher(None, x['reply'].lower(), y['reply'].lower()).ratio() for x, y in pairs]
    return {'turns': len(pairs), 'same_route': sum(same_route), 'same_records': sum(same_records),
            'same_grounding': sum(x['grounding'] == y['grounding'] for x, y in pairs),
            'identical_wording': sum(x['reply'] == y['reply'] for x, y in pairs),
            'wording_similarity': round(mean(wording), 3) if wording else None}


async def run(args) -> dict:
    credential = (Path(args.workspace) / 'local-access.key').read_text().strip()
    voice_a = await voice_run(credential, args.core)
    voice_b = await voice_run(credential, args.core)
    text = await text_run(args.tibi)
    engine = current()
    return {'schema': 1, 'at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'engine': {k: engine[k] for k in ('version', 'fingerprint', 'models')}, 'questions': QUESTIONS,
            'digital_sme_vs_voice': compare(voice_a, text), 'voice_vs_voice': compare(voice_a, voice_b),
            'turns': [{'question': q, 'voice': a, 'voice_again': b, 'digital_sme': t}
                      for q, a, b, t in zip(QUESTIONS, voice_a, voice_b, text)]}


def markdown(card: dict) -> str:
    a, b = card['digital_sme_vs_voice'], card['voice_vs_voice']
    rows = [('Same route', 'same_route'), ('Same records', 'same_records'), ('Same grounding', 'same_grounding'),
            ('Word-for-word identical', 'identical_wording')]
    lines = ['# Digital SME and Tibi: same answers', '', f"{card['at']} · engine {card['engine']['version']} · "
             f"{len(card['questions'])} questions as one conversation", '',
             '| Measure | Digital SME against the voice | The voice against itself (baseline) |', '|---|---|---|']
    lines += [f"| {label} | {a[key]} of {a['turns']} | {b[key]} of {b['turns']} |" for label, key in rows]
    lines += [f"| Wording similarity (0 to 1) | {a['wording_similarity']} | {b['wording_similarity']} |", '']
    differ = [t for t in card['turns'] if t['voice']['route'] != t['digital_sme']['route'] or
              t['voice']['records'] != t['digital_sme']['records']]
    if differ:
        lines += ['## Turns where the route or records differ', '']
        for t in differ:
            lines.append(f"- “{t['question']}”: voice {t['voice']['route']} {t['voice']['records']}, voice again "
                         f"{t['voice_again']['route']} {t['voice_again']['records']}, Digital SME {t['digital_sme']['route']} "
                         f"{t['digital_sme']['records']}")
        lines.append('')
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--core', required=True, help='a disposable OpsAtlas Sales core')
    parser.add_argument('--tibi', required=True, help='a disposable Tibi service talking to that core')
    parser.add_argument('--workspace', required=True, help="the disposable workspace (for the engine's credential)")
    parser.add_argument('--results', default=str(RESULTS))
    parser.add_argument('--no-save', action='store_true')
    args = parser.parse_args(argv)
    card = asyncio.run(run(args))
    print(markdown(card))
    if not args.no_save:
        results = Path(args.results)
        results.mkdir(parents=True, exist_ok=True)
        stem = f"{card['at'][:16].replace(':', '')}-digital-sme-parity"
        (results / f'{stem}.json').write_text(json.dumps(card, indent=1, ensure_ascii=False) + '\n')
        (results / f'{stem}.md').write_text(markdown(card))
        print(f'Saved {results / stem}.json and .md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
