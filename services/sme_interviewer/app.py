"""Loopback-only speech audition and transient microphone transcription."""

from __future__ import annotations

import array
import asyncio
import base64
import binascii
import io
import json
import math
import secrets
import sys
import tempfile
import time
import uuid
import wave
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .catalog import BY_PROMPT, DEFAULT_VOICE, PROMPTS, VOICES
from .continuous import attach_conversation
from .interview import Interviews, routes
from .live import Events, attach
from .speech import ROOT, SpeechWorker, transcribe

MAX_BODY = 8_000_000
MAX_AUDIO_SECONDS = 180


def validate_wave(data: bytes) -> float:
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            frames = audio.getnframes()
            if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getframerate() != 16000:
                raise ValueError("Use mono 16 kHz PCM audio")
            if not 1600 <= frames <= 16000 * MAX_AUDIO_SECONDS:
                raise ValueError("Record between 0.1 and 180 seconds")
            if len(audio.readframes(frames)) != frames * 2:
                raise ValueError("Incomplete audio")
            return frames / 16000
    except (wave.Error, EOFError) as exc:
        raise ValueError("Invalid WAV audio") from exc


def audio_levels(data: bytes):
    with wave.open(io.BytesIO(data), "rb") as audio:
        samples = array.array("h", audio.readframes(audio.getnframes()))
    if sys.byteorder != "little":
        samples.byteswap()
    peak = max(abs(value) for value in samples) / 32768
    rms = math.sqrt(sum(value * value for value in samples) / len(samples)) / 32768
    return {
        "audio_seconds": round(len(samples) / 16000, 3),
        "peak_dbfs": round(20 * math.log10(max(peak, 1e-9)), 1),
        "rms_dbfs": round(20 * math.log10(max(rms, 1e-9)), 1),
    }


def trim_quiet_edges(data: bytes):
    """Remove near-silent edges with 250 ms padding; retain the original preview/metrics."""
    with wave.open(io.BytesIO(data), "rb") as audio:
        samples = array.array("h", audio.readframes(audio.getnframes()))
    if sys.byteorder != "little":
        samples.byteswap()
    first = next((i for i, sample in enumerate(samples) if abs(sample) >= 32), None)
    if first is None:
        return data, {"trimmed_leading_seconds": 0, "recognizer_audio_seconds": len(samples) / 16000}
    last = len(samples) - next(i for i, sample in enumerate(reversed(samples)) if abs(sample) >= 32)
    start, end = max(0, first - 4000), min(len(samples), last + 4000)
    trimmed = samples[start:end]
    if sys.byteorder != "little":
        trimmed.byteswap()
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(trimmed.tobytes())
    return output.getvalue(), {
        "trimmed_leading_seconds": round(start / 16000, 3),
        "recognizer_audio_seconds": round((end - start) / 16000, 3),
    }


class TurnManager:
    def __init__(self, runtime: Path, worker_factory=SpeechWorker, recognizer=transcribe):
        self.runtime = runtime
        self.workers = {engine: worker_factory(engine, runtime) for engine in {v["engine"] for v in VOICES.values()}}
        self.events = None
        self.recognizer = recognizer
        self.jobs: dict[str, dict] = {}

    def prune(self):
        for key, job in list(self.jobs.items()):
            if job["state"] not in {"running", "cancelling"} and time.monotonic() - job["created"] > 600:
                job["path"].unlink(missing_ok=True)
                del self.jobs[key]

    def create(self, candidate: str, text: str | None = None, audio: bytes | None = None):
        self.prune()
        if any(job["state"] in {"running", "cancelling"} for job in self.jobs.values()):
            raise HTTPException(409, "Stop the current request before starting another")
        if len(self.jobs) >= 24:
            oldest = next(iter(self.jobs))
            self.jobs[oldest]["path"].unlink(missing_ok=True)
            del self.jobs[oldest]
        identifier = uuid.uuid4().hex
        folder = self.runtime / "transient"
        folder.mkdir(parents=True, exist_ok=True)
        job = {"id": identifier, "state": "running", "created": time.monotonic(), "path": folder / (identifier + ".wav")}
        self.jobs[identifier] = job
        job["task"] = asyncio.create_task(self._run(job, candidate, text, audio))
        return {"id": identifier, "state": job["state"]}

    async def _run(self, job, candidate, text, audio):
        start = time.perf_counter()
        try:
            if audio is not None:
                with tempfile.TemporaryDirectory(prefix="sme-audio-") as directory:
                    path = Path(directory) / "input.wav"
                    prepared, trimmed = trim_quiet_edges(audio)
                    path.write_bytes(prepared)
                    job.update(trimmed)
                    text = await self.recognizer(self.runtime, path)
                job["text"] = text
                job.update(audio_levels(audio))
                if job["audio_seconds"] >= 10 and len(text.split()) <= 2:
                    job["warning"] = (
                        "Very few words were recognised from this recording. "
                        "Listen to your recording and check the microphone before confirming."
                    )
                job["recognition_ms"] = (time.perf_counter() - start) * 1000
                # Transcription is never silently sent to a dialogue model or spoken as a fact.
                job["state"] = "ready"
                return
            metrics = await self.workers[VOICES[candidate]["engine"]].synthesize(candidate, text, job["path"])
            job.update(metrics)
            job["wall_ms"] = (time.perf_counter() - start) * 1000
            job["state"] = "ready"
        except asyncio.CancelledError:
            job["state"] = "cancelled"
            job["path"].unlink(missing_ok=True)
        except Exception:
            job["state"] = "failed"
            job["error"] = "The local audio worker could not complete this request. Check setup and try again."
            job["path"].unlink(missing_ok=True)

        finally:
            if self.events:
                self.events.publish("audio", {k: v for k, v in job.items() if k not in {"task", "path", "created"}})

    async def cancel(self, identifier):
        job = self.jobs.get(identifier)
        if not job:
            raise HTTPException(404, "Request expired")
        if job["state"] in {"running", "cancelling"}:
            if job["state"] == "running":
                job["state"] = "cancelling"
                job["task"].cancel()
            await asyncio.gather(job["task"], return_exceptions=True)
        job["state"] = "cancelled"
        job["path"].unlink(missing_ok=True)
        job.pop("text", None)
        if self.events:
            self.events.publish("audio", {"id": identifier, "state": "cancelled"})
        return {"id": identifier, "state": "cancelled"}

    async def close(self):
        for key in list(self.jobs):
            await self.cancel(key)
        for worker in self.workers.values():
            await worker.close()


def create_app(runtime: Path | None = None, worker_factory=SpeechWorker, recognizer=transcribe, planner=None, evidence=None):
    runtime = runtime or ROOT / ".runtime"
    manager = TurnManager(runtime, worker_factory, recognizer)
    interviews = Interviews(runtime, planner, evidence)
    token = secrets.token_urlsafe(32)
    events = Events()
    manager.events = interviews.events = events

    @asynccontextmanager
    async def lifespan(app):
        interviews.store.recover()
        folder = runtime / "transient"
        if folder.exists():
            for path in folder.glob("*.wav"):
                if len(path.stem) == 32 and all(c in "0123456789abcdef" for c in path.stem):
                    path.unlink(missing_ok=True)

        async def cleanup():
            while True:
                await asyncio.sleep(30)
                manager.prune()

        cleaner = asyncio.create_task(cleanup())
        try:
            yield
        finally:
            cleaner.cancel()
            await asyncio.gather(cleaner, return_exceptions=True)
            await manager.close()
            await interviews.close()

    app = FastAPI(title="OpsAtlas local voice audition", lifespan=lifespan, docs_url=None, redoc_url=None)
    attach(app, token, interviews, manager, events)
    attach_conversation(app, runtime, token, interviews)
    app.state.manager = manager
    app.state.interviews = interviews
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])

    @app.middleware("http")
    async def local_boundary(request, call_next):
        origin = request.headers.get("origin")
        expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
        if origin and origin != expected:
            return JSONResponse({"detail": "Use the local audition page"}, status_code=403)
        if request.method != "GET" and not secrets.compare_digest(request.headers.get("x-sme-token", ""), token):
            return JSONResponse({"detail": "Refresh the local audition page"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; media-src 'self' blob:; "
            "connect-src 'self'; object-src 'none'; frame-ancestors 'none'"
        )
        return response

    async def body(request):
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > MAX_BODY:
                raise HTTPException(413, "Audio request is too large")
        try:
            result = json.loads(data)
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(400, "Invalid request") from exc

    app.include_router(routes(interviews, body, manager))

    @app.get("/interview")
    async def interview_page():
        return FileResponse(ROOT / "web/interview.html")

    @app.get("/conversation")
    async def conversation_page():
        return FileResponse(ROOT / "web/conversation.html")

    @app.get("/conversation.js")
    async def conversation_script():
        return FileResponse(ROOT / "web/conversation.js")

    @app.get("/conversation.css")
    async def conversation_style():
        return FileResponse(ROOT / "web/conversation.css")

    @app.get("/voice-worklet.js")
    async def voice_worklet():
        return FileResponse(ROOT / "web/voice-worklet.js", media_type="application/javascript")

    @app.get("/live.js")
    async def live_script():
        return FileResponse(ROOT / "web/live.js")

    @app.get("/timing.js")
    async def timing_script():
        return FileResponse(ROOT / "web/timing.js")

    @app.get("/interview.js")
    async def interview_javascript():
        return FileResponse(ROOT / "web/interview.js", media_type="text/javascript")

    @app.get("/interview.css")
    async def interview_stylesheet():
        return FileResponse(ROOT / "web/interview.css", media_type="text/css")

    @app.get("/")
    async def index():
        return FileResponse(ROOT / "web/index.html")

    @app.get("/app.js")
    async def javascript():
        return FileResponse(ROOT / "web/app.js", media_type="text/javascript")

    @app.get("/style.css")
    async def stylesheet():
        return FileResponse(ROOT / "web/style.css", media_type="text/css")

    @app.get("/api/bootstrap")
    async def bootstrap():
        return {
            "token": token,
            "prompts": PROMPTS,
            "candidates": list(VOICES),
            "default_voice": DEFAULT_VOICE,
            "stage": "G1 voice audition",
            "available": {key: [p["id"] for p in PROMPTS if (runtime / "audition" / f"{key}-{p['id']}.wav").exists()] for key in VOICES},
        }

    @app.get("/api/models")
    async def models():
        return VOICES

    @app.get("/api/samples/{candidate}/{prompt}")
    async def sample(candidate: str, prompt: str):
        if candidate not in VOICES or prompt not in BY_PROMPT:
            raise HTTPException(404, "Unknown sample")
        path = runtime / "audition" / f"{candidate}-{prompt}.wav"
        if not path.exists():
            raise HTTPException(404, "This sample has not been prepared")
        return FileResponse(path, media_type="audio/wav")

    @app.post("/api/turns")
    async def turn(request: Request):
        data = await body(request)
        candidate = data.get("candidate")
        text = data.get("text")
        if not isinstance(candidate, str) or candidate not in VOICES or not isinstance(text, str) or not 1 <= len(text.strip()) <= 600:
            raise HTTPException(400, "Choose a candidate and enter 1–600 characters")
        return manager.create(candidate, text=text.strip())

    @app.post("/api/transcribe")
    async def recognize(request: Request):
        data = await body(request)
        try:
            audio = base64.b64decode(data.get("wave", ""), validate=True)
            validate_wave(audio)
            levels = audio_levels(audio)
            if levels["peak_dbfs"] < -50 or levels["rms_dbfs"] < -65:
                raise ValueError(
                    "No usable microphone signal. Select your headset microphone, check its mute switch and input level, then record again."
                )
        except (ValueError, TypeError, binascii.Error) as exc:
            raise HTTPException(400, str(exc)[:120]) from exc
        return manager.create("A", audio=audio)

    @app.get("/api/turns/{identifier}")
    async def status(identifier: str):
        manager.prune()
        job = manager.jobs.get(identifier)
        if not job:
            raise HTTPException(404, "Request expired")
        return {k: v for k, v in job.items() if k not in {"task", "path", "created"}}

    @app.get("/api/turns/{identifier}/audio")
    async def audio(identifier: str):
        job = manager.jobs.get(identifier)
        if not job or job["state"] != "ready" or not job["path"].exists():
            raise HTTPException(404, "Audio is not ready or was cancelled")
        return FileResponse(job["path"], media_type="audio/wav")

    @app.post("/api/turns/{identifier}/cancel")
    async def cancel(identifier: str):
        return await manager.cancel(identifier)

    return app


app = create_app()
