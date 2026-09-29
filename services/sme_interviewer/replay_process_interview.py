"""Replay a spoken process interview through the real Tibi service (TIBI E5, PI F8 and F13).

The first real process interview was spoken, with the pauses people make while describing a process, and it was cut
into fragments: most replies were discarded while their notes were kept. The typed evaluation never went through
that path. This replay does: a made-up participant's answers are synthesised one sentence at a time, joined with real
thinking pauses (and one pause long enough for Tibi to start replying before the speaker carries on), and streamed in
real time to a disposable copy of the workspace, as the browser does.

    python -m services.sme_interviewer.replay_process_interview --out docs/.../evaluations/<file>.json

For each answer it records how many turns it became, how many replies it got, and what was heard; then the working
model the interview saved, scored against what was said. Nothing touches the live workspace.
"""
import argparse
import asyncio
import base64
import json
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .replay_latency import FRAME, REPO, prepare_workspace, speak, start_services, wait_ready

VOICE = 'Daniel'
# Each answer: (sentence, pause after it in seconds). A made-up shop, BeePee; the 2.3 s pause is longer than the
# interview's 1.3 s patience, so Tibi starts on a reply and the speaker carries on over it.
ANSWERS = [
    [("Hi, I'm Alex Moore.", 0.8), ("I'm the store manager at the BeePee high street shop.", 0)],
    [("I'd like to talk about how we handle customer returns.", 0)],
    [("A return starts when a customer brings an item back to the service desk.", 0.9),
     ("The sales assistant checks the receipt on the till.", 1.0),
     ("If the item is damaged, the assistant calls the duty manager.", 2.3),
     ("Otherwise the assistant refunds the customer on the till.", 0.8),
     ("Then the item goes back onto the shelf.", 0)],
    [("The duty manager decides whether to send the item back to the supplier.", 0)],
    [("Sorry, one correction.", 0.7), ("The refund is done on the card machine, not on the till.", 0)],
    # A change to the shape: Tibi should say it back and make it only on a yes (PI F9).
    [("And the item goes back onto the shelf before the refund, not after it.", 0)],
    [("Yes, please.", 0)],
    # An alternative path that splits off early (PI F10).
    [("Oh, and gift cards are different.", 0.9),
     ("After the receipt check, for a gift card the assistant just issues store credit.", 0)],
    [("That's the end of it.", 0)],
]
# What was said, for scoring the saved model: (words about the step, who, system).
TRUTH = [
    ({'return', 'brings', 'bring'}, 'customer', ''),
    ({'receipt'}, 'sales assistant', 'till'),
    ({'duty manager', 'call'}, 'sales assistant', ''),
    ({'refund'}, 'sales assistant', 'card machine'),
    ({'shelf'}, '', ''),
    ({'supplier', 'decide'}, 'duty manager', ''),
]


def silence(seconds):
    return b'\0\0' * int(16000 * seconds)


def build(answers, root):
    clips = []
    for a, answer in enumerate(answers):
        pcm = b''
        for s, (sentence, pause) in enumerate(answer):
            pcm += speak(sentence, VOICE, root / f'a{a:02}s{s}.wav') + silence(pause)
        clips.append((' '.join(sentence for sentence, _ in answer), pcm))
    return clips


async def interview(voice_port, token, clips, space):
    import httpx
    import websockets

    origin = f'http://127.0.0.1:{voice_port}'
    async with httpx.AsyncClient(base_url=origin, trust_env=False, timeout=10) as client:
        response = await client.post('/api/interviews', headers={'x-sme-token': token, 'origin': origin}, json={
            'request_id': str(uuid.uuid4()), 'accept_local_storage': True,
            'scope': {'region': 'unknown', 'variant': 'unknown', 'date': ''},
            'process_interview': {'space': space, 'space_name': 'BeePee'}})
        response.raise_for_status()
        session = response.json()
    answers = []
    async with websockets.connect(f'ws://127.0.0.1:{voice_port}/api/conversation/{session["id"]}',
                                  origin=origin, max_size=8_000_000) as socket:
        await socket.send(json.dumps({'token': token, 'listener_practice': False, 'social_voice': 'higgs', 'text_only': False}))
        events = asyncio.Queue()
        feed = {'pcm': b'', 'sent_end': None}

        async def receiver():
            async for raw in socket:
                message = json.loads(raw)
                message['_at'] = time.perf_counter()
                if message['type'] == 'audio_chunk':
                    await socket.send(json.dumps({'type': 'audio_ack', 'generation_id': message['generation_id'],
                                                  'index': message['index']}))
                await events.put(message)

        async def sender():
            # Continuous real-time frames, like the browser's AudioWorklet: the queued answer, otherwise silence.
            sequence, started = 0, time.perf_counter()
            while True:
                chunk, feed['pcm'] = feed['pcm'][:FRAME * 2], feed['pcm'][FRAME * 2:]
                if chunk and not feed['pcm']:
                    feed['sent_end'] = time.perf_counter()
                await socket.send(json.dumps({'type': 'frame', 'sequence': sequence,
                                              'pcm': base64.b64encode(chunk.ljust(FRAME * 2, b'\0')).decode()}))
                sequence += 1
                await asyncio.sleep(max(0, started + sequence * FRAME / 16000 - time.perf_counter()))

        async def until(kind, timeout):
            deadline = time.perf_counter() + timeout
            while True:
                message = await asyncio.wait_for(events.get(), max(0.01, deadline - time.perf_counter()))
                if message['type'] == kind:
                    return message

        tasks = [asyncio.create_task(receiver())]
        await until('ready', 240)
        tasks.append(asyncio.create_task(sender()))
        await until('speech_done', 90)  # Tibi's opening
        for said, pcm in clips:
            while not events.empty():
                events.get_nowait()
            feed['sent_end'], feed['pcm'] = None, pcm
            record = {'said': said, 'turns': [], 'replies': [], 'errors': []}
            deadline = time.perf_counter() + 90
            try:
                while True:
                    message = await asyncio.wait_for(events.get(), max(0.01, deadline - time.perf_counter()))
                    kind = message['type']
                    if kind == 'final_transcript':
                        record['turns'].append({'heard': message.get('text'),
                                                'during_answer': feed['sent_end'] is None})
                    elif kind == 'social_reply':
                        record['replies'].append({'reply': message.get('reply'), 'goal': (message.get('process_turn') or {}).get('goal'),
                                                  'reasoning_ms': message.get('reasoning_ms'),
                                                  'during_answer': feed['sent_end'] is None,
                                                  'after_end_ms': round((message['_at'] - feed['sent_end']) * 1000)
                                                  if feed['sent_end'] else None})
                    elif kind == 'error':
                        record['errors'].append(message.get('message'))
                    elif kind == 'speech_done' and record['replies'] and feed['sent_end'] is not None:
                        break
            except TimeoutError:
                record['errors'].append('no reply within 90 s')
            answers.append(record)
            await asyncio.sleep(1.0)
        for task in tasks:
            task.cancel()
    return session['id'], answers


def score(model):
    p = (model.get('processes') or [{}])[0]
    steps = [s for s in p.get('steps', []) if s.get('kind') == 'task']
    shelf = next((s for s in steps if 'shelf' in s['label'].casefold()), None)
    refund = next((s for s in steps if 'refund' in s['label'].casefold()), None)
    receipt = next((s for s in steps if 'receipt' in s['label'].casefold()), None)
    by_id = {s['id']: s for s in p.get('steps', [])}
    after_receipt = [by_id.get(n['to']) for n in (receipt or {}).get('next', [])]
    gift = any(d and d['kind'] == 'decision' and any('credit' in (by_id.get(n['to']) or {}).get('label', '').casefold()
                                                     for n in d['next']) for d in after_receipt)
    found, owners, systems, used = 0, 0, 0, set()
    for keys, who, system in TRUTH:
        about = [s for s in steps if s['id'] not in used and any(k in f"{s['label']} {s['who']}".casefold() for k in keys)]
        match = next((s for s in about if who and who.split()[-1] in s['who'].casefold()), about[0] if about else None)
        if match is None:
            continue
        used.add(match['id'])
        found += 1
        owners += (who.split()[-1] in match['who'].casefold()) if who else 1  # no one named: any owner will do
        systems += (system in match['system'].casefold()) if system else not match['system']
    # Strict (PI F14): straight before the refund, on the path that leads to it. Only "somewhere before it" let a move
    # before the damage check pass, which sent damaged items back to the shelf too.
    into_refund = [s for s in p.get('steps', []) if any(n['to'] == (refund or {}).get('id') for n in s['next'])]
    return {'shelf_moved_before_refund': bool(shelf and refund and [s['id'] for s in into_refund] == [shelf['id']]
                                              and shelf['next'] == [{'to': refund['id'], 'label': ''}]),
            'refund_on_card_machine': 'card' in (refund or {}).get('system', '').casefold(),
            'gift_card_path_splits_after_receipt_check': gift,
            'steps_found': f'{found}/{len(TRUTH)}', 'owners_right': f'{owners}/{len(TRUTH)}',
            'systems_right': f'{systems}/{len(TRUTH)}', 'steps': [
                {k: s.get(k) for k in ('label', 'who', 'system', 'status')} for s in steps],
            'decisions': [{'question': s['label'], 'branches': [n['label'] for n in s['next']]}
                          for s in p.get('steps', []) if s.get('kind') == 'decision']}


async def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--core-port', type=int, default=8790)
    parser.add_argument('--voice-port', type=int, default=8793)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--keep', action='store_true', help='keep the disposable workspace for inspection')
    args = parser.parse_args()
    import httpx
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    root = REPO / '.runtime/latency-replay' / f'process-{stamp}'
    prepare_workspace(root)
    space = next((s['id'] for s in json.loads((root / 'spaces.json').read_text())['spaces'] if s['kind'] == 'organisation'), 'beepee')
    clips = build(ANSWERS, root)
    core, voice = start_services(root, args.core_port, args.voice_port)
    try:
        token = await wait_ready(args.voice_port, 180)
        session_id, answers = await interview(args.voice_port, token, clips, space)
        await asyncio.sleep(8)  # the last answer's notes, if they were still being taken
        async with httpx.AsyncClient(trust_env=False, timeout=10) as client:
            saved = (await client.get(f'http://127.0.0.1:{args.voice_port}/api/interviews/{session_id}')).json()
        continued = sum(1 for line in (root / 'logs/activity').glob('tibi-*.jsonl')
                        for event in line.read_text().splitlines() if '"answer continued"' in event)
    finally:
        for process in (voice, core):
            process.terminate()
        for process in (voice, core):
            try:
                process.wait(10)
            except Exception:
                process.kill()
    model = saved.get('process_model') or {}
    said_turns = [m['content'] for m in saved.get('social_transcript', []) if m['role'] == 'user']
    heard = ' '.join(t['heard'] or '' for a in answers for t in a['turns'])
    result = {
        'answers': len(answers),
        'answers_heard_as_one_turn': sum(1 for a in answers if len(a['turns']) == 1),
        'answers_replied_to_once': sum(1 for a in answers if len(a['replies']) == 1),
        'replies_while_still_speaking': sum(1 for a in answers for r in a['replies'] if r['during_answer']),
        'answers_continued_over_a_reply': continued,
        'transcript_answers': len(said_turns),
        'pending_notes_left': len(saved.get('process_pending') or []),
        'first_audio_after_end_ms': [r['after_end_ms'] for a in answers for r in a['replies'] if r['after_end_ms'] is not None],
        'reasoning_ms': [round(r['reasoning_ms']) for a in answers for r in a['replies'] if r.get('reasoning_ms')],
        'notes_seconds': [e['seconds'] for e in saved.get('process_log') or []],
        'heard_beepee': 'beepee' in heard.casefold(), 'heard_till': heard.casefold().count('till'),
        'heard_tool': heard.casefold().count('tool'),
        **score(model),
    }
    report = {'at': datetime.now(timezone.utc).isoformat(), 'data': 'made-up (BeePee, a fictional shop)', 'result': result,
              'answers': answers, 'transcript': saved.get('social_transcript'), 'model': model}
    print(json.dumps(result, indent=1, ensure_ascii=False))
    for a in answers:
        print(f"\nSAID  {a['said']}")
        for t in a['turns']:
            print(f"  HEARD{' (mid-answer)' if t['during_answer'] else ''}: {t['heard']}")
        for r in a['replies']:
            print(f"  TIBI [{r['goal']}]{' (mid-answer)' if r['during_answer'] else ''}: {r['reply']}")
        for e in a['errors']:
            print(f'  ERROR: {e}')
    if args.out:
        args.out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + '\n')
        print('Evidence:', args.out)
    if not args.keep:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == '__main__':
    asyncio.run(main())
