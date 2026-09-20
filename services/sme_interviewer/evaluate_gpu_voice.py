"""Real sandboxed Voice B streaming probe; synthetic text, no human quality rating."""

import asyncio
import base64
import json
import time

import numpy as np
from scipy.signal import resample_poly

from .resident import Resident
from .speech import ROOT, SpeechWorker

PHRASES = [
    "How did Finance verify the bank details were correct?",
    "What happened to the request after you sent it?",
    "The limit is £15,000, not £50,000. Approval happens before activation.",
    "The buyer requested a new supplier for a repair order. Finance checked the bank details. "
    "The purchasing manager recorded approval in the workflow. I changed the status from on hold to active. "
    "The buyer could then place the order. I do not know who may approve an exception. "
    "This account is still provisional. We will check the wording together before saving the draft.",
]


async def main():
    runtime = ROOT / '.runtime'
    speaker, asr = SpeechWorker('kokoro_mlx', runtime), Resident(runtime, 'asr', 'ggml-small.en.bin')
    rows = []
    try:
        await asyncio.gather(speaker.start(), asr.start())
        for text in PHRASES:
            started, first, chunks = time.perf_counter(), None, []
            async for chunk in speaker.stream(text):
                if first is None:
                    first = round((time.perf_counter() - started) * 1000)
                chunks.append(base64.b64decode(chunk['pcm']))
            elapsed = round((time.perf_counter() - started) * 1000)
            pcm = np.frombuffer(b''.join(chunks), dtype='<i2').astype(np.float32) / 32768
            heard = await asr.infer(resample_poly(pcm, 2, 3).astype(np.float32).tobytes())
            row = {'text': text, 'first_chunk_ms': first, 'total_ms': elapsed,
                   'audio_seconds': len(pcm) / 24000, 'recognised': heard.get('text')}
            rows.append(row)
            print(json.dumps(row), flush=True)
    finally:
        await asyncio.gather(speaker.close(), asr.close())
    report = {'method': 'Sandboxed GPU Voice B streaming followed by resident ASR. Not perceptual or human naturalness evidence.',
              'rows': rows}
    path = runtime / 'gpu-voice-development.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(path)


if __name__ == '__main__':
    asyncio.run(main())
