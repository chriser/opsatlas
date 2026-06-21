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


# Calibrated for nomic-embed-text: relevant passages score ~0.55-0.85, unrelated
# ~0.30-0.40, so 0.45 separates them. Re-tune per embedding model / real corpus.
DEFAULT_MIN_SIMILARITY = 0.45


class RetrievalService:
    def __init__(
        self,
        register: SourceRegister,
        section_store: SectionStore,
        embedder: Embedder | None = None,
        cache: EmbeddingCache | None = None,
        rewriter=None,
        reranker=None,
        min_similarity: float = DEFAULT_MIN_SIMILARITY,
    ) -> None:
        self.register = register
        self.section_store = section_store
        self.embedder = embedder
        self.cache = cache
        self.rewriter = rewriter
        self.reranker = reranker
        self.min_similarity = min_similarity

    def _relevant(self, lexical_score: float, semantic_score: float | None) -> bool:
        # Drop weak matches: by cosine when semantic is available, else require
        # at least one query term (positive BM25).
        if semantic_score is not None:
            return semantic_score >= self.min_similarity
        return lexical_score > 0.0

    def _corpus(self) -> list[tuple]:
        # Only approved sources are queryable (human-in-the-loop governance gate).
        items = []
        for record in self.register.list():
            if record.approval_status != "approved":
                continue
            for section in self.section_store.list_for_source(record.id):
                items.append((record, section))
        return items

    def search(self, query: str, top_k: int = 5) -> tuple[list[SearchResult], str]:
        items = self._corpus()
        if not items or not query.strip():
            return [], "empty"

        # Rewrite the question into a standalone search query (large-corpus quality lever).
        search_query = self.rewriter.rewrite(query) if self.rewriter is not None else query

        texts = [section.text for _, section in items]
        # BM25Plus keeps IDF strictly positive, so it still discriminates on the
        # very small corpora typical of this PoC (plain BM25's IDF can hit zero).
        bm25 = BM25Plus([_tokenize(t) for t in texts])
        lexical = list(bm25.get_scores(_tokenize(search_query)))

        mode = "lexical"
        semantic: list[float] | None = None
        if self.embedder is not None and self.cache is not None:
            try:
                vectors = self.cache.get_or_embed(self.embedder, texts)
                query_vector = self.embedder.embed([search_query])[0]
                semantic = [_cosine(query_vector, v) for v in vectors]
                mode = "hybrid"
            except Exception:
                semantic = None
                mode = "lexical"

        order = self._fuse(lexical, semantic)
        # Gather a larger relevant pool when a reranker can re-order it, else just top_k.
        pool_size = max(top_k, 10) if self.reranker is not None else top_k
        results: list[SearchResult] = []
        for index, score in order:
            if not self._relevant(lexical[index], semantic[index] if semantic is not None else None):
                continue
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
            if len(results) >= pool_size:
                break

        if self.reranker is not None and len(results) > 1:
            new_order = self.reranker.rerank(search_query, [r.text for r in results])
            results = [results[i] for i in new_order]

        return results[:top_k], mode

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
