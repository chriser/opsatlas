"""Offline benchmark tests for the local avatar render service."""

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.avatar_render.app import app
from services.avatar_render.benchmark import run_offline_benchmark
from services.avatar_render.models import OfflineBenchmarkRequest


def _benchmark_payload() -> dict[str, object]:
    return {
        "speech_id": "avatar-benchmark-test",
        "text": "Supplier setup requires due diligence checks before onboarding [1].",
        "style": "natural",
        "voice_profile_id": "local-voice",
        "avatar_profile_id": "local-avatar",
        "render_mode": "offline",
        "run_commands": False,
        "metadata": {
            "source": "knowledge-assistant",
            "answer_id": "answer-001",
        },
    }


def test_offline_benchmark_endpoint_writes_readiness_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("AVATAR_RENDER_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("AVATAR_TTS_COMMAND", raising=False)
    monkeypatch.delenv("AVATAR_RENDER_COMMAND", raising=False)
    monkeypatch.delenv("AVATAR_BENCHMARK_ALLOW_EXECUTE", raising=False)
    client = TestClient(app)

    response = client.post("/benchmarks/offline", json=_benchmark_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert body["speech_id"] == "avatar-benchmark-test"
    assert body["data_root"] == str(tmp_path.resolve())
    dependencies = {item["name"]: item for item in body["dependencies"]}
    assert dependencies["openvoice_command"]["status"] == "missing"
    assert dependencies["musetalk_command"]["status"] == "missing"
    artifacts = {item["kind"]: item for item in body["artifacts"]}
    assert artifacts["manifest"]["exists"] is True
    assert artifacts["approved_text"]["exists"] is True
    assert Path(artifacts["manifest"]["path"]).read_text(encoding="utf-8").startswith("{")


def test_offline_benchmark_rejects_question_shaped_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("AVATAR_RENDER_DATA_DIR", str(tmp_path))
    client = TestClient(app)
    payload = {
        **_benchmark_payload(),
        "question": "Can you answer this directly?",
        "documents": ["source material must stay out of render service"],
    }

    response = client.post("/benchmarks/offline", json=payload)

    assert response.status_code == 422
    assert "approved speech text only" in response.text
    assert "documents" in response.text
    assert "question" in response.text


def test_offline_benchmark_function_records_text_metric_and_ignored_artifact_paths(tmp_path, monkeypatch):
    monkeypatch.delenv("AVATAR_TTS_COMMAND", raising=False)
    monkeypatch.delenv("AVATAR_RENDER_COMMAND", raising=False)
    request = OfflineBenchmarkRequest.model_validate(_benchmark_payload())

    report = run_offline_benchmark(request, tmp_path)

    assert report.status == "blocked"
    assert report.run_dir.startswith(str(tmp_path))
    assert any(metric.name == "text_characters" and metric.value == len(request.text) for metric in report.metrics)
    assert any(artifact.kind == "approved_text" and artifact.exists for artifact in report.artifacts)


def test_offline_benchmark_reports_unwritable_data_root(tmp_path, monkeypatch):
    monkeypatch.delenv("AVATAR_TTS_COMMAND", raising=False)
    monkeypatch.delenv("AVATAR_RENDER_COMMAND", raising=False)
    request = OfflineBenchmarkRequest.model_validate(_benchmark_payload())

    with patch("pathlib.Path.mkdir", side_effect=OSError("blocked")):
        report = run_offline_benchmark(request, tmp_path)

    assert report.status == "failed"
    assert report.artifacts == []
    assert "writable local path" in report.warnings[0]
    assert "Could not create benchmark run directory" in report.errors[0]
