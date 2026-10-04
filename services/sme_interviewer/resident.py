"""Persistent offline inference pipes. A cancelled request cannot leak into the next one."""

import asyncio
import json

from .speech import ROOT


class Resident:
    def __init__(self, runtime, mode, model="ggml-base.en.bin", vocabulary=None):
        if model not in {"ggml-base.en.bin", "ggml-small.en.bin"}:
            raise ValueError("Unknown local recognition model")
        if vocabulary is not None and (not isinstance(vocabulary, str) or not 1 <= len(vocabulary) <= 400):
            raise ValueError("Use a short recognition vocabulary")
        self.runtime, self.mode, self.model = runtime, mode, model
        # Product names whisper would otherwise mishear ("OpsAtlas" as "all sadness").
        self.vocabulary = vocabulary if mode == "asr" else None
        self.process = None
        self.lock = asyncio.Lock()

    async def start(self):
        if self.process and self.process.returncode is None:
            return
        model = "ggml-silero-v6.2.0.bin" if self.mode == "vad" else self.model
        with (self.runtime / (self.mode + "-resident.log")).open("wb") as log:
            self.process = await asyncio.create_subprocess_exec(
                "/usr/bin/sandbox-exec",
                "-f",
                str(ROOT / "offline.sb"),
                str(self.runtime / "conversation-recognizer"),
                self.mode,
                str(self.runtime / "models" / model),
                *([self.vocabulary] if self.vocabulary else []),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=log,
            )
        if not (await self.read()).get("ready"):
            raise RuntimeError("Resident speech engine did not start")

    async def read(self):
        raw = await asyncio.wait_for(self.process.stdout.readline(), 30)
        if not raw:
            raise RuntimeError("Resident speech engine stopped")
        result = json.loads(raw)
        if result.get("error"):
            raise RuntimeError("Local recognition failed")
        return result

    async def infer(self, pcm_float):
        return await self._infer(pcm_float, False)

    async def final(self, pcm_float):
        return await self._infer(pcm_float, True)

    async def _infer(self, pcm_float, final):
        async with self.lock:
            try:
                await self.start()
                suffix = " final" if final else ""
                self.process.stdin.write((str(len(pcm_float) // 4) + suffix + "\n").encode() + pcm_float)
                await self.process.stdin.drain()
                return await self.read()
            except BaseException:
                await self.close()
                raise

    async def close(self):
        process, self.process = self.process, None
        if process and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 2)
            except TimeoutError:
                process.kill()
                await process.wait()
