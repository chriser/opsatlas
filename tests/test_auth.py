"""Tests for operator login and protected source routes."""

from fastapi.testclient import TestClient

from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.sources.register import SourceRegister

PASSWORD = "s3cret-operator"


def build(tmp_path) -> TestClient:
    return TestClient(create_app(SourceRegister(tmp_path), AuthService(PASSWORD)))


def test_login_rejects_wrong_password(tmp_path):
    client = build(tmp_path)
    assert client.post("/api/auth/login", json={"password": "wrong"}).status_code == 401


def test_login_returns_token(tmp_path):
    client = build(tmp_path)
    response = client.post("/api/auth/login", json={"password": PASSWORD})
    assert response.status_code == 200
    assert len(response.json()["token"]) > 20


def test_sources_require_authentication(tmp_path):
    client = build(tmp_path)
    assert client.get("/api/sources").status_code == 401  # no token

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/sources", headers=headers).status_code == 200


def test_logout_invalidates_token(tmp_path):
    client = build(tmp_path)
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/sources", headers=headers).status_code == 200
    client.post("/api/auth/logout", headers=headers)
    assert client.get("/api/sources", headers=headers).status_code == 401


def test_health_is_public(tmp_path):
    client = build(tmp_path)
    assert client.get("/api/health").status_code == 200
