"""Answer generation via a local Ollama model (stdlib only; injectable)."""

from __future__ import annotations

import json
import urllib.request
from typing import Protocol


class Generator(Protocol):
    def generate(self, prompt: str) -> str: ...


# The longest answer in the benchmarks is about 930 tokens (Classic); the bound only stops a runaway generation.
DEFAULT_NUM_PREDICT = 1536


class OllamaGenerator:
    """One model call. ``think=False`` switches off a reasoning model's hidden thinking (ARCH H3a): left on,
    ``qwen3.5:4b`` wrote 1,366–2,623 tokens of reasoning before a one-sentence guide answer (13–28 s against 0.2 s).
    Models that cannot think accept ``False``; ``None`` leaves the model's own default, as before."""

    def __init__(
        self,
        model: str = "qwen2.5:7b-instruct",
        base_url: str = "http://127.0.0.1:11434",
        num_ctx: int = 8192,
        temperature: float = 0.1,
        timeout: float = 120.0,
        think: bool | None = False,
        num_predict: int | None = DEFAULT_NUM_PREDICT,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.num_ctx = num_ctx
        self.temperature = temperature
        self.timeout = timeout
        self.think = think
        self.num_predict = num_predict

    def payload(self, prompt: str) -> dict:
        options: dict = {"num_ctx": self.num_ctx, "temperature": self.temperature}
        if self.num_predict:
            options["num_predict"] = self.num_predict
        body: dict = {"model": self.model, "prompt": prompt, "stream": False, "options": options}
        if self.think is not None:
            body["think"] = self.think
        return body

    def generate(self, prompt: str) -> str:
        payload = json.dumps(self.payload(prompt)).encode()
        request = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read())["response"].strip()
