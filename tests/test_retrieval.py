"""Retrieval tests — hermetic (no Ollama): lexical-only and a fake embedder."""

from fastapi.testclient import TestClient

from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.ingestion.store import SectionStore
from assistant.retrieval.embedder import EmbeddingCache
from assistant.retrieval.service import RetrievalService
from assistant.sources.register import SourceRegister

PASSWORD = "test-pass"

DOC = """# Supplier setup

Supplier setup begins with a business request and a completed form.

# Credit controls

Due diligence and credit checks are mandatory gates before onboarding.
"""


class FakeEmbedder:
    """Deterministic bag-of-words vectors over a tiny vocabulary (no network)."""

    VOCAB = ["supplier", "request", "diligence", "credit", "checks", "gates"]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(t.lower().count(w)) for w in self.VOCAB] for t in texts]


def make_client(tmp_path, embedder=None) -> TestClient:
    register = SourceRegister(tmp_path)
    store = SectionStore(register.base_dir)
    retrieval = RetrievalService(
        register, store, embedder=embedder, cache=EmbeddingCache(register.base_dir) if embedder else None
    )
    client = TestClient(create_app(register, AuthService(PASSWORD), retrieval=retrieval))
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def seed(client) -> None:
    record = client.post(
        "/api/sources/upload",
        files={"file": ("supplier.md", DOC.encode(), "text/markdown")},
        data={"title": "Supplier setup"},
    ).json()
    client.post(f"/api/sources/{record['id']}/ingest")
    client.post(f"/api/governance/sources/{record['id']}/approve")


def test_query_requires_auth(tmp_path):
    client = make_client(tmp_path)
    client.headers.pop("Authorization")
    assert client.post("/api/query", json={"q": "credit"}).status_code == 401


def test_empty_corpus_returns_empty(tmp_path):
    client = make_client(tmp_path)
    body = client.post("/api/query", json={"q": "credit checks"}).json()
    assert body["mode"] == "empty"
    assert body["results"] == []


def test_lexical_retrieval_finds_relevant_section(tmp_path):
    client = make_client(tmp_path)
    seed(client)
    body = client.post("/api/query", json={"q": "due diligence credit checks"}).json()
    assert body["mode"] == "lexical"
    assert body["results"], "expected at least one result"
    top = body["results"][0]
    assert top["heading"] == "Credit controls"
    assert top["source_title"] == "Supplier setup"


def test_hybrid_mode_with_embedder(tmp_path):
    client = make_client(tmp_path, embedder=FakeEmbedder())
    seed(client)
    body = client.post("/api/query", json={"q": "credit checks gates", "top_k": 2}).json()
    assert body["mode"] == "hybrid"
    assert any(r["heading"] == "Credit controls" for r in body["results"])
