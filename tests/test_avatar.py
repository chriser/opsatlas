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
    def generate(self, _prompt: str) -> str:
        return "Due diligence checks must be completed before onboarding [1]."


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


def test_avatar_answer_endpoint_returns_rendered_text_and_canonical_metadata(tmp_path):
    client = _client_with_answer(tmp_path)

    response = client.post("/api/avatar/answer", json={"q": "What checks are needed?", "style": "natural"})

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "anam"
    assert body["style"] == "natural"
    assert body["rendered_text"].startswith("Here is the approved answer in plain terms.")
    assert "Due diligence checks must be completed before onboarding [1]." in body["rendered_text"]
    assert body["answer"]["answer"] == "Due diligence checks must be completed before onboarding [1]."
    assert body["answer"]["citations"][0]["heading"] == "Supplier setup"
