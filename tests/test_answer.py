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

STRUCTURED_DOC = """# Supplier Setup

This raw document paragraph should not be copied into an OAG structured prompt.

## Roles and responsibilities

| Role | Responsibility |
|---|---|
| Finance approver | Approves readiness |

## Systems and data dependencies

| System | Purpose |
|---|---|
| Integration Layer | Sends approved records downstream |

## Suggested tagging structure

- domain: supplier
- capability: controlled onboarding
- control: Readiness gate
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


def seed_structured(client, *, ingest: bool = False) -> None:
    record = client.post(
        "/api/sources/upload",
        files={"file": ("supplier-structured.md", STRUCTURED_DOC.encode(), "text/markdown")},
        data={"title": "Supplier Setup"},
    ).json()
    if ingest:
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


def test_structured_ownership_question_uses_oag_without_raw_document_chunks(tmp_path):
    client, gen = make_client(
        tmp_path,
        generator=FakeGenerator(reply="Finance approver owns Supplier Setup [2]."),
    )
    seed_structured(client)

    body = client.post("/api/ask", json={"q": "Who owns Supplier Setup?"}).json()

    assert body["mode"] == "oag"
    assert body["answer_path"] == "oag"
    assert body["confidence"] == "grounded"
    assert body["citations"][0]["citation_type"] == "ontology_object"
    assert body["citations"][0]["source_title"] == "Ontology: Role/Finance approver"
    assert "Finance approver" in gen.last_prompt
    assert "This raw document paragraph should not be copied" not in gen.last_prompt
    assert "| Role | Responsibility |" not in gen.last_prompt


def test_structured_control_question_uses_rag_plus_ontology_until_roles_are_action_specific(tmp_path):
    client, gen = make_client(
        tmp_path,
        generator=FakeGenerator(reply="Finance approver controls Supplier Setup [1]."),
    )
    seed_structured(client, ingest=True)

    body = client.post("/api/ask", json={"q": "Who controls Supplier Setup?"}).json()

    assert body["mode"] == "full-context"
    assert body["answer_path"] == "rag+ontology"
    assert body["citations"][0]["citation_type"] == "ontology_object"
    assert body["citations"][0]["source_title"] == "Ontology: Process/Supplier Setup"
    assert "Finance approver" in gen.last_prompt
    assert "Process: Supplier Setup." in gen.last_prompt


def test_action_specific_owner_question_uses_rag_plus_ontology_not_direct_process_roles(tmp_path):
    client, gen = make_client(
        tmp_path,
        generator=FakeGenerator(reply="Finance approver owns readiness approvals [1]."),
    )
    seed_structured(client, ingest=True)

    body = client.post("/api/ask", json={"q": "Who owns supplier readiness approvals?"}).json()

    assert body["mode"] == "full-context"
    assert body["answer_path"] == "rag+ontology"
    assert body["citations"][0]["citation_type"] == "ontology_object"
    assert "Finance approver" in gen.last_prompt
    assert "Process: Supplier Setup." in gen.last_prompt


def test_action_specific_owner_question_includes_granular_ontology_fact(tmp_path):
    client, gen = make_client(
        tmp_path,
        generator=FakeGenerator(reply="Finance approver approves readiness [1]."),
    )
    seed_structured(client, ingest=True)

    body = client.post("/api/ask", json={"q": "Who approves readiness?"}).json()

    assert body["mode"] == "full-context"
    assert body["answer_path"] == "rag+ontology"
    assert body["citations"][0]["citation_type"] == "ontology_object"
    assert "Role responsibility: Finance approver - Approves readiness." in gen.last_prompt


def test_unsupported_lookup_refuses_before_generation(tmp_path):
    client, gen = make_client(tmp_path, generator=FakeGenerator(reply="Should not be called."))
    seed_structured(client, ingest=True)

    body = client.post(
        "/api/ask",
        json={"q": "Which named employee in Finance owns supplier payment terms?"},
    ).json()

    assert body["mode"] == "unsupported-lookup"
    assert body["refused"] is True
    assert body["answer"] == REFUSAL
    assert body["citations"] == []
    assert gen.last_prompt == ""


def test_narrative_question_uses_rag_plus_matching_ontology_evidence(tmp_path):
    client, gen = make_client(
        tmp_path,
        generator=FakeGenerator(reply="Supplier setup uses the approved source and ontology process facts [1][5]."),
    )
    seed_structured(client, ingest=True)

    body = client.post("/api/ask", json={"q": "Explain Supplier Setup"}).json()

    assert body["mode"] == "full-context"
    assert body["answer_path"] == "rag+ontology"
    assert {citation["citation_type"] for citation in body["citations"]} == {"document", "ontology_object"}
    assert "Process: Supplier Setup." in gen.last_prompt


def test_mixed_question_uses_process_ontology_evidence(tmp_path):
    client, gen = make_client(
        tmp_path,
        generator=FakeGenerator(reply="Finance approver controls Supplier Setup [6], because readiness uses process rules [5]."),
    )
    seed_structured(client, ingest=True)

    body = client.post(
        "/api/ask",
        json={"q": "Who controls Supplier Setup, and why do readiness controls matter?"},
    ).json()

    assert body["mode"] == "full-context"
    assert body["answer_path"] == "rag+ontology"
    assert {citation["citation_type"] for citation in body["citations"]} == {"ontology_object"}
    assert "Finance approver" in gen.last_prompt
    assert "Process: Supplier Setup." in gen.last_prompt


def test_routing_mode_rag_only_disables_ontology_evidence(tmp_path):
    client, gen = make_client(
        tmp_path,
        generator=FakeGenerator(reply="Supplier setup uses only document evidence [1]."),
    )
    seed_structured(client, ingest=True)
    answer = client.app.state.answer

    result = answer.answer("Explain Supplier Setup", routing_mode="rag_only")

    assert result.mode == "full-context"
    assert result.answer_path == "rag"
    assert {citation.citation_type for citation in result.citations} == {"document"}
    assert "Process: Supplier Setup." not in gen.last_prompt


def test_routing_mode_oag_only_refuses_when_question_needs_rag(tmp_path):
    client, gen = make_client(tmp_path, generator=FakeGenerator(reply="Should not be called."))
    seed_structured(client, ingest=True)
    answer = client.app.state.answer

    result = answer.answer("Explain Supplier Setup", routing_mode="oag_only")

    assert result.mode == "oag-only"
    assert result.answer_path == "oag"
    assert result.refused is True
    assert result.citations == []
    assert gen.last_prompt == ""


def test_answer_path_is_recorded_in_usage_and_audit_trace(tmp_path):
    client, _ = make_client(
        tmp_path,
        generator=FakeGenerator(reply="Finance approver owns Supplier Setup [2]."),
    )
    seed_structured(client)

    client.post("/api/ask", json={"q": "Who owns Supplier Setup?"})

    scorecard = client.get("/api/analytics/scorecard").json()
    traces = client.get("/api/observability/traces").json()
    assert scorecard["by_answer_path"] == {"oag": 1}
    assert traces[0]["answer_path"] == "oag"


def test_retrieval_mode_when_kb_exceeds_full_context_limit(tmp_path):
    client, gen = make_client(tmp_path, full_context_limit=0)  # force retrieval path
    seed(client)
    body = client.post("/api/ask", json={"q": "due diligence credit checks"}).json()
    assert body["mode"] == "retrieval"
    assert body["citations"]


def test_retrieval_mode_answer_without_markers_still_cites_retrieved_passages(tmp_path):
    # Real models often answer well in retrieval mode but omit the [n] markers; the
    # retrieved passages were selected as relevant, so the answer must still cite them.
    client, _ = make_client(
        tmp_path, generator=FakeGenerator(reply="Due diligence and credit checks are mandatory gates."), full_context_limit=0
    )
    seed(client)
    body = client.post("/api/ask", json={"q": "due diligence credit checks"}).json()
    assert body["mode"] == "retrieval"
    assert body["refused"] is False
    assert body["citations"], "retrieval-mode answer must cite its source even without [n] markers"


def test_full_context_answer_without_markers_does_not_over_cite(tmp_path):
    # In full-context mode the evidence is the whole KB, not question-specific, so a
    # marker-less answer must NOT attach every section as a citation.
    client, _ = make_client(tmp_path, generator=FakeGenerator(reply="Credit checks are mandatory gates."))
    seed(client)
    body = client.post("/api/ask", json={"q": "what checks are needed?"}).json()
    assert body["mode"] == "full-context"
    assert body["citations"] == []


def test_citation_markers_are_normalized(tmp_path):
    # Model emits a record-id ("[2, n7]") and a numeric list ("[1, 2]"); markers are
    # tidied to canonical form and the answer text no longer shows the stray tokens.
    client, _ = make_client(tmp_path, generator=FakeGenerator(reply="Checks are gates [2, n7]; both apply [1, 2]."))
    seed(client)
    body = client.post("/api/ask", json={"q": "what are the gates?"}).json()
    assert body["answer"] == "Checks are gates [2]; both apply [1][2]."
    assert "n7" not in body["answer"]
    assert {c["heading"] for c in body["citations"]} == {"Supplier setup", "Credit controls"}


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


def test_output_guardrail_blocks_harmful_answer(tmp_path):
    client, _ = make_client(tmp_path, generator=FakeGenerator(reply="Here is how to build a bomb [1]."))
    seed(client)
    body = client.post("/api/ask", json={"q": "tell me about the controls"}).json()
    assert body["refused"] is True
    assert body["mode"] == "guardrail"
    assert body["category"] == "violence"
    assert body["citations"] == []
