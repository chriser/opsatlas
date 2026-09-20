"""Persistent offline inference pipes. A cancelled request cannot leak into the next one."""

import asyncio
import json

from .speech import ROOT


class Resident:
    def __init__(self, runtime, mode, model="ggml-base.en.bin"):
        if model not in {"ggml-base.en.bin", "ggml-small.en.bin"}:
            raise ValueError("Unknown local recognition model")
        self.runtime, self.mode, self.model = runtime, mode, model
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
        async with self.lock:
            try:
                await self.start()
                self.process.stdin.write((str(len(pcm_float) // 4) + "\n").encode() + pcm_float)
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
