"""Controlled ASR stress probes using the selected synthetic voice, not human WER."""

import asyncio
import json
import subprocess
import tempfile
import time
from pathlib import Path

from .catalog import BY_PROMPT
from .speech import ROOT, transcribe


async def run():
    import numpy as np
    import soundfile as sf

    runtime = ROOT / ".runtime"
    rows = []
    rng = np.random.default_rng(42)
    with tempfile.TemporaryDirectory(prefix="sme-asr-stress-") as directory:
        path = Path(directory) / "input.wav"
        for prompt in ("numbers", "acronyms", "correction", "unknown"):
            subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(runtime / "audition" / f"B-{prompt}.wav"),
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    str(path),
                ],
                check=True,
            )
            signal, rate = sf.read(path, dtype="float32")
            for snr in (None, 20, 10, 0):
                noise = rng.normal(0, 1, len(signal)).astype(np.float32)
                scale = np.sqrt(np.mean(signal**2) / np.mean(noise**2)) / (10 ** ((snr or 0) / 20))
                mixed = signal if snr is None else signal + noise * scale
                sf.write(path, np.clip(mixed, -1, 1), rate, subtype="PCM_16")
                started = time.perf_counter()
                heard = await transcribe(runtime, path)
                rows.append(
                    {
                        "prompt": prompt,
                        "snr_db": snr,
                        "expected": BY_PROMPT[prompt]["text"],
                        "heard": heard,
                        "wall_ms": (time.perf_counter() - started) * 1000,
                    }
                )
                print(prompt, snr, heard, flush=True)
    report = {
        "fixture": "Kokoro bf_isabella synthetic speech; mono 16k; seeded Gaussian additive noise; clean/20/10/0 dB SNR",
        "rows": rows,
        "limits": "No human WER, room echo, far-field acoustics or spontaneous hesitation claim; "
        "all microphone transcripts still require explicit review.",
    }
    (runtime / "audition/recognition-stress.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    asyncio.run(run())
