"""The policy evaluator (IAM F4): one deterministic answer to "may this principal do this, here?".

An operation is allowed only when every step holds, in this order: the principal is active; the space exists and is
active; a current role binding grants the exact permission at an applicable scope (a platform binding never grants
space permissions, nor the other way round); no explicit deny applies; the ownership condition of an "own" permission
holds; and a restricted resource names the principal in its audience. Anything unknown is denied. A deny for a
resource the principal cannot see is *hidden*: the API answers 404, not 403, so denial reveals nothing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from . import catalogue
from . import roles as seeds
from .store import IamStore


@dataclass(frozen=True)
class AuthorizationContext:
    principal_id: str
    principal_type: str = "human"
    session_id: str | None = None
    delegated_by: str | None = None
    selected_space_ids: tuple[str, ...] = ()
    policy_version: int = 0
    credential_epoch: int = 0
    authenticated_at: datetime | None = None
    request_id: str = ""


@dataclass(frozen=True)
class Decision:
    allowed: bool
    code: str
    reason: str
    permission: str
    scope: str
    binding_id: str | None = None
    hidden: bool = False  # the target should look absent (404), not forbidden (403)

    def __bool__(self) -> bool:
        return self.allowed


class PolicyEngine:
    def __init__(self, store: IamStore) -> None:
        self.store = store

    # -- roles ---------------------------------------------------------------------------------------------------
    def role(self, role_id: str) -> dict | None:
        builtin = seeds.BUILTIN.get(role_id)
        if builtin is not None:
            return builtin.to_dict()
        row = self.store.one("SELECT * FROM roles WHERE id = ? AND deleted_at IS NULL", (role_id,))
        if row is None:
            return None
        return {**row, "permissions": json.loads(row["permissions"]), "grantable": json.loads(row["grantable"]),
                "builtin": False, "protected": False, "system": False}

    def role_permissions(self, role_id: str) -> frozenset[str]:
        """The role's permissions that the catalogue still registers: a custom role saved before a permission was
        retired (catalogue v2) keeps the key in its row, and it grants nothing."""
        role = self.role(role_id)
        return frozenset(k for k in role["permissions"] if k in catalogue.PERMISSIONS) if role else frozenset()

    # -- the principal's standing --------------------------------------------------------------------------------
    def subjects_of(self, user_id: str, now: str) -> list[tuple[str, str]]:
        groups = self.store.all(
            "SELECT gm.group_id FROM group_members gm JOIN groups g ON g.id = gm.group_id WHERE gm.user_id = ? "
            "AND g.deleted_at IS NULL AND (gm.expires_at IS NULL OR gm.expires_at > ?)", (user_id, now))
        return [("user", user_id)] + [("group", g["group_id"]) for g in groups]

    def active_bindings(self, subjects: list[tuple[str, str]], now: str) -> list[dict]:
        rows: list[dict] = []
        for subject_type, subject_id in subjects:
            rows += self.store.all(
                "SELECT * FROM role_bindings WHERE subject_type = ? AND subject_id = ? AND revoked_at IS NULL "
                "AND starts_at <= ? AND (ends_at IS NULL OR ends_at > ?) ORDER BY starts_at", (subject_type, subject_id, now, now))
        return rows

    def active_denies(self, subjects: list[tuple[str, str]], permission: str, now: str) -> list[dict]:
        rows: list[dict] = []
        for subject_type, subject_id in subjects:
            rows += self.store.all(
                "SELECT * FROM policy_denies WHERE subject_type = ? AND subject_id = ? AND permission = ? "
                "AND revoked_at IS NULL AND starts_at <= ? AND (ends_at IS NULL OR ends_at > ?)",
                (subject_type, subject_id, permission, now, now))
        return rows

    def membership_active(self, user_id: str, space_id: str, now: str) -> bool:
        return self.store.one(
            "SELECT 1 FROM memberships WHERE user_id = ? AND space_id = ? AND status = 'active' "
            "AND (expires_at IS NULL OR expires_at > ?)", (user_id, space_id, now)) is not None

    # -- the decision --------------------------------------------------------------------------------------------
    def evaluate(self, ctx: AuthorizationContext, permission: str, *, space_id: str | None = None,
                 resource: tuple[str, str] | list[tuple[str, str]] | None = None, owner_id: str | None = None) -> Decision:
        """``resource`` is one (type, id) or a chain: a document then the folders it sits in, innermost first. A grant
        on any of them applies, and a restriction on any of them applies (REF S13)."""
        scope = space_id or "platform"
        chain = [resource] if isinstance(resource, tuple) else list(resource or [])
        scoped = {f"{space_id}/{kind}:{key}" for kind, key in chain}

        def deny(code: str, reason: str, hidden: bool = False) -> Decision:
            return Decision(False, code, reason, permission, scope, hidden=hidden)

        perm = catalogue.get(permission)
        if perm is None:
            return deny("UNKNOWN_PERMISSION", "That permission is not registered")
        user = self.store.one("SELECT id, state, kind FROM users WHERE id = ?", (ctx.principal_id,))
        if user is None or user["state"] != "active":
            return deny("PRINCIPAL_INACTIVE", "The account is not active")
        now = self.store.stamp()
        if space_id is not None:
            space = self.store.one("SELECT status FROM spaces WHERE id = ?", (space_id,))
            if space is None or (space["status"] != "active" and permission != "spaces.restore"):
                return deny("SPACE_UNAVAILABLE", "No such space", hidden=True)  # an archived space only supports restoring
            if not perm.in_spaces:
                return deny("SCOPE_INVALID", "A platform permission is not checked in a space")
        elif not perm.at_platform and perm.scopes != (catalogue.OWN,):
            return deny("SCOPE_INVALID", "That permission needs a space")
        subjects = self.subjects_of(user["id"], now)
        granting = None
        for binding in self.active_bindings(subjects, now):
            if permission not in self.role_permissions(binding["role_id"]):
                continue
            if space_id is None:
                if binding["scope_type"] == "platform":
                    granting = binding
                    break
            elif binding["scope_type"] == "space" and binding["scope_id"] == space_id:
                if self.membership_active(user["id"], space_id, now):
                    granting = binding
                    break
            elif (binding["scope_type"] in ("resource", "collection") and chain
                  and binding["space_id"] == space_id and binding["scope_id"] in scoped):
                granting = binding
                break
        if granting is None:
            hidden = space_id is not None and (permission == "spaces.read" or not self.can_see(user["id"], space_id))
            return deny("NO_GRANT", "No role allows this here", hidden=hidden)
        for denial in self.active_denies(subjects, permission, now):
            if denial["scope_type"] == "platform" or (denial["scope_type"] == "space" and denial["scope_id"] == space_id):
                return deny("EXPLICIT_DENY", f"Explicitly denied: {denial['reason'] or 'no reason given'}")
        if perm.scopes == (catalogue.OWN,) or (catalogue.OWN in perm.scopes and owner_id is not None):
            if owner_id is None or owner_id != user["id"]:
                return deny("NOT_OWNER", "Only the owner may do this")
        if chain and space_id is not None and not self.administers(user["id"], space_id):
            for kind, key in chain:
                policy = self.store.one("SELECT restricted_to FROM resource_policies WHERE resource_type = ? AND resource_id = ? "
                                        "AND space_id = ?", (kind, key, space_id))
                if policy is not None:
                    audience = set(json.loads(policy["restricted_to"]))
                    if audience and not any(f"{t}:{i}" in audience for t, i in subjects):
                        return deny("RESTRICTED", "The resource is restricted to a named audience", hidden=True)
        return Decision(True, "ALLOWED", f"Allowed by the role {granting['role_id']}", permission, scope, granting["id"])

    def administers(self, user_id: str, space_id: str) -> bool:
        """Those who manage a space's access always read its restricted documents (REF S13): its owners and the
        platform administrators."""
        if "resources.permissions.manage" in self.effective(user_id, space_id):
            return True
        return "resources.permissions.manage" in self.role_union_at_platform(user_id)

    def role_union_at_platform(self, user_id: str) -> set[str]:
        now = self.store.stamp()
        keys: set[str] = set()
        for binding in self.active_bindings(self.subjects_of(user_id, now), now):
            if binding["scope_type"] == "platform":
                keys |= set(self.role_permissions(binding["role_id"]))
        return keys

    def can_see(self, user_id: str, space_id: str) -> bool:
        return "spaces.read" in self.effective(user_id, space_id)

    def effective(self, user_id: str, space_id: str | None = None) -> set[str]:
        """The permissions a person holds at the platform or in one space: for capabilities and explanations; the
        evaluator above stays authoritative for every decision."""
        user = self.store.one("SELECT id, state FROM users WHERE id = ?", (user_id,))
        if user is None or user["state"] != "active":
            return set()
        now = self.store.stamp()
        if space_id is not None:
            space = self.store.one("SELECT status FROM spaces WHERE id = ?", (space_id,))
            if space is None or space["status"] != "active" or not self.membership_active(user_id, space_id, now):
                return set()
        subjects = self.subjects_of(user_id, now)
        keys: set[str] = set()
        for binding in self.active_bindings(subjects, now):
            perms = self.role_permissions(binding["role_id"])
            if space_id is None and binding["scope_type"] == "platform":
                keys |= {k for k in perms if catalogue.PERMISSIONS[k].at_platform or catalogue.PERMISSIONS[k].scopes == (catalogue.OWN,)}
            elif space_id is not None and binding["scope_type"] == "space" and binding["scope_id"] == space_id:
                keys |= {k for k in perms if catalogue.PERMISSIONS[k].in_spaces}
        for key in list(keys):
            for denial in self.active_denies(subjects, key, now):
                if denial["scope_type"] == "platform" or (denial["scope_type"] == "space" and denial["scope_id"] == space_id):
                    keys.discard(key)
        return keys

    def explain(self, user_id: str, permission: str, space_id: str | None = None) -> dict:
        ctx = AuthorizationContext(principal_id=user_id)
        decision = self.evaluate(ctx, permission, space_id=space_id)
        now = self.store.stamp()
        subjects = self.subjects_of(user_id, now)
        considered = []
        for binding in self.active_bindings(subjects, now):
            role = self.role(binding["role_id"]) or {"name": binding["role_id"]}
            considered.append({
                "binding_id": binding["id"], "role_id": binding["role_id"], "role_name": role.get("name"),
                "via_group": binding["subject_id"] if binding["subject_type"] == "group" else None,
                "scope_type": binding["scope_type"], "scope_id": binding["scope_id"], "ends_at": binding["ends_at"],
                "grants_permission": permission in self.role_permissions(binding["role_id"]),
                "applies_here": (binding["scope_type"] == "platform") if space_id is None
                                else (binding["scope_type"] == "space" and binding["scope_id"] == space_id),
            })
        denies = [{"id": d["id"], "scope_type": d["scope_type"], "scope_id": d["scope_id"], "reason": d["reason"],
                   "ends_at": d["ends_at"]} for d in self.active_denies(subjects, permission, now)]
        return {"allowed": decision.allowed, "code": decision.code, "reason": decision.reason, "permission": permission,
                "space_id": space_id, "bindings": considered, "denies": denies,
                "membership_active": self.membership_active(user_id, space_id, now) if space_id else None}
