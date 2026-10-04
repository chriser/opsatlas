"""Persistent isolated TTS worker. JSON lines on stdin/stdout; no network access."""

import asyncio
import base64
import contextlib
import json
import os
import queue
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))
from services.sme_interviewer.catalog import VOICES  # noqa: E402
from services.sme_interviewer.spoken_text import POLICY_VERSION, for_speech  # noqa: E402

os.environ.update(
    HF_HUB_OFFLINE="1",
    TRANSFORMERS_OFFLINE="1",
    HF_HUB_DISABLE_TELEMETRY="1",
    HF_HOME=str(ROOT / ".runtime" / "hf"),
    TOKENIZERS_PARALLELISM="false",
)


def main():
    import numpy as np
    import soundfile as sf

    engine = sys.argv[1]
    runtime = Path(sys.argv[2])
    start = time.perf_counter()
    with contextlib.redirect_stdout(sys.stderr):
        if engine in ("higgs", "higgs_female"):
            from services.sme_interviewer.higgs_voice import HiggsVoice

            model = HiggsVoice(runtime, female=engine == "higgs_female")
        else:
            raise ValueError("Unknown engine")
    print(json.dumps({"ready": True, "load_ms": (time.perf_counter() - start) * 1000}), flush=True)
    # A reader thread lets a {"cancel": id} message stop the current stream between
    # frames, so a barge-in never has to kill and reload a resident model.
    requests, cancel = queue.Queue(), {"id": None}

    def read():
        for raw in sys.stdin:
            try:
                message = json.loads(raw)
            except ValueError:
                message = {}
            if "cancel" in message:
                cancel["id"] = message["cancel"]
            else:
                requests.put(raw)
        requests.put(None)

    threading.Thread(target=read, daemon=True).start()
    while (line := requests.get()) is not None:
        try:
            request = json.loads(line)
            config = VOICES[request["candidate"]]
            if not 1 <= len(request["text"]) <= 600:
                raise ValueError("Invalid synthesis request")
            spoken_text = for_speech(request["text"])
            start = time.perf_counter()
            if request.get("stream"):

                async def stream():
                    index = 0
                    pending = b""
                    options = {"cancelled": lambda: request.get("id") is not None and cancel["id"] == request.get("id")}
                    iterator = model.create_stream(spoken_text, voice=config["voice"], speed=config["speed"], lang="en-gb", **options)
                    while True:
                        try:
                            with contextlib.redirect_stdout(sys.stderr):
                                audio, rate = await anext(iterator)
                        except StopAsyncIteration:
                            break
                        pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()
                        pending += pcm
                        packet_bytes = rate * 2 * 80 // 1000
                        while len(pending) >= packet_bytes:
                            packet, pending = pending[:packet_bytes], pending[packet_bytes:]
                            print(json.dumps({"chunk": index, "rate": rate, "pcm": base64.b64encode(packet).decode()}), flush=True)
                            index += 1
                    if pending:
                        print(json.dumps({"chunk": index, "rate": rate, "pcm": base64.b64encode(pending).decode()}), flush=True)
                        index += 1
                    return index

                chunks = asyncio.run(stream())
                print(
                    json.dumps({"ok": True, "done": True, "chunks": chunks, "total_ms": (time.perf_counter() - start) * 1000,
                                "cancelled": request.get("id") is not None and cancel["id"] == request.get("id")}), flush=True
                )
                continue
            with contextlib.redirect_stdout(sys.stderr):
                async def collect():
                    chunks = []
                    first = None
                    async for chunk, rate in model.create_stream(spoken_text):
                        if first is None:
                            first = (time.perf_counter() - start) * 1000
                        chunks.append(chunk)
                    return np.concatenate(chunks), rate, first
                audio, rate, first_ms = asyncio.run(collect())
            if not len(audio) or not np.isfinite(audio).all():
                raise RuntimeError("Invalid generated audio")
            sf.write(request["output"], audio, rate, subtype="PCM_16")
            print(
                json.dumps(
                    {
                        "ok": True,
                        "first_chunk_ms": first_ms,
                        "total_ms": (time.perf_counter() - start) * 1000,
                        "audio_seconds": len(audio) / rate,
                        "sample_rate": rate,
                        "speech_text_policy": POLICY_VERSION,
                    }
                ),
                flush=True,
            )
        except Exception as exc:
            # No transcript/text or credentials in operational logs.
            print(json.dumps({"ok": False, "error": type(exc).__name__}), flush=True)


if __name__ == "__main__":
    main()
