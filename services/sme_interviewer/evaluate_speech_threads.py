"""Local CPU/batching development benchmark; output is JSON, not a listening-quality score."""

import asyncio
import json
import time
from pathlib import Path

import onnxruntime as ort
from kokoro_onnx import Kokoro
from kokoro_onnx.chunker import split_phonemes

root = Path(__file__).parent / ".runtime/models"
texts = [
    "How was the bank details check evidenced or verified?",
    "What happened between the request arriving and the first person picking it up?",
    "Which part of the handover needed the most judgement, and why?",
]


async def run():
    records = []
    for threads in [2, 4, 8]:
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(str(root / "kokoro-v1.0.onnx"), sess_options=options, providers=["CPUExecutionProvider"])
        model = Kokoro.from_session(session, str(root / "voices-v1.0.bin"))
        for limit in [510, 100, 70]:
            model._split_phonemes = lambda phonemes: split_phonemes(phonemes, limit)
            for text in texts:
                t = time.perf_counter()
                first = None
                chunks = 0
                duration = 0
                async for audio, rate in model.create_stream(text, voice="bf_isabella", speed=1, lang="en-gb"):
                    if first is None:
                        first = time.perf_counter() - t
                    chunks += 1
                    duration += len(audio) / rate
                records.append(
                    dict(
                        threads=threads,
                        phonemes=limit,
                        text=text,
                        first_ms=round(first * 1000),
                        total_ms=round((time.perf_counter() - t) * 1000),
                        chunks=chunks,
                        seconds=round(duration, 2),
                    )
                )
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    asyncio.run(run())
