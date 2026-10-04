"""Measure name activation (REH S10): missed activations, accidental triggers, several speakers, Tibi hearing itself.

Phrases are spoken by ten macOS system voices (British, Irish, Australian, Indian, South African and American
speakers), recognised by Tibi's own speech recognition (whisper small.en with Tibi's vocabulary, as in a
conversation) and judged by services/sme_interviewer/wake.py:

* activations: the name addressed to Tibi, at the start, at the end, alone, or after another speaker's sentence;
* near-misses and the name in passing: "Toby", "TV", "the Tiber", "I told Tibi ...", "Tibi is our assistant";
* two speakers in one utterance, as a single capture joins them when nobody pauses;
* Tibi's own replies, as a speakerphone lets the microphone hear them: they must be recognised as its echo.

This is a proxy for the room. Tibi's real voice (Higgs), the Jabra speakerphone's echo cancellation and real people
are tested by the Human with the protocol in docs/initiatives/sme-interviewer/51-sales-rehearsal-and-wake-name.md.

    services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.evaluate_wake [--voices 10] [--assets DIR]
"""
from __future__ import annotations

import argparse
import array
import asyncio
import json
import subprocess
import sys
import tempfile
import wave
from datetime import datetime, timezone
from pathlib import Path

from .rehearsal import intent_of
from .resident import Resident
from .sales_preview import VOCABULARY
from .wake import addressed, echo_of

REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / 'evaluation/results/tibi'
VOICES = ('Daniel', 'Flo (English (UK))', 'Reed (English (UK))', 'Sandy (English (UK))', 'Moira', 'Karen', 'Rishi', 'Tessa',
          'Samantha', 'Eddy (English (US))')
ACTIVATIONS = [  # (said, the request it should carry, its kind of help)
    ('Tibi, what have I missed?', 'missed'),
    ('Hey Tibi, explain that more simply.', 'simpler'),
    ('Tiberius, help me answer that question.', 'answer'),
    ('What have I missed, Tibi?', 'missed'),
    ('OK Tibi, give an example relevant to this customer.', 'example'),
    ('Tibi, can it run on our own servers?', 'ask'),
    ('Hey Tiberius, what else should I mention?', 'missed'),
    ('Tibi?', None),
]
NOT_ACTIVATIONS = [
    'I told Tibi about the pilot yesterday.',
    'Tibi is our assistant for this meeting.',
    'The TV in the meeting room was not working.',
    'Toby from finance will join us later.',
    'We walked along the river Tiber last summer.',
    'Tabby cats are my favourite.',
    'Can you give me an example?',
    'What have I missed?',
    "Tibi's voice sounds very natural.",
    'Our team uses Tibco for integration.',
]
TWO_SPEAKERS = [  # (first speaker, second speaker, addressed to Tibi?)
    ('We are a regional bank with forty branches.', 'Tibi, what have I missed?', True),
    ('Our procedures change every month.', 'Tibi, help me answer that question.', True),
    ('Tibi was mentioned in the last meeting.', 'We should look at pricing next.', False),
]
# A held-out set (audit F07): phrases written on 27 September 2026 after the heard spellings were added from the set
# above, never used to change the rules, and run once. The same voices; new wording, requests and near-misses.
HELDOUT_ACTIVATIONS = [
    ('Tibi, how would you answer that?', 'answer'),
    ('Hey Tibi, can you put that more simply?', 'simpler'),
    ("Tiberius, anything I've forgotten to mention?", 'missed'),
    ('Tibi, give them an example from a bank.', 'example'),
    ('Right, Tibi, does it work offline?', 'ask'),
    ('Can you help me with that one, Tibi?', 'answer'),
    ("Tibi, what's a good example for an insurer?", 'example'),
    ('Hey Tibi.', None),
]
HELDOUT_NOT_ACTIVATIONS = [
    "Let's ask the team about TB later.",
    'Tibi said the same thing last week.',
    'We use Tableau for our dashboards.',
    'Debbie will send the slides tomorrow.',
    'Tiberius was a Roman emperor.',
    'What else should we cover today?',
    'Is Tibi available on mobile?',
    "I think Tibi's answers were good.",
    'Toby, can you explain that more simply?',
    'Teddy, what have I missed?',
]
HELDOUT_TWO_SPEAKERS = [
    ('Our branches close at five.', 'Tibi, how would you answer that?', True),
    ('Tibi told me it runs locally.', "Let's move on to pricing.", False),
]
HELDOUT_ECHOES = [
    'Every record is approved by a person before I use it in an answer.',
    'The Enterprise Activity Model is built from the same governed ontology.',
]
ECHOES = [
    "My day is a steady stream of conversations like this one.",
    'OpsAtlas answers from approved company knowledge and cites the records it used.',
    'The Enterprise Activity Model shows processes, roles and risks in five views.',
]


def synthesise(text: str, voice: str, folder: Path) -> bytes:
    """16 kHz mono 16-bit PCM of ``text`` in ``voice``."""
    aiff, wav = folder / 'say.aiff', folder / 'say.wav'
    subprocess.run(['say', '-v', voice, '-o', str(aiff), text], check=True)
    subprocess.run(['afconvert', '-f', 'WAVE', '-d', 'LEI16@16000', '-c', '1', str(aiff), str(wav)], check=True)
    with wave.open(str(wav)) as w:
        return w.readframes(w.getnframes())


def floats(pcm: bytes, pad: float = 0.3) -> bytes:
    """Float32 samples as Tibi's recogniser takes them, with a little silence either side."""
    silence = [0.0] * int(16000 * pad)
    shorts = array.array('h', pcm)
    return array.array('f', [*silence, *(v / 32768 for v in shorts), *silence]).tobytes()


async def run(args) -> dict:
    heldout = getattr(args, 'set', 'main') == 'heldout'
    activations = HELDOUT_ACTIVATIONS if heldout else ACTIVATIONS
    not_activations = HELDOUT_NOT_ACTIVATIONS if heldout else NOT_ACTIVATIONS
    two_speakers = HELDOUT_TWO_SPEAKERS if heldout else TWO_SPEAKERS
    echoes = HELDOUT_ECHOES if heldout else ECHOES
    assets = Path(args.assets)
    with tempfile.TemporaryDirectory() as scratch:
        runtime = Path(scratch)
        (runtime / 'models').symlink_to(assets / 'models', target_is_directory=True)
        (runtime / 'conversation-recognizer').symlink_to(assets / 'recognition-check/conversation-recognizer')
        asr = Resident(runtime, 'asr', 'ggml-small.en.bin', VOCABULARY)
        await asr.start()
        rows = []

        async def hear(pcm):
            return ' '.join((await asr.infer(floats(pcm))).get('text', '').split())
        try:
            for voice in VOICES[:args.voices]:
                for said, kind in activations:
                    heard = await hear(synthesise(said, voice, runtime))
                    ok, request = addressed(heard)
                    rows.append({'test': 'activation', 'voice': voice, 'said': said, 'heard': heard, 'activated': ok,
                                 'request_kind': intent_of(request) if request else None, 'expected_kind': kind,
                                 'pass': ok and (kind is None and not request or kind is not None and intent_of(request) == kind)})
                for said in not_activations:
                    heard = await hear(synthesise(said, voice, runtime))
                    ok, _ = addressed(heard)
                    rows.append({'test': 'not_activation', 'voice': voice, 'said': said, 'heard': heard, 'activated': ok, 'pass': not ok})
            for n, (first, second, expected) in enumerate(two_speakers):
                a, b = VOICES[n % len(VOICES)], VOICES[(n + 3) % len(VOICES)]
                pcm = synthesise(first, a, runtime) + bytes(int(16000 * 0.25) * 2) + synthesise(second, b, runtime)
                heard = await hear(pcm)
                ok, request = addressed(heard)
                rows.append({'test': 'two_speakers', 'voice': f'{a} + {b}', 'said': f'{first} {second}', 'heard': heard,
                             'activated': ok, 'pass': ok == expected})
            for reply in echoes:
                heard = await hear(synthesise(reply, VOICES[0], runtime))
                rows.append({'test': 'own_voice', 'voice': VOICES[0], 'said': reply, 'heard': heard,
                             'echo': echo_of(heard, reply), 'activated': addressed(heard)[0],
                             'pass': echo_of(heard, reply) and not addressed(heard)[0]})
        finally:
            await asr.close()
    card = summarise(rows, args)
    card['set'] = 'heldout' if heldout else 'main'
    return card


def summarise(rows, args) -> dict:
    def share(test, key='pass'):
        chosen = [r for r in rows if r['test'] == test]
        return round(sum(1 for r in chosen if r[key]) / len(chosen), 3) if chosen else None
    activations = [r for r in rows if r['test'] == 'activation']
    named = [r for r in activations if 'Tibi' in r['said'] or 'Tiberius' in r['said']]
    names = sorted({r['heard'].split(',')[0].split()[0] if r['heard'] else '' for r in named})
    return {'schema': 1, 'at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'voices': list(VOICES[:args.voices]),
            'recogniser': 'whisper ggml-small.en with Tibi vocabulary',
            'measures': {'activation_recall': share('activation', 'activated'),
                         'activation_with_right_request': share('activation'),
                         'accidental_trigger_rate': share('not_activation', 'activated'),
                         'two_speakers_correct': share('two_speakers'),
                         'own_voice_recognised_as_echo': share('own_voice')},
            'name_heard_as': names, 'missed': [r for r in activations if not r['activated']],
            'accidental': [r for r in rows if r['test'] == 'not_activation' and r['activated']], 'rows': rows}


def markdown(card) -> str:
    m = card['measures']
    title = '# Tibi name activation (spoken test' + (', held-out phrases' if card.get('set') == 'heldout' else '') + ')'
    lines = [title, '', f"{card['at']} · {len(card['voices'])} voices · {card['recogniser']}", '',
             '| Measure | Result |', '|---|---|']
    lines += [f"| {k.replace('_', ' ')} | {v} |" for k, v in m.items()]
    lines += ['', f"The name was heard as: {', '.join(repr(n) for n in card['name_heard_as'])}", '']
    for title, found in (('Missed activations', card['missed']), ('Accidental triggers', card['accidental'])):
        if found:
            lines += [f'## {title}', ''] + [f"- {r['voice']}: said “{r['said']}”, heard “{r['heard']}”" for r in found] + ['']
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--voices', type=int, default=len(VOICES))
    parser.add_argument('--assets', default=str(REPO / 'services/sme_interviewer/.runtime'), help='speech models and recogniser')
    parser.add_argument('--results', default=str(RESULTS))
    parser.add_argument('--no-save', action='store_true')
    parser.add_argument('--set', choices=('main', 'heldout'), default='main',
                        help='heldout: phrases never used to change the rules (run once, report as measured)')
    args = parser.parse_args(argv)
    card = asyncio.run(run(args))
    print(markdown(card))
    if not args.no_save:
        results = Path(args.results)
        results.mkdir(parents=True, exist_ok=True)
        stem = f"{card['at'][:16].replace(':', '')}-wake" + ('-heldout' if card['set'] == 'heldout' else '')
        (results / f'{stem}.json').write_text(json.dumps(card, indent=1, ensure_ascii=False) + '\n')
        (results / f'{stem}.md').write_text(markdown(card))
        print(f'Saved {results / stem}.json and .md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
