"""Minimal operator authentication for the control panel.

A single configurable operator password (KP_OPERATOR_PASSWORD) is exchanged for
a short-lived bearer token held in memory. This is intentionally simple for the
proof of concept — a full enterprise access model is out of scope.
"""

from __future__ import annotations

import os
import secrets


class AuthService:
    def __init__(self, password: str) -> None:
        self._password = password
        self._tokens: set[str] = set()

    def login(self, password: str) -> str | None:
        if password and secrets.compare_digest(password, self._password):
            token = secrets.token_hex(24)
            self._tokens.add(token)
            return token
        return None

    def validate(self, token: str | None) -> bool:
        return bool(token) and token in self._tokens

    def logout(self, token: str | None) -> None:
        if token:
            self._tokens.discard(token)


def auth_from_env() -> AuthService:
    return AuthService(os.environ.get("KP_OPERATOR_PASSWORD", "knowledge-demo"))


def bearer_token(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None
