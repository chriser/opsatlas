"""Grounded-answer tests — hermetic (fake generator, no Ollama)."""

from fastapi.testclient import TestClient

from assistant.answer.prompt import REFUSAL
from assistant.answer.service import AnswerService
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.ingestion.store import SectionStore
from assistant.retrieval.service import RetrievalService
from assistant.sources.register import SourceRegister

PASSWORD = "test-pass"

DOC = """# Supplier setup

Supplier setup begins with a business request and a completed form.

# Credit controls

Due diligence and credit checks are mandatory gates before onboarding.
"""


class FakeGenerator:
    """Echoes the evidence headings so tests can assert grounding without Ollama."""

    def __init__(self, reply: str | None = None) -> None:
        self.reply = reply
        self.last_prompt = ""

    def generate(self, prompt: str) -> str:
        self.last_prompt = prompt
        if self.reply is not None:
            return self.reply
        return "Based on the evidence [1], due diligence and credit checks are mandatory gates."


def make_client(tmp_path, generator=None, full_context_limit=24000) -> tuple[TestClient, FakeGenerator]:
    register = SourceRegister(tmp_path)
    store = SectionStore(register.base_dir)
    retrieval = RetrievalService(register, store)  # lexical-only (no embedder)
    gen = generator or FakeGenerator()
    answer = AnswerService(retrieval, gen, full_context_char_limit=full_context_limit)
    client = TestClient(create_app(register, AuthService(PASSWORD), retrieval=retrieval, answer=answer))
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client, gen


def seed(client) -> None:
    record = client.post(
        "/api/sources/upload",
        files={"file": ("supplier.md", DOC.encode(), "text/markdown")},
        data={"title": "Supplier setup"},
    ).json()
    client.post(f"/api/sources/{record['id']}/ingest")
    client.post(f"/api/governance/sources/{record['id']}/approve")


def test_ask_requires_auth(tmp_path):
    client, _ = make_client(tmp_path)
    client.headers.pop("Authorization")
    assert client.post("/api/ask", json={"q": "x"}).status_code == 401


def test_empty_knowledge_base_refuses_without_calling_model(tmp_path):
    client, gen = make_client(tmp_path)
    body = client.post("/api/ask", json={"q": "what checks are needed?"}).json()
    assert body["mode"] == "empty"
    assert body["refused"] is True
    assert body["answer"] == REFUSAL
    assert body["citations"] == []
    assert gen.last_prompt == ""  # generator must not be called when there is no evidence


def test_full_context_answer_has_citations(tmp_path):
    client, gen = make_client(tmp_path)
    seed(client)
    body = client.post("/api/ask", json={"q": "what checks are needed before onboarding?"}).json()
    assert body["mode"] == "full-context"
    assert body["refused"] is False
    assert body["confidence"] == "grounded"
    assert body["citations"], "grounded answer should carry citations"
    assert "EVIDENCE:" in gen.last_prompt  # evidence was passed to the model


def test_retrieval_mode_when_kb_exceeds_full_context_limit(tmp_path):
    client, gen = make_client(tmp_path, full_context_limit=0)  # force retrieval path
    seed(client)
    body = client.post("/api/ask", json={"q": "due diligence credit checks"}).json()
    assert body["mode"] == "retrieval"
    assert body["citations"]


def test_model_refusal_drops_citations(tmp_path):
    client, _ = make_client(tmp_path, generator=FakeGenerator(reply=REFUSAL))
    seed(client)
    body = client.post("/api/ask", json={"q": "what is the capital of France?"}).json()
    assert body["refused"] is True
    assert body["citations"] == []


def test_citations_track_the_markers_the_model_used(tmp_path):
    # Evidence order is [1] Supplier setup, [2] Credit controls; model cites only [2].
    client, _ = make_client(tmp_path, generator=FakeGenerator(reply="The gates are checks [2]."))
    seed(client)
    body = client.post("/api/ask", json={"q": "what are the gates?"}).json()
    assert [c["heading"] for c in body["citations"]] == ["Credit controls"]


def test_spurious_appended_refusal_is_stripped(tmp_path):
    reply = f"Due diligence and credit checks must pass [2].\n\n{REFUSAL}"
    client, _ = make_client(tmp_path, generator=FakeGenerator(reply=reply))
    seed(client)
    body = client.post("/api/ask", json={"q": "what checks are needed?"}).json()
    assert body["refused"] is False
    assert body["answer"] == "Due diligence and credit checks must pass [2]."
    assert body["citations"], "a real answer keeps its cited evidence even if a refusal was appended"
