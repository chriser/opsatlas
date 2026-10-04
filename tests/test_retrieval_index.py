"""The in-memory search index (ARCH F7): the same results as the search it replaces, rebuilt only when the corpus
changes, an embedder that was down retried, and an embeddings cache that no longer grows for ever."""
import hashlib
import math
import random
import threading

import pytest
from rank_bm25 import BM25Plus

from assistant.ingestion.store import Section, SectionStore
from assistant.retrieval.embedder import EmbeddingCache
from assistant.retrieval.index import cosine, tokenize
from assistant.retrieval.service import RetrievalService
from assistant.sources.models import SourceRecord
from assistant.sources.register import SourceRegister
from tests.door_helpers import decided

WORDS = "supplier onboarding credit check approval invoice payment dispute return warehouse pick pack ship customer contract".split()


class HashEmbedder:
    """Deterministic vectors from the text, so two implementations see the same numbers; counts its calls."""

    def __init__(self, dim: int = 16) -> None:
        self.dim, self.calls, self.down = dim, 0, False

    def embed(self, texts):
        if self.down:
            raise ConnectionError("embedder down")
        self.calls += 1
        out = []
        for text in texts:
            rng = random.Random(text)
            out.append([rng.uniform(-1, 1) for _ in range(self.dim)])
        return out


def reference_search(register, store, embedder, cache, query, top_k, min_similarity=0.55):
    """The search as it was before the index: rebuilt on every call, cosines one by one."""
    items = [(r, s) for r in register.list() if r.approval_status == "approved" for s in store.list_for_source(r.id)]
    if not items:
        return [], "empty"
    texts = [s.text for _, s in items]
    bm25 = BM25Plus([tokenize(t) for t in texts])
    lexical = list(bm25.get_scores(tokenize(query)))
    semantic = None
    mode = "lexical"
    if embedder is not None:
        vectors = cache.get_or_embed(embedder, texts)
        q = embedder.embed([query])[0]
        semantic = [cosine(q, v) for v in vectors]
        mode = "hybrid"
    order = RetrievalService._fuse(lexical, semantic)
    results = []
    for index, score in order:
        relevant = semantic[index] >= min_similarity if semantic is not None else lexical[index] > 0
        if relevant:
            results.append((items[index][0].id, items[index][1].ordinal, round(float(score), 4)))
        if len(results) >= top_k:
            break
    return results, mode


def corpus(tmp_path, sources=6, sections=8, seed=1):
    rng = random.Random(seed)
    register = SourceRegister(tmp_path)
    store = SectionStore(register.base_dir)
    for i in range(sources):
        body = f"# x{i}".encode()  # a real fingerprint: an approval names its text (REF S23, S8)
        record = SourceRecord(id=f"s{i}", filename=f"s{i}.md", title=f"Source {i}", size_bytes=1,
                              content_sha256=hashlib.sha256(body).hexdigest(),
                              created_at="2026-09-30T00:00:00+00:00", approval_status="approved" if i % 3 else "pending",
                              processing_state="ingested", section_count=sections)
        register.add(record, body)
        texts = [" ".join(rng.choice(WORDS) for _ in range(12)) for _ in range(sections)]
        store.replace_for_source(record.id, [
            Section(source_id=record.id, ordinal=n, heading=f"H{n}", text=text, char_count=len(text)) for n, text in enumerate(texts)])
    return register, store


@pytest.mark.parametrize("hybrid", [False, True])
def test_the_index_returns_exactly_what_the_rebuilt_search_returned(tmp_path, hybrid):
    register, store = corpus(tmp_path)
    embedder = HashEmbedder() if hybrid else None
    cache = EmbeddingCache(tmp_path) if hybrid else None
    service = RetrievalService(register, store, embedder=embedder, cache=cache, min_similarity=0.0 if hybrid else 0.55)
    for query in ("credit check", "supplier invoice payment", "warehouse pick pack ship", "nothing here", "customer contract dispute"):
        expected, expected_mode = reference_search(register, store, embedder, cache, query, 5, service.min_similarity)
        results, mode = service.search(query, top_k=5)
        assert mode == expected_mode
        assert [(r.source_id, r.ordinal, r.score) for r in results] == expected, query


def test_the_index_is_built_once_and_again_only_when_the_corpus_changes(tmp_path):
    register, store = corpus(tmp_path)
    service = RetrievalService(register, store)
    for _ in range(5):
        service.search("credit check")
    assert service.index.builds == 1
    # A new approved source, an approval, a new version and a deletion each change what is searchable.
    record = SourceRecord(id="new", filename="new.md", title="New", size_bytes=1, content_sha256="f" * 64,
                          created_at="2026-09-30T00:00:00+00:00", approval_status="approved", processing_state="ingested", section_count=1)
    register.add(record, b"# new")
    store.replace_for_source("new", [Section(source_id="new", ordinal=0, heading="H", text="a brand new credit check rule", char_count=29)])
    assert any(r.source_id == "new" for r in service.search("brand new credit check rule")[0]) and service.index.builds == 2
    decided(register, "s0", approval_status="approved")
    service.search("credit check")
    assert service.index.builds == 3
    register.update("new", version=2, section_count=1)
    service.search("credit check")
    assert service.index.builds == 4
    register.remove("new")
    assert not any(r.source_id == "new" for r in service.search("brand new credit check rule")[0]) and service.index.builds == 5
    service.search("credit check")
    assert service.index.builds == 5  # nothing changed: nothing rebuilt


def test_an_embedder_that_was_down_is_retried_and_the_corpus_vectors_are_fetched_once(tmp_path):
    register, store = corpus(tmp_path)
    embedder, cache = HashEmbedder(), EmbeddingCache(tmp_path)
    service = RetrievalService(register, store, embedder=embedder, cache=cache, min_similarity=0.0)
    embedder.down = True
    assert service.search("credit check")[1] == "lexical"  # fell back, as before
    embedder.down = False
    assert service.search("credit check")[1] == "hybrid"
    calls = embedder.calls
    for _ in range(4):
        service.search("supplier invoice")
    assert embedder.calls == calls + 4  # one call per search, for the query; the corpus is embedded once


def test_the_embeddings_cache_is_pruned_of_texts_no_longer_in_the_corpus(tmp_path):
    cache = EmbeddingCache(tmp_path)
    embedder = HashEmbedder()
    cache.get_or_embed(embedder, ["kept one", "kept two", "gone one", "gone two"])
    assert len(cache) == 4
    assert cache.prune(["kept one", "kept two"]) == 2 and len(cache) == 2
    assert cache.prune(["kept one", "kept two"]) == 0
    assert cache.get_or_embed(embedder, ["kept one"]) and embedder.calls == 1  # still cached


def test_searches_from_several_threads_share_one_build(tmp_path):
    register, store = corpus(tmp_path, sources=9, sections=20)
    service = RetrievalService(register, store)
    errors = []

    def worker():
        try:
            for _ in range(10):
                service.search("credit check")
        except Exception as exc:  # pragma: no cover - the assertion below reports it
            errors.append(exc)
    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors and service.index.builds == 1


def test_the_reference_cosine_matches_the_matrix_cosine(tmp_path):
    register, store = corpus(tmp_path, sources=3, sections=5)
    embedder, cache = HashEmbedder(), EmbeddingCache(tmp_path)
    service = RetrievalService(register, store, embedder=embedder, cache=cache)
    snapshot = service.index.current()
    query = embedder.embed(["credit check"])[0]
    expected = [cosine(query, v) for v in cache.get_or_embed(embedder, snapshot.texts)]
    assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(snapshot.cosines(query, embedder, cache), expected))


def test_a_deleted_sources_vectors_leave_the_cache_at_the_next_search(tmp_path):
    register, store = corpus(tmp_path, sources=3, sections=4)  # s1, s2 approved; s0 pending (its vectors are kept)
    embedder, cache = HashEmbedder(), EmbeddingCache(tmp_path)
    service = RetrievalService(register, store, embedder=embedder, cache=cache, min_similarity=0.0)
    service.search("credit check")
    assert len(cache) == 8  # the approved sections only were embedded
    cache.get_or_embed(embedder, ["a text from nowhere"])
    register.remove("s2")
    service.search("credit check")
    assert len(cache) == 4  # s2's four vectors and the stray one are gone; s1's stay
