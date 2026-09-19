"""Persistent isolated TTS worker. JSON lines on stdin/stdout; no network access."""

import contextlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))
from services.sme_interviewer.catalog import VOICE_STYLE, VOICES  # noqa: E402

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
            options.intra_op_num_threads = 4
            options.inter_op_num_threads = 1
            session = ort.InferenceSession(
                str(runtime / "models/kokoro-v1.0.onnx"), sess_options=options, providers=["CPUExecutionProvider"]
            )
            model = Kokoro.from_session(session, str(runtime / "models/voices-v1.0.bin"))
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
            if config["engine"] != engine or not 1 <= len(request["text"]) <= 600:
                raise ValueError("Invalid synthesis request")
            start = time.perf_counter()
            with contextlib.redirect_stdout(sys.stderr):
                if engine == "kokoro":
                    audio, rate = model.create(request["text"], voice=config["voice"], speed=config["speed"], lang="en-gb")
                    first_ms = (time.perf_counter() - start) * 1000
                else:
                    mx.random.seed(42)
                    chunks = []
                    first_ms = None
                    for result in model.generate_voice_design(
                        text=request["text"],
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
                    }
                ),
                flush=True,
            )
        except Exception as exc:
            # No transcript/text or credentials in operational logs.
            print(json.dumps({"ok": False, "error": type(exc).__name__}), flush=True)


if __name__ == "__main__":
    main()
