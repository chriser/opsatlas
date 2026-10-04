"""Fallbacks made visible (ARCH F5): a step that fails is logged as a warning and kept with the answer's audit record."""
import logging

from fastapi.testclient import TestClient

from assistant.answer.service import AnswerService
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.ingestion.store import SectionStore
from assistant.observability import fallbacks
from assistant.observability.trace import AuditTrace
from assistant.retrieval.embedder import EmbeddingCache
from assistant.retrieval.rerank import LLMReranker
from assistant.retrieval.rewrite import QueryRewriter
from assistant.retrieval.service import RetrievalService
from assistant.sources.register import SourceRegister

PASSWORD = "test-pass"
DOC = """# Supplier setup
Supplier setup begins with a business request and a completed form.
# Credit controls
Due diligence and credit checks are mandatory gates before onboarding.
"""
REWRITE_FELL_BACK = {"step": "query rewrite", "cause": "ConnectionError: model not reachable", "kept": "the question as asked"}


class Broken:
    """A model that is down: every call raises."""

    def generate(self, prompt: str) -> str:
        raise ConnectionError("model not reachable")

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise ConnectionError("embedder not reachable")


class Answers:
    def generate(self, prompt: str) -> str:
        return "Based on the evidence [1], due diligence and credit checks are mandatory gates."


def make(tmp_path, *, rewriter=None, embedder=None, full_context_limit=24000):
    """A client over one approved source, with the retrieval service and the audit trace it writes to."""
    register = SourceRegister(tmp_path)
    store = SectionStore(register.base_dir)
    cache = EmbeddingCache(tmp_path) if embedder is not None else None
    retrieval = RetrievalService(register, store, embedder=embedder, cache=cache, rewriter=rewriter)
    trace = AuditTrace(tmp_path)
    answer = AnswerService(retrieval, Answers(), full_context_char_limit=full_context_limit, audit_trace=trace)
    client = TestClient(create_app(register, AuthService(PASSWORD), retrieval=retrieval, answer=answer))
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    record = client.post("/api/sources/upload", files={"file": ("supplier.md", DOC.encode(), "text/markdown")},
                         data={"title": "Supplier setup"}).json()
    client.post(f"/api/sources/{record['id']}/ingest")
    client.post(f"/api/governance/sources/{record['id']}/approve", json={"sha": record["content_sha256"]})
    return client, retrieval, trace


def test_a_failed_rewrite_keeps_the_question_and_says_so(caplog):
    with caplog.at_level(logging.WARNING, logger="assistant.fallbacks"):
        assert QueryRewriter(Broken()).rewrite("what checks are needed?") == "what checks are needed?"
    assert "Fallback in query rewrite (ConnectionError: model not reachable); kept the question as asked." in caplog.text


def test_a_failed_rerank_keeps_the_search_order_and_says_so(caplog):
    with caplog.at_level(logging.WARNING, logger="assistant.fallbacks"):
        assert LLMReranker(Broken()).rerank("q", ["a", "b", "c"]) == [0, 1, 2]
    assert "Fallback in rerank (ConnectionError: model not reachable); kept the search order." in caplog.text


def test_a_failed_embedding_falls_back_to_lexical_search_and_says_so(tmp_path, caplog):
    _, retrieval, _ = make(tmp_path, embedder=Broken())
    with caplog.at_level(logging.WARNING, logger="assistant.fallbacks"):
        results, mode = retrieval.search("credit checks", top_k=3)
    assert mode == "lexical" and results
    assert "Fallback in semantic search (ConnectionError: embedder not reachable); kept lexical search only." in caplog.text


def test_the_audit_trace_keeps_the_fallbacks_of_each_answer(tmp_path):
    """Two answers over a broken rewriter each record their own fallback; a clean answer records none."""
    client, _, trace = make(tmp_path / "broken", rewriter=QueryRewriter(Broken()), full_context_limit=0)
    for _ in range(2):
        body = client.post("/api/ask", json={"q": "what checks are needed before onboarding?"}).json()
        assert body["mode"] == "retrieval" and body["refused"] is False
    assert [record["fallbacks"] for record in trace.recent(10)] == [[REWRITE_FELL_BACK], [REWRITE_FELL_BACK]]

    client, _, trace = make(tmp_path / "clean", full_context_limit=0)
    assert client.post("/api/ask", json={"q": "what checks are needed before onboarding?"}).json()["refused"] is False
    assert [record["fallbacks"] for record in trace.recent(10)] == [[]]


def test_outside_an_answer_a_fallback_is_logged_but_not_collected(caplog):
    with caplog.at_level(logging.WARNING, logger="assistant.fallbacks"):
        fallbacks.note("rerank", "the model returned nothing usable", kept="the search order")
    assert "Fallback in rerank (the model returned nothing usable); kept the search order." in caplog.text
    assert fallbacks.collect() == []
