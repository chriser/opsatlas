"""Authentication routes and the auth dependency."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from .auth import AuthService, bearer_token


class LoginRequest(BaseModel):
    password: str


def build_auth_router(auth: AuthService) -> APIRouter:
    router = APIRouter(prefix="/api/auth", tags=["auth"])

    @router.post("/login")
    def login(body: LoginRequest) -> dict:
        token = auth.login(body.password)
        if not token:
            raise HTTPException(status_code=401, detail="Invalid operator password.")
        return {"token": token}

    @router.post("/logout")
    def logout(authorization: str | None = Header(default=None)) -> dict:
        auth.logout(bearer_token(authorization))
        return {"ok": True}

    return router


def make_require_auth(auth: AuthService):
    """FastAPI dependency that rejects requests without a valid bearer token."""

    def require_auth(authorization: str | None = Header(default=None)) -> None:
        if not auth.validate(bearer_token(authorization)):
            raise HTTPException(status_code=401, detail="Not authenticated.")

    return require_auth
