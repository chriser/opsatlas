"""Process diagram service status and start-control tests."""

from urllib.error import URLError

from fastapi.testclient import TestClient

from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.process.diagram import ProcessDiagramClient, ProcessDiagramServiceManager
from assistant.sources.register import SourceRegister

PASSWORD = "diagram-control-pass"


class _Response:
    def __init__(self, body: str) -> None:
        self.body = body.encode()

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class _FakeProcess:
    pid = 4321


def test_process_diagram_client_health_reads_service_status():
    def opener(req, timeout):
        assert req.full_url == "http://127.0.0.1:5300/health"
        assert timeout == 2
        return _Response('{"status":"ok","service":"process-diagram"}')

    client = ProcessDiagramClient(timeout=2, opener=opener)

    assert client.health()["service"] == "process-diagram"


def test_process_diagram_service_manager_starts_local_uvicorn(tmp_path, monkeypatch):
    calls = {"health": 0, "command": []}

    def opener(req, timeout):
        calls["health"] += 1
        if calls["health"] == 1:
            raise URLError("connection refused")
        return _Response('{"status":"ok"}')

    def fake_popen(command, **kwargs):
        calls["command"] = command
        assert kwargs["cwd"] == tmp_path
        assert kwargs["start_new_session"] is True
        return _FakeProcess()

    monkeypatch.setenv("PROCESS_DIAGRAM_LOG_PATH", str(tmp_path / "diagram.log"))
    manager = ProcessDiagramServiceManager(
        client=ProcessDiagramClient(base_url="http://127.0.0.1:5300", opener=opener),
        repo_root=tmp_path,
        popen=fake_popen,
        sleeper=lambda seconds: None,
    )

    status = manager.start()

    assert status.running is True
    assert status.started is True
    assert status.pid == 4321
    assert "services.process_diagram.app:app" in calls["command"]
    assert "5300" in calls["command"]


def test_process_diagram_service_status_endpoint_is_protected(tmp_path):
    register = SourceRegister(tmp_path)
    client = TestClient(create_app(register, AuthService(PASSWORD)))

    assert client.get("/api/process/diagrams/service/status").status_code == 401

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    response = client.get("/api/process/diagrams/service/status", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["service_url"].startswith("http")
    assert isinstance(body["running"], bool)
