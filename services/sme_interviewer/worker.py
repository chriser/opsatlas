"""Persistent isolated TTS worker. JSON lines on stdin/stdout; no network access."""

import asyncio
import base64
import contextlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))
from services.sme_interviewer.catalog import VOICE_STYLE, VOICES  # noqa: E402
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
        if engine == "kokoro":
            import onnxruntime as ort
            from kokoro_onnx import Kokoro

            options = ort.SessionOptions()
            options.intra_op_num_threads = 8
            options.inter_op_num_threads = 1
            session = ort.InferenceSession(
                str(runtime / "models/kokoro-v1.0.onnx"), sess_options=options, providers=["CPUExecutionProvider"]
            )
            model = Kokoro.from_session(session, str(runtime / "models/voices-v1.0.bin"))
        elif engine == "kokoro_mlx":
            from services.sme_interviewer.mlx_voice import MetalKokoro

            model = MetalKokoro(runtime)
            model.create("I am ready when you are.", voice=VOICES["B"]["voice"], speed=1, lang="en-gb")
        elif engine == "pocket":
            from services.sme_interviewer.pocket_voice import PocketCharles

            model = PocketCharles(runtime)
        elif engine == "qwen_custom":
            from services.sme_interviewer.expressive_voice import CustomVoice

            model = CustomVoice(runtime)
        elif engine == "chatterbox":
            from services.sme_interviewer.expressive_voice import ExpressiveVoice

            model = ExpressiveVoice(runtime)
        elif engine in ("higgs", "higgs_female"):
            from services.sme_interviewer.higgs_voice import HiggsVoice

            model = HiggsVoice(runtime, female=engine == "higgs_female")
        elif engine == "qwen":
            import mlx.core as mx
            from mlx_audio.tts.utils import load_model

            model = load_model(str(runtime / "models/qwen-voice-design"))
        else:
            raise ValueError("Unknown engine")
    print(json.dumps({"ready": True, "load_ms": (time.perf_counter() - start) * 1000}), flush=True)
    for line in sys.stdin:
        try:
            request = json.loads(line)
            config = VOICES[request["candidate"]]
            if ((engine not in ("pocket", "chatterbox", "qwen_custom", "higgs", "higgs_female")
                 and config["engine"] != ("kokoro" if engine == "kokoro_mlx" else engine))
                    or not 1 <= len(request["text"]) <= 600):
                raise ValueError("Invalid synthesis request")
            spoken_text = for_speech(request["text"])
            start = time.perf_counter()
            if request.get("stream") and engine in ("kokoro", "kokoro_mlx", "pocket", "chatterbox", "qwen_custom", "higgs", "higgs_female"):

                async def stream():
                    index = 0
                    pending = b""
                    options = {"style": request.get("style", "warm")} if engine == "qwen_custom" else {}
                    iterator = model.create_stream(spoken_text, voice=config["voice"], speed=config["speed"], lang="en-gb", **options)
                    while True:
                        try:
                            with contextlib.redirect_stdout(sys.stderr):
                                audio, rate = await anext(iterator)
                        except StopAsyncIteration:
                            break
                        pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()
                        if engine in ("pocket", "chatterbox", "qwen_custom", "higgs", "higgs_female"):
                            pending += pcm
                            packet_bytes = rate * 2 * 80 // 1000
                            while len(pending) >= packet_bytes:
                                packet, pending = pending[:packet_bytes], pending[packet_bytes:]
                                print(json.dumps({"chunk": index, "rate": rate, "pcm": base64.b64encode(packet).decode()}), flush=True)
                                index += 1
                        else:
                            print(json.dumps({"chunk": index, "rate": rate, "pcm": base64.b64encode(pcm).decode()}), flush=True)
                            index += 1
                    if pending:
                        print(json.dumps({"chunk": index, "rate": rate, "pcm": base64.b64encode(pending).decode()}), flush=True)
                        index += 1
                    return index

                chunks = asyncio.run(stream())
                print(
                    json.dumps({"ok": True, "done": True, "chunks": chunks, "total_ms": (time.perf_counter() - start) * 1000}), flush=True
                )
                continue
            with contextlib.redirect_stdout(sys.stderr):
                if engine in ("kokoro", "kokoro_mlx"):
                    audio, rate = model.create(spoken_text, voice=config["voice"], speed=config["speed"], lang="en-gb")
                    first_ms = (time.perf_counter() - start) * 1000
                elif engine in ("higgs", "higgs_female"):
                    async def collect():
                        chunks = []
                        first = None
                        async for chunk, rate in model.create_stream(spoken_text):
                            if first is None:
                                first = (time.perf_counter() - start) * 1000
                            chunks.append(chunk)
                        return np.concatenate(chunks), rate, first
                    audio, rate, first_ms = asyncio.run(collect())
                else:
                    mx.random.seed(42)
                    chunks = []
                    first_ms = None
                    for result in model.generate_voice_design(
                        text=spoken_text,
                        instruct=VOICE_STYLE,
                        language="English",
                        temperature=0.7,
                        max_tokens=1200,
                        stream=True,
                        streaming_interval=0.32,
                        verbose=False,
                    ):
                        chunk = np.asarray(result.audio, dtype=np.float32).reshape(-1)
                        if first_ms is None:
                            first_ms = (time.perf_counter() - start) * 1000
                        chunks.append(chunk)
                        rate = result.sample_rate
                    if not chunks:
                        raise RuntimeError("No audio generated")
                    audio = np.concatenate(chunks)
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
                        **(model.memory() if engine == "kokoro_mlx" else {}),
                    }
                ),
                flush=True,
            )
        except Exception as exc:
            # No transcript/text or credentials in operational logs.
            print(json.dumps({"ok": False, "error": type(exc).__name__}), flush=True)


if __name__ == "__main__":
    main()
