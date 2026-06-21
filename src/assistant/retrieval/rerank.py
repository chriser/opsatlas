"""Reranking — re-order retrieved candidates by relevance.

A local/OSS reranker: one bounded model call scores the candidate passages
against the query and returns a new order. Falls back to the original order on
any failure.
"""

from __future__ import annotations

import re
from typing import Protocol

from ..answer.generator import Generator

_RERANK_PROMPT = (
    "Rank the PASSAGES by how well they answer the QUESTION. Return the passage "
    "numbers, most relevant first, comma-separated (e.g. 2,1,3). Numbers only.\n\n"
    "QUESTION: {q}\n\nPASSAGES:\n{passages}"
)
_MAX_PASSAGE_CHARS = 500


class Reranker(Protocol):
    def rerank(self, query: str, passages: list[str]) -> list[int]: ...


class LLMReranker:
    def __init__(self, generator: Generator) -> None:
        self.generator = generator

    def rerank(self, query: str, passages: list[str]) -> list[int]:
        n = len(passages)
        if n <= 1:
            return list(range(n))
        listing = "\n".join(f"[{i + 1}] {p[:_MAX_PASSAGE_CHARS]}" for i, p in enumerate(passages))
        try:
            out = self.generator.generate(_RERANK_PROMPT.format(q=query, passages=listing))
        except Exception:
            return list(range(n))
        order: list[int] = []
        for match in re.findall(r"\d+", out):
            idx = int(match) - 1
            if 0 <= idx < n and idx not in order:
                order.append(idx)
        for i in range(n):  # append any the model omitted, preserving coverage
            if i not in order:
                order.append(i)
        return order
