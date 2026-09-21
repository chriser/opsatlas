"""Bounded subprocess lifecycle: cancellation stops computation as well as playback."""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class SpeechWorker:
    def __init__(self, engine: str, runtime: Path):
        self.engine = engine
        self.runtime = runtime
        self.process = None
        self.load_ms = None
        self.lock = asyncio.Lock()

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
            str(self.runtime / "experience-env/bin/python") if self.engine == "pocket" else sys.executable,
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


    async def stream(self, text, style=None):
        """Yield actual speech chunks before the full utterance completes."""
        async with self.lock:
            try:
                await self.start()
                self.process.stdin.write((json.dumps({"candidate": "B", "text": text, "stream": True, "style": style})+"\n").encode())
                await self.process.stdin.drain()
                while True:
                    result = await self._read()
                    if result.get("done"):
                        return
                    if "chunk" not in result:
                        raise RuntimeError("Streamed speech failed")
                    yield result
            except asyncio.CancelledError:
                # Playback is already invalidated. Drain one short in-flight batch so
                # an ordinary interruption does not force a cold model reload.
                # Slow/unresponsive synthesis is still killed within one second.
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
        self.chunks = []
        self.changed = asyncio.Event()
        self.done = False
        self.error = None
        self.task = asyncio.create_task(self.prepare(worker))

    async def prepare(self, worker):
        size = 0
        try:
            async for chunk in worker.stream(self.text):
                size += len(chunk["pcm"])
                if size > 4_000_000 or len(self.chunks) >= 1024:
                    raise ValueError("Prepared speech exceeds its memory bound")
                self.chunks.append(chunk)
                self.changed.set()
        except BaseException as exc:
            self.error = exc
        finally:
            self.done = True
            self.changed.set()

    async def stream(self):
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
