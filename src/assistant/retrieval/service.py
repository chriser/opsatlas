"""Hybrid retrieval over ingested sections."""

from __future__ import annotations

from pydantic import BaseModel

from ..ingestion.store import SectionStore
from ..observability import fallbacks
from ..sources.register import SourceRegister
from .embedder import Embedder, EmbeddingCache
from .index import CorpusIndex, cosine, tokenize


class SearchResult(BaseModel):
    source_id: str
    source_title: str
    heading: str
    ordinal: int
    text: str
    score: float


_tokenize = tokenize  # the index and the search tokenise alike
_cosine = cosine  # kept for the governance intelligence's pairwise comparisons


# The 0.55 threshold originated from early nomic-embed-text calibration and was
# retained after final proof-of-concept regression and benchmark validation.
# Re-tune when the embedding model or corpus changes materially.
DEFAULT_MIN_SIMILARITY = 0.55


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
        self.index = CorpusIndex(register, section_store)  # built once per corpus change (ARCH F7)

    def _relevant(self, lexical_score: float, semantic_score: float | None) -> bool:
        # Drop weak matches: by cosine when semantic is available, else require
        # at least one query term (positive BM25).
        if semantic_score is not None:
            return semantic_score >= self.min_similarity
        return lexical_score > 0.0

    def _corpus(self) -> list[tuple]:
        """The approved sections, as the index holds them (only approved sources are queryable: the human-in-the-loop
        governance gate)."""
        return list(self.index.current().items)

    def search(self, query: str, top_k: int = 5) -> tuple[list[SearchResult], str]:
        snapshot = self.index.current()
        items = snapshot.items
        if not items or not query.strip():
            return [], "empty"

        # Rewrite the question into a standalone search query (large-corpus quality lever).
        search_query = self.rewriter.rewrite(query) if self.rewriter is not None else query

        lexical = list(snapshot.bm25.get_scores(_tokenize(search_query)))

        mode = "lexical"
        semantic: list[float] | None = None
        if self.embedder is not None and self.cache is not None:
            if not snapshot.pruned:  # once per corpus change: vectors of sections edited away or deleted go
                snapshot.pruned = True
                try:
                    self.cache.prune(self.index.all_texts())
                except OSError:
                    pass  # a cache that cannot be rewritten now is pruned at the next change
            try:
                query_vector = self.embedder.embed([search_query])[0]
                semantic = snapshot.cosines(query_vector, self.embedder, self.cache)
                mode = "hybrid"
            except Exception as exc:
                fallbacks.note("semantic search", exc, kept="lexical search only")
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
