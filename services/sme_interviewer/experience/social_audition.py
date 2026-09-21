"""Repeatable expressive exchanges; local inference, no microphone or downloads."""
import argparse
import asyncio
import base64
import json
import os
import time

from .catalog import ROOT, RUNTIME

CASES = [
    ('Greeting: “Hi, how are you?”', 'Ready to listen, thank you. How has your day been?', 'warm'),
    ('Good news: “I finally finished the project!”', 'That is lovely news! It sounds as though you have earned a breather.', 'bright'),
    ('A difficult day: “Honestly, I am exhausted.”', 'That sounds like a long day. We can keep this short, if that would help.', 'gentle'),
    ('A joke: “My coffee has filed a complaint about being overworked.”', 'Fair enough. We had better give it a break.', 'amused'),
    ('Closing: “Thanks for your time. Goodbye.”', 'Thank you for making the time. Take care, and enjoy the rest of your day.', 'warm'),
]
DIRECTIONS = {
    'warm': 'Speak warmly and conversationally, with a welcoming smile and natural pauses.',
    'bright': 'Sound pleased and quietly excited about good news. Bright, friendly, not theatrical.',
    'gentle': 'Speak gently, sympathetically and calmly, with space between thoughts. Do not sound cheerful or laugh.',
    'amused': 'Sound lightly amused, with a small smile in your voice. Gentle dry humour, not exaggerated laughter.',
}


async def run(engine):
    import numpy as np
    import soundfile as sf
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
    directory = RUNTIME / 'social-comparison'
    directory.mkdir(exist_ok=True)
    manifest = directory / 'results.json'
    rows = json.loads(manifest.read_text()) if manifest.exists() else []
    rows = [r for r in rows if r['engine'] != engine]
    worker = None
    if engine == 'Charles baseline':
        from ..speech import SpeechWorker
        worker = SpeechWorker('pocket', ROOT / '.runtime/expressive-preview')
        await worker.start()
    elif engine == 'Chatterbox Turbo':
        from ..expressive_voice import ExpressiveVoice
        model = ExpressiveVoice(ROOT / '.runtime')
    else:
        import mlx.core as mx
        from mlx_audio.tts.utils import load_model
        mx.set_cache_limit(256 * 1024**2)
        model = load_model(str(RUNTIME / 'qwen-custom'))
        model.eval()
        mx.eval(model.parameters())
    try:
        for index, (context, text, style) in enumerate(CASES):
            start = time.perf_counter()
            chunks = []
            first = None
            rate = 24000
            def consume(audio):
                nonlocal first
                if first is None:
                    first = (time.perf_counter() - start) * 1000
                chunks.append(np.asarray(audio).reshape(-1))
            if worker:
                async for chunk in worker.stream(text):
                    rate = chunk['rate']
                    consume(np.frombuffer(base64.b64decode(chunk['pcm']), dtype='<i2').astype(np.float32) / 32768)
            elif engine == 'Chatterbox Turbo':
                async for audio, rate in model.create_stream(('[chuckle] ' if style == 'amused' else '') + text):
                    consume(audio)
            else:
                for result in model.generate_custom_voice(text=text, speaker='Aiden', language='English',
                        instruct='Use clear British English. ' + DIRECTIONS[style], stream=True,
                        streaming_interval=0.4, max_tokens=650, temperature=0.7):
                    rate = result.sample_rate
                    consume(result.audio)
            elapsed = (time.perf_counter() - start) * 1000
            audio = np.concatenate(chunks)
            assert len(audio) and np.isfinite(audio).all() and np.max(np.abs(audio)) > 0
            rms = float(np.sqrt(np.mean(audio ** 2)))
            audio *= min(0.1 / max(rms, 1e-8), 0.95 / float(np.max(np.abs(audio))))
            name = engine.lower().replace(' ', '-') + '-' + str(index) + '.wav'
            sf.write(directory / name, audio, rate, subtype='PCM_16')
            row = {'context': context, 'text': text, 'style': style, 'engine': engine, 'file': name,
                   'first_chunk_ms': round(first, 1), 'synthesis_ms': round(elapsed, 1),
                   'audio_seconds': round(len(audio) / rate, 3), 'cold': index == 0}
            rows.append(row)
            manifest.write_text(json.dumps(rows, indent=2)+'\n')
            print(json.dumps(row), flush=True)
    finally:
        if worker:
            await worker.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('engine', choices=['Charles baseline', 'Chatterbox Turbo', 'Qwen CustomVoice'])
    asyncio.run(run(parser.parse_args().engine))
