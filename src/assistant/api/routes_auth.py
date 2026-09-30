"""Sign-in and the person's own account (IAM F3): cookie sessions, CSRF, password and invitation links."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from ..iam.service import IamError
from .access import (
    CSRF_HEADER,
    PREAUTH_COOKIE,
    AccessError,
    Actor,
    current_actor,
    need,
    public,
    resolve_actor,
    signed_in,
)
from .auth import LEGACY_LOGIN, AuthService


class LoginRequest(BaseModel):
    login: str = ""
    password: str


class PasswordRequest(BaseModel):
    password: str


class ChangePasswordRequest(BaseModel):
    current: str
    new: str


class ForgotRequest(BaseModel):
    login: str


class TokenRequest(BaseModel):
    token: str


class ResetRequest(BaseModel):
    token: str
    password: str


class AcceptRequest(BaseModel):
    token: str
    password: str
    display_name: str | None = None


class ProfileRequest(BaseModel):
    display_name: str | None = None


def _set_session_cookie(response: Response, auth: AuthService, session: dict, secret: str) -> None:
    hours = auth.iam.setting("session.privileged_absolute_hours" if session["privileged"] else "session.absolute_hours")
    response.set_cookie(auth.cookie_name, secret, max_age=hours * 3600, httponly=True, samesite="lax",
                        secure=auth.secure_cookie, path="/")


def _clear_session_cookie(response: Response, auth: AuthService) -> None:
    response.delete_cookie(auth.cookie_name, path="/", httponly=True, samesite="lax", secure=auth.secure_cookie)


def _client(request: Request) -> tuple[str, str]:
    return (request.client.host if request.client else "", request.headers.get("user-agent", "")[:120])


def _session_summary(auth: AuthService, session: dict) -> dict:
    view = auth.iam._session_view(session, session["id"])
    return {**view, "csrf": session["csrf"], "idle_minutes": auth.iam.idle_minutes(session),
            "fresh_minutes": auth.iam.setting("reauth.fresh_minutes")}


def me_payload(auth: AuthService, actor: Actor) -> dict:
    iam = auth.iam
    capabilities = iam.capabilities(actor.id)
    spaces = [{"id": s["id"], "name": s["name"], "kind": s["kind"], "solo_operator": bool(s["solo_operator"]),
               "permissions": capabilities["spaces"].get(s["id"], [])} for s in iam.visible_spaces(actor.id)]
    user = {k: actor.user[k] for k in ("id", "login", "email", "display_name", "state", "created_at", "last_sign_in_at")}
    return {"user": {**user, "role_label": actor.role_label}, "session": _session_summary(auth, actor.session),
            "platform_permissions": capabilities["platform"], "spaces": spaces, "legacy": auth.legacy_login}


def build_auth_router(auth: AuthService) -> APIRouter:
    router = APIRouter(prefix="/api/auth", tags=["auth"])
    iam = auth.iam

    @router.get("/csrf", dependencies=[public("pre-authentication CSRF token; no identity")])
    def csrf(response: Response) -> dict:
        token = secrets.token_urlsafe(24)
        response.set_cookie(PREAUTH_COOKIE, token, max_age=900, httponly=True, samesite="lax", secure=auth.secure_cookie, path="/")
        return {"csrf": token}

    def _browser_csrf(request: Request) -> None:
        """A browser (it sends Origin) must hold the pre-authentication token; other clients never send Origin."""
        if request.headers.get("origin"):
            token = request.cookies.get(PREAUTH_COOKIE, "")
            if not token or token != request.headers.get(CSRF_HEADER, ""):
                raise AccessError(403, "CSRF_REQUIRED", "Reload the page and sign in again")

    @router.post("/login", dependencies=[public("sign-in; throttled per account and per address")])
    def login(body: LoginRequest, request: Request, response: Response) -> dict:
        _browser_csrf(request)
        login_name = body.login.strip()
        if not login_name:
            if not auth.legacy_login:
                raise AccessError(401, "INVALID_CREDENTIALS", "Sign in with your email address and password")
            login_name = LEGACY_LOGIN
        address, device = _client(request)
        session, info = iam.login(login_name, body.password, address=address, device=device)
        if session is None:
            if info["code"] == "RATE_LIMITED":
                raise AccessError(429, "RATE_LIMITED", f"Too many attempts; try again in {info['retry_after']} seconds",
                                  headers={"Retry-After": str(info["retry_after"])})
            raise AccessError(401, "INVALID_CREDENTIALS", "That email address and password do not match")
        secret = session.pop("secret")
        _set_session_cookie(response, auth, session, secret)
        response.delete_cookie(PREAUTH_COOKIE, path="/")
        user = iam.user(session["user_id"])
        actor = Actor(user, session, auth, getattr(request.state, "request_id", ""), True)
        payload = me_payload(auth, actor)
        if not request.headers.get("origin"):  # an API client, not a browser: it can read the Set-Cookie header anyway
            payload["token"] = secret
        return payload

    @router.post("/logout", dependencies=[public("ends the session presented, if any; idempotent")])
    def logout(request: Request, response: Response) -> dict:
        actor = None
        try:
            actor = resolve_actor(request)
        except AccessError:
            pass  # a stale or forged request still just clears the cookie
        if actor is not None:
            iam.logout(actor.session)
        _clear_session_cookie(response, auth)
        return {"ok": True}

    @router.post("/logout-all", dependencies=[need("account.sessions.revoke_self", fresh=True)])
    def logout_all(request: Request, response: Response) -> dict:
        actor = current_actor(request)
        count = iam.logout_all(actor.iam_actor(), actor.id)
        _clear_session_cookie(response, auth)
        return {"revoked": count}

    @router.get("/me", dependencies=[signed_in("the caller's own account and capabilities")])
    def me(request: Request) -> dict:
        return me_payload(auth, current_actor(request))

    @router.patch("/me", dependencies=[need("account.update_self")])
    def update_me(body: ProfileRequest, request: Request) -> dict:
        actor = current_actor(request)
        user = iam.update_user(actor.iam_actor(), actor.id, display_name=body.display_name)
        actor.user = user
        return me_payload(auth, actor)

    @router.post("/reauthenticate", dependencies=[signed_in("verifies the caller's own password")])
    def reauthenticate(body: PasswordRequest, request: Request) -> dict:
        actor = current_actor(request)
        if not iam.reauthenticate(actor.session, body.password):
            raise AccessError(403, "INVALID_CREDENTIALS", "That password is not right")
        return {"ok": True, "fresh_minutes": iam.setting("reauth.fresh_minutes")}

    @router.post("/password/change", dependencies=[need("account.password.change")])
    def change_password(body: ChangePasswordRequest, request: Request, response: Response) -> dict:
        actor = current_actor(request)
        address, device = _client(request)
        session, secret = iam.change_password(actor.session, body.current, body.new, address=address, device=device)
        _set_session_cookie(response, auth, session, secret)
        payload = {"ok": True, "session": _session_summary(auth, session)}
        if not request.headers.get("origin"):  # an API client continues on the new session by its secret
            payload["token"] = secret
        return payload

    @router.post("/password/forgot", dependencies=[public("the same answer for every address; nothing is sent without a mail channel")])
    def forgot(body: ForgotRequest) -> dict:
        iam.forgot(body.login)
        return {"ok": True, "message": "If that address has an account, an administrator can hand you a recovery link."}

    @router.post("/password/reset/preview", dependencies=[public("what a reset link is for, without using it")])
    def reset_preview(body: TokenRequest) -> dict:
        return iam.preview(body.token, "reset")

    @router.post("/password/reset", dependencies=[public("one-use reset link; all sessions end; sign in afresh")])
    def reset(body: ResetRequest) -> dict:
        user = iam.reset_password(body.token, body.password)
        return {"ok": True, "login": user["login"]}

    @router.post("/invitations/preview", dependencies=[public("what an invitation is for, without using it")])
    def invitation_preview(body: TokenRequest) -> dict:
        return iam.preview(body.token, "invitation")

    @router.post("/invitations/accept", dependencies=[public("one-use invitation link; the person chooses a password")])
    def accept(body: AcceptRequest) -> dict:
        user = iam.accept_invitation(body.token, body.password, body.display_name)
        return {"ok": True, "login": user["login"], "display_name": user["display_name"]}

    @router.get("/sessions", dependencies=[need("account.sessions.read_self")])
    def sessions(request: Request) -> dict:
        actor = current_actor(request)
        return {"sessions": iam.sessions_of(actor.iam_actor(), actor.id, actor.session["id"])}

    @router.delete("/sessions/{session_id}", dependencies=[need("account.sessions.revoke_self", fresh=True)])
    def revoke_session(session_id: str, request: Request) -> dict:
        actor = current_actor(request)
        iam.revoke_session(actor.iam_actor(), session_id, "revoked by the account holder")
        return {"ok": True}

    return router


def make_require_auth(auth: AuthService):
    """Kept for older callers: the dependency that only insists on a session."""

    def require_auth(actor: Actor = Depends(current_actor)) -> Actor:
        return actor

    require_auth.iam = {"kind": "human", "handler_checks": "authenticated only (legacy dependency)"}  # type: ignore[attr-defined]
    return require_auth


__all__ = ["build_auth_router", "make_require_auth", "IamError", "me_payload"]
