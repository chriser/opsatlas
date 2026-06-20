"""Embeddings via a local Ollama model, with a content-hash cache.

Uses the standard library only (urllib) so the backend gains no heavy runtime
dependency. The embedder is injectable; tests pass a fake or ``None``.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Protocol


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OllamaEmbedder:
    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 30.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            payload = json.dumps({"model": self.model, "prompt": text}).encode()
            request = urllib.request.Request(
                f"{self.base_url}/api/embeddings",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                vectors.append(json.loads(response.read())["embedding"])
        return vectors


def _key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class EmbeddingCache:
    """Caches embeddings by text hash so unchanged sections are embedded once."""

    def __init__(self, base_dir: str | Path) -> None:
        self.path = Path(base_dir) / "embeddings.json"

    def _load(self) -> dict[str, list[float]]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text() or "{}")

    def get_or_embed(self, embedder: Embedder, texts: list[str]) -> list[list[float]]:
        cache = self._load()
        missing = list(dict.fromkeys(t for t in texts if _key(t) not in cache))
        if missing:
            for text, vector in zip(missing, embedder.embed(missing)):
                cache[_key(text)] = vector
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(cache))
        return [cache[_key(t)] for t in texts]
