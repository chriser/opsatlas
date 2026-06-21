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


class RelatedEmbedder:
    """Related but not duplicate: 'mandatory' vs 'optional' ~0.7 cosine."""

    def embed(self, texts):
        out = []
        for t in texts:
            tl = t.lower()
            out.append([1.0, 0.0, 0.0] if "mandatory" in tl else [0.7, 0.7, 0.0] if "optional" in tl else [0.0, 0.0, 1.0])
        return out


class ConflictGenerator:
    def generate(self, prompt):
        return "CONFLICT: one says mandatory, the other says optional."


def test_intelligence_flags_not_ingested(tmp_path):
    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    register_upload(reg, "a.txt", b"some content")  # registered, 0 sections
    report = KnowledgeIntelligence(reg, store).run()
    assert report["total_issues"] >= 1
    assert report["categories"]["compliance"] >= 1
    assert any(i["check"] == "not_ingested" for i in report["issues"]["compliance"])


def test_severity_and_health(tmp_path):
    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    register_upload(reg, "a.txt", b"some content")  # not_ingested -> high severity
    report = KnowledgeIntelligence(reg, store).run()
    issue = report["issues"]["compliance"][0]
    assert issue["severity"] == "high" and issue["score"] == 3
    assert report["health"] == "red"  # a high-severity issue is present


def test_health_green_when_clean(tmp_path):
    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    assert KnowledgeIntelligence(reg, store).run()["health"] == "green"


def test_duplicate_detection(tmp_path):
    from assistant.retrieval.embedder import EmbeddingCache

    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    for name in ("a.md", "b.md"):
        rec = register_upload(reg, name, b"# H\n\nDue diligence and credit checks are mandatory gates.")
        store.replace_for_source(rec.id, build_sections(rec.id, "# H\n\nDue diligence and credit checks are mandatory gates."))
    report = KnowledgeIntelligence(reg, store, IdenticalEmbedder(), EmbeddingCache(reg.base_dir)).run()
    assert report["categories"]["consistency"] >= 1


def test_conflict_detection(tmp_path):
    from assistant.retrieval.embedder import EmbeddingCache

    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    for name, body in (("a.md", "# Checks\n\nCredit checks are mandatory before onboarding."),
                       ("b.md", "# Checks\n\nCredit checks are optional before onboarding.")):
        rec = register_upload(reg, name, body.encode())
        store.replace_for_source(rec.id, build_sections(rec.id, body))
    report = KnowledgeIntelligence(
        reg, store, RelatedEmbedder(), EmbeddingCache(reg.base_dir), generator=ConflictGenerator()
    ).run()
    assert report["categories"]["correctness"] >= 1
    assert any(i["check"] == "conflict" for i in report["issues"]["correctness"])


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
