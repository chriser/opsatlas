"""Paced synthetic PCM over the real websocket; simulated playback, no microphone.

Uses the actual ASR, turn detector, planner and Charles worker. Output-delivery
latency includes real-time pacing of acknowledgements, but is not headset latency.
"""
import asyncio
import base64
import json
import time
import uuid
from pathlib import Path

import httpx
import numpy as np
import websockets
from scipy.signal import resample_poly

from .speech import ROOT, SpeechWorker

ANSWERS = [
    'The supplier was activated after the purchasing manager approved it. The buyer could then place the order.',
    'Finance checked the bank details by calling the supplier on its published phone number.',
    'I need to correct that. It was the procurement manager who approved it, not the purchasing manager.',
    'The football match was great yesterday. My team won three nil.',
    'I do not know who approves emergency exceptions. I have never handled one.',
]


async def run():
    source = SpeechWorker('kokoro_mlx', ROOT / '.runtime')
    inputs = []
    try:
        for text in ANSWERS:
            parts = []
            async for chunk in source.stream(text):
                parts.append(np.frombuffer(base64.b64decode(chunk['pcm']), dtype='<i2').astype(np.float32) / 32768)
            inputs.append(resample_poly(np.concatenate(parts), 2, 3))
    finally:
        await source.close()
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8770', trust_env=False) as client:
        token = (await client.get('/api/bootstrap')).json()['token']
        response = await client.post('/api/interviews', headers={'x-sme-token': token}, json={
            'request_id': str(uuid.uuid4()), 'accept_synthetic_storage': True,
            'scope': {'region': 'unknown', 'variant': 'unknown', 'date': ''}})
        response.raise_for_status()
        session = response.json()
    records, events = [], []
    async with websockets.connect(f"ws://127.0.0.1:8770/api/conversation/{session['id']}",
                                  origin='http://127.0.0.1:8770', max_size=8_000_000) as ws:
        await ws.send(json.dumps({'token': token}))
        ready, done, reviewed = asyncio.Event(), asyncio.Event(), asyncio.Event()
        playback = asyncio.Queue()
        pending = []
        seq = 0
        stream_start = None
        current = None

        async def consume():
            while True:
                message = await playback.get()
                if current is not None and not message.get('cue') and 'response_started' not in current:
                    current['response_started'] = time.monotonic()
                await asyncio.sleep(len(base64.b64decode(message['pcm'])) / 2 / message['rate'])
                await ws.send(json.dumps({'type': 'audio_ack', 'index': message['index'], 'generation_id': message['generation_id']}))
                playback.task_done()

        async def read():
            async for raw in ws:
                msg = json.loads(raw)
                kind = msg['type']
                if kind == 'ready':
                    ready.set()
                elif kind == 'review_complete':
                    reviewed.set()
                    events.append({'type': kind})
                elif kind == 'audio_chunk':
                    await playback.put(msg)
                elif kind == 'speech_done' and not msg.get('cue'):
                    done.set()
                elif kind == 'endpoint' and current is not None:
                    current['detected_speech_end'] = stream_start + msg['speech_end_sample'] / 16000
                    current['endpoint_ms'] = round((time.monotonic() - current['detected_speech_end']) * 1000)
                elif kind in ('final_transcript', 'question', 'clarification', 'quality_notice', 'error', 'speech'):
                    events.append({k: v for k, v in msg.items() if k not in ('session_id',)})
                    if current is not None:
                        current.setdefault('events', []).append(events[-1])

        async def feed():
            nonlocal seq, stream_start
            await ready.wait()
            stream_start = time.monotonic()
            while True:
                samples = pending.pop(0) if pending else np.zeros(512, dtype=np.float32)
                pcm = (np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes()
                await ws.send(json.dumps({'type': 'frame', 'sequence': seq, 'pcm': base64.b64encode(pcm).decode()}))
                seq += 1
                await asyncio.sleep(max(0, stream_start + seq * .032 - time.monotonic()))

        tasks = [asyncio.create_task(fn()) for fn in (read, feed, consume)]
        try:
            await asyncio.wait_for(ready.wait(), 60)
            await asyncio.wait_for(done.wait(), 60)
            await playback.join()
            for text, audio in zip(ANSWERS, inputs):
                done.clear()
                current = {'input': text}
                padded = np.pad(audio, (0, (-len(audio)) % 512))
                pending.extend(padded[i:i + 512] for i in range(0, len(padded), 512))
                await asyncio.wait_for(done.wait(), 60)
                await asyncio.wait_for(playback.join(), 60)
                if 'response_started' in current and 'detected_speech_end' in current:
                    current['response_gap_ms'] = round((current['response_started'] - current['detected_speech_end']) * 1000)
                records.append(current)
                print(json.dumps(current), flush=True)
                current = None
            await ws.send(json.dumps({'type': 'recap'}))
            await asyncio.wait_for(reviewed.wait(), 120)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            output = Path('/tmp/sme-expressive-replay.json')
            output.write_text(json.dumps({'boundary': ('Paced synthetic websocket with simulated real-time playback acknowledgements; '
                                                  'not browser or headset'),
                                          'records': records, 'events': events}, indent=2))


if __name__ == '__main__':
    asyncio.run(run())
