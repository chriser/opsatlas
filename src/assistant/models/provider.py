"""Model provider interface and the Ollama adapter.

A provider exposes embed / generate / health. Services depend on the provider
rather than a hardcoded backend, so the LLM and embedding models can be swapped
via environment configuration (no code changes) — e.g. to A/B a larger model.
"""

from __future__ import annotations

import os
import urllib.request
from typing import Protocol

from ..answer.generator import DEFAULT_NUM_PREDICT, OllamaGenerator
from ..retrieval.embedder import OllamaEmbedder

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_LLM_MODEL = "qwen2.5:7b-instruct"
DEFAULT_EMBED_MODEL = "nomic-embed-text"


class ModelProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def generate(self, prompt: str) -> str: ...
    def health(self) -> dict: ...


class OllamaProvider:
    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_URL,
        llm_model: str = DEFAULT_LLM_MODEL,
        embed_model: str = DEFAULT_EMBED_MODEL,
        num_ctx: int = 8192,
        temperature: float = 0.1,
        timeout: float = 120.0,
        think: bool | None = False,
        num_predict: int | None = DEFAULT_NUM_PREDICT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.llm_model = llm_model
        self.embed_model = embed_model
        self._embedder = OllamaEmbedder(model=embed_model, base_url=self.base_url)
        self._generator = OllamaGenerator(
            model=llm_model, base_url=self.base_url, num_ctx=num_ctx, temperature=temperature, timeout=timeout,
            think=think, num_predict=num_predict,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._embedder.embed(texts)

    def generate(self, prompt: str) -> str:
        return self._generator.generate(prompt)

    def info(self) -> dict:
        return {"backend": "ollama", "llm": self.llm_model, "embed": self.embed_model}

    def health(self) -> dict:
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=3) as r:
                r.read()
            return {"ok": True, **self.info()}
        except Exception:
            return {"ok": False, **self.info()}


def provider_from_env() -> OllamaProvider:
    return OllamaProvider(
        base_url=os.environ.get("KP_OLLAMA_URL", DEFAULT_OLLAMA_URL),
        llm_model=os.environ.get("KP_LLM_MODEL", DEFAULT_LLM_MODEL),
        embed_model=os.environ.get("KP_EMBED_MODEL", DEFAULT_EMBED_MODEL),
        num_ctx=int(os.environ.get("KP_LLM_NUM_CTX", "8192")),
        timeout=float(os.environ.get("KP_LLM_TIMEOUT", "120")),  # seconds per generation; a loaded machine may need more
        think=_think_setting(os.environ.get("KP_LLM_THINK", "0")),
        num_predict=int(os.environ.get("KP_LLM_NUM_PREDICT", str(DEFAULT_NUM_PREDICT))) or None,
    )


def _think_setting(value: str) -> bool | None:
    """KP_LLM_THINK: "0" (the default) switches a reasoning model's thinking off, "1" on, "auto" leaves the model's own."""
    value = value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"auto", ""}:
        return None
    return False
