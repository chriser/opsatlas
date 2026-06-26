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


def _age_restriction_answer_result() -> AnswerResult:
    return AnswerResult(
        answer=(
            "1. Identify Item Families: The business owner or compliance owner identifies which item families require "
            "age restrictions and the current legal thresholds.\n"
            "2. Configure Grouped Restriction: The master data owner or system owner sets up the age restriction in a "
            "way that supports grouped outputs, compatible with downstream platforms.\n"
            "3. Assign Item Attributes: The master data operator or support team assigns the correct restriction "
            "grouping or attribute to affected items.\n"
            "4. Protect Integrated Groupings: The integration owner or system owner ensures tax-related groupings are "
            "correctly sent alongside age restrictions to avoid overwriting.\n"
            "5. Maintain Annual Categories: The support team or master data owner uses mass maintenance for categories "
            "that change annually, while keeping stable categories unchanged.\n"
            "6. Test Downstream Logic: Testing is conducted to ensure grouped logic behaves as expected in the downstream "
            "retail system.\n"
            "7. Prepare Legal Updates: Compliance and system owners review future legal changes and update grouping "
            "models accordingly."
        ),
        citations=[
            Citation(source_id="src-1", source_title="Age restrictions", heading="Grouping", ordinal=1),
            Citation(source_id="src-2", source_title="Age restrictions", heading="Integration", ordinal=2),
            Citation(source_id="src-3", source_title="Age restrictions", heading="Updates", ordinal=4),
        ],
        mode="retrieval",
        refused=False,
        confidence="grounded",
    )


def _tax_handling_answer_result() -> AnswerResult:
    return AnswerResult(
        answer=(
            "1. Close Old Tax Definition: Where a tax rate changes generally, the preferred approach is to close the "
            "old tax definition and open a new one with the updated validity period.\n"
            "2. Apply Selective Updates: For cases where only a subset of items changes tax treatment, mass maintenance "
            "or selective pricing-related updates are required.\n"
            "3. Structure Tax Codes: Tax codes should be sufficiently structured for downstream interpretation; "
            "descriptive text alone may be insufficient.\n"
            "4. Define Tax Parameters: The process involves defining tax-rate parameter definitions, which can then be "
            "applied broadly or selectively based on the nature of the change.\n"
            "5. Validate Downstream Interpretation: Validation steps are necessary to ensure that changes in tax-related "
            "data do not disrupt downstream interpretations and operations.\n"
            "6. Test Related Groupings: Testing should include how grouped age restriction and tax information behave "
            "together in downstream retail systems."
        ),
        citations=[
            Citation(source_id="src-1", source_title="Tax handling", heading="Definitions", ordinal=3),
            Citation(source_id="src-2", source_title="Tax handling", heading="Codes", ordinal=1),
            Citation(source_id="src-3", source_title="Tax handling", heading="Validation", ordinal=6),
            Citation(source_id="src-4", source_title="Tax handling", heading="Testing", ordinal=4),
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


def test_numbered_steps_keep_hyphen_and_asterisk_labels():
    from assistant.avatar.style import _numbered_steps

    steps = _numbered_steps(
        "1. Trading Support - data check: verify the fields\n"
        "2. **Enter pre-form**: start the supplier creation\n"
        "3. Review overlapping data: decide ownership"
    )
    assert len(steps) == 3  # none dropped
    assert steps[0] == ("Trading Support - data check", "verify the fields")  # hyphen label not truncated


def test_avatar_natural_fallback_does_not_open_with_yes_for_negative_answer():
    result = AnswerResult(
        answer="No, a supplier cannot be activated until credit checks have passed [1].",
        citations=[Citation(source_id="s1", source_title="Supplier", heading="Controls", ordinal=1)],
        mode="retrieval",
        refused=False,
        confidence="grounded",
    )
    # No generator -> deterministic fallback path (where the opener was hard-coded "Yes —").
    rendered = render_avatar_answer(result, "natural", "Can a supplier be activated without credit checks?")
    assert not rendered.rendered_text.lower().startswith("yes")
    assert rendered.rendered_text.startswith("In plain terms")


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
    assert "approved address book" in rendered.rendered_text
    assert "business equivalent of two people talking about the same supplier" in rendered.rendered_text
    assert "So the short version is:" in rendered.rendered_text
    assert "[3]" in rendered.rendered_text
    assert any("fallback" in note for note in rendered.render_notes)


def test_avatar_natural_style_rejects_bland_process_paraphrase_without_short_close():
    result = _process_answer_result()
    generator = FakeGenerator(
        natural_reply=(
            "To set up a new supplier, start by identifying the need within your business team. Next, fill out the "
            "supplier request form with all necessary details and send it to the support team. They will review the "
            "form for completeness and ask for any missing information if needed.\n\n"
            "Once everything is in order, they'll prepare a due diligence pack, which includes important supporting "
            "documents. The support team will then run necessary checks like due diligence and credit assessments."
        )
    )

    rendered = render_avatar_answer(result, "natural", "Can you tell me how to setup supplier?", generator=generator)

    assert not rendered.rendered_text.startswith("To set up a new supplier")
    assert "approved address book" in rendered.rendered_text
    assert "The two records then need to be mapped together" in rendered.rendered_text
    assert "So the short version is:" in rendered.rendered_text
    assert any("fallback" in note for note in rendered.render_notes)


def test_avatar_natural_style_process_title_does_not_start_with_yes_template():
    result = _age_restriction_answer_result()
    generator = FakeGenerator(
        natural_reply=(
            "Yes — in plain terms, this process is about getting the request captured, checked, created in the right "
            "places, and only released once the required controls are complete. [1]\n\n"
            "So the short version is: capture it, check it, complete the controls, then release it."
        )
    )

    rendered = render_avatar_answer(result, "natural", "Age Restriction Grouping Process", generator=generator)

    assert not rendered.rendered_text.startswith("Yes")
    assert rendered.rendered_text.startswith("The age restriction grouping process")
    assert "age-restriction groupings" in rendered.rendered_text
    assert "have we got everything" not in rendered.rendered_text
    assert "identify the restricted item families" in rendered.rendered_text
    assert any("fallback" in note for note in rendered.render_notes)


def test_avatar_natural_style_tax_question_uses_tax_specific_intro():
    result = _tax_handling_answer_result()

    rendered = render_avatar_answer(result, "natural", "what is the tax handling process?")

    assert not rendered.rendered_text.startswith("Yes")
    assert rendered.rendered_text.startswith("The tax handling process")
    assert "managing tax-rate changes" in rendered.rendered_text
    assert "getting the request captured" not in rendered.rendered_text
    assert "identify the tax change" in rendered.rendered_text


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
