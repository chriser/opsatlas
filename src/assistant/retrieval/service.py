"""Hybrid retrieval over ingested sections."""

from __future__ import annotations

import math

from pydantic import BaseModel
from rank_bm25 import BM25Plus

from ..ingestion.store import SectionStore
from ..sources.register import SourceRegister
from .embedder import Embedder, EmbeddingCache


class SearchResult(BaseModel):
    source_id: str
    source_title: str
    heading: str
    ordinal: int
    text: str
    score: float


def _tokenize(text: str) -> list[str]:
    return [w for w in text.lower().split() if w]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class RetrievalService:
    def __init__(
        self,
        register: SourceRegister,
        section_store: SectionStore,
        embedder: Embedder | None = None,
        cache: EmbeddingCache | None = None,
    ) -> None:
        self.register = register
        self.section_store = section_store
        self.embedder = embedder
        self.cache = cache

    def _corpus(self) -> list[tuple]:
        items = []
        for record in self.register.list():
            for section in self.section_store.list_for_source(record.id):
                items.append((record, section))
        return items

    def search(self, query: str, top_k: int = 5) -> tuple[list[SearchResult], str]:
        items = self._corpus()
        if not items or not query.strip():
            return [], "empty"

        texts = [section.text for _, section in items]
        # BM25Plus keeps IDF strictly positive, so it still discriminates on the
        # very small corpora typical of this PoC (plain BM25's IDF can hit zero).
        bm25 = BM25Plus([_tokenize(t) for t in texts])
        lexical = list(bm25.get_scores(_tokenize(query)))

        mode = "lexical"
        semantic: list[float] | None = None
        if self.embedder is not None and self.cache is not None:
            try:
                vectors = self.cache.get_or_embed(self.embedder, texts)
                query_vector = self.embedder.embed([query])[0]
                semantic = [_cosine(query_vector, v) for v in vectors]
                mode = "hybrid"
            except Exception:
                semantic = None
                mode = "lexical"

        order = self._fuse(lexical, semantic)
        results: list[SearchResult] = []
        for index, score in order[:top_k]:
            record, section = items[index]
            results.append(
                SearchResult(
                    source_id=record.id,
                    source_title=record.title,
                    heading=section.heading,
                    ordinal=section.ordinal,
                    text=section.text,
                    score=round(float(score), 4),
                )
            )
        return results, mode

    @staticmethod
    def _fuse(lexical: list[float], semantic: list[float] | None) -> list[tuple[int, float]]:
        n = len(lexical)
        if semantic is None:
            order = sorted(range(n), key=lambda i: lexical[i], reverse=True)
            return [(i, lexical[i]) for i in order]

        # Reciprocal rank fusion of the two rankings.
        lex_rank = {i: r for r, i in enumerate(sorted(range(n), key=lambda i: lexical[i], reverse=True))}
        sem_rank = {i: r for r, i in enumerate(sorted(range(n), key=lambda i: semantic[i], reverse=True))}
        k = 60
        rrf = {i: 1.0 / (k + lex_rank[i]) + 1.0 / (k + sem_rank[i]) for i in range(n)}
        order = sorted(range(n), key=lambda i: rrf[i], reverse=True)
        return [(i, rrf[i]) for i in order]
