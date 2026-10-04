"""Access at the API boundary (IAM F5): who is asking, and whether they may, on every route.

The session comes from the cookie (the control panel) or a bearer header (API clients and tests); a cookie-borne
change needs the session's CSRF token in ``X-CSRF-Token`` as well. A route declares what it needs with ``need()``
(one permission, at the app's space or the platform), ``by_method()`` (a permission per method, for a whole router),
``signed_in()`` (the handler decides per object), ``service()`` or ``public()``. Every route carries one of these
markers; the manifest test fails on one that does not, so a new route cannot be forgotten. Denials that would reveal
a space or a resource the person cannot see answer 404.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import Depends, HTTPException, Request

from ..iam import catalogue
from ..iam.context import Principal, set_principal
from ..iam.service import Actor as IamActor
from ..iam.service import IamError
from ..iam.visibility import Visibility, hides_any, set_visibility, visible

COOKIE = "opsatlas_session"  # loopback HTTP: the development cookie; an HTTPS deployment uses the __Host- name
SECURE_COOKIE = "__Host-opsatlas_session"
PREAUTH_COOKIE = "opsatlas_preauth"
CSRF_HEADER = "x-csrf-token"
INTERACTION_HEADER = "x-opsatlas-interaction"  # "1" when the request follows a deliberate action; polls leave it out
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
DEFAULT_SPACE = "default"


class AccessError(HTTPException):
    """An HTTP error with a code the client can act on (AUTH_REQUIRED, ACCESS_DENIED, NOT_FOUND, REAUTH_REQUIRED,
    CSRF_REQUIRED, RATE_LIMITED)."""

    def __init__(self, status: int, code: str, message: str, headers: dict | None = None) -> None:
        super().__init__(status_code=status, detail=message, headers=headers)
        self.code = code


@dataclass
class Actor:
    """The signed-in person behind one request."""
    user: dict
    session: dict
    auth: Any  # the AuthService
    request_id: str
    via_cookie: bool

    @property
    def id(self) -> str:
        return self.user["id"]

    @property
    def display_name(self) -> str:
        return self.user["display_name"]

    @property
    def login(self) -> str:
        return self.user["login"]

    @property
    def role_label(self) -> str:
        return self.auth.iam_role_label(self.id)

    def fresh(self) -> bool:
        return self.auth.iam.is_fresh(self.session)

    def iam_actor(self) -> IamActor:
        return IamActor(self.id, session_id=self.session["id"], request_id=self.request_id,
                        address=self.session.get("address") or None, fresh=self.fresh())

    def can(self, permission: str, space_id: str | None = None, **conditions) -> bool:
        ctx = self.auth.iam.context(self.user, self.session, self.request_id)
        return bool(self.auth.iam.decide(ctx, permission, space_id, **conditions))

    def require(self, permission: str, space_id: str | None = None, **conditions) -> None:
        ctx = self.auth.iam.context(self.user, self.session, self.request_id)
        decision = self.auth.iam.decide(ctx, permission, space_id, **conditions)
        if not decision:
            if decision.hidden:
                raise AccessError(404, "NOT_FOUND", "Not found")
            raise AccessError(403, "ACCESS_DENIED", decision.reason)


def resolve_actor(request: Request) -> Actor | None:
    """The actor of the request, once per request; None when there is no live session."""
    if hasattr(request.state, "actor"):
        return request.state.actor
    auth = request.app.state.auth
    request_id = request.headers.get("x-request-id", "")[:40] or uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    # A bearer header when there is one (an API client or the test suite: no form can send one across sites, so no
    # CSRF token is needed), and only that; the cookie otherwise, with the CSRF token on every change.
    header = request.headers.get("authorization", "")
    secret = header[7:].strip() if header.lower().startswith("bearer ") else None
    via_cookie = False
    if not secret:
        secret = request.cookies.get(auth.cookie_name)
        via_cookie = bool(secret)
    deliberate = request.method not in SAFE_METHODS or request.headers.get(INTERACTION_HEADER) == "1"
    resolved = auth.iam.resolve(secret, touch=deliberate) if secret else None
    actor = None
    if resolved is not None:
        user, session = resolved
        if via_cookie and request.method not in SAFE_METHODS:
            if request.headers.get(CSRF_HEADER, "") != session["csrf"]:
                raise AccessError(403, "CSRF_REQUIRED", "The request did not carry the session's CSRF token")
        actor = Actor(user, session, auth, request_id, via_cookie)
    request.state.actor = actor
    set_principal(Principal(actor.id, actor.display_name, actor.role_label) if actor else None)
    return actor


class PrincipalMiddleware:
    """Resolve the request's person before routing (REF S3). A route's permission check runs on a worker thread, and a
    context variable set there never reaches the route or the services it calls, so the content workflow, the actions
    engine and the workspace's records saw no person and fell back to a configured name. Resolved here, in the
    request's own context, the person is visible to every route and service of the request. A failed resolution (a
    missing CSRF token, say) is left to the route's own check, which raises it with the right status."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] == "http" and scope.get("path", "").startswith(("/api/", "/services/")) and "app" in scope:
            actor = None
            try:
                actor = resolve_actor(Request(scope))
            except AccessError:
                pass
            set_visibility(_visibility(scope["app"], actor) if actor is not None else None)
        await self.app(scope, receive, send)


def source_guard(request: Request) -> None:
    """A route about one document answers 404 when the person may not read that document (REF S13): the document's
    id in the path, either end of a pair, or the document a comment belongs to."""
    for name in ("source_id", "a_id", "b_id"):
        source_id = request.path_params.get(name)
        if source_id and not visible(source_id):
            raise AccessError(404, "NOT_FOUND", "Not found")
    comment_id = request.path_params.get("comment_id")
    content = getattr(request.app.state, "content", None)
    if comment_id and content is not None:
        comment = content.store.comment(comment_id)
        if comment is not None and not visible(comment["source_id"]):
            raise AccessError(404, "NOT_FOUND", "Not found")


def still_allowed(request: Request, permission: str) -> None:
    """Checked again just before a slow result is delivered (REF S16): the session is read afresh from the store and the
    permission evaluated afresh, so a session ended or a role revoked while an answer was being prepared withholds it.
    Raises the same 401, 403 or 404 a new request would get."""
    actor = getattr(request.state, "actor", None)
    if actor is None:
        raise AccessError(401, "AUTH_REQUIRED", "Sign in to continue")
    iam = request.app.state.auth.iam
    session = iam.store.one("SELECT * FROM sessions WHERE id = ?", (actor.session["id"],))
    if session is None or session["revoked_at"] or iam._check_session(session, touch=False) is None:  # noqa: SLF001
        raise AccessError(401, "AUTH_REQUIRED", "Your session ended while the answer was prepared; sign in again")
    decision = iam.decide(iam.context(actor.user, session, actor.request_id), permission,
                          _space_for(request, permission, "auto"))
    if not decision:
        raise AccessError(404 if decision.hidden else 403, "ACCESS_DENIED", "Your access changed while the answer was prepared")


def derived_guard(request: Request) -> None:
    """The facts map, the activity model and the process views are built from every approved document of a space. A
    person from whom some of those are hidden is not shown them at all (REF S13): read requests answer 403 with the
    reason. Capturing a process (a POST) is not affected."""
    if request.method != "GET":
        return
    register = getattr(request.app.state, "register", None)
    if register is not None and hides_any(r.id for r in register.list() if r.approval_status == "approved"):
        raise AccessError(403, "RESTRICTED_EVIDENCE", "Built from documents you may not read in this space; ask a space owner")


def _visibility(app: Any, actor: Actor) -> Visibility | None:
    """What this person may read in the app's space (REF S13), for the routes, retrieval and answers of the request."""
    auth = getattr(app.state, "auth", None)
    space = getattr(app.state, "space_id", None)
    if auth is None or space is None:
        return None
    content = getattr(app.state, "content", None)
    return Visibility(auth.iam, actor.id, space, content.store.folders_of if content is not None else None)


def current_actor(request: Request) -> Actor:
    actor = resolve_actor(request)
    if actor is None:
        raise AccessError(401, "AUTH_REQUIRED", "Sign in to continue")
    return actor


def _space_for(request: Request, permission: str, scope: str) -> str | None:
    if scope == "platform":
        return None
    if scope.startswith("path:"):
        return request.path_params.get(scope[5:])
    entry = catalogue.get(permission)
    if entry is not None and entry.scopes == (catalogue.OWN,):
        return None  # the caller's own things: checked at the platform, with the caller as owner
    if scope == "space" or (entry is not None and entry.in_spaces):
        return getattr(request.app.state, "space_id", None) or DEFAULT_SPACE
    return None


def _conditions(actor: Actor, permission: str) -> dict:
    entry = catalogue.get(permission)
    return {"owner_id": actor.id} if entry is not None and entry.scopes == (catalogue.OWN,) else {}


def _check(request: Request, actor: Actor, permission: str, scope: str) -> None:
    space, conditions = _space_for(request, permission, scope), _conditions(actor, permission)
    entry = catalogue.get(permission)
    if space is None and scope == "auto" and entry is not None and entry.scopes == (catalogue.OWN,) and entry.in_spaces:
        # One's own things (REF S14): a platform role grants it everywhere, a role in this space grants it here. The
        # route still decides whose the thing is.
        if actor.can(permission, None, **conditions):
            return
        space = getattr(request.app.state, "space_id", None) or DEFAULT_SPACE
    actor.require(permission, space, **conditions)


def need(permission: str, *, scope: str = "auto", fresh: bool = False) -> Any:
    """The route needs ``permission``: at the app's space (a space permission), at the platform (a platform one), or
    as told: ``scope="platform"``, ``"space"`` or ``"path:<param>"`` for a space named in the path."""
    if catalogue.get(permission) is None:
        raise ValueError(f"Unregistered permission on a route: {permission}")

    def dependency(request: Request) -> Actor:
        actor = current_actor(request)
        _check(request, actor, permission, scope)
        if fresh and not actor.fresh():
            raise AccessError(403, "REAUTH_REQUIRED", "Enter your password again to continue")
        return actor

    dependency.iam = {"kind": "human", "permission": permission, "scope": scope, "fresh": fresh}  # type: ignore[attr-defined]
    return Depends(dependency)


def require(request: Request, permission: str, *, scope: str = "auto") -> Actor:
    """The check ``need()`` makes, for a permission a route knows only once it has read the request: an action's own
    permission, for instance (REF S3)."""
    if catalogue.get(permission) is None:
        raise ValueError(f"Unregistered permission: {permission}")
    actor = current_actor(request)
    _check(request, actor, permission, scope)
    return actor


def by_method(**permissions: str) -> list[Any]:
    """For a whole router: the permission each method needs (``GET="documents.read"``). A method not listed is only
    authenticated here, and its route must declare its own ``need()`` — the manifest test insists."""
    for key in permissions.values():
        if catalogue.get(key) is None:
            raise ValueError(f"Unregistered permission on a router: {key}")
    mapping = {k.upper(): v for k, v in permissions.items()}

    def dependency(request: Request) -> Actor:
        actor = current_actor(request)
        permission = mapping.get(request.method)
        if permission:
            actor.require(permission, _space_for(request, permission, "auto"), **_conditions(actor, permission))
        return actor

    dependency.iam = {"kind": "human", "by_method": mapping}  # type: ignore[attr-defined]
    return [Depends(dependency)]


def signed_in(note: str) -> Any:
    """Authenticated; the handler checks the permission itself, per object (say why in ``note``)."""

    def dependency(request: Request) -> Actor:
        return current_actor(request)

    dependency.iam = {"kind": "human", "handler_checks": note}  # type: ignore[attr-defined]
    return Depends(dependency)


def public(note: str) -> Any:
    def dependency() -> None:
        return None

    dependency.iam = {"kind": "public", "note": note}  # type: ignore[attr-defined]
    return Depends(dependency)


def service(check: Callable[[Request], None], note: str) -> Any:
    """A service-to-service credential checked by ``check`` (raises on failure)."""

    def dependency(request: Request) -> None:
        check(request)

    dependency.iam = {"kind": "service", "note": note}  # type: ignore[attr-defined]
    return Depends(dependency)


def mark_websocket(endpoint: Callable, permission: str, note: str) -> Callable:
    endpoint.iam = {"kind": "human", "permission": permission, "websocket": True, "note": note}  # type: ignore[attr-defined]
    return endpoint


# -- the manifest ---------------------------------------------------------------------------------------------------
DOCS_PATHS = ("/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc")


def _walk(routes: Any, prefix: str = "", inherited: tuple = ()) -> Any:
    """Every route, through included routers and mounted apps, with the markers inherited on the way."""
    for route in routes:
        kind = type(route).__name__
        if kind == "_IncludedRouter":  # FastAPI keeps an included router as one entry: look inside it
            context = route.include_context
            markers = inherited + tuple(m for m in (getattr(d.dependency, "iam", None) for d in context.dependencies) if m)
            yield from _walk(route.original_router.routes, prefix + (context.prefix or ""), markers)
        elif hasattr(route, "routes"):
            yield from _walk(route.routes, prefix + (getattr(route, "path", "") or ""), inherited)
        else:
            yield prefix + (getattr(route, "path", "") or ""), route, inherited


def manifest(app: Any) -> list[dict]:
    """Every route of the app (and any mounted app) with its classification, for the test and the guide."""
    rows: list[dict] = []
    for path, route, inherited in _walk(app.routes):
        endpoint = getattr(route, "endpoint", None)
        markers = list(inherited)
        markers += [m for m in (getattr(d.call, "iam", None) for d in getattr(getattr(route, "dependant", None), "dependencies", [])) if m]
        if endpoint is not None and getattr(endpoint, "iam", None):
            markers.append(endpoint.iam)
        if type(route).__name__ == "APIWebSocketRoute" or (not hasattr(route, "methods") and hasattr(route, "endpoint")):
            methods = ["WEBSOCKET"]
        else:
            methods = sorted(getattr(route, "methods", None) or [])
        if not methods:
            continue
        for method in methods:
            permissions: set[str] = set()
            kinds: set[str] = set()
            note = None
            for marker in markers:
                kinds.add(marker["kind"])
                if marker.get("permission"):
                    permissions.add(marker["permission"])
                if marker.get("by_method", {}).get(method):
                    permissions.add(marker["by_method"][method])
                if marker.get("handler_checks") or marker.get("note"):
                    note = marker.get("handler_checks") or marker.get("note")
            if path in DOCS_PATHS:
                kind, note = "public", "the API reference of the development core"
            elif "public" in kinds:
                kind = "public"
            elif "service" in kinds:
                kind = "service"
            elif permissions or note:
                kind = "human"
            else:
                kind = "unclassified"
            rows.append({"method": method, "path": path, "kind": kind, "permissions": sorted(permissions), "note": note})
    return rows


def unclassified(app: Any) -> list[str]:
    return [f"{row['method']} {row['path']}" for row in manifest(app) if row["kind"] == "unclassified"]


def iam_error_response(exc: IamError) -> tuple[int, dict]:
    return exc.status, {"detail": exc.message, "code": exc.code}
