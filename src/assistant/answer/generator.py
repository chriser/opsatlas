"""Answer generation via a local Ollama model (stdlib only; injectable)."""

from __future__ import annotations

import json
import urllib.request
from typing import Protocol


class Generator(Protocol):
    def generate(self, prompt: str) -> str: ...


class OllamaGenerator:
    def __init__(
        self,
        model: str = "qwen2.5:7b-instruct",
        base_url: str = "http://127.0.0.1:11434",
        num_ctx: int = 8192,
        temperature: float = 0.1,
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.num_ctx = num_ctx
        self.temperature = temperature
        self.timeout = timeout

    def generate(self, prompt: str) -> str:
        return self._generate(prompt)

    def generate_json(self, prompt: str) -> str:
        """Request one valid JSON object from Ollama for tool protocols."""

        return self._generate(prompt, response_format="json")

    def _generate(self, prompt: str, *, response_format: str = "") -> str:
        payload_body = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_ctx": self.num_ctx, "temperature": self.temperature},
        }
        if response_format:
            payload_body["format"] = response_format
        payload = json.dumps(payload_body).encode()
        request = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read())["response"].strip()
