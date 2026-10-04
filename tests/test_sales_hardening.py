"""REF S6: the workspace's browser policy and the HTTPS cookie setting."""
import os

from fastapi.testclient import TestClient
from iam_helpers import EMAIL, PASSWORD, bootstrap


def _app(tmp_path, monkeypatch, **env):
    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    os.environ.update({"SME_TIBI_VOICE_URL": "http://127.0.0.1:9", **env})
    app = create_sales_app(tmp_path / "sales")
    bootstrap(app)
    return app


def test_every_response_carries_a_policy_that_runs_only_the_panels_own_scripts(tmp_path, monkeypatch):
    with TestClient(_app(tmp_path, monkeypatch)) as client:
        response = client.get("/api/health")
        policy = response.headers["content-security-policy"]
        assert "script-src 'self'" in policy and "'unsafe-inline'" not in policy and "'unsafe-eval'" not in policy
        assert "object-src 'none'" in policy and "frame-ancestors 'none'" in policy
        assert response.headers["x-content-type-options"] == "nosniff"


def test_the_session_cookie_is_https_only_when_the_setting_says_so(tmp_path, monkeypatch):
    with TestClient(_app(tmp_path / "plain", monkeypatch)) as client:
        cookie = client.post("/api/auth/login", json={"login": EMAIL, "password": PASSWORD}).headers["set-cookie"]
        assert "secure" not in cookie.lower()  # loopback HTTP: the default
    secure = _app(tmp_path / "https", monkeypatch, OPSATLAS_SECURE_COOKIE="1", OPSATLAS_ORIGIN="https://127.0.0.1")
    with TestClient(secure, base_url="https://127.0.0.1") as client:
        cookie = client.post("/api/auth/login", json={"login": EMAIL, "password": PASSWORD}).headers["set-cookie"]
        assert "secure" in cookie.lower()
