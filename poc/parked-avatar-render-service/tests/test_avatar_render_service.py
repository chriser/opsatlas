"""Local avatar render microservice contract tests."""

from fastapi.testclient import TestClient
from services.avatar_render.app import app
from services.avatar_render.models import AvatarRenderRequest


def _speech_payload() -> dict[str, object]:
    return {
        "speech_id": "avatar-test-001",
        "text": "Supplier setup requires due diligence checks before onboarding [1].",
        "style": "natural",
        "voice_profile_id": "local-voice",
        "avatar_profile_id": "local-avatar",
        "render_mode": "offline",
        "metadata": {
            "source": "knowledge-assistant",
            "answer_id": "answer-001",
        },
    }


def test_health_reports_local_contract_and_missing_models():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "avatar-render-service.v1"
    assert body["service"] == "avatar-render"
    assert body["status"] == "degraded"
    assert body["local_only"] is True
    assert body["data_root"].endswith("/data/avatar")
    dependencies = {item["name"]: item for item in body["dependencies"]}
    assert dependencies["openvoice"]["status"] == "missing"
    assert dependencies["musetalk"]["status"] == "missing"
    assert "approved speech text only" in body["warnings"][1]


def test_health_reports_configured_smoke_renderer_without_claiming_musetalk(tmp_path, monkeypatch):
    monkeypatch.setenv("AVATAR_RENDER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AVATAR_TTS_COMMAND", "python -m services.avatar_render.runtime_wrappers.openvoice_tts")
    monkeypatch.setenv("AVATAR_RENDER_COMMAND", "python -m services.avatar_render.runtime_wrappers.smoke_avatar_render")
    monkeypatch.setattr("services.avatar_render.app.shutil.which", lambda command: "/usr/bin/ffmpeg")
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    dependencies = {item["name"]: item for item in body["dependencies"]}
    assert dependencies["openvoice"]["status"] == "ready"
    assert dependencies["musetalk"]["status"] == "disabled"
    assert "smoke renderer is active" in body["warnings"][2]


def test_models_endpoint_lists_spike_stack_candidates():
    client = TestClient(app)

    response = client.get("/models")

    assert response.status_code == 200
    body = response.json()
    models = {item["id"]: item for item in body["models"]}
    assert models["openvoice-local"]["kind"] == "tts"
    assert models["openvoice-local"]["status"] == "missing"
    assert models["musetalk-v1.5"]["kind"] == "avatar_renderer"
    assert models["musetalk-v1.5"]["status"] == "missing"
    assert models["cpu-smoke-avatar"]["kind"] == "avatar_renderer"
    assert models["cpu-smoke-avatar"]["status"] == "disabled"
    assert models["aiortc-local"]["kind"] == "media_transport"
    assert models["aiortc-local"]["status"] == "disabled"


def test_openapi_exposes_render_only_contract_endpoints():
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/health" in paths
    assert "/models" in paths
    assert "/tts/synthesize" in paths
    assert "/avatar/render" in paths


def test_valid_render_payload_is_accepted_then_reports_renderer_unavailable():
    client = TestClient(app)

    response = client.post("/avatar/render", json=_speech_payload())

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "renderer_not_configured"
    assert detail["speech_id"] == "avatar-test-001"
    assert detail["missing"] == ["musetalk-v1.5"]


def test_render_payload_rejects_raw_question_or_agent_fields():
    client = TestClient(app)
    payload = {
        **_speech_payload(),
        "question": "How do I set up a supplier?",
        "documents": ["source text should not enter the render service"],
        "conversation_history": ["user asked a raw question"],
    }

    response = client.post("/avatar/render", json=payload)

    assert response.status_code == 422
    assert "approved speech text only" in response.text
    assert "conversation_history" in response.text
    assert "documents" in response.text
    assert "question" in response.text


def test_tts_payload_rejects_raw_question_aliases():
    client = TestClient(app)
    payload = {
        "speech_id": "tts-test-001",
        "text": "Approved speech text only.",
        "style": "formal",
        "voice_profile_id": "local-voice",
        "q": "What is the answer?",
        "messages": [{"role": "user", "content": "answer this"}],
    }

    response = client.post("/tts/synthesize", json=payload)

    assert response.status_code == 422
    assert "approved speech text only" in response.text
    assert "messages" in response.text
    assert "q" in response.text


def test_voice_profile_enrollment_requires_explicit_consent():
    client = TestClient(app)

    response = client.post(
        "/voice/profiles",
        json={
            "profile_id": "local-voice",
            "display_name": "Local Voice",
            "sample_paths": ["data/avatar/samples/local.wav"],
        },
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "voice_consent_required"
    assert detail["missing"] == ["consent_confirmed"]


def test_render_request_model_preserves_approved_text_and_metadata():
    request = AvatarRenderRequest.model_validate(_speech_payload())

    assert request.text == "Supplier setup requires due diligence checks before onboarding [1]."
    assert request.metadata["source"] == "knowledge-assistant"
    assert request.render_mode == "offline"
