"""Avatar rendering integration routes."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Callable
from urllib import request
from urllib.error import HTTPError, URLError

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..answer.service import AnswerResult, AnswerService
from ..avatar.style import AvatarStyleMode, render_avatar_answer

SESSION_TOKEN_ENDPOINT = "https://api.anam.ai/v1/auth/session-token"


@dataclass(frozen=True)
class AnamSettings:
    api_key: str
    persona_id: str

    @property
    def missing(self) -> list[str]:
        missing: list[str] = []
        if not self.api_key:
            missing.append("ANAM_API_KEY")
        if not self.persona_id:
            missing.append("ANAM_PERSONA_ID")
        return missing


class AvatarConfigResponse(BaseModel):
    provider: str = "anam"
    configured: bool
    missing: list[str]
    persona_id_hint: str = ""


class AvatarSessionTokenResponse(BaseModel):
    provider: str = "anam"
    session_token: str


class AvatarAnswerRequest(BaseModel):
    q: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    style: AvatarStyleMode = "natural"


class AvatarAnswerResponse(BaseModel):
    provider: str = "anam"
    style: AvatarStyleMode
    rendered_text: str
    render_notes: list[str]
    answer: AnswerResult


def _settings_from_env() -> AnamSettings:
    return AnamSettings(
        api_key=os.environ.get("ANAM_API_KEY", "").strip(),
        persona_id=os.environ.get("ANAM_PERSONA_ID", "").strip(),
    )


def _hint(value: str) -> str:
    return f"{value[:6]}..." if value else ""


def create_anam_session_token(
    settings: AnamSettings,
    *,
    opener: Callable = request.urlopen,
) -> str:
    missing = settings.missing
    if missing:
        raise ValueError(f"Missing Anam configuration: {', '.join(missing)}")

    payload = json.dumps({"personaConfig": {"personaId": settings.persona_id}}).encode("utf-8")
    req = request.Request(
        SESSION_TOKEN_ENDPOINT,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.api_key}",
        },
    )
    try:
        with opener(req, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"Anam session token request failed ({exc.code}): {detail}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Anam session token request failed: {exc}") from exc

    token = str(body.get("sessionToken") or "")
    if not token:
        raise RuntimeError("Anam session token response did not include sessionToken.")
    return token


def build_avatar_router(answer_service: AnswerService | None = None, dependencies: Sequence | None = None) -> APIRouter:
    router = APIRouter(prefix="/api/avatar", tags=["avatar"], dependencies=list(dependencies or []))

    @router.get("/anam/config", response_model=AvatarConfigResponse)
    def config() -> AvatarConfigResponse:
        settings = _settings_from_env()
        missing = settings.missing
        return AvatarConfigResponse(
            configured=not missing,
            missing=missing,
            persona_id_hint=_hint(settings.persona_id),
        )

    @router.post("/anam/session-token", response_model=AvatarSessionTokenResponse)
    def session_token() -> AvatarSessionTokenResponse:
        settings = _settings_from_env()
        if settings.missing:
            raise HTTPException(status_code=503, detail=f"Missing Anam configuration: {', '.join(settings.missing)}")
        try:
            token = create_anam_session_token(settings)
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return AvatarSessionTokenResponse(session_token=token)

    if answer_service is not None:

        @router.post("/answer", response_model=AvatarAnswerResponse)
        def avatar_answer(body: AvatarAnswerRequest) -> AvatarAnswerResponse:
            result = answer_service.answer(
                body.q,
                body.top_k,
                persona="avatar_lab",
                telemetry_metadata={
                    "avatar_style": body.style,
                    "avatar_rendered": True,
                },
            )
            rendered = render_avatar_answer(result, body.style, body.q, generator=answer_service.generator)
            return AvatarAnswerResponse(
                style=rendered.style,
                rendered_text=rendered.rendered_text,
                render_notes=rendered.render_notes,
                answer=result,
            )

    return router
