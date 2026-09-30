"""An in-memory search index, built once per corpus change (ARCH F7).

Until now every search read the register and every section file, tokenised every section for BM25 and, in hybrid
mode, loaded the whole embeddings cache and took each cosine in pure Python: about a second per search at five
thousand sections, four at twenty thousand (measured on 30 September 2026). The index keeps, per core, the approved
sections, their BM25 model and one normalised matrix of their embeddings, and rebuilds them only when the register's
approved records change (a source uploaded, approved, edited, transferred, deleted). The search itself then costs a
BM25 pass and one matrix product. Scores are the same as before: the same tokens, the same BM25Plus over the same
sections in the same order, cosines against the same vectors.
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field

import numpy as np
from rank_bm25 import BM25Plus

from ..ingestion.store import Section, SectionStore
from ..sources.models import SourceRecord
from ..sources.register import SourceRegister
from .embedder import Embedder, EmbeddingCache


def tokenize(text: str) -> list[str]:
    return [w for w in text.lower().split() if w]


def cosine(a: list[float], b: list[float]) -> float:
    """One cosine in plain Python: the reference the matrix reproduces, and what pairwise comparisons elsewhere use."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


@dataclass
class Snapshot:
    """The searchable corpus at one moment: immutable once built, except the embedding matrix, which is added on
    the first hybrid search (and again after a failed attempt, so an embedder that was down is retried)."""
    fingerprint: tuple
    items: list[tuple[SourceRecord, Section]]
    bm25: BM25Plus | None
    texts: list[str]
    matrix: np.ndarray | None = None  # rows unit-normalised (a zero vector stays zero), float32
    pruned: bool = False  # the embeddings cache was pruned of texts no longer in any section, once per build
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def semantic_matrix(self, embedder: Embedder, cache: EmbeddingCache) -> np.ndarray:
        with self._lock:
            if self.matrix is None:
                vectors = np.asarray(cache.get_or_embed(embedder, self.texts), dtype=np.float32)
                if vectors.ndim != 2:
                    vectors = vectors.reshape(len(self.texts), -1)
                norms = np.linalg.norm(vectors, axis=1, keepdims=True)
                self.matrix = np.divide(vectors, norms, out=np.zeros_like(vectors), where=norms > 0)
            return self.matrix

    def cosines(self, query_vector: list[float], embedder: Embedder, cache: EmbeddingCache) -> list[float]:
        matrix = self.semantic_matrix(embedder, cache)
        query = np.asarray(query_vector, dtype=np.float32)
        norm = float(np.linalg.norm(query))
        if not norm or matrix.size == 0:
            return [0.0] * len(self.items)
        return (matrix @ (query / norm)).astype(np.float64).tolist()


class CorpusIndex:
    def __init__(self, register: SourceRegister, section_store: SectionStore) -> None:
        self.register = register
        self.section_store = section_store
        self._snapshot: Snapshot | None = None
        self._lock = threading.Lock()
        self.builds = 0  # how many times the index was built (tests and diagnostics)

    def fingerprint(self) -> tuple:
        """What the searchable corpus is: the approved records with their version, content and section count. It
        reads only the register, so checking it on every search is cheap."""
        return tuple(
            (r.id, r.version, r.content_sha256, r.section_count)
            for r in self.register.list()
            if r.approval_status == "approved"
        )

    def current(self) -> Snapshot:
        fingerprint = self.fingerprint()
        snapshot = self._snapshot
        if snapshot is not None and snapshot.fingerprint == fingerprint:
            return snapshot
        with self._lock:
            snapshot = self._snapshot
            if snapshot is not None and snapshot.fingerprint == fingerprint:
                return snapshot
            self._snapshot = snapshot = self._build(fingerprint)
            self.builds += 1
            return snapshot

    def _build(self, fingerprint: tuple) -> Snapshot:
        # Only approved sources are searchable (the human-in-the-loop governance gate), in the register's order.
        items: list[tuple[SourceRecord, Section]] = []
        for record in self.register.list():
            if record.approval_status != "approved":
                continue
            for section in self.section_store.list_for_source(record.id):
                items.append((record, section))
        texts = [section.text for _, section in items]
        # BM25Plus keeps IDF strictly positive, so it still discriminates on the very small corpora typical of this
        # PoC (plain BM25's IDF can hit zero).
        bm25 = BM25Plus([tokenize(t) for t in texts]) if texts else None
        return Snapshot(fingerprint, items, bm25, texts)

    def all_texts(self) -> list[str]:
        """Every section's text, approved or not: what the embeddings cache should keep."""
        return [s.text for r in self.register.list() for s in self.section_store.list_for_source(r.id)]

    def invalidate(self) -> None:
        with self._lock:
            self._snapshot = None
