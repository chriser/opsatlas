"""Replay spoken questions through the live Tiberius turn path and measure every stage.

Independent review 2 (S147): the G1.5 gate needs at least 100 in-browser turns measured from
the end of the participant's speech to Tibi's first audio. This harness exercises the same
websocket protocol as the browser (16 kHz PCM frames in real time, playback acknowledgements)
against a disposable copy of the sales workspace on separate ports, so the Human's live
services and saved conversations are never touched.

    services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.replay_latency --turns 100

Questions are spoken with the macOS British system voices (no model downloads). Results are
written as JSON evidence with per-turn stage timings and p50/p95 summaries. Timings are measured
at the client socket; the browser adds its 120 ms playback pre-buffer on top of first audio.
"""
import argparse
import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIVE = REPO / '.runtime/opsatlas-sales'
FRAME = 512  # samples per frame at 16 kHz, as the browser AudioWorklet sends
QUESTIONS = [
    'Hello, how are you today?',
    'What is OpsAtlas?',
    'How much would it cost us per year?',
    'Is the platform secure enough for a bank?',
    'Does it support single sign-on?',
    'Can it run offline?',
    'Why is that?',
    'Tell me about Tibi.',
    'Who are your customers?',
    'How does it work?',
    'What is an ontology?',
    'Can it draw process diagrams?',
    'Can we integrate it with SharePoint?',
    'Tell me a joke.',
    'Is it ready for production?',
    'What is the return on investment?',
    'How do you make sure the answers are right?',
    'I have been in meetings all day.',
    'What does approval mean in this workspace?',
    'Thanks, that is really helpful.',
]
VOICES = ('Daniel', 'Flo (English (UK))')


def speak(text, voice, path):
    """Synthesise ``text`` to a 16 kHz mono WAV with the macOS system voice."""
    aiff = path.with_suffix('.aiff')
    subprocess.run(['say', '-v', voice, '-o', str(aiff), text], check=True)
    subprocess.run(['afconvert', '-f', 'WAVE', '-d', 'LEI16@16000', '-c', '1', str(aiff), str(path)], check=True)
    aiff.unlink()
    with wave.open(str(path)) as w:
        pcm = w.readframes(w.getnframes())
    # Trailing silence is the harness's job: trim to the last clearly voiced sample.
    samples = memoryview(pcm).cast('h')
    last = max((i for i in range(len(samples)) if abs(samples[i]) > 600), default=len(samples) - 1)
    return pcm[:(last + 1) * 2]


def prepare_workspace(root):
    root.mkdir(parents=True)
    shutil.copytree(LIVE / 'core', root / 'core')
    for name in ('workspace.json', 'local-access.key'):
        shutil.copy2(LIVE / name, root / name)
    (root / 'voice').mkdir()


def start_services(root, core_port, voice_port):
    env = {**os.environ, 'PYTHONPATH': f'{REPO / "src"}:{REPO}'}
    core = subprocess.Popen([str(REPO / '.venv/bin/python'), '-c',
                             'import sys, uvicorn; from services.opsatlas_sales.app import create_sales_app; '
                             f'uvicorn.run(create_sales_app(sys.argv[1]), host="127.0.0.1", port={core_port}, log_level="warning")',
                             str(root)], cwd=REPO, env=env, stdout=(root / 'core.log').open('w'), stderr=subprocess.STDOUT)
    voice = subprocess.Popen([str(REPO / 'services/sme_interviewer/.venv/bin/python'), '-c',
                              'import sys, uvicorn; from services.sme_interviewer.sales_preview import sales_app; '
                              f'uvicorn.run(sales_app(sys.argv[1], "http://127.0.0.1:{core_port}"), host="127.0.0.1", '
                              f'port={voice_port}, log_level="warning", ws_max_size=8_000_000)', str(root)],
                             cwd=REPO, env=env, stdout=(root / 'voice.log').open('w'), stderr=subprocess.STDOUT)
    return core, voice


async def wait_ready(voice_port, timeout=120):
    import httpx

    deadline = time.monotonic() + timeout
    async with httpx.AsyncClient(trust_env=False, timeout=2) as client:
        while time.monotonic() < deadline:
            try:
                response = await client.get(f'http://127.0.0.1:{voice_port}/api/bootstrap')
                if response.status_code == 200:
                    return response.json()['token']
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1)
    raise RuntimeError('Replay services did not start; inspect core.log and voice.log in the workspace')


def percentile(values, q):
    values = sorted(values)
    if not values:
        return None
    index = min(len(values) - 1, max(0, round(q / 100 * (len(values) - 1))))
    return round(values[index], 1)


async def approve_spoken(voice_port, token):
    """Disposable workspace only: draft spoken wording and approve it, to measure the pre-rendered path."""
    import httpx

    origin = f'http://127.0.0.1:{voice_port}'
    headers = {'x-sme-token': token, 'origin': origin}
    async with httpx.AsyncClient(base_url=origin, trust_env=False, timeout=120) as client:
        drafted = (await client.post('/api/sales/spoken/draft', headers=headers, json={})).json()
        variants = (await client.get('/api/sales/spoken')).json()['variants']
        approved = 0
        for variant in variants:
            if variant['status'] == 'pending' and variant['current']:
                response = await client.post(f"/api/sales/spoken/{variant['id']}/review", headers=headers,
                                             json={'expected_hash': variant['text_sha256'], 'approve': True})
                approved += response.status_code == 200
    return {'drafted': len(drafted['drafted']), 'discarded': len(drafted['rejected']), 'approved': approved}


async def replay(voice_port, token, clips, turns, voice, root=None, prerendered=0):
    import httpx
    import websockets

    origin = f'http://127.0.0.1:{voice_port}'
    async with httpx.AsyncClient(base_url=origin, trust_env=False, timeout=10) as client:
        response = await client.post('/api/interviews', headers={'x-sme-token': token, 'origin': origin}, json={
            'request_id': str(uuid.uuid4()), 'accept_local_storage': True,
            'scope': {'region': 'unknown', 'variant': 'unknown', 'date': ''}})
        response.raise_for_status()
        session = response.json()
    results = []
    async with websockets.connect(f'ws://127.0.0.1:{voice_port}/api/conversation/{session["id"]}',
                                  origin=origin, max_size=8_000_000) as socket:
        await socket.send(json.dumps({'token': token, 'listener_practice': False, 'social_voice': voice, 'text_only': False}))
        events = asyncio.Queue()
        sequence = 0
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
            # Continuous real-time frames, like the AudioWorklet: queued speech, otherwise silence.
            nonlocal sequence
            started, sent = time.perf_counter(), 0
            while True:
                chunk, feed['pcm'] = feed['pcm'][:FRAME * 2], feed['pcm'][FRAME * 2:]
                if chunk and not feed['pcm']:
                    feed['sent_end'] = time.perf_counter()
                chunk = chunk.ljust(FRAME * 2, b'\0')
                await socket.send(json.dumps({'type': 'frame', 'sequence': sequence,
                                              'pcm': base64.b64encode(chunk).decode()}))
                sequence += 1
                sent += 1
                await asyncio.sleep(max(0, started + sent * FRAME / 16000 - time.perf_counter()))

        async def until(kind, timeout):
            deadline = time.perf_counter() + timeout
            while True:
                message = await asyncio.wait_for(events.get(), max(0.01, deadline - time.perf_counter()))
                if message['type'] == kind:
                    return message

        tasks = [asyncio.create_task(receiver())]
        await until('ready', 180)
        tasks.append(asyncio.create_task(sender()))
        await until('speech_done', 60)  # the opening line
        if prerendered:
            # Let the idle pre-render loop put every approved answer in the live voice first.
            cache = root / 'voice/spoken-audio'
            for _ in range(240):
                if cache.exists() and len(list(cache.rglob('*.json'))) >= prerendered:
                    break
                await asyncio.sleep(0.5)
        for index in range(turns):
            text, pcm = clips[index % len(clips)]
            while not events.empty():
                events.get_nowait()
            feed['sent_end'] = None
            feed['pcm'] = pcm
            turn = {'index': index, 'question': text, 'marks': {}}
            try:
                deadline = time.perf_counter() + 45
                while True:
                    message = await asyncio.wait_for(events.get(), max(0.01, deadline - time.perf_counter()))
                    kind, at = message['type'], message['_at']
                    marks = turn['marks']
                    if kind == 'endpoint':
                        marks.setdefault('endpoint', at)
                    elif kind == 'final_transcript':
                        marks.setdefault('final_transcript', at)
                        turn['heard'] = message.get('text')
                    elif kind == 'reply_preparing':
                        marks.setdefault('reply_preparing', at)
                        turn['speculative'] = bool(message.get('speculative'))
                    elif kind == 'audio_chunk' and not message.get('cue'):
                        marks.setdefault('first_audio', at)
                    elif kind == 'social_reply':
                        turn.update(route=message.get('route'), grounding=message.get('grounding'),
                                    reply=message.get('reply'), server_marks=message.get('marks'),
                                    blocked=message.get('blocked') or [])
                    elif kind == 'speech_done' and 'first_audio' in marks:
                        marks.setdefault('speech_done', at)
                        deadline = min(deadline, time.perf_counter() + 1.5)  # social_reply follows the audio
                    elif kind == 'error':
                        turn['error'] = message.get('message')
                    if 'speech_done' in marks and 'route' in turn:
                        break
            except TimeoutError:
                if 'speech_done' not in turn['marks']:
                    turn['error'] = turn.get('error') or 'timeout'
            end = feed['sent_end']
            turn['stages_ms'] = {k: round((v - end) * 1000, 1) for k, v in turn['marks'].items()} if end else {}
            turn.pop('marks')
            results.append(turn)
            done = turn['stages_ms']
            print(f"{index + 1:3} {done.get('endpoint', -1):6.0f} {done.get('final_transcript', -1):6.0f} "
                  f"{done.get('reply_preparing', -1):6.0f} {done.get('first_audio', -1):6.0f} ms "
                  f"{turn.get('route', '?'):12} {'spec' if turn.get('speculative') else '    '} {text}", flush=True)
            await asyncio.sleep(0.8)
        for task in tasks:
            task.cancel()
    return session['id'], results


def summarise(results):
    summary = {}
    for stage in ('endpoint', 'final_transcript', 'reply_preparing', 'first_audio'):
        values = [r['stages_ms'][stage] for r in results if stage in r.get('stages_ms', {})]
        summary[stage] = {'n': len(values), 'p50': percentile(values, 50), 'p95': percentile(values, 95),
                          'max': max(values) if values else None}
    completed = [r for r in results if 'first_audio' in r.get('stages_ms', {})]
    for route in sorted({r.get('route') for r in completed if r.get('route')}):
        values = [r['stages_ms']['first_audio'] for r in completed if r.get('route') == route]
        summary['first_audio_' + route] = {'n': len(values), 'p50': percentile(values, 50), 'p95': percentile(values, 95)}
    summary['speculative_adopted'] = sum(bool(r.get('speculative')) for r in completed)
    summary['errors'] = sum(1 for r in results if r.get('error'))
    summary['heard_exactly'] = sum(1 for r in results if (r.get('heard') or '').strip().lower().rstrip('.?!')
                                   == r['question'].lower().rstrip('.?!'))
    return summary


async def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--turns', type=int, default=100)
    parser.add_argument('--voice', default='higgs')
    parser.add_argument('--core-port', type=int, default=8790)
    parser.add_argument('--voice-port', type=int, default=8793)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--keep', action='store_true', help='keep the disposable workspace for inspection')
    parser.add_argument('--approve-spoken', action='store_true',
                        help='draft and approve spoken answers in the disposable copy (never the live workspace)')
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    root = REPO / '.runtime/latency-replay' / stamp
    prepare_workspace(root)
    clips = [(text, speak(text, VOICES[i % len(VOICES)], root / f'q{i:02}.wav')) for i, text in enumerate(QUESTIONS)]
    core, voice = start_services(root, args.core_port, args.voice_port)
    try:
        token = await wait_ready(args.voice_port)
        spoken = await approve_spoken(args.voice_port, token) if args.approve_spoken else None
        session, results = await replay(args.voice_port, token, clips, args.turns, args.voice, root,
                                        spoken['approved'] if spoken else 0)
    finally:
        for process in (voice, core):
            process.terminate()
        for process in (voice, core):
            try:
                process.wait(10)
            except subprocess.TimeoutExpired:
                process.kill()
    evidence = {'schema': 1, 'measured_at': datetime.now(timezone.utc).isoformat(), 'voice': args.voice,
                'spoken_answers': spoken or 'none approved (as the live workspace on 25 September 2026)',
                'turns': len(results), 'reference': 'end of the question audio sent to the socket',
                'note': 'Client-socket timings; the browser adds a 120 ms playback pre-buffer after first audio.',
                'summary': summarise(results), 'results': results, 'session': session}
    out = args.out or root / 'latency-replay.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=1) + '\n')
    print(json.dumps(evidence['summary'], indent=1))
    print('Evidence:', out)
    if not args.keep:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
