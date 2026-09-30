"""The authentication service of one deployment (IAM F3): the identity store behind the API's sessions.

Two ways to make one. ``AuthService.from_workspace(root)`` is the secured mode: personal accounts in
``<root>/iam.db``, cookie sessions, no shared password. ``AuthService(password)`` is the single-operator legacy mode
kept for the test suite and the generic development core: an in-memory store with one platform administrator,
"operator", whose password is the one given, and a login body of just ``{"password"}``. The Sales workspace never
uses the legacy mode.
"""

from __future__ import annotations

import os
from pathlib import Path

from ..iam import passwords
from ..iam.service import Identity
from ..iam.store import IamStore
from .access import COOKIE, DEFAULT_SPACE, SECURE_COOKIE

LEGACY_LOGIN = "operator@opsatlas.local"


class AuthService:
    def __init__(self, password: str | None = None, *, iam: Identity | None = None, secure_cookie: bool = False) -> None:
        self.secure_cookie = secure_cookie
        if iam is not None:
            self.iam, self.legacy_login = iam, False
            return
        passwords.use_fast_profile()
        self.iam = Identity(IamStore(), origin="http://testserver")
        self.legacy_login = True
        self.iam.register_space(DEFAULT_SPACE, "Knowledge base", "product")
        self.iam.bootstrap_admin(LEGACY_LOGIN, "Operator", password=password or "knowledge-demo", enforce_policy=False)

    @classmethod
    def from_workspace(cls, root: str | Path, *, origin: str, guide_space: str, secure_cookie: bool = False) -> AuthService:
        iam = Identity(IamStore(Path(root) / "iam.db"), origin=origin, guide_space=guide_space)
        return cls(iam=iam, secure_cookie=secure_cookie)

    @property
    def cookie_name(self) -> str:
        return SECURE_COOKIE if self.secure_cookie else COOKIE

    def register_space(self, space_id: str, name: str, kind: str, status: str = "active") -> None:
        self.iam.register_space(space_id, name, kind, status)

    def iam_role_label(self, user_id: str) -> str:
        """The person's most senior role, for display beside their name."""
        now = self.iam.store.stamp()
        names = []
        for binding in self.iam.policy.active_bindings([("user", user_id)], now):
            role = self.iam.policy.role(binding["role_id"])
            if role and not role.get("system"):
                names.append((0 if role["boundary"] == "platform" else 1, role["name"]))
        return sorted(names)[0][1] if names else "Signed-in user"

    # -- the old operator API, kept for callers that only need a yes or no ---------------------------------------
    def login(self, password: str) -> str | None:
        if not self.legacy_login:
            return None
        session, _ = self.iam.login(LEGACY_LOGIN, password)
        return session["secret"] if session else None

    def validate(self, token: str | None) -> bool:
        return self.iam.resolve(token, touch=False) is not None

    def logout(self, token: str | None) -> None:
        resolved = self.iam.resolve(token, touch=False)
        if resolved is not None:
            self.iam.logout(resolved[1])


def auth_from_env() -> AuthService:
    """The generic core on its own: the legacy operator password if one is configured, else a secured store in the
    data directory (bootstrap it with ``python -m assistant.iam bootstrap --root <data dir>``)."""
    password = os.environ.get("KP_OPERATOR_PASSWORD")
    if password:
        return AuthService(password)
    root = Path(os.environ.get("KP_DATA_DIR", "data"))
    return AuthService.from_workspace(root, origin=os.environ.get("OPSATLAS_ORIGIN", "http://127.0.0.1:8010"), guide_space=DEFAULT_SPACE)


def bearer_token(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None
