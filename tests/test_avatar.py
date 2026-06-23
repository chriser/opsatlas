"""Avatar integration tests."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from assistant.answer.prompt import REFUSAL
from assistant.answer.service import AnswerResult, AnswerService, Citation
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.api.routes_avatar import AnamSettings, create_anam_session_token
from assistant.avatar.style import render_avatar_answer
from assistant.ingestion.store import SectionStore
from assistant.retrieval.service import RetrievalService
from assistant.sources.register import SourceRegister

PASSWORD = "avatar-test-pass"
DOC = """# Supplier setup

Supplier setup requires due diligence checks before onboarding.
"""


class FakeGenerator:
    def __init__(
        self,
        *,
        reply: str = "Due diligence checks must be completed before onboarding [1].",
        natural_reply: str = (
            "Yes — due diligence checks are the gate here. Before onboarding can continue, those checks need to be "
            "completed [1]."
        ),
    ) -> None:
        self.reply = reply
        self.natural_reply = natural_reply
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if "NATURAL SPOKEN ANSWER:" in prompt:
            return self.natural_reply
        return self.reply


def _client(tmp_path) -> TestClient:
    return TestClient(create_app(SourceRegister(tmp_path), AuthService(PASSWORD)))


def _headers(client: TestClient) -> dict[str, str]:
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _client_with_answer(tmp_path) -> TestClient:
    register = SourceRegister(tmp_path)
    store = SectionStore(register.base_dir)
    retrieval = RetrievalService(register, store)
    answer = AnswerService(retrieval, FakeGenerator())
    client = TestClient(create_app(register, AuthService(PASSWORD), retrieval=retrieval, answer=answer))
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    record = client.post(
        "/api/sources/upload",
        files={"file": ("supplier.md", DOC.encode(), "text/markdown")},
        data={"title": "Supplier setup"},
    ).json()
    client.post(f"/api/sources/{record['id']}/ingest")
    client.post(f"/api/governance/sources/{record['id']}/approve")
    return client


def _answer_result(*, refused: bool = False) -> AnswerResult:
    return AnswerResult(
        answer=REFUSAL if refused else "Due diligence checks must be completed before onboarding [1].",
        citations=[] if refused else [
            Citation(source_id="src-1", source_title="Supplier setup", heading="Supplier setup", ordinal=1)
        ],
        mode="guardrail" if refused else "retrieval",
        refused=refused,
        confidence="none" if refused else "grounded",
    )


def _process_answer_result() -> AnswerResult:
    return AnswerResult(
        answer=(
            "The process for setting up a new supplier involves several steps and gating controls as outlined in "
            "the evidence [1] and [3]:\n\n"
            "1. Trigger Supplier Setup: A business team identifies the need for a new supplier or a change to existing "
            "supplier details, and this triggers the formal request.\n"
            "2. Prepare Supplier Request Form: The requester completes the form with available supplier details and sends "
            "it to the support team.\n"
            "3. Review Request for Completeness: The support team checks the form for missing information and returns "
            "queries if necessary.\n"
            "4. Prepare Due Diligence Pack: A due diligence pack is prepared, including relevant supporting information; "
            "this step requires validation of some fields.\n"
            "5. Initiate Due Diligence and Credit Checks: These are mandatory gating controls that must be completed "
            "before setup can proceed further.\n"
            "6. Create Supplier in Target Master Data Tool: If checks pass, a supplier record is created using the "
            "required mandatory fields.\n"
            "7. Create Supplier in Finance Master Environment: The supplier is also created in the finance master data "
            "environment through the finance-side process.\n"
            "8. Map Supplier Identifiers: The supplier identifier from the operational tool is mapped to the finance-side "
            "identifier for payment and reconciliation processes.\n"
            "9. Complete Contract Links and Readiness Controls: The supplier is linked to mandatory operational contracts, "
            "and any remaining setup controls are completed before activation.\n"
            "10. Activate Supplier for Use: Once all mandatory steps are complete, the supplier status can be set to active "
            "or otherwise released for use.\n"
            "11. Confirm Completion to Requester: The requester is informed that the supplier has been created and is "
            "available for use.\n"
            "It's important to note that a supplier record may exist but still be incomplete until these steps are fully "
            "completed [3][4]."
        ),
        citations=[
            Citation(source_id="src-1", source_title="Supplier setup", heading="Supplier setup", ordinal=1),
            Citation(source_id="src-2", source_title="Supplier controls", heading="Controls", ordinal=3),
            Citation(source_id="src-3", source_title="Supplier readiness", heading="Readiness", ordinal=4),
        ],
        mode="retrieval",
        refused=False,
        confidence="grounded",
    )


def test_avatar_config_requires_authentication(tmp_path):
    client = _client(tmp_path)

    assert client.get("/api/avatar/anam/config").status_code == 401


def test_avatar_config_reports_missing_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANAM_API_KEY", raising=False)
    monkeypatch.delenv("ANAM_PERSONA_ID", raising=False)
    client = _client(tmp_path)

    response = client.get("/api/avatar/anam/config", headers=_headers(client))

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    assert body["missing"] == ["ANAM_API_KEY", "ANAM_PERSONA_ID"]


def test_avatar_session_token_missing_env_is_service_unavailable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANAM_API_KEY", raising=False)
    monkeypatch.delenv("ANAM_PERSONA_ID", raising=False)
    client = _client(tmp_path)

    response = client.post("/api/avatar/anam/session-token", headers=_headers(client))

    assert response.status_code == 503
    assert "ANAM_API_KEY" in response.json()["detail"]


def test_create_anam_session_token_uses_persona_without_exposing_api_key():
    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps({"sessionToken": "session-123"}).encode()

    def fake_opener(req, timeout):
        calls.append((req, timeout))
        return FakeResponse()

    token = create_anam_session_token(
        AnamSettings(api_key="secret-key", persona_id="persona-abc"),
        opener=fake_opener,
    )

    req, timeout = calls[0]
    assert token == "session-123"
    assert timeout == 30
    assert req.get_header("Authorization") == "Bearer secret-key"
    assert json.loads(req.data.decode()) == {"personaConfig": {"personaId": "persona-abc"}}


def test_avatar_formal_style_uses_canonical_answer_exactly():
    result = _answer_result()

    rendered = render_avatar_answer(result, "formal")

    assert rendered.rendered_text == result.answer
    assert rendered.render_notes == ["Canonical assistant answer used without style changes."]


def test_avatar_natural_style_keeps_refusal_exact():
    result = _answer_result(refused=True)

    rendered = render_avatar_answer(result, "natural")

    assert rendered.rendered_text == REFUSAL
    assert rendered.render_notes == ["Refusal or compliance-boundary answer preserved exactly."]


def test_avatar_natural_style_turns_process_steps_into_spoken_overview():
    result = _process_answer_result()
    natural = (
        "Yes — setting up a supplier is a bit like getting someone officially added to the company's approved address "
        "book, but with more checks before anyone starts buying from them [1].\n\n"
        "From there, the request is checked, the due diligence gates are completed, the supplier is created in the "
        "operational and finance environments, and the records are mapped together [3].\n\n"
        "So the short version is: request it, check it, approve it, create it in the right systems, link it, then activate it [4]."
    )
    generator = FakeGenerator(natural_reply=natural)

    rendered = render_avatar_answer(result, "natural", "Can you tell me how to setup supplier?", generator=generator)

    assert rendered.rendered_text == natural
    assert "CANONICAL GROUNDED ANSWER:" in generator.prompts[0]
    assert "Valid markers for this answer: [1] [3] [4]." in generator.prompts[0]
    assert "1. Trigger Supplier Setup" not in rendered.rendered_text
    assert "I found 3 supporting citations." not in rendered.rendered_text
    assert any("Used constrained LLM natural-spoken renderer" in note for note in rendered.render_notes)
    assert "[1]" in rendered.rendered_text
    assert "[3]" in rendered.rendered_text
    assert "[4]" in rendered.rendered_text


def test_avatar_natural_style_uses_general_renderer_for_non_supplier_answers():
    result = AnswerResult(
        answer=(
            "Article activation waits until product structure, pricing dependencies and tax handling have passed "
            "validation [1]. Exceptions must be reviewed before activation [2]."
        ),
        citations=[
            Citation(source_id="src-1", source_title="Article setup", heading="Activation", ordinal=1),
            Citation(source_id="src-2", source_title="Article setup", heading="Exceptions", ordinal=2),
        ],
        mode="retrieval",
        refused=False,
        confidence="grounded",
    )
    generator = FakeGenerator(
        natural_reply=(
            "Yes — for article activation, think of validation as the final set of traffic lights. The article should "
            "not go live until product structure, pricing and tax handling have all cleared their checks [1]. If there "
            "is an exception, it needs review before activation [2]."
        )
    )

    rendered = render_avatar_answer(result, "natural", "What stops an article being activated?", generator=generator)

    assert rendered.rendered_text.startswith("Yes — for article activation")
    assert "traffic lights" in rendered.rendered_text
    assert "[1]" in rendered.rendered_text
    assert "[2]" in rendered.rendered_text
    assert "supplier" not in rendered.rendered_text.lower()


def test_avatar_natural_style_falls_back_when_renderer_invents_citation_marker():
    result = _answer_result()
    generator = FakeGenerator(natural_reply="Yes — this sounds friendlier, but it invents a citation [9].")

    rendered = render_avatar_answer(result, "natural", "What checks are needed?", generator=generator)

    assert "[9]" not in rendered.rendered_text
    assert "[1]" in rendered.rendered_text
    assert any("fallback" in note for note in rendered.render_notes)


def test_avatar_natural_style_rejects_numbered_list_renderer_output():
    result = _process_answer_result()
    generator = FakeGenerator(
        natural_reply=(
            "Sure! Here's how you can set up a supplier:\n\n"
            "1. Identify the Need: First, your business team spots the need for a new supplier.\n"
            "2. Fill Out the Form: The requester fills out the supplier setup form.\n"
            "3. Run Checks: The support team starts due diligence and credit checks [3]."
        )
    )

    rendered = render_avatar_answer(result, "natural", "Can you tell me how to setup supplier?", generator=generator)

    assert "1. Identify the Need" not in rendered.rendered_text
    assert "2. Fill Out the Form" not in rendered.rendered_text
    assert "The process starts when" in rendered.rendered_text
    assert "So the short version is:" in rendered.rendered_text
    assert "[3]" in rendered.rendered_text
    assert any("fallback" in note for note in rendered.render_notes)


def test_avatar_answer_endpoint_returns_rendered_text_and_canonical_metadata(tmp_path):
    client = _client_with_answer(tmp_path)

    response = client.post("/api/avatar/answer", json={"q": "What checks are needed?", "style": "natural"})

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "anam"
    assert body["style"] == "natural"
    assert body["rendered_text"].startswith("Yes — due diligence checks are the gate here.")
    assert "Before onboarding can continue" in body["rendered_text"]
    assert body["answer"]["answer"] == "Due diligence checks must be completed before onboarding [1]."
    assert body["answer"]["citations"][0]["heading"] == "Supplier setup"


def test_avatar_answer_endpoint_defaults_to_natural_style(tmp_path):
    client = _client_with_answer(tmp_path)

    response = client.post("/api/avatar/answer", json={"q": "What checks are needed?"})

    assert response.status_code == 200
    body = response.json()
    assert body["style"] == "natural"
    assert body["rendered_text"].startswith("Yes — due diligence checks are the gate here.")
