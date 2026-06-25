"""Schemas for the local avatar render service."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "avatar-render-service.v1"
MAX_SPEECH_TEXT_CHARS = 12000

JsonScalar = str | int | float | bool | None
SpeechStyle = Literal["natural", "formal"]
RenderMode = Literal["offline", "realtime"]
DependencyState = Literal["ready", "missing", "disabled", "error"]
ModelKind = Literal["tts", "avatar_renderer", "motion", "media_transport"]
BenchmarkStatus = Literal["blocked", "completed", "failed"]
ArtifactKind = Literal["manifest", "approved_text", "audio", "video", "log"]

FORBIDDEN_AGENT_FIELDS = frozenset({
    "answer",
    "conversation_history",
    "documents",
    "messages",
    "prompt",
    "q",
    "question",
    "retrieval_query",
    "source_text",
    "sources",
    "tool_calls",
})


def reject_agent_payload(data: Any) -> Any:
    """Reject fields that would make the service look like an answer or agent layer."""

    if isinstance(data, dict):
        forbidden = sorted(str(key) for key in data if str(key) in FORBIDDEN_AGENT_FIELDS)
        if forbidden:
            names = ", ".join(forbidden)
            raise ValueError(
                "Avatar render service accepts approved speech text only; "
                f"remove raw question or agent fields: {names}."
            )
    return data


class HealthDependency(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: DependencyState
    detail: str = ""


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    status: Literal["ok", "degraded", "error"] = "degraded"
    service: str = "avatar-render"
    local_only: bool = True
    data_root: str
    dependencies: list[HealthDependency]
    warnings: list[str] = Field(default_factory=list)


class AvatarModelStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: ModelKind
    provider: str
    status: DependencyState
    detail: str = ""


class ModelListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    service: str = "avatar-render"
    local_only: bool = True
    data_root: str
    models: list[AvatarModelStatus]
    warnings: list[str] = Field(default_factory=list)


class VoiceProfileCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=160)
    consent_confirmed: bool = False
    sample_paths: list[str] = Field(default_factory=list, max_length=20)
    notes: str = Field(default="", max_length=1000)

    @field_validator("profile_id", "display_name")
    @classmethod
    def required_text_fields_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Field must not be blank.")
        return value

    @field_validator("sample_paths")
    @classmethod
    def sample_paths_must_be_local_references(cls, value: list[str]) -> list[str]:
        for path in value:
            if not path.strip():
                raise ValueError("Sample paths must not be blank.")
            if "://" in path:
                raise ValueError("Voice samples must be local paths, not URLs.")
        return value


class VoiceProfileSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str
    display_name: str
    status: DependencyState
    detail: str = ""


class VoiceProfileListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    profiles: list[VoiceProfileSummary] = Field(default_factory=list)


class SpeechPayloadBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_SPEECH_TEXT_CHARS)
    style: SpeechStyle = "natural"
    voice_profile_id: str = Field(min_length=1, max_length=120)
    metadata: dict[str, JsonScalar] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def reject_raw_agent_payload(cls, data: Any) -> Any:
        return reject_agent_payload(data)

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Speech text must not be blank.")
        return value

    @field_validator("voice_profile_id")
    @classmethod
    def voice_profile_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Voice profile id must not be blank.")
        return value


class VoiceSynthesisRequest(SpeechPayloadBase):
    model_config = ConfigDict(extra="forbid")

    speech_id: str = Field(min_length=1, max_length=120)

    @field_validator("speech_id")
    @classmethod
    def speech_id_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Speech id must not be blank.")
        return value


class AvatarRenderRequest(SpeechPayloadBase):
    model_config = ConfigDict(extra="forbid")

    speech_id: str = Field(min_length=1, max_length=120)
    avatar_profile_id: str = Field(min_length=1, max_length=120)
    render_mode: RenderMode = "offline"

    @field_validator("speech_id", "avatar_profile_id")
    @classmethod
    def required_ids_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Identifier fields must not be blank.")
        return value


class UnavailableDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    speech_id: str | None = None
    missing: list[str] = Field(default_factory=list)


class OfflineBenchmarkRequest(AvatarRenderRequest):
    model_config = ConfigDict(extra="forbid")

    run_commands: bool = False
    notes: str = Field(default="", max_length=1000)


class BenchmarkDependency(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: DependencyState
    detail: str = ""


class BenchmarkArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ArtifactKind
    path: str
    exists: bool
    size_bytes: int = 0


class BenchmarkMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    value: float | int | str
    unit: str = ""


class OfflineBenchmarkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    status: BenchmarkStatus
    speech_id: str
    run_id: str
    data_root: str
    run_dir: str
    dependencies: list[BenchmarkDependency]
    artifacts: list[BenchmarkArtifact]
    metrics: list[BenchmarkMetric] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
