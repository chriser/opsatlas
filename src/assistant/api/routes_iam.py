"""Identity and access administration (IAM F7): people, roles, grants, groups, denies, requests, audit, settings.

Every handler passes the caller to the identity service, which checks the caller's authority for that exact change
(within their grant ceiling, never on themselves, a fresh password for protected roles) and records it.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from ..iam import catalogue
from ..iam import roles as seeds
from .access import Actor, current_actor, need, signed_in
from .auth import AuthService


class InviteRequest(BaseModel):
    email: str
    display_name: str = ""
    role_id: str | None = None
    space_id: str | None = None
    days: int | None = None
    message: str = ""


class UserUpdate(BaseModel):
    display_name: str | None = None
    email: str | None = None
    note: str | None = None


class Reason(BaseModel):
    reason: str = ""


class RoleCreate(BaseModel):
    name: str
    boundary: str
    permissions: list[str]
    description: str = ""
    based_on: str | None = None


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    permissions: list[str] | None = None


class GrantRequest(BaseModel):
    subject_id: str
    subject_type: str = "user"
    role_id: str
    scope_type: str
    scope_id: str = ""
    days: int | None = None
    reason: str = ""


class GroupCreate(BaseModel):
    name: str
    space_id: str | None = None
    description: str = ""


class GroupMember(BaseModel):
    user_id: str


class DenyRequest(BaseModel):
    subject_id: str
    subject_type: str = "user"
    permission: str
    scope_type: str
    scope_id: str = ""
    reason: str = ""
    days: int | None = None


class AccessRequestBody(BaseModel):
    role_id: str
    space_id: str | None = None
    reason: str = ""
    days: int | None = None


class DecisionBody(BaseModel):
    approve: bool
    reason: str = ""
    days: int | None = None


class ExplainRequest(BaseModel):
    user_id: str
    permission: str
    space_id: str | None = None


class SettingsUpdate(BaseModel):
    changes: dict[str, int] = Field(default_factory=dict)


class SoloOperator(BaseModel):
    enabled: bool
    reason: str = ""


def build_iam_router(auth: AuthService) -> APIRouter:
    router = APIRouter(prefix="/api/iam", tags=["iam"])
    iam = auth.iam

    def who(request: Request) -> Actor:
        return current_actor(request)

    # -- the registry ------------------------------------------------------------------------------------------------
    @router.get("/permissions", dependencies=[signed_in("the registry is not secret: every signed-in person may read it")])
    def permissions() -> dict:
        return {**catalogue.registry(), "roles_version": seeds.SEED_VERSION}

    # -- people --------------------------------------------------------------------------------------------------------
    @router.get("/users", dependencies=[need("iam.users.read", scope="platform")])
    def users(request: Request) -> dict:
        return {"users": iam.users(who(request).iam_actor())}

    @router.post("/users/invite", dependencies=[signed_in("iam.users.invite at the platform, or spaces.members.invite in the space")])
    def invite(body: InviteRequest, request: Request) -> dict:
        return iam.invite(
            who(request).iam_actor(),
            email=body.email,
            display_name=body.display_name,
            role_id=body.role_id,
            space_id=body.space_id,
            days=body.days,
            message=body.message,
        )

    @router.patch("/users/{user_id}", dependencies=[need("iam.users.update", scope="platform")])
    def update_user(user_id: str, body: UserUpdate, request: Request) -> dict:
        return iam.update_user(who(request).iam_actor(), user_id, display_name=body.display_name, email=body.email, note=body.note)

    @router.post("/users/{user_id}/suspend", dependencies=[need("iam.users.suspend", scope="platform")])
    def suspend(user_id: str, body: Reason, request: Request) -> dict:
        return iam.suspend(who(request).iam_actor(), user_id, body.reason)

    @router.post("/users/{user_id}/reactivate", dependencies=[need("iam.users.reactivate", scope="platform")])
    def reactivate(user_id: str, body: Reason, request: Request) -> dict:
        return iam.reactivate(who(request).iam_actor(), user_id, body.reason)

    @router.post("/users/{user_id}/deactivate", dependencies=[need("iam.users.deactivate", scope="platform", fresh=True)])
    def deactivate(user_id: str, body: Reason, request: Request) -> dict:
        return iam.deactivate(who(request).iam_actor(), user_id, body.reason)

    @router.post("/users/{user_id}/recovery", dependencies=[need("iam.users.recovery.initiate", scope="platform", fresh=True)])
    def recovery(user_id: str, body: Reason, request: Request) -> dict:
        return iam.initiate_recovery(who(request).iam_actor(), user_id, body.reason)

    @router.post("/users/{user_id}/invitation/resend", dependencies=[need("iam.users.invite", scope="platform")])
    def resend(user_id: str, request: Request) -> dict:
        return iam.resend_invitation(who(request).iam_actor(), user_id)

    @router.get("/users/{user_id}/sessions", dependencies=[need("iam.sessions.read", scope="platform")])
    def user_sessions(user_id: str, request: Request) -> dict:
        actor = who(request)
        return {"sessions": iam.sessions_of(actor.iam_actor(), user_id, actor.session["id"])}

    @router.post("/users/{user_id}/logout-all", dependencies=[need("iam.sessions.revoke", scope="platform")])
    def user_logout_all(user_id: str, request: Request) -> dict:
        return {"revoked": iam.logout_all(who(request).iam_actor(), user_id)}

    # -- sessions ------------------------------------------------------------------------------------------------------
    @router.get("/sessions", dependencies=[need("iam.sessions.read", scope="platform")])
    def sessions(request: Request) -> dict:
        actor = who(request)
        return {"sessions": iam.all_sessions(actor.iam_actor(), actor.session["id"])}

    @router.delete("/sessions/{session_id}", dependencies=[need("iam.sessions.revoke", scope="platform")])
    def revoke_session(session_id: str, request: Request, reason: str = "") -> dict:
        iam.revoke_session(who(request).iam_actor(), session_id, reason or "revoked by an administrator")
        return {"ok": True}

    # -- roles -----------------------------------------------------------------------------------------------------------
    @router.get("/roles", dependencies=[signed_in("roles are readable by anyone who may give one; the list carries no secrets")])
    def roles() -> dict:
        return {"roles": iam.roles(), "space_role_ids": list(seeds.SPACE_ROLE_IDS), "platform_role_ids": list(seeds.PLATFORM_ROLE_IDS)}

    @router.post("/roles", dependencies=[need("iam.roles.create", scope="platform")])
    def create_role(body: RoleCreate, request: Request) -> dict:
        return iam.create_role(
            who(request).iam_actor(),
            name=body.name,
            boundary=body.boundary,
            permissions=body.permissions,
            description=body.description,
            based_on=body.based_on,
        )

    @router.patch("/roles/{role_id}", dependencies=[need("iam.roles.update", scope="platform")])
    def update_role(role_id: str, body: RoleUpdate, request: Request) -> dict:
        return iam.update_role(
            who(request).iam_actor(), role_id, name=body.name, description=body.description, permissions=body.permissions
        )

    @router.delete("/roles/{role_id}", dependencies=[need("iam.roles.delete", scope="platform")])
    def delete_role(role_id: str, request: Request) -> dict:
        iam.delete_role(who(request).iam_actor(), role_id)
        return {"ok": True}

    @router.get("/grantable", dependencies=[signed_in("what the caller may give, at the platform or in a space")])
    def grantable(request: Request, space_id: str | None = None) -> dict:
        return {"roles": iam.grantable_roles(who(request).iam_actor(), space_id)}

    # -- grants ------------------------------------------------------------------------------------------------------------
    @router.get("/bindings", dependencies=[signed_in("iam.users.read at the platform, or spaces.members.read in the space asked for")])
    def bindings(
        request: Request, user_id: str | None = None, space_id: str | None = None, role_id: str | None = None, include_system: bool = False
    ) -> dict:
        return {
            "bindings": iam.bindings(
                who(request).iam_actor(), user_id=user_id, space_id=space_id, role_id=role_id, include_system=include_system
            )
        }

    @router.post("/bindings", dependencies=[signed_in("iam.roles.assign at the scope, within the caller's grant ceiling")])
    def grant(body: GrantRequest, request: Request) -> dict:
        return iam.grant(
            who(request).iam_actor(),
            subject_id=body.subject_id,
            subject_type=body.subject_type,
            role_id=body.role_id,
            scope_type=body.scope_type,
            scope_id=body.scope_id,
            days=body.days,
            reason=body.reason,
        )

    @router.delete("/bindings/{binding_id}", dependencies=[signed_in("iam.roles.assign at the grant's scope")])
    def revoke(binding_id: str, request: Request, reason: str = "") -> dict:
        iam.revoke_binding(who(request).iam_actor(), binding_id, reason)
        return {"ok": True}

    @router.get("/spaces/{space_id}/members", dependencies=[signed_in("spaces.members.read in that space, or iam.users.read")])
    def members(space_id: str, request: Request) -> dict:
        return {"members": iam.members(who(request).iam_actor(), space_id)}

    @router.delete("/spaces/{space_id}/members/{user_id}", dependencies=[signed_in("spaces.members.manage in that space")])
    def remove_member(space_id: str, user_id: str, request: Request, reason: str = "") -> dict:
        iam.remove_member(who(request).iam_actor(), space_id, user_id, reason)
        return {"ok": True}

    @router.post("/spaces/{space_id}/solo-operator", dependencies=[need("platform.settings.manage", scope="platform", fresh=True)])
    def solo_operator(space_id: str, body: SoloOperator, request: Request) -> dict:
        return iam.set_solo_operator(who(request).iam_actor(), space_id, body.enabled, body.reason)

    # -- groups ----------------------------------------------------------------------------------------------------------------
    @router.get("/groups", dependencies=[signed_in("iam.groups.read at the platform or in the space asked for")])
    def groups(request: Request, space_id: str | None = None) -> dict:
        return {"groups": iam.groups(who(request).iam_actor(), space_id)}

    @router.post("/groups", dependencies=[signed_in("iam.groups.create at the platform or in the space")])
    def create_group(body: GroupCreate, request: Request) -> dict:
        return iam.create_group(who(request).iam_actor(), name=body.name, space_id=body.space_id, description=body.description)

    @router.delete("/groups/{group_id}", dependencies=[signed_in("iam.groups.delete at the group's boundary")])
    def delete_group(group_id: str, request: Request) -> dict:
        iam.delete_group(who(request).iam_actor(), group_id)
        return {"ok": True}

    @router.post(
        "/groups/{group_id}/members",
        dependencies=[signed_in("iam.groups.members.manage; the group's roles must be within the caller's ceiling")],
    )
    def add_member(group_id: str, body: GroupMember, request: Request) -> dict:
        iam.add_group_member(who(request).iam_actor(), group_id, body.user_id)
        return {"ok": True}

    @router.delete("/groups/{group_id}/members/{user_id}", dependencies=[signed_in("iam.groups.members.manage at the group's boundary")])
    def remove_group_member(group_id: str, user_id: str, request: Request) -> dict:
        iam.remove_group_member(who(request).iam_actor(), group_id, user_id)
        return {"ok": True}

    # -- denies ----------------------------------------------------------------------------------------------------------------
    @router.get("/denies", dependencies=[signed_in("iam.access.deny.manage at the platform or in the space asked for")])
    def denies(request: Request, space_id: str | None = None) -> dict:
        return {"denies": iam.denies(who(request).iam_actor(), space_id)}

    @router.post("/denies", dependencies=[signed_in("iam.access.deny.manage at the deny's scope")])
    def deny(body: DenyRequest, request: Request) -> dict:
        return iam.deny(
            who(request).iam_actor(),
            subject_id=body.subject_id,
            subject_type=body.subject_type,
            permission=body.permission,
            scope_type=body.scope_type,
            scope_id=body.scope_id,
            reason=body.reason,
            days=body.days,
        )

    @router.delete("/denies/{deny_id}", dependencies=[signed_in("iam.access.deny.manage at the deny's scope")])
    def lift(deny_id: str, request: Request, reason: str = "") -> dict:
        iam.lift_deny(who(request).iam_actor(), deny_id, reason)
        return {"ok": True}

    # -- access requests and explanations ------------------------------------------------------------------------------------
    @router.get("/access-requests", dependencies=[signed_in("own requests, or those the caller may decide")])
    def access_requests(request: Request, own: bool = False) -> dict:
        return {"requests": iam.requests(who(request).iam_actor(), own=own)}

    @router.post("/access-requests", dependencies=[need("iam.access.requests.create", scope="platform")])
    def request_access(body: AccessRequestBody, request: Request) -> dict:
        return iam.request_access(
            who(request).iam_actor(), role_id=body.role_id, space_id=body.space_id, reason=body.reason, days=body.days
        )

    @router.post(
        "/access-requests/{request_id}/decide",
        dependencies=[signed_in("iam.access.requests.decide at the request's scope; never one's own")],
    )
    def decide(request_id: str, body: DecisionBody, request: Request) -> dict:
        return iam.decide_request(who(request).iam_actor(), request_id, body.approve, body.reason, body.days)

    @router.post("/access-requests/{request_id}/cancel", dependencies=[need("iam.access.requests.cancel_own", scope="platform")])
    def cancel(request_id: str, request: Request) -> dict:
        iam.cancel_request(who(request).iam_actor(), request_id)
        return {"ok": True}

    @router.post("/access/explain", dependencies=[signed_in("iam.access.explain at the platform or in the space asked about")])
    def explain(body: ExplainRequest, request: Request) -> dict:
        return iam.explain(who(request).iam_actor(), user_id=body.user_id, permission=body.permission, space_id=body.space_id)

    @router.get("/capabilities/{user_id}", dependencies=[need("iam.users.read", scope="platform")])
    def capabilities(user_id: str) -> dict:
        return iam.capabilities(user_id)

    # -- audit, security, settings ------------------------------------------------------------------------------------------
    @router.get("/audit", dependencies=[signed_in("audit.read at the platform, or in the space filtered on")])
    def audit(
        request: Request,
        limit: int = Query(100, ge=1, le=500),
        before: int | None = None,
        action: str | None = None,
        actor_id: str | None = None,
        space_id: str | None = None,
        outcome: str | None = None,
        target_id: str | None = None,
    ) -> dict:
        rows = iam.events(
            who(request).iam_actor(),
            limit=limit,
            before_seq=before,
            action=action,
            actor_id=actor_id,
            space_id=space_id,
            outcome=outcome,
            target_id=target_id,
        )
        names = {u["id"]: u["display_name"] for u in iam.store.all("SELECT id, display_name FROM users")}
        for row in rows:
            row["actor_name"] = names.get(row["actor_id"]) if row["actor_id"] else None
        return {"events": rows, "next": rows[-1]["seq"] if len(rows) == limit else None}

    @router.get("/audit/verify", dependencies=[need("audit.read", scope="platform")])
    def verify_audit() -> dict:
        intact, checked = iam.audit.verify_chain()
        return {"intact": intact, "events": checked}

    @router.get("/security/overview", dependencies=[need("audit.read", scope="platform")])
    def security_overview(request: Request) -> dict:
        actor = who(request)
        return {
            "attacks": iam.attack_summary(actor.iam_actor()),
            "recovery_events": iam.recovery_events(actor.iam_actor()),
            "policy_version": iam.store.policy_version(),
            "refusals": iam.audit.events(limit=20, outcome="refused"),
        }

    @router.get("/settings", dependencies=[need("platform.settings.read", scope="platform")])
    def settings() -> dict:
        return {
            "settings": iam.settings(),
            "spaces": [
                {"id": s["id"], "name": s["name"], "kind": s["kind"], "status": s["status"], "solo_operator": bool(s["solo_operator"])}
                for s in iam.spaces()
            ],
        }

    @router.patch("/settings", dependencies=[need("platform.settings.manage", scope="platform", fresh=True)])
    def update_settings(body: SettingsUpdate, request: Request) -> dict:
        return {"settings": iam.update_settings(who(request).iam_actor(), body.changes)}

    return router
