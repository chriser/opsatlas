"""Generate synthetic listening samples and measured, explicitly bounded evidence."""

import argparse
import asyncio
import json
import platform
import statistics
import subprocess
import time
from pathlib import Path

from .catalog import PROMPTS, VOICE_STYLE, VOICES
from .speech import SpeechWorker, transcribe

ROOT = Path(__file__).resolve().parent


def summary(values):
    ordered = sorted(values)
    return {"n": len(values), "p50": statistics.median(values), "p95": ordered[min(len(values) - 1, int(len(values) * 0.95))]}


async def run(runtime: Path, count: int):
    import psutil

    output = runtime / "audition"
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for candidate, config in VOICES.items():
        worker = SpeechWorker(config["engine"], runtime)
        try:
            for index, prompt in enumerate(PROMPTS[:count]):
                path = output / f"{candidate}-{prompt['id']}.wav"
                rss = []

                async def sample_memory():
                    while True:
                        if worker.process and worker.process.returncode is None:
                            try:
                                rss.append(psutil.Process(worker.process.pid).memory_info().rss)
                            except psutil.Error:
                                pass
                        await asyncio.sleep(0.025)

                monitor = asyncio.create_task(sample_memory())
                start = time.perf_counter()
                try:
                    metrics = await worker.synthesize(candidate, prompt["text"], path)
                finally:
                    monitor.cancel()
                    await asyncio.gather(monitor, return_exceptions=True)
                row = {
                    "candidate": candidate,
                    "prompt": prompt["id"],
                    "cold": index == 0,
                    "load_ms": worker.load_ms,
                    "wall_ms": (time.perf_counter() - start) * 1000,
                    "peak_worker_rss_bytes": max(rss, default=0),
                    **metrics,
                }
                rows.append(row)
                (output / "measurements.json").write_text(json.dumps(rows, indent=2) + "\n")
                print(candidate, prompt["id"], f"{row['total_ms']:.0f} ms synthesis, {row['audio_seconds']:.1f} s audio", flush=True)
        finally:
            await worker.close()

    # Recognition checks use synthetic TTS, not evidence of human accent/noise robustness.
    recognition = []
    for candidate in VOICES:
        for prompt in [p for p in PROMPTS[:count] if p["id"] in {"welcome", "challenge", "numbers"}]:
            source = output / f"{candidate}-{prompt['id']}.wav"
            wave = output / "recognition-input.wav"
            subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(source),
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    "-c:a",
                    "pcm_s16le",
                    str(wave),
                ],
                check=True,
            )
            try:
                start = time.perf_counter()
                text = await transcribe(runtime, wave)
                recognition.append(
                    {
                        "candidate": candidate,
                        "prompt": prompt["id"],
                        "expected": prompt["text"],
                        "heard": text,
                        "wall_ms": (time.perf_counter() - start) * 1000,
                    }
                )
                print("ASR", candidate, prompt["id"], text, flush=True)
            finally:
                wave.unlink(missing_ok=True)
    report = {
        "schema": 1,
        "host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "memory_bytes": psutil.virtual_memory().total,
            "cpu_count": psutil.cpu_count(),
        },
        "configurations": VOICES,
        "qwen_style": VOICE_STYLE,
        "rows": rows,
        "recognition": recognition,
        "warm_synthesis_ms": {
            candidate: summary([r["total_ms"] for r in rows if r["candidate"] == candidate and not r["cold"]])
            for candidate in VOICES
            if count > 1
        },
        "limits": [
            "Synthetic speech only; listening preference and human microphone tests pending.",
            "First chunk is model output, not browser playback or full conversation latency.",
            "Warm samples below 100 turns; this does not pass the proposed end-to-end latency gate.",
            "RSS excludes some shared GPU allocations; record concurrent Atlas load separately.",
            "Workers run under macOS network-deny policy after explicit provisioning.",
        ],
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Saved", output / "report.json", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, default=ROOT / ".runtime")
    parser.add_argument("--count", type=int, choices=range(1, 24), default=23)
    args = parser.parse_args()
    asyncio.run(run(args.runtime.resolve(), args.count))
