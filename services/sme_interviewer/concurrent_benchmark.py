"""Bounded concurrent Atlas Ask + TTS experiment; never touches production data."""

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path

import httpx
import psutil

from .benchmark import summary
from .catalog import PROMPTS, VOICES
from .speech import ROOT, SpeechWorker

QUESTIONS = [
    "Who approves supplier activation?",
    "What happens before supplier activation?",
    "When does the supplier record stay on hold?",
    "What do emergency supplier requests require?",
    "Explain the supplier activation approval in one sentence.",
]


async def run():
    repo = ROOT.parents[1]
    runtime = ROOT / ".runtime"
    report = {
        "workload": "5 sequential HTTP Ask requests per condition; one synthetic approved document; lexical retrieval; "
        "RAG-only; qwen2.5:7b-instruct, context 8192, temperature 0.1; no rewrite/rerank/validator; "
        "warm model; speech continuously generated during each concurrent condition",
        "conditions": {},
    }
    with tempfile.TemporaryDirectory(prefix="sme-atlas-benchmark-") as directory:
        env = {
            **os.environ,
            "SME_BENCHMARK_DATA": directory,
            "KP_DATA_DIR": str(Path(directory) / "data"),
            "PYTHONPATH": f"{repo / 'src'}:{repo}",
            "KP_LLM_MODEL": "qwen2.5:7b-instruct",
            "KP_OLLAMA_URL": "http://127.0.0.1:11434",
            "KP_QUERY_REWRITE": "0",
            "KP_RERANK": "0",
            "KP_VALIDATE_GROUNDING": "0",
        }
        with (runtime / "atlas-benchmark.log").open("wb") as log:
            process = await asyncio.create_subprocess_exec(
                str(repo / ".venv/bin/python"),
                "-m",
                "uvicorn",
                "services.sme_interviewer.atlas_fixture:create_fixture",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                "8117",
                cwd=directory,
                env=env,
                stdout=log,
                stderr=log,
            )
        try:
            async with httpx.AsyncClient(base_url="http://127.0.0.1:8117", timeout=120) as client:
                for _ in range(100):
                    try:
                        response = await client.get("/api/health")
                        response.raise_for_status()
                        break
                    except httpx.HTTPError:
                        if process.returncode is not None:
                            raise RuntimeError("Isolated Atlas fixture failed to start") from None
                        await asyncio.sleep(0.1)
                response = await client.post("/api/auth/login", json={"password": "synthetic-benchmark"})
                response.raise_for_status()
                client.headers["authorization"] = "Bearer " + response.json()["token"]
                warm = await client.post("/api/ask", json={"q": QUESTIONS[0]})
                warm.raise_for_status()
                report["warmup"] = {"refused": warm.json()["refused"], "answer_path": warm.json()["answer_path"]}
                for candidate in [None, "A", "B", "C"]:
                    worker = SpeechWorker(VOICES[candidate]["engine"], runtime) if candidate else None
                    stop = asyncio.Event()
                    speech_rows, ask_rows, memory = [], [], []
                    output = runtime / "concurrent-speech.wav"
                    if worker:
                        await worker.synthesize(candidate, PROMPTS[0]["text"], output)

                    async def speak():
                        index = 0
                        while not stop.is_set():
                            result = await worker.synthesize(candidate, PROMPTS[index % len(PROMPTS)]["text"], output)
                            speech_rows.append(result)
                            index += 1

                    async def sample():
                        while not stop.is_set():
                            memory.append(
                                {
                                    "system_available_bytes": psutil.virtual_memory().available,
                                    "worker_rss_bytes": psutil.Process(worker.process.pid).memory_info().rss if worker else 0,
                                }
                            )
                            await asyncio.sleep(0.05)

                    speech_task = asyncio.create_task(speak()) if worker else None
                    monitor = asyncio.create_task(sample())
                    try:
                        for question in QUESTIONS:
                            started = time.perf_counter()
                            response = await client.post("/api/ask", json={"q": question})
                            response.raise_for_status()
                            data = response.json()
                            ask_rows.append(
                                {
                                    "question": question,
                                    "wall_ms": (time.perf_counter() - started) * 1000,
                                    "refused": data["refused"],
                                    "answer_path": data["answer_path"],
                                    "citation_count": len(data["citations"]),
                                }
                            )
                    finally:
                        stop.set()
                        if speech_task:
                            await speech_task
                        await monitor
                        if worker:
                            await worker.close()
                        output.unlink(missing_ok=True)
                    report["conditions"][candidate or "atlas-alone"] = {
                        "ask": ask_rows,
                        "ask_ms": summary([r["wall_ms"] for r in ask_rows]),
                        "speech": speech_rows,
                        "speech_ms": summary([r["total_ms"] for r in speech_rows]) if speech_rows else None,
                        "minimum_system_available_bytes": min(r["system_available_bytes"] for r in memory),
                        "peak_worker_rss_bytes": max(r["worker_rss_bytes"] for r in memory),
                    }
                    (runtime / "audition/concurrent-report.json").write_text(json.dumps(report, indent=2) + "\n")
                    print(candidate or "atlas-alone", report["conditions"][candidate or "atlas-alone"]["ask_ms"], flush=True)
        finally:
            if process.returncode is None:
                process.terminate()
                await process.wait()
    report["limits"] = [
        "n=5 per condition; order/cache/thermal effects not controlled; descriptive only, not a release gate.",
        "Only the bounded fixture described above; no claim about full production Atlas or parallel governance.",
        "System available memory is not process GPU allocation. RSS excludes some Metal/shared memory.",
    ]
    (runtime / "audition/concurrent-report.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    asyncio.run(run())
