"""FastAPI entrypoint for the independent local avatar render service."""

from __future__ import annotations

import os
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


def model_statuses() -> list[AvatarModelStatus]:
    return [
        AvatarModelStatus(
            id="openvoice-local",
            kind="tts",
            provider="OpenVoice",
            status="missing",
            detail="Spike 1 contract only; OpenVoice is not installed or configured yet.",
        ),
        AvatarModelStatus(
            id="musetalk-v1.5",
            kind="avatar_renderer",
            provider="MuseTalk",
            status="missing",
            detail="Spike 1 contract only; MuseTalk is not installed or configured yet.",
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
    return [
        HealthDependency(
            name="data_root",
            status=data_status,
            detail=f"{data_root} {'exists' if data_root.exists() else 'does not exist yet'}; keep this path out of git.",
        ),
        HealthDependency(
            name="openvoice",
            status="missing",
            detail="TTS engine not configured in Spike 1.",
        ),
        HealthDependency(
            name="musetalk",
            status="missing",
            detail="Avatar renderer not configured in Spike 1.",
        ),
        HealthDependency(
            name="ffmpeg",
            status="disabled",
            detail="Media assembly dependency will be checked when renderer integration starts.",
        ),
    ]


def service_warnings() -> list[str]:
    return [
        "Render/TTS models are intentionally not wired in Spike 1.",
        "The service must receive approved speech text only, never raw user questions or source documents.",
    ]


def unavailable(code: str, message: str, *, speech_id: str | None = None, missing: list[str] | None = None) -> None:
    detail = UnavailableDetail(code=code, message=message, speech_id=speech_id, missing=missing or [])
    raise HTTPException(status_code=503, detail=detail.model_dump(mode="json"))


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    dependencies = health_dependencies()
    status = "ok" if all(item.status == "ready" for item in dependencies) else "degraded"
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
