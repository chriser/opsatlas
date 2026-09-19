"""Loopback-only speech audition and transient microphone transcription."""

from __future__ import annotations

import asyncio
import base64
import binascii
import io
import json
import secrets
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
from .speech import ROOT, SpeechWorker, transcribe

MAX_BODY = 2_000_000


def validate_wave(data: bytes) -> float:
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            frames = audio.getnframes()
            if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getframerate() != 16000:
                raise ValueError("Use mono 16 kHz PCM audio")
            if not 1600 <= frames <= 480000:
                raise ValueError("Record between 0.1 and 30 seconds")
            if len(audio.readframes(frames)) != frames * 2:
                raise ValueError("Incomplete audio")
            return frames / 16000
    except (wave.Error, EOFError) as exc:
        raise ValueError("Invalid WAV audio") from exc


class TurnManager:
    def __init__(self, runtime: Path, worker_factory=SpeechWorker, recognizer=transcribe):
        self.runtime = runtime
        self.workers = {engine: worker_factory(engine, runtime) for engine in {v["engine"] for v in VOICES.values()}}
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
                    path.write_bytes(audio)
                    text = await self.recognizer(self.runtime, path)
                job["text"] = text
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
        return {"id": identifier, "state": "cancelled"}

    async def close(self):
        for key in list(self.jobs):
            await self.cancel(key)
        for worker in self.workers.values():
            await worker.close()


def create_app(runtime: Path | None = None, worker_factory=SpeechWorker, recognizer=transcribe):
    runtime = runtime or ROOT / ".runtime"
    manager = TurnManager(runtime, worker_factory, recognizer)
    token = secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(app):
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

    app = FastAPI(title="OpsAtlas local voice audition", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.manager = manager
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
