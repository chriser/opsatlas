"""Governance tests — knowledge intelligence + the approval gate (hermetic)."""

from fastapi.testclient import TestClient

from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.governance.intelligence import KnowledgeIntelligence
from assistant.ingestion.sections import build_sections
from assistant.ingestion.store import SectionStore
from assistant.retrieval.service import RetrievalService
from assistant.sources.register import SourceRegister
from assistant.sources.service import register_upload

PASSWORD = "test-pass"


class IdenticalEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]  # all identical -> cosine 1.0


def test_intelligence_flags_not_ingested(tmp_path):
    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    register_upload(reg, "a.txt", b"some content")  # registered, 0 sections
    report = KnowledgeIntelligence(reg, store).run()
    assert report["total_issues"] >= 1
    assert report["categories"]["compliance"] >= 1
    assert any(i["check"] == "not_ingested" for i in report["issues"]["compliance"])


def test_duplicate_detection(tmp_path):
    from assistant.retrieval.embedder import EmbeddingCache

    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    for name in ("a.md", "b.md"):
        rec = register_upload(reg, name, b"# H\n\nDue diligence and credit checks are mandatory gates.")
        store.replace_for_source(rec.id, build_sections(rec.id, "# H\n\nDue diligence and credit checks are mandatory gates."))
    report = KnowledgeIntelligence(reg, store, IdenticalEmbedder(), EmbeddingCache(reg.base_dir)).run()
    assert report["categories"]["consistency"] >= 1


def make_client(tmp_path):
    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    retrieval = RetrievalService(reg, store)  # lexical only
    client = TestClient(create_app(reg, AuthService(PASSWORD), retrieval=retrieval))
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def test_approval_gate_controls_queryability(tmp_path):
    client = make_client(tmp_path)
    rec = client.post(
        "/api/sources/upload",
        files={"file": ("s.md", b"# Controls\n\nDue diligence and credit checks are mandatory gates.", "text/markdown")},
        data={"title": "Controls"},
    ).json()
    client.post(f"/api/sources/{rec['id']}/ingest")

    # Not approved yet -> not queryable.
    assert client.post("/api/query", json={"q": "credit checks"}).json()["mode"] == "empty"

    # Approve -> queryable.
    approved = client.post(f"/api/governance/sources/{rec['id']}/approve").json()
    assert approved["approval_status"] == "approved"
    assert client.post("/api/query", json={"q": "credit checks"}).json()["results"]


def test_reject_missing_source_404(tmp_path):
    client = make_client(tmp_path)
    assert client.post("/api/governance/sources/nope/reject").status_code == 404
