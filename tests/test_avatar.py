"""Avatar integration tests."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.api.routes_avatar import AnamSettings, create_anam_session_token
from assistant.sources.register import SourceRegister

PASSWORD = "avatar-test-pass"


def _client(tmp_path) -> TestClient:
    return TestClient(create_app(SourceRegister(tmp_path), AuthService(PASSWORD)))


def _headers(client: TestClient) -> dict[str, str]:
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


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
