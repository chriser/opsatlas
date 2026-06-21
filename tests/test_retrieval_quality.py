"""Tests for query rewriting and the relevance threshold (hermetic)."""

from assistant.ingestion.sections import build_sections
from assistant.ingestion.store import SectionStore
from assistant.retrieval.embedder import EmbeddingCache
from assistant.retrieval.rewrite import QueryRewriter
from assistant.retrieval.service import RetrievalService
from assistant.sources.register import SourceRegister
from assistant.sources.service import register_upload


class FakeGen:
    def generate(self, prompt):
        return "credit checks gates\n(extra ignored line)"


def seed(tmp_path, embedder=None):
    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    body = "# Controls\n\nDue diligence and credit checks are mandatory gates."
    rec = register_upload(reg, "a.md", body.encode())
    store.replace_for_source(rec.id, build_sections(rec.id, body))
    reg.update(rec.id, approval_status="approved")
    cache = EmbeddingCache(reg.base_dir) if embedder else None
    return reg, store, cache


def test_query_rewriter_takes_first_line():
    assert QueryRewriter(FakeGen()).rewrite("erm, what about the checks?") == "credit checks gates"


def test_rewriter_is_applied_in_search(tmp_path):
    reg, store, _ = seed(tmp_path)
    retrieval = RetrievalService(reg, store, rewriter=QueryRewriter(FakeGen()))
    # The raw question shares no terms, but the rewrite ("credit checks gates") does.
    results, _ = retrieval.search("zzz")
    assert results and results[0].heading == "Controls"


def test_relevance_threshold_filters_irrelevant(tmp_path):
    class Orthogonal:
        def embed(self, texts):
            return [[0.0, 1.0, 0.0] if "credit" in t.lower() else [1.0, 0.0, 0.0] for t in texts]

    reg, store, cache = seed(tmp_path, embedder=Orthogonal())
    retrieval = RetrievalService(reg, store, embedder=Orthogonal(), cache=cache, min_similarity=0.5)
    # Query embeds to [1,0,0]; the only section embeds to [0,1,0] -> cosine 0 -> filtered.
    results, mode = retrieval.search("dogs")
    assert mode == "hybrid"
    assert results == []


def test_below_threshold_falls_back_in_answer(tmp_path):
    # Lexical-only: a query with no matching terms returns no passages.
    reg, store, _ = seed(tmp_path)
    retrieval = RetrievalService(reg, store)
    assert retrieval.search("xylophone")[0] == []
