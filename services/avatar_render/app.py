"""FastAPI entrypoint for the independent local avatar render service."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException

from .benchmark import run_offline_benchmark
from .models import (
    AvatarModelStatus,
    AvatarRenderRequest,
    HealthDependency,
    HealthResponse,
    ModelListResponse,
    OfflineBenchmarkRequest,
    OfflineBenchmarkResponse,
    UnavailableDetail,
    VoiceProfileCreateRequest,
    VoiceProfileListResponse,
    VoiceSynthesisRequest,
)

SERVICE_NAME = "avatar-render"
DEFAULT_DATA_ROOT = "data/avatar"

app = FastAPI(
    title="Local Avatar Render Service",
    version="0.1.0",
    description=(
        "Local render/TTS microservice boundary for Avatar Lab. "
        "This service accepts approved speech text only and does not perform retrieval, answer generation or agent logic."
    ),
)


def avatar_data_root() -> Path:
    configured = os.environ.get("AVATAR_RENDER_DATA_DIR", DEFAULT_DATA_ROOT)
    return Path(configured).expanduser().resolve()


def _configured_command(env_var: str) -> str:
    return os.environ.get(env_var, "").strip()


def model_statuses() -> list[AvatarModelStatus]:
    tts_command = _configured_command("AVATAR_TTS_COMMAND")
    render_command = _configured_command("AVATAR_RENDER_COMMAND")
    openvoice_status = "ready" if tts_command else "missing"
    musetalk_status = "ready" if "musetalk_render" in render_command else "missing"
    if render_command and "musetalk_render" not in render_command:
        musetalk_status = "disabled"
    smoke_status = "ready" if "smoke_avatar_render" in render_command else "disabled"
    return [
        AvatarModelStatus(
            id="openvoice-local",
            kind="tts",
            provider="OpenVoice",
            status=openvoice_status,
            detail=(
                "AVATAR_TTS_COMMAND is configured."
                if tts_command
                else "OpenVoice is not configured. Set AVATAR_TTS_COMMAND for benchmark execution."
            ),
        ),
        AvatarModelStatus(
            id="musetalk-v1.5",
            kind="avatar_renderer",
            provider="MuseTalk",
            status=musetalk_status,
            detail=(
                "AVATAR_RENDER_COMMAND points at the MuseTalk wrapper."
                if musetalk_status == "ready"
                else "MuseTalk is not the active renderer command."
            ),
        ),
        AvatarModelStatus(
            id="cpu-smoke-avatar",
            kind="avatar_renderer",
            provider="Pillow/ffmpeg smoke renderer",
            status=smoke_status,
            detail=(
                "CPU smoke renderer is configured for visible API previews; this is not a MuseTalk quality benchmark."
                if smoke_status == "ready"
                else "CPU smoke renderer is available as an explicit preview wrapper."
            ),
        ),
        AvatarModelStatus(
            id="local-motion-layer",
            kind="motion",
            provider="LivePortrait or idle motion template",
            status="disabled",
            detail="Optional companion layer; only needed if MuseTalk alone fails the head/eye/expression quality bar.",
        ),
        AvatarModelStatus(
            id="aiortc-local",
            kind="media_transport",
            provider="aiortc",
            status="disabled",
            detail="Realtime WebRTC transport is reserved for the later realtime spike.",
        ),
    ]


def health_dependencies() -> list[HealthDependency]:
    data_root = avatar_data_root()
    data_status = "ready" if data_root.exists() else "missing"
    tts_command = _configured_command("AVATAR_TTS_COMMAND")
    render_command = _configured_command("AVATAR_RENDER_COMMAND")
    if "musetalk_render" in render_command:
        musetalk_status = "ready"
        musetalk_detail = "AVATAR_RENDER_COMMAND points at the MuseTalk wrapper."
    elif render_command:
        musetalk_status = "disabled"
        musetalk_detail = "MuseTalk is not active; AVATAR_RENDER_COMMAND points at a non-MuseTalk renderer."
    else:
        musetalk_status = "missing"
        musetalk_detail = "Avatar renderer not configured. Set AVATAR_RENDER_COMMAND for benchmark execution."
    ffmpeg = shutil.which("ffmpeg")
    return [
        HealthDependency(
            name="data_root",
            status=data_status,
            detail=f"{data_root} {'exists' if data_root.exists() else 'does not exist yet'}; keep this path out of git.",
        ),
        HealthDependency(
            name="openvoice",
            status="ready" if tts_command else "missing",
            detail=(
                "AVATAR_TTS_COMMAND is configured."
                if tts_command
                else "TTS engine not configured. Set AVATAR_TTS_COMMAND for benchmark execution."
            ),
        ),
        HealthDependency(
            name="musetalk",
            status=musetalk_status,
            detail=musetalk_detail,
        ),
        HealthDependency(
            name="ffmpeg",
            status="ready" if ffmpeg else "missing",
            detail=ffmpeg or "ffmpeg is not on PATH.",
        ),
    ]


def service_warnings() -> list[str]:
    warnings = [
        (
            "Render/TTS command execution is configured through local environment variables."
            if _configured_command("AVATAR_TTS_COMMAND") or _configured_command("AVATAR_RENDER_COMMAND")
            else "Render/TTS model commands are not configured yet."
        ),
        "The service must receive approved speech text only, never raw user questions or source documents.",
    ]
    if "smoke_avatar_render" in _configured_command("AVATAR_RENDER_COMMAND"):
        warnings.append("CPU smoke renderer is active for previews; it is not MuseTalk or a lip-sync quality benchmark.")
    return warnings


def unavailable(code: str, message: str, *, speech_id: str | None = None, missing: list[str] | None = None) -> None:
    detail = UnavailableDetail(code=code, message=message, speech_id=speech_id, missing=missing or [])
    raise HTTPException(status_code=503, detail=detail.model_dump(mode="json"))


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    dependencies = health_dependencies()
    status = "ok" if all(item.status in {"ready", "disabled"} for item in dependencies) else "degraded"
    return HealthResponse(
        status=status,
        data_root=str(avatar_data_root()),
        dependencies=dependencies,
        warnings=service_warnings(),
    )


@app.get("/models", response_model=ModelListResponse)
def models() -> ModelListResponse:
    return ModelListResponse(
        data_root=str(avatar_data_root()),
        models=model_statuses(),
        warnings=service_warnings(),
    )


@app.get("/voice/profiles", response_model=VoiceProfileListResponse)
def voice_profiles() -> VoiceProfileListResponse:
    return VoiceProfileListResponse()


@app.post("/voice/profiles")
def create_voice_profile(body: VoiceProfileCreateRequest) -> None:
    if not body.consent_confirmed:
        unavailable(
            "voice_consent_required",
            "Voice profile enrollment requires explicit local consent before samples can be processed.",
            missing=["consent_confirmed"],
        )
    unavailable(
        "tts_not_configured",
        "Voice profile storage and OpenVoice enrollment are not implemented in Spike 1.",
        missing=["openvoice-local"],
    )


@app.post("/tts/synthesize")
def synthesize_speech(body: VoiceSynthesisRequest) -> None:
    unavailable(
        "tts_not_configured",
        "OpenVoice synthesis is not implemented in Spike 1.",
        speech_id=body.speech_id,
        missing=["openvoice-local"],
    )


@app.post("/avatar/render")
def render_avatar(body: AvatarRenderRequest) -> None:
    unavailable(
        "renderer_not_configured",
        "MuseTalk rendering is not implemented in Spike 1.",
        speech_id=body.speech_id,
        missing=["musetalk-v1.5"],
    )


@app.post("/benchmarks/offline", response_model=OfflineBenchmarkResponse)
def offline_benchmark(body: OfflineBenchmarkRequest) -> OfflineBenchmarkResponse:
    return run_offline_benchmark(body, avatar_data_root())
