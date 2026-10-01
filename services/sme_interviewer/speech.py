"""Bounded subprocess lifecycle: cancellation stops computation as well as playback."""

import asyncio
import base64
import contextlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# The stutter guard (PI F16). Speech is generated while it plays: about 1.36x real time on a quiet machine, and
# 1.05-1.10x measured with another model busy on the same GPU, when playback overtook generation and stuttered.
CHARS_PER_SECOND = 15  # the voice says about 17; fewer overestimates an utterance's length, which errs on the safe side
SAFETY = 1.15          # the rate is taken as this much worse than lately measured
MARGIN = 0.2           # seconds of audio kept in hand beyond what the rate needs
HOLD_LIMIT = 5.0       # never silent longer than this after the first audio is ready


def seconds(chunk):
    """The length of a chunk of 16-bit mono audio."""
    return len(base64.b64decode(chunk["pcm"])) / 2 / chunk["rate"]


class SpeechWorker:
    def __init__(self, engine: str, runtime: Path):
        self.engine = engine
        self.runtime = runtime
        self.process = None
        self.load_ms = None
        self.lock = asyncio.Lock()
        self.request_id = 0

    async def close(self):
        process, self.process = self.process, None
        if process and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 3)
            except TimeoutError:
                process.kill()
                await process.wait()

    async def start(self):
        if self.process and self.process.returncode is None:
            return
        self.runtime.mkdir(parents=True, exist_ok=True)
        # macOS Seatbelt denies all network operations in the model process.
        command = [
            "/usr/bin/sandbox-exec",
            "-f",
            str(ROOT / "offline.sb"),
            sys.executable,
            str(ROOT / "worker.py"),
            self.engine,
            str(self.runtime),
        ]
        with (self.runtime / (self.engine + "-worker.log")).open("wb") as log:
            self.process = await asyncio.create_subprocess_exec(
                *command, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=log, limit=4_000_000
            )
        ready = await self._read()
        if not ready.get("ready"):
            raise RuntimeError("Local speech worker did not initialise")
        self.load_ms = ready["load_ms"]

    async def _read(self):
        line = await asyncio.wait_for(self.process.stdout.readline(), 120)
        if not line:
            raise RuntimeError("Local speech worker exited; inspect its local runtime log")
        return json.loads(line)

    async def synthesize(self, candidate: str, text: str, output: Path):
        async with self.lock:
            try:
                await self.start()
                self.process.stdin.write((json.dumps({"candidate": candidate, "text": text, "output": str(output)}) + "\n").encode())
                await self.process.stdin.drain()
                response = await self._read()
                if not response.get("ok"):
                    raise RuntimeError("Local synthesis failed: " + response.get("error", "unknown"))
                return response
            except BaseException:
                await self.close()
                output.unlink(missing_ok=True)
                raise


    async def stream(self, text):
        """Yield actual speech chunks before the full utterance completes."""
        async with self.lock:
            self.request_id += 1
            request_id = self.request_id
            try:
                await self.start()
                self.process.stdin.write((json.dumps({"candidate": "B", "text": text, "stream": True,
                                                      "id": request_id})+"\n").encode())
                await self.process.stdin.drain()
                while True:
                    result = await self._read()
                    if result.get("done"):
                        return
                    if "chunk" not in result:
                        raise RuntimeError("Streamed speech failed")
                    yield result
            except asyncio.CancelledError:
                # Playback is already invalidated. Ask the worker to stop between frames,
                # then drain its in-flight output so an interruption never forces a cold
                # model reload. An unresponsive worker is still killed within one second.
                with contextlib.suppress(Exception):
                    self.process.stdin.write((json.dumps({"cancel": request_id}) + "\n").encode())
                    await self.process.stdin.drain()

                async def drain():
                    while True:
                        result = await self._read()
                        if result.get("done") or result.get("ok") is False:
                            return
                try:
                    await asyncio.wait_for(drain(), 1)
                except BaseException:
                    await self.close()
                raise
            except BaseException:
                await self.close()
                raise


async def transcribe(runtime: Path, wave_path: Path):
    """Caller provides a validated mono 16 kHz PCM WAV; raw audio is temporary."""
    command = [
        "/usr/bin/sandbox-exec",
        "-f",
        str(ROOT / "offline.sb"),
        str(runtime / "whisper.cpp/build/bin/whisper-cli"),
        "-m",
        str(runtime / "models/ggml-base.en.bin"),
        "-f",
        str(wave_path),
        "-l",
        "en",
        "-nt",
        "-np",
        "-t",
        "4",
    ]
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), 120)
        if process.returncode:
            raise RuntimeError("Local recognition failed")
        return stdout.decode().strip()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


class PreparedSpeech:
    """One bounded, cancellable utterance prepared before its playback is authorised."""

    def __init__(self, worker, text):
        self.text = text
        self.worker = worker
        self.chunks = []
        self.arrived = []  # (when, seconds of audio) per chunk: how fast the voice is being generated
        self.changed = asyncio.Event()
        self.done = False
        self.error = None
        self.held = False
        self.task = asyncio.create_task(self.prepare(worker))

    async def prepare(self, worker):
        size = 0
        try:
            async for chunk in worker.stream(self.text):
                size += len(chunk["pcm"])
                if size > 4_000_000 or len(self.chunks) >= 1024:
                    raise ValueError("Prepared speech exceeds its memory bound")
                self.chunks.append(chunk)
                with contextlib.suppress(KeyError, TypeError, ValueError, ZeroDivisionError):
                    self.arrived.append((time.monotonic(), seconds(chunk)))
                self.changed.set()
        except BaseException as exc:
            self.error = exc
        finally:
            self.done = True
            self._learn_rate()
            self.changed.set()

    def _rate(self):
        """Seconds of audio generated per second since the first chunk; None until enough has arrived to tell."""
        if len(self.arrived) < 4 or self.arrived[-1][0] - self.arrived[0][0] < 0.5:
            return None
        return sum(s for _, s in self.arrived[1:]) / (self.arrived[-1][0] - self.arrived[0][0])

    def _learn_rate(self):
        # Kept on the resident voice, so the next utterance knows at once whether the voice is keeping up.
        rate = self._rate() if self.error is None else None
        if rate is not None and sum(s for _, s in self.arrived) >= 1.0:
            recent = getattr(self.worker, "recent_rate", None)
            with contextlib.suppress(AttributeError):
                self.worker.recent_rate = rate if recent is None else (recent + rate) / 2

    async def hold(self):
        """Start playback only when it will not overtake generation. On a quiet machine the voice is well ahead and
        nothing waits. When it has lately been generated barely faster than it plays, or slower, wait until the audio
        in hand covers the shortfall (length x (1 - rate), plus a margin): a moment's silence, not a stutter (PI F16)."""
        if self.held:
            return
        self.held = True
        recent = getattr(self.worker, "recent_rate", None)
        if not isinstance(recent, (int, float)) or recent / SAFETY >= 1:
            return
        expected = len(self.text) / CHARS_PER_SECOND
        started = self.arrived[0][0] if self.arrived else time.monotonic()
        while not self.done:
            rate = self._rate() or recent
            ready = sum(s for _, s in self.arrived)
            if ready >= expected * max(0.0, 1 - rate / SAFETY) + MARGIN:
                return
            left = started + HOLD_LIMIT - time.monotonic()
            if left <= 0:
                return
            self.changed.clear()
            if self.done:
                return
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self.changed.wait(), left)

    async def wait_ready(self):
        while not self.chunks and not self.done:
            self.changed.clear()
            if not self.chunks and not self.done:
                await self.changed.wait()
        if self.error:
            raise self.error
        if not self.chunks:
            raise RuntimeError("No prepared speech")

    async def stream(self):
        await self.hold()
        index = 0
        while True:
            self.changed.clear()
            while index < len(self.chunks):
                yield self.chunks[index]
                index += 1
            if self.done:
                if self.error:
                    raise self.error
                return
            await self.changed.wait()

    def cancel(self):
        self.task.cancel()
