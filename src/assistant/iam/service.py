"""Identity: the service behind sign-in, accounts, sessions, roles and grants (IAM F2–F4).

Every public method takes the acting principal (``Actor``) first, checks that principal's authority through the
policy engine, makes its change in one transaction and records it in the audit. Nothing here trusts a name: people
are their opaque ids, logins are canonicalised only for matching, and secrets exist in memory just long enough to be
handed over once.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import re
import secrets
import sqlite3
import unicodedata
from dataclasses import dataclass
from datetime import timedelta

from . import catalogue, passwords
from . import roles as seeds
from .audit import Audit
from .policy import AuthorizationContext, Decision, PolicyEngine
from .store import IamStore, parse

_log = logging.getLogger("assistant.iam")

DEFAULT_SETTINGS: dict[str, int] = {
    "session.idle_minutes": 30,
    "session.absolute_hours": 12,
    "session.privileged_idle_minutes": 15,
    "session.privileged_absolute_hours": 8,
    "session.max_active": 10,
    "reauth.fresh_minutes": 5,
    "throttle.account_attempts": 5,
    "throttle.account_window_minutes": 15,
    "throttle.network_attempts": 100,
    "throttle.network_window_minutes": 15,
    "throttle.recovery_per_hour": 3,
    "throttle.cap_minutes": 15,
    "invitation.hours": 72,
    "reset.minutes": 30,
    "ws_ticket.seconds": 30,
    "guest.days": 30,
    "elevated.days": 7,
    "review.admin_days": 30,
    "review.member_days": 90,
}
SETTING_RANGES: dict[str, tuple[int, int]] = {
    "session.idle_minutes": (5, 720),
    "session.absolute_hours": (1, 72),
    "session.privileged_idle_minutes": (5, 720),
    "session.privileged_absolute_hours": (1, 72),
    "session.max_active": (1, 50),
    "reauth.fresh_minutes": (1, 60),
    "throttle.account_attempts": (3, 50),
    "throttle.account_window_minutes": (1, 120),
    "throttle.network_attempts": (10, 10000),
    "throttle.network_window_minutes": (1, 120),
    "throttle.recovery_per_hour": (1, 20),
    "throttle.cap_minutes": (1, 60),
    "invitation.hours": (1, 720),
    "reset.minutes": (5, 240),
    "ws_ticket.seconds": (10, 300),
    "guest.days": (1, 365),
    "elevated.days": (1, 365),
    "review.admin_days": (7, 365),
    "review.member_days": (7, 365),
}
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
# A person's picture (IAM F10): cropped to a square in the browser, kept as a small JPEG.
PICTURE_UPLOAD_BYTES = 4 * 1024 * 1024
PICTURE_SIDE = 256
PICTURE_MAX_PIXELS = 8000 * 8000
PICTURE_BACKGROUND = (31, 41, 55)  # under a transparent picture: the sidebar's slate
INVITATION, RESET, TICKET = "invitation", "reset", "ws_ticket"


class IamError(Exception):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


@dataclass(frozen=True)
class Actor:
    """Who is asking: a signed-in person, or the host running a local procedure (``id`` None)."""

    id: str | None
    type: str = "human"
    session_id: str | None = None
    request_id: str | None = None
    address: str | None = None
    fresh: bool = False  # the password was entered within the fresh-authentication window

    @property
    def is_host(self) -> bool:
        return self.id is None


HOST = Actor(None, type="host")


def canonical(login: str) -> str:
    return unicodedata.normalize("NFKC", login or "").strip().casefold()


def digest(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def new_secret() -> str:
    return secrets.token_urlsafe(32)  # 256 bits


class Identity:
    def __init__(self, store: IamStore, *, origin: str = "http://127.0.0.1:8780", guide_space: str | None = None) -> None:
        self.store = store
        self.origin = origin.rstrip("/")
        self.guide_space = guide_space
        self.audit = Audit(store)
        self.policy = PolicyEngine(store)
        # Who holds a document or folder, set by the app that serves the spaces (Bug #2202, REF S13):
        # (space_id, resource_type, resource_id) -> True, False, or None when it cannot tell.
        self.holds = None
        self._solo_existing_spaces()

    def _people(self) -> int:
        return self.store.one("SELECT COUNT(*) AS n FROM users WHERE state = 'active' AND kind = 'human'")["n"]

    def _solo_existing_spaces(self) -> None:
        """Once (REF S15, the Human's decision of 2 Oct 2026): the spaces registered before author-approver separation
        was enforced start in solo-operator mode, so the one person using them keeps publishing their own edits, each
        recorded as an exception. Turned off per space on the Security page once a second approver exists."""
        if self.store.setting("ref_s15_solo_existing") is not None:
            return
        with self.store.transaction():
            spaces = self.store.all("SELECT id FROM spaces WHERE solo_operator = 0")
            for row in spaces:
                self.store.update("spaces", {"id": row["id"]}, {"solo_operator": 1})
            self.store.set_setting("ref_s15_solo_existing", [row["id"] for row in spaces])

    # -- settings ------------------------------------------------------------------------------------------------
    def setting(self, key: str) -> int:
        return int(self.store.setting(key, DEFAULT_SETTINGS[key]))

    def settings(self) -> dict:
        return {key: self.setting(key) for key in DEFAULT_SETTINGS}

    def update_settings(self, actor: Actor, changes: dict) -> dict:
        self._require(actor, "platform.settings.manage")
        before = self.settings()
        with self.store.transaction():
            for key, value in changes.items():
                if key not in SETTING_RANGES:
                    raise IamError("UNKNOWN_SETTING", f"No such setting: {key}")
                low, high = SETTING_RANGES[key]
                if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
                    raise IamError("SETTING_OUT_OF_RANGE", f"{key} must be a whole number from {low} to {high}")
                self.store.set_setting(key, value, actor.id)
            after = self.settings()
            self._audit(actor, "settings.changed", before={k: before[k] for k in changes}, after={k: after[k] for k in changes})
        return after

    # -- spaces --------------------------------------------------------------------------------------------------
    def spaces(self, status: str | None = None) -> list[dict]:
        rows = self.store.all("SELECT * FROM spaces ORDER BY registered_at")
        return [r for r in rows if status is None or r["status"] == status]

    def space(self, space_id: str) -> dict | None:
        return self.store.one("SELECT * FROM spaces WHERE id = ?", (space_id,))

    def register_space(self, space_id: str, name: str, kind: str, status: str = "active") -> dict:
        """Known to the policy: a space the cores serve. A new space gets every platform administrator's explicit
        bindings at once, and the Product Guide gives every active person its reader entitlement."""
        with self.store.transaction():
            existing = self.space(space_id)
            if existing is None:
                # A space registered while one person uses the installation starts in solo-operator mode (REF S15).
                self.store.insert(
                    "spaces", {"id": space_id, "name": name, "kind": kind, "status": status, "registered_at": self.store.stamp(),
                               "solo_operator": int(self._people() <= 1)}
                )
                # An invited administrator included: the binding waits for the account, as the bootstrap's does.
                for admin in self._platform_administrators(active_only=False):
                    if admin["state"] == "deactivated":
                        continue
                    self._bind(
                        admin["id"], "platform_administrator", "space", space_id, issuer=None, reason="platform administrator", system=True
                    )
                if space_id == self.guide_space:
                    for user in self.store.all("SELECT id FROM users WHERE state = 'active' AND kind = 'human'"):
                        self._bind(
                            user["id"],
                            seeds.PRODUCT_GUIDE_ROLE,
                            "space",
                            space_id,
                            issuer=None,
                            reason="Product Guide entitlement",
                            system=True,
                        )
            else:
                self.store.update("spaces", {"id": space_id}, {"name": name, "kind": kind, "status": status})
            return self.space(space_id)  # type: ignore[return-value]

    def set_solo_operator(self, actor: Actor, space_id: str, enabled: bool, reason: str = "") -> dict:
        self._require(actor, "platform.settings.manage")
        if self.space(space_id) is None:
            raise IamError("NOT_FOUND", "No such space", 404)
        with self.store.transaction():
            self.store.update("spaces", {"id": space_id}, {"solo_operator": int(enabled)})
            self._audit(
                actor,
                "space.solo_operator",
                target_type="space",
                target_id=space_id,
                space_id=space_id,
                reason=reason,
                after={"solo_operator": enabled},
            )
        return self.space(space_id)  # type: ignore[return-value]

    def solo_operator(self, space_id: str) -> bool:
        space = self.space(space_id)
        return bool(space and space["solo_operator"])

    # -- restricted documents and folders (REF S13) ------------------------------------------------------------
    RESOURCE_TYPES = ("document", "folder")

    def restrictions(self, space_id: str) -> list[dict]:
        rows = self.store.all("SELECT resource_type, resource_id, restricted_to, updated_at, updated_by FROM resource_policies "
                              "WHERE space_id = ? AND restricted_to != '[]'", (space_id,))
        return [{**r, "restricted_to": json.loads(r["restricted_to"])} for r in rows]

    def restrict(self, actor: Actor, space_id: str, resource_type: str, resource_id: str, audience: list[str],
                 reason: str = "") -> dict:
        """Restrict a document or folder in a space to named people or groups ("user:<id>", "group:<id>"); an empty
        audience lifts the restriction. Those who administer the space always keep access. Recorded in the audit."""
        self._require(actor, "resources.permissions.manage", space_id)
        if resource_type not in self.RESOURCE_TYPES:
            raise IamError("INVALID", "Restrict a document or a folder")
        if self.space(space_id) is None:
            raise IamError("NOT_FOUND", "No such space", 404)
        clean: list[str] = []
        for entry in audience or []:
            kind, _, key = str(entry).partition(":")
            if kind == "user":
                self._existing(key)
            elif kind == "group":
                if self.store.one("SELECT 1 FROM groups WHERE id = ? AND deleted_at IS NULL", (key,)) is None:
                    raise IamError("NOT_FOUND", "No such group", 404)
            else:
                raise IamError("INVALID", "An audience is people (user:<id>) or groups (group:<id>)")
            if entry not in clean:
                clean.append(entry)
        before = self.store.one("SELECT restricted_to, space_id FROM resource_policies WHERE resource_type = ? AND "
                                "resource_id = ?", (resource_type, resource_id))
        if not self._may_restrict(space_id, resource_type, resource_id, before):
            raise IamError("NOT_FOUND", "No such document or folder in this space", 404)
        with self.store.transaction():
            if before is None:
                try:
                    self.store.insert("resource_policies", {"resource_type": resource_type, "resource_id": resource_id,
                                                            "space_id": space_id, "restricted_to": json.dumps(clean),
                                                            "updated_at": self.store.stamp(), "updated_by": actor.id})
                except sqlite3.IntegrityError:
                    if self.store.one("SELECT 1 FROM resource_policies WHERE resource_type = ? AND resource_id = ?",
                                      (resource_type, resource_id)) is None:
                        raise  # not a row written meanwhile: a real fault
                    raise IamError("CONFLICT", "The restriction changed meanwhile; try again", 409) from None
            elif not self._move_row(resource_type, resource_id, before["space_id"],
                                    (json.dumps(clean), self.store.stamp(), actor.id, space_id)):
                raise IamError("CONFLICT", "The restriction changed meanwhile; try again", 409)
            self.store.bump_policy_version()
            self._audit(actor, "resource.restricted" if clean else "resource.unrestricted", target_type=resource_type,
                        target_id=resource_id, space_id=space_id, reason=reason,
                        before={"restricted_to": json.loads(before["restricted_to"]) if before else []},
                        after={"restricted_to": clean})
        return {"resource_type": resource_type, "resource_id": resource_id, "space_id": space_id, "restricted_to": clean}

    def _move_row(self, resource_type: str, resource_id: str, from_space: str, values: tuple) -> bool:
        """The row's change: (restricted_to, updated_at, updated_by, space_id), applied only if the row's space is still the
        one the check saw (Bug #2202, R2-2), so the row follows its holder. False if it changed meanwhile."""
        return self.store.run(
            "UPDATE resource_policies SET restricted_to = ?, version = version + 1, updated_at = ?, updated_by = ?, "
            "space_id = ? WHERE resource_type = ? AND resource_id = ? AND space_id = ?",
            (*values, resource_type, resource_id, from_space)).rowcount == 1

    def _held(self, space_id: str, resource_type: str, resource_id: str) -> bool | None:
        """Whether ``space_id`` holds the resource now: True, False, or None when it cannot tell (no resolver, a store that
        cannot be read). Unknown counts against a change (Bug #2202). An archived space serves no one, so it holds nothing
        a restriction protects, and blocks no space that holds the resource (the code red team's CRT-1)."""
        if self.holds is None:
            return None
        space = self.space(space_id)
        if space is not None and space["status"] == "archived":
            return False
        try:
            return self.holds(space_id, resource_type, resource_id)
        except Exception:
            _log.warning("Who holds %s %s in %s could not be told; the restriction's change is refused", resource_type,
                         resource_id, space_id, exc_info=True)
            return None

    def _takes_from_holder(self, space_id: str, resource_type: str, resource_id: str, row: dict | None) -> bool:
        """(b) The row belongs to another space that may still hold the resource (a document held twice): no taking it."""
        return row is not None and row["space_id"] != space_id and self._held(row["space_id"], resource_type, resource_id) is not False

    def _may_restrict(self, space_id: str, resource_type: str, resource_id: str, row: dict | None) -> bool:
        """Bug #2202 (REF S13): a resource's restriction is written only for a space that holds the resource now.
        (a) A holder may set, change or lift it, and the row follows the holder; (b) but may not take it from another space
        that also still holds it; (c) a space that does not hold it is refused, except the row's own space when no space
        holds the resource any more (lifting a deleted document's restriction)."""
        held = self._held(space_id, resource_type, resource_id)
        if held is True:
            return not self._takes_from_holder(space_id, resource_type, resource_id, row)
        if held is None or row is None or row["space_id"] != space_id:
            return False
        return all(self._held(space["id"], resource_type, resource_id) is False for space in self.spaces())

    # -- users ---------------------------------------------------------------------------------------------------
    def user(self, user_id: str) -> dict | None:
        return self.store.one("SELECT * FROM users WHERE id = ?", (user_id,))

    def user_by_login(self, login: str) -> dict | None:
        return self.store.one("SELECT * FROM users WHERE login_canonical = ?", (canonical(login),))

    def users(self, actor: Actor) -> list[dict]:
        self._require(actor, "iam.users.read")
        now = self.store.stamp()
        rows = self.store.all("SELECT * FROM users ORDER BY created_at")
        for row in rows:
            row["roles"] = self._role_summary(row["id"], now)
            row["sessions"] = self.store.one(
                "SELECT COUNT(*) AS n FROM sessions WHERE user_id = ? AND revoked_at IS NULL AND absolute_expires_at > ?", (row["id"], now)
            )["n"]
            row["invitation"] = self._open_token(row["id"], INVITATION)
        return rows

    def _role_summary(self, user_id: str, now: str) -> list[dict]:
        out = []
        for binding in self.policy.active_bindings([("user", user_id)], now):
            role = self.policy.role(binding["role_id"])
            if role is None or role.get("system"):
                continue
            space = self.space(binding["scope_id"]) if binding["scope_type"] == "space" else None
            out.append(
                {
                    "binding_id": binding["id"],
                    "role_id": binding["role_id"],
                    "role_name": role["name"],
                    "scope_type": binding["scope_type"],
                    "scope_id": binding["scope_id"],
                    "space_name": space["name"] if space else None,
                    "ends_at": binding["ends_at"],
                }
            )
        return out

    def _open_token(self, user_id: str, purpose: str) -> dict | None:
        row = self.store.one(
            "SELECT expires_at, issued_at FROM lifecycle_tokens WHERE user_id = ? AND purpose = ? AND consumed_at IS NULL "
            "AND revoked_at IS NULL AND expires_at > ? ORDER BY issued_at DESC LIMIT 1",
            (user_id, purpose, self.store.stamp()),
        )
        return row

    def _create_user(self, email: str, display_name: str, *, state: str) -> dict:
        email = (email or "").strip()
        if not _EMAIL.match(email) or len(email) > 254:
            raise IamError("INVALID_EMAIL", "Enter a valid email address")
        display_name = " ".join((display_name or "").split())[:80] or email.split("@")[0]
        if self.user_by_login(email) is not None:
            raise IamError("EXISTS", "An account with that email already exists", 409)
        now = self.store.stamp()
        row = {
            "id": self.store.new_id("usr"),
            "login": email,
            "login_canonical": canonical(email),
            "email": email,
            "display_name": display_name,
            "state": state,
            "kind": "human",
            "credential_epoch": 1,
            "created_at": now,
            "updated_at": now,
        }
        self.store.insert("users", row)
        return row

    def _activate(self, user_id: str) -> None:
        now = self.store.stamp()
        self.store.update("users", {"id": user_id}, {"state": "active", "activated_at": now, "updated_at": now})
        self._bind(user_id, "signed_in_user", "platform", "", issuer=None, reason="signed-in user", system=True)
        if self.store.one(
            "SELECT 1 FROM role_bindings WHERE subject_type = 'user' AND subject_id = ? AND role_id = 'platform_administrator' "
            "AND scope_type = 'platform' AND revoked_at IS NULL",
            (user_id,),
        ):
            for space in self.spaces():  # a platform administrator invited before the spaces were known gets them all now
                self._bind(
                    user_id, "platform_administrator", "space", space["id"], issuer=None, reason="platform administrator", system=True
                )
        if self.guide_space and self.space(self.guide_space):
            self._bind(
                user_id, seeds.PRODUCT_GUIDE_ROLE, "space", self.guide_space, issuer=None, reason="Product Guide entitlement", system=True
            )

    def _platform_administrators(self, active_only: bool = True) -> list[dict]:
        return self.store.all(
            "SELECT DISTINCT u.* FROM users u JOIN role_bindings b ON b.subject_type = 'user' AND b.subject_id = u.id "
            "WHERE b.role_id = 'platform_administrator' AND b.scope_type = 'platform' AND b.revoked_at IS NULL "
            + ("AND u.state = 'active'" if active_only else "")
        )

    def bootstrap_admin(
        self, email: str, display_name: str, *, password: str | None = None, host_user: str = "", enforce_policy: bool = True
    ) -> tuple[dict, str | None]:
        """Initial set-up, from the host: one named platform administrator. With no password, the person sets their
        own through a one-time invitation link (shown once). Refused once an administrator is active."""
        if self._platform_administrators():
            raise IamError("ALREADY_INITIALISED", "Set-up is complete: a platform administrator is active", 409)
        with self.store.transaction():
            user = self.user_by_login(email)
            others = [
                a
                for a in self._platform_administrators(active_only=False)
                if a["state"] != "deactivated" and (user is None or a["id"] != user["id"])
            ]
            if others:  # an invitation is pending for someone else: set-up is theirs to finish, or to be re-issued for them
                raise IamError(
                    "ALREADY_INITIALISED", f"An invitation is already out for {others[0]['email']}; re-run for that address", 409
                )
            if user is None:
                user = self._create_user(email, display_name, state="invited")
            self._bind(user["id"], "platform_administrator", "platform", "", issuer=None, reason="bootstrap", system=True)
            for space in self.spaces():
                self._bind(user["id"], "platform_administrator", "space", space["id"], issuer=None, reason="bootstrap", system=True)
            token = None
            if password is not None:
                self._set_password(
                    user["id"], password, login=user["login"], display_name=user["display_name"], enforce_policy=enforce_policy
                )
                self._activate(user["id"])
            else:
                token = self._issue(
                    INVITATION,
                    user,
                    issuer=None,
                    hours=self.setting("invitation.hours"),
                    payload={"bootstrap": True, "role_id": "platform_administrator"},
                )
            self.audit.record(
                action="iam.bootstrap",
                actor_type="host",
                target_type="user",
                target_id=user["id"],
                target_label=user["display_name"],
                detail={"host_user": host_user, "invited": token is not None},
            )
        return self.user(user["id"]), token  # type: ignore[return-value]

    def emergency_recovery(self, user: dict, reason: str, host_user: str) -> str:
        """Emergency recovery, from the host: a one-time reset link for an active account, every session of it ended, the
        recovery recorded and audited, in one transaction. The link's secret, shown once by the caller. An account that is
        not active is refused, with nothing changed (REF S68, its red team's R1)."""
        with self.store.transaction():
            current = self.user(user["id"])
            if current is None or current["state"] != "active":
                raise IamError("NOT_ACTIVE", "No active account with that login", 409)
            token = self._issue(RESET, user, issuer=None, minutes=self.setting("reset.minutes"),
                                payload={"recovery": True, "reason": reason})
            self._revoke_sessions(user["id"], "emergency recovery")
            self.store.insert(
                "recovery_events",
                {
                    "id": self.store.new_id("rec"),
                    "at": self.store.stamp(),
                    "user_id": user["id"],
                    "kind": "password reset",
                    "reason": reason[:500],
                    "host_user": host_user,
                },
            )
            self.audit.record(
                action="recovery.emergency",
                actor_type="host",
                target_type="user",
                target_id=user["id"],
                target_label=user["display_name"],
                reason=reason,
                detail={"host_user": host_user},
            )
        return token

    def invite(
        self,
        actor: Actor,
        *,
        email: str,
        display_name: str = "",
        role_id: str | None = None,
        space_id: str | None = None,
        days: int | None = None,
        message: str = "",
    ) -> dict:
        """A person is invited with a concrete role in a concrete space (or none: the Product Guide only). A new
        account waits as *invited* until the link is used; an existing active account receives the grant at once."""
        role = self.policy.role(role_id) if role_id else None
        if role_id and role is None:
            raise IamError("NOT_FOUND", "No such role", 404)
        if role and role["boundary"] == "space" and not space_id:
            raise IamError("SPACE_REQUIRED", "A space role needs a space")
        if role and role["boundary"] == "platform" and space_id:
            raise IamError("SCOPE_INVALID", "A platform role is not bound to a space")
        if space_id and not self.space(space_id):
            raise IamError("NOT_FOUND", "No such space", 404)
        if space_id:
            self._require(actor, "spaces.members.invite", space_id, alternative=("iam.users.invite", None))
        else:
            self._require(actor, "iam.users.invite")
        if role:
            self._assert_grantable(actor, role, space_id)
        with self.store.transaction():
            user = self.user_by_login(email)
            new = user is None
            if new:
                user = self._create_user(email, display_name, state="invited")
            elif user["state"] == "deactivated":
                raise IamError("DEACTIVATED", "That account was deactivated; reactivate it instead", 409)
            binding = None
            if role:
                binding = self._bind(
                    user["id"],
                    role_id,
                    "platform" if role["boundary"] == "platform" else "space",
                    space_id or "",
                    issuer=actor.id,
                    reason=message[:200],
                    ends_at=self._ends(days),
                )
            token = None
            if user["state"] == "invited":
                token = self._issue(
                    INVITATION,
                    user,
                    issuer=actor.id,
                    hours=self.setting("invitation.hours"),
                    payload={"space_id": space_id, "role_id": role_id, "message": message[:500]},
                )
            self._audit(
                actor,
                "user.invited" if new else "user.granted",
                target_type="user",
                target_id=user["id"],
                target_label=user["display_name"],
                space_id=space_id,
                detail={"role_id": role_id, "days": days, "new_account": new, "link_shown": token is not None},
            )
        return {
            "user": self.user(user["id"]),
            "binding": binding,
            "token": token,
            "link": self.link(INVITATION, token) if token else None,
            "expires_at": self._open_token(user["id"], INVITATION)["expires_at"] if token else None,
        }

    def resend_invitation(self, actor: Actor, user_id: str) -> dict:
        user = self._existing(user_id)
        if user["state"] != "invited":
            raise IamError("NOT_INVITED", "That account is not waiting for an invitation", 409)
        self._require(actor, "iam.users.invite")
        with self.store.transaction():
            token = self._issue(INVITATION, user, issuer=actor.id, hours=self.setting("invitation.hours"), payload={"resent": True})
            self._audit(actor, "user.invitation_resent", target_type="user", target_id=user_id, target_label=user["display_name"])
        return {"token": token, "link": self.link(INVITATION, token), "expires_at": self._open_token(user_id, INVITATION)["expires_at"]}

    def preview(self, secret: str, purpose: str) -> dict:
        """What a link is for, without using it up: the landing page shows it before the person commits."""
        row = self._token_row(secret, purpose)
        user = self.user(row["user_id"]) if row["user_id"] else None
        payload = json.loads(row["payload"] or "{}")
        space = self.space(payload["space_id"]) if payload.get("space_id") else None
        role = self.policy.role(payload["role_id"]) if payload.get("role_id") else None
        return {
            "purpose": purpose,
            "email": user["email"] if user else row["email"],
            "display_name": user["display_name"] if user else "",
            "expires_at": row["expires_at"],
            "space": {"id": space["id"], "name": space["name"]} if space else None,
            "role": {"id": role["id"], "name": role["name"]} if role else None,
            "message": payload.get("message", ""),
            "bootstrap": bool(payload.get("bootstrap")),
        }

    def accept_invitation(self, secret: str, password: str, display_name: str | None = None) -> dict:
        with self.store.transaction():
            row = self._consume(secret, INVITATION)
            user = self.user(row["user_id"])
            if user is None or user["state"] != "invited":
                raise IamError("TOKEN_INVALID", "That invitation is no longer valid", 410)
            if display_name is not None and display_name.strip():
                self.store.update("users", {"id": user["id"]}, {"display_name": " ".join(display_name.split())[:80]})
                user = self.user(user["id"])
            self._set_password(user["id"], password, login=user["login"], display_name=user["display_name"])
            self._activate(user["id"])
            self.audit.record(
                action="user.activated", actor_id=user["id"], target_type="user", target_id=user["id"], target_label=user["display_name"]
            )
        return self.user(user["id"])  # type: ignore[return-value]

    # -- pictures (IAM F10) ----------------------------------------------------------------------------------------
    def _may_change(self, actor: Actor, user_id: str) -> None:
        if actor.id == user_id:
            self._require(actor, "account.update_self", owner_id=user_id)
        else:
            self._require(actor, "iam.users.update")

    def picture(self, user_id: str) -> dict | None:
        """A person's picture: ``image`` (JPEG bytes), ``content_type`` and ``updated_at``; None when they have none."""
        return self.store.one("SELECT image, content_type, updated_at FROM user_pictures WHERE user_id = ?", (user_id,))

    def picture_stamp(self, user_id: str) -> str | None:
        row = self.store.one("SELECT updated_at FROM user_pictures WHERE user_id = ?", (user_id,))
        return row["updated_at"] if row else None

    def set_picture(self, actor: Actor, user_id: str, data: bytes) -> dict:
        """Keep a person's picture: their own (account.update_self) or anyone's (iam.users.update). Whatever was sent is
        decoded and saved again as a square JPEG, so nothing but the picture is kept (no location or camera details)."""
        user = self._existing(user_id)
        self._may_change(actor, user_id)
        image = square_picture(data)
        with self.store.transaction():
            stamp = self.store.stamp()
            self.store.run(
                "INSERT INTO user_pictures (user_id, image, content_type, updated_at) VALUES (?, ?, 'image/jpeg', ?) "
                "ON CONFLICT(user_id) DO UPDATE SET image = excluded.image, content_type = excluded.content_type, "
                "updated_at = excluded.updated_at",
                (user_id, image, stamp),
            )
            self._audit(actor, "user.picture_changed", target_type="user", target_id=user_id, target_label=user["display_name"],
                        detail={"bytes": len(image)})
        return user

    def remove_picture(self, actor: Actor, user_id: str) -> dict:
        user = self._existing(user_id)
        self._may_change(actor, user_id)
        with self.store.transaction():
            if self.store.run("DELETE FROM user_pictures WHERE user_id = ?", (user_id,)).rowcount:
                self._audit(actor, "user.picture_removed", target_type="user", target_id=user_id, target_label=user["display_name"])
        return user

    def update_user(
        self, actor: Actor, user_id: str, *, display_name: str | None = None, email: str | None = None, note: str | None = None
    ) -> dict:
        user = self._existing(user_id)
        if actor.id == user_id and email is None and note is None:
            self._require(actor, "account.update_self", owner_id=user_id)
        else:
            self._require(actor, "iam.users.update")
        changes: dict = {}
        if display_name is not None:
            changes["display_name"] = " ".join(display_name.split())[:80] or user["display_name"]
        if email is not None and email.strip() != user["email"]:
            email = email.strip()
            if not _EMAIL.match(email):
                raise IamError("INVALID_EMAIL", "Enter a valid email address")
            other = self.user_by_login(email)
            if other is not None and other["id"] != user_id:
                raise IamError("EXISTS", "Another account uses that email", 409)
            changes.update({"email": email, "login": email, "login_canonical": canonical(email)})
        if note is not None:
            changes["note"] = note[:500]
        if not changes:
            return user
        with self.store.transaction():
            changes["updated_at"] = self.store.stamp()
            self.store.update("users", {"id": user_id}, changes)
            self._audit(
                actor,
                "user.updated",
                target_type="user",
                target_id=user_id,
                target_label=user["display_name"],
                before={k: user[k] for k in changes if k in user},
                after=changes,
            )
        return self.user(user_id)  # type: ignore[return-value]

    def suspend(self, actor: Actor, user_id: str, reason: str = "") -> dict:
        user = self._existing(user_id)
        self._require(actor, "iam.users.suspend")
        if user["state"] != "active":
            raise IamError("NOT_ACTIVE", "Only an active account can be suspended", 409)
        with self.store.transaction():
            self._protect_last_administrator(user_id)
            self.store.update("users", {"id": user_id}, {"state": "suspended", "updated_at": self.store.stamp()})
            self._revoke_sessions(user_id, "account suspended")
            self._revoke_tokens(user_id)
            self.store.bump_policy_version()
            self._audit(actor, "user.suspended", target_type="user", target_id=user_id, target_label=user["display_name"], reason=reason)
        return self.user(user_id)  # type: ignore[return-value]

    def reactivate(self, actor: Actor, user_id: str, reason: str = "") -> dict:
        user = self._existing(user_id)
        self._require(actor, "iam.users.reactivate")
        if user["state"] != "suspended":
            raise IamError("NOT_SUSPENDED", "Only a suspended account can be reactivated", 409)
        with self.store.transaction():
            self.store.update("users", {"id": user_id}, {"state": "active", "updated_at": self.store.stamp()})
            self.store.bump_policy_version()
            self._audit(actor, "user.reactivated", target_type="user", target_id=user_id, target_label=user["display_name"], reason=reason)
        return self.user(user_id)  # type: ignore[return-value]

    def deactivate(self, actor: Actor, user_id: str, reason: str = "") -> dict:
        """Offboarding: access, invitations and sessions go; the account and its attribution stay."""
        user = self._existing(user_id)
        self._require(actor, "iam.users.deactivate")
        if actor.id == user_id:
            raise IamError("SELF_CHANGE", "You cannot deactivate your own account", 409)
        if user["state"] == "deactivated":
            raise IamError("ALREADY", "The account is already deactivated", 409)
        with self.store.transaction():
            self._protect_last_administrator(user_id)
            now = self.store.stamp()
            self.store.update("users", {"id": user_id}, {"state": "deactivated", "deactivated_at": now, "updated_at": now})
            self._revoke_sessions(user_id, "account deactivated")
            self._revoke_tokens(user_id)
            self.store.run(
                "UPDATE role_bindings SET revoked_at = ?, revoked_by = ?, revoked_reason = 'account deactivated' "
                "WHERE subject_type = 'user' AND subject_id = ? AND revoked_at IS NULL",
                (now, actor.id, user_id),
            )
            self.store.run(
                "UPDATE memberships SET status = 'revoked', revoked_at = ?, revoked_by = ? WHERE user_id = ? AND status = 'active'",
                (now, actor.id, user_id),
            )
            self.store.run("DELETE FROM group_members WHERE user_id = ?", (user_id,))
            self.store.bump_policy_version()
            self._audit(actor, "user.deactivated", target_type="user", target_id=user_id, target_label=user["display_name"], reason=reason)
        return self.user(user_id)  # type: ignore[return-value]

    def initiate_recovery(self, actor: Actor, user_id: str, reason: str = "") -> dict:
        """An administrator starts a reset: a 30-minute, one-use link, shown once. Never a password."""
        user = self._existing(user_id)
        self._require(actor, "iam.users.recovery.initiate")
        if user["state"] != "active":
            raise IamError("NOT_ACTIVE", "Recovery is for active accounts; an invited one gets its invitation resent", 409)
        if self._limited(f"recovery:{user_id}", self.setting("throttle.recovery_per_hour"), 60):
            raise IamError("RATE_LIMITED", "Too many recovery links for that account this hour; try later", 429)
        with self.store.transaction():
            token = self._issue(RESET, user, issuer=actor.id, minutes=self.setting("reset.minutes"), payload={"reason": reason[:200]})
            self._audit(
                actor,
                "recovery.initiated",
                target_type="user",
                target_id=user_id,
                target_label=user["display_name"],
                reason=reason,
                detail={"link_shown_once": True},
            )
        return {"token": token, "link": self.link(RESET, token), "expires_at": self._open_token(user_id, RESET)["expires_at"]}

    def forgot(self, login: str) -> None:
        """The same answer whether or not the account exists. Without a configured mail channel nothing is sent; an
        administrator hands over a recovery link instead."""
        user = self.user_by_login(login)
        self.audit.record(
            action="password.forgot", outcome="noted", actor_type="anonymous", target_type="user", target_id=user["id"] if user else None
        )

    def reset_password(self, secret: str, password: str) -> dict:
        with self.store.transaction():
            row = self._consume(secret, RESET)
            user = self.user(row["user_id"])
            if user is None or user["state"] != "active":
                raise IamError("TOKEN_INVALID", "That link is no longer valid", 410)
            self._set_password(user["id"], password, login=user["login"], display_name=user["display_name"])
            self._new_epoch(user["id"], "password reset")
            self.audit.record(action="password.reset", actor_id=user["id"], target_type="user", target_id=user["id"])
        return self.user(user["id"])  # type: ignore[return-value]

    # -- passwords and sessions --------------------------------------------------------------------------------------
    def _set_password(self, user_id: str, password: str, *, login: str, display_name: str, enforce_policy: bool = True) -> None:
        problems = passwords.problems(password, login=login, display_name=display_name) if enforce_policy else []
        if problems:
            raise IamError("WEAK_PASSWORD", " ".join(problems), 422)
        now = self.store.stamp()
        self.store.run("UPDATE credentials SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL", (now, user_id))
        self.store.insert(
            "credentials",
            {
                "id": self.store.new_id("cred"),
                "user_id": user_id,
                "type": "password",
                "hash": passwords.hash_password(password),
                "params": json.dumps(passwords.current_params()),
                "changed_at": now,
            },
        )

    def _credential(self, user_id: str) -> dict | None:
        return self.store.one(
            "SELECT * FROM credentials WHERE user_id = ? AND type = 'password' AND revoked_at IS NULL ORDER BY changed_at DESC LIMIT 1",
            (user_id,),
        )

    def _new_epoch(self, user_id: str, reason: str) -> None:
        self.store.run(
            "UPDATE users SET credential_epoch = credential_epoch + 1, updated_at = ? WHERE id = ?", (self.store.stamp(), user_id)
        )
        self._revoke_sessions(user_id, reason)
        self._revoke_tokens(user_id, purposes=(RESET, TICKET))

    def login(self, login: str, password: str, *, address: str = "", device: str = "") -> tuple[dict | None, dict]:
        """A session, or why not. Failures are counted per account and per network address; the answer for an
        unknown account takes as long as for a known one."""
        canon = canonical(login)
        keys = [("account", canon, self.setting("throttle.account_attempts"), self.setting("throttle.account_window_minutes"))]
        if address:
            keys.append(("network", address, self.setting("throttle.network_attempts"), self.setting("throttle.network_window_minutes")))
        wait = max((self._blocked_for(f"{kind}:{who}") for kind, who, _, _ in keys), default=0)
        if wait:
            self.audit.record(action="sign_in", outcome="refused", reason="RATE_LIMITED", actor_type="anonymous", address=address)
            return None, {"code": "RATE_LIMITED", "retry_after": wait}
        user = self.user_by_login(login) if canon else None
        credential = self._credential(user["id"]) if user else None
        ok = rehash = False
        if credential is not None:
            ok, rehash = passwords.verify(credential["hash"], password or "")
        else:
            passwords.dummy_verify(password or "")
        if not ok or user is None or user["state"] != "active" or user["kind"] != "human":
            for kind, who, attempts, window in keys:
                self._count_failure(f"{kind}:{who}", attempts, window)
            self.audit.record(
                action="sign_in",
                outcome="refused",
                reason="INVALID_CREDENTIALS",
                actor_type="anonymous",
                target_type="user",
                target_id=user["id"] if user else None,
                address=address,
            )
            return None, {"code": "INVALID_CREDENTIALS"}
        with self.store.transaction():
            for kind, who, _, _ in keys:
                self.store.run("DELETE FROM rate_limits WHERE key = ?", (f"{kind}:{who}",))
            if rehash:
                self.store.update(
                    "credentials",
                    {"id": credential["id"]},
                    {"hash": passwords.hash_password(password), "params": json.dumps(passwords.current_params())},
                )
            session, secret = self._new_session(user, address, device)
            self.store.update("users", {"id": user["id"]}, {"last_sign_in_at": self.store.stamp()})
            self.audit.record(action="sign_in", outcome="success", actor_id=user["id"], session_ref=session["id"], address=address)
        return {**session, "secret": secret}, {"code": "OK"}

    def _privileged(self, user_id: str) -> bool:
        now = self.store.stamp()
        return any(
            self.policy.role(b["role_id"])
            and self.policy.role(b["role_id"])["boundary"] == "platform"
            and not self.policy.role(b["role_id"])["system"]
            for b in self.policy.active_bindings([("user", user_id)], now)
        )

    def _new_session(self, user: dict, address: str, device: str) -> tuple[dict, str]:
        privileged = self._privileged(user["id"])
        hours = self.setting("session.privileged_absolute_hours" if privileged else "session.absolute_hours")
        secret = new_secret()
        now = self.store.stamp()
        row = {
            "id": self.store.new_id("ses"),
            "digest": digest(secret),
            "user_id": user["id"],
            "credential_epoch": user["credential_epoch"],
            "csrf": secrets.token_hex(16),
            "privileged": int(privileged),
            "created_at": now,
            "authenticated_at": now,
            "last_seen_at": now,
            "absolute_expires_at": self.store.later(hours=hours),
            "device": (device or "")[:120],
            "address": (address or "")[:64],
        }
        self.store.insert("sessions", row)
        return row, secret

    def idle_minutes(self, session: dict) -> int:
        return self.setting("session.privileged_idle_minutes" if session["privileged"] else "session.idle_minutes")

    def resolve(self, secret: str | None, *, touch: bool = True) -> tuple[dict, dict] | None:
        """The person behind a session secret, if the session is alive: not revoked, within its absolute life and
        its idle window, and issued for the person's current credentials."""
        if not secret:
            return None
        session = self.store.one("SELECT * FROM sessions WHERE digest = ?", (digest(secret),))
        if session is None or session["revoked_at"]:
            return None
        return self._check_session(session, touch=touch)

    def _check_session(self, session: dict, *, touch: bool) -> tuple[dict, dict] | None:
        now = self.store.now()
        if now >= parse(session["absolute_expires_at"]):
            self._revoke_session(session["id"], "expired")
            return None
        if now >= parse(session["last_seen_at"]) + timedelta(minutes=self.idle_minutes(session)):
            self._revoke_session(session["id"], "idle")
            return None
        user = self.user(session["user_id"])
        if user is None or user["state"] != "active" or user["credential_epoch"] != session["credential_epoch"]:
            self._revoke_session(session["id"], "credentials changed" if user and user["state"] == "active" else "account not active")
            return None
        if touch and now - parse(session["last_seen_at"]) > timedelta(seconds=60):
            self.store.update("sessions", {"id": session["id"]}, {"last_seen_at": self.store.stamp(now)})
            session = {**session, "last_seen_at": self.store.stamp(now)}
        return user, session

    def session_by_id(self, session_id: str) -> tuple[dict, dict] | None:
        session = self.store.one("SELECT * FROM sessions WHERE id = ?", (session_id,))
        if session is None or session["revoked_at"]:
            return None
        return self._check_session(session, touch=False)

    def _revoke_session(self, session_id: str, reason: str) -> None:
        self.store.run(
            "UPDATE sessions SET revoked_at = ?, revoked_reason = ? WHERE id = ? AND revoked_at IS NULL",
            (self.store.stamp(), reason, session_id),
        )

    def _revoke_sessions(self, user_id: str, reason: str, *, except_id: str | None = None) -> int:
        return self.store.run(
            "UPDATE sessions SET revoked_at = ?, revoked_reason = ? WHERE user_id = ? AND revoked_at IS NULL AND id != ?",
            (self.store.stamp(), reason, user_id, except_id or ""),
        ).rowcount

    def logout(self, session: dict, reason: str = "signed out") -> None:
        with self.store.transaction():
            self._revoke_session(session["id"], reason)
            self._revoke_tokens(session["user_id"], purposes=(TICKET,))
            self.audit.record(action="sign_out", actor_id=session["user_id"], session_ref=session["id"], reason=reason)

    def logout_all(self, actor: Actor, user_id: str) -> int:
        if actor.id == user_id:
            self._require(actor, "account.sessions.revoke_self", owner_id=user_id)
        else:
            self._require(actor, "iam.sessions.revoke")
        with self.store.transaction():
            count = self._revoke_sessions(user_id, "signed out everywhere")
            self._audit(actor, "sessions.revoked_all", target_type="user", target_id=user_id, detail={"sessions": count})
        return count

    def sessions_of(self, actor: Actor, user_id: str, current_id: str | None = None) -> list[dict]:
        if actor.id == user_id:
            self._require(actor, "account.sessions.read_self", owner_id=user_id)
        else:
            self._require(actor, "iam.sessions.read")
        return [
            self.session_view(s, current_id)
            for s in self.store.all(
                "SELECT * FROM sessions WHERE user_id = ? AND revoked_at IS NULL AND absolute_expires_at > ? ORDER BY created_at DESC",
                (user_id, self.store.stamp()),
            )
        ]

    def all_sessions(self, actor: Actor, current_id: str | None = None) -> list[dict]:
        self._require(actor, "iam.sessions.read")
        rows = self.store.all(
            "SELECT s.*, u.display_name, u.login FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.revoked_at IS NULL AND s.absolute_expires_at > ? ORDER BY s.last_seen_at DESC",
            (self.store.stamp(),),
        )
        return [{**self.session_view(s, current_id), "display_name": s["display_name"], "login": s["login"]} for s in rows]

    def session_view(self, session: dict, current_id: str | None) -> dict:
        idle_until = parse(session["last_seen_at"]) + timedelta(minutes=self.idle_minutes(session))
        return {
            "id": session["id"],
            "user_id": session["user_id"],
            "created_at": session["created_at"],
            "authenticated_at": session["authenticated_at"],
            "last_seen_at": session["last_seen_at"],
            "absolute_expires_at": session["absolute_expires_at"],
            "idle_expires_at": self.store.stamp(idle_until),
            "privileged": bool(session["privileged"]),
            "device": session["device"],
            "address": session["address"],
            "current": session["id"] == current_id,
        }

    def revoke_session(self, actor: Actor, session_id: str, reason: str = "") -> None:
        session = self.store.one("SELECT * FROM sessions WHERE id = ?", (session_id,))
        if session is None:
            raise IamError("NOT_FOUND", "No such session", 404)
        if actor.id == session["user_id"]:
            self._require(actor, "account.sessions.revoke_self", owner_id=session["user_id"])
        else:
            self._require(actor, "iam.sessions.revoke")
        with self.store.transaction():
            self._revoke_session(session_id, reason or "revoked")
            self._audit(
                actor, "session.revoked", target_type="session", target_id=session_id, reason=reason, detail={"user_id": session["user_id"]}
            )

    def reauthenticate(self, session: dict, password: str) -> bool:
        user = self.user(session["user_id"])
        credential = self._credential(user["id"]) if user else None
        key = f"account:{user['login_canonical']}" if user else "account:"
        if self._blocked_for(key):
            raise IamError("RATE_LIMITED", "Too many attempts; wait a moment", 429)
        ok = credential is not None and passwords.verify(credential["hash"], password or "")[0]
        if not ok:
            self._count_failure(key, self.setting("throttle.account_attempts"), self.setting("throttle.account_window_minutes"))
            self.audit.record(action="reauthenticate", outcome="refused", actor_id=session["user_id"], session_ref=session["id"])
            return False
        with self.store.transaction():
            self.store.update("sessions", {"id": session["id"]}, {"authenticated_at": self.store.stamp()})
            self.audit.record(action="reauthenticate", outcome="success", actor_id=session["user_id"], session_ref=session["id"])
        return True

    def is_fresh(self, session: dict) -> bool:
        return self.store.now() < parse(session["authenticated_at"]) + timedelta(minutes=self.setting("reauth.fresh_minutes"))

    def change_password(self, session: dict, current: str, new: str, *, address: str = "", device: str = "") -> tuple[dict, str]:
        """Current password required; other sessions end, and this client continues on a fresh session."""
        user = self.user(session["user_id"])
        credential = self._credential(user["id"]) if user else None
        if user is None or credential is None or not passwords.verify(credential["hash"], current or "")[0]:
            self.audit.record(action="password.change", outcome="refused", actor_id=session["user_id"], session_ref=session["id"])
            raise IamError("INVALID_CREDENTIALS", "The current password is not right", 403)
        with self.store.transaction():
            self._set_password(user["id"], new, login=user["login"], display_name=user["display_name"])
            self._new_epoch(user["id"], "password changed")
            user = self.user(user["id"])
            fresh, secret = self._new_session(user, address, device)
            self.audit.record(action="password.change", outcome="success", actor_id=user["id"], session_ref=fresh["id"])
        return fresh, secret

    # -- throttling ------------------------------------------------------------------------------------------------
    def _blocked_for(self, key: str) -> int:
        row = self.store.one("SELECT blocked_until FROM rate_limits WHERE key = ?", (key,))
        if row is None or not row["blocked_until"]:
            return 0
        remaining = (parse(row["blocked_until"]) - self.store.now()).total_seconds()
        return int(remaining) + 1 if remaining > 0 else 0

    def _count_failure(self, key: str, attempts: int, window_minutes: int) -> None:
        with self.store.transaction():
            now = self.store.now()
            row = self.store.one("SELECT * FROM rate_limits WHERE key = ?", (key,))
            if row is None or now >= parse(row["window_started_at"]) + timedelta(minutes=window_minutes):
                count, started = 1, self.store.stamp(now)
            else:
                count, started = row["count"] + 1, row["window_started_at"]
            blocked = None
            if count >= attempts:
                delay = min(self.setting("throttle.cap_minutes") * 60, 30 * 2 ** (count - attempts))
                blocked = self.store.stamp(now + timedelta(seconds=delay))
            self.store.run(
                "INSERT INTO rate_limits (key, window_started_at, count, blocked_until) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET window_started_at = excluded.window_started_at, count = excluded.count, "
                "blocked_until = excluded.blocked_until",
                (key, started, count, blocked),
            )

    def _limited(self, key: str, per_window: int, window_minutes: int) -> bool:
        """A plain counter for actions that are simply limited per window (recovery links)."""
        with self.store.transaction():
            now = self.store.now()
            row = self.store.one("SELECT * FROM rate_limits WHERE key = ?", (key,))
            if row is None or now >= parse(row["window_started_at"]) + timedelta(minutes=window_minutes):
                self.store.run(
                    "INSERT INTO rate_limits (key, window_started_at, count) VALUES (?, ?, 1) ON CONFLICT(key) DO UPDATE "
                    "SET window_started_at = excluded.window_started_at, count = 1, blocked_until = NULL",
                    (key, self.store.stamp(now)),
                )
                return False
            if row["count"] >= per_window:
                return True
            self.store.run("UPDATE rate_limits SET count = count + 1 WHERE key = ?", (key,))
            return False

    def attack_summary(self, actor: Actor) -> list[dict]:
        self._require(actor, "audit.read")
        return self.store.all(
            "SELECT key, window_started_at, count, blocked_until FROM rate_limits WHERE count >= 3 ORDER BY count DESC LIMIT 50"
        )

    # -- lifecycle tokens ----------------------------------------------------------------------------------------------
    def _issue(
        self,
        purpose: str,
        user: dict,
        *,
        issuer: str | None,
        payload: dict | None = None,
        hours: int = 0,
        minutes: int = 0,
        seconds: int = 0,
    ) -> str:
        secret = new_secret()
        now = self.store.stamp()
        self.store.run(
            "UPDATE lifecycle_tokens SET revoked_at = ? WHERE user_id = ? AND purpose = ? AND consumed_at IS NULL AND revoked_at IS NULL",
            (now, user["id"], purpose),
        )
        self.store.insert(
            "lifecycle_tokens",
            {
                "id": self.store.new_id("tok"),
                "digest": digest(secret),
                "purpose": purpose,
                "user_id": user["id"],
                "email": user["email"],
                "issuer_id": issuer,
                "payload": json.dumps(payload or {}),
                "issued_at": now,
                "expires_at": self.store.later(hours=hours, minutes=minutes, seconds=seconds),
            },
        )
        return secret

    def _token_row(self, secret: str, purpose: str) -> dict:
        row = self.store.one("SELECT * FROM lifecycle_tokens WHERE digest = ?", (digest(secret or ""),))
        if row is None or row["purpose"] != purpose or row["consumed_at"] or row["revoked_at"] or row["expires_at"] <= self.store.stamp():
            raise IamError("TOKEN_INVALID", "That link is not valid any more", 410)
        return row

    def _consume(self, secret: str, purpose: str) -> dict:
        """Single use, even under concurrent submissions: the update that marks it used succeeds once."""
        with self.store.transaction():
            row = self._token_row(secret, purpose)
            changed = self.store.run(
                "UPDATE lifecycle_tokens SET consumed_at = ? WHERE id = ? AND consumed_at IS NULL", (self.store.stamp(), row["id"])
            ).rowcount
            if changed != 1:
                raise IamError("TOKEN_INVALID", "That link has already been used", 410)
            return row

    def _revoke_tokens(self, user_id: str, purposes: tuple[str, ...] = (INVITATION, RESET, TICKET)) -> None:
        marks = ",".join("?" for _ in purposes)
        self.store.run(
            f"UPDATE lifecycle_tokens SET revoked_at = ? WHERE user_id = ? AND purpose IN ({marks}) "
            "AND consumed_at IS NULL AND revoked_at IS NULL",
            (self.store.stamp(), user_id, *purposes),
        )

    def link(self, purpose: str, token: str) -> str:
        return f"{self.origin}/#{purpose}:{token}"

    def issue_ticket(self, session: dict, conversation_id: str, space_id: str | None) -> str:
        """A one-use ticket for the voice socket: the browser cannot send its cookie's proof in a socket hello."""
        user = self.user(session["user_id"])
        with self.store.transaction():
            secret = self._issue(
                TICKET,
                user,
                issuer=session["user_id"],
                seconds=self.setting("ws_ticket.seconds"),
                payload={"session_id": session["id"], "conversation_id": conversation_id, "space_id": space_id},
            )
        return secret

    def consume_ticket(self, secret: str, conversation_id: str) -> tuple[dict, dict] | None:
        try:
            row = self._consume(secret, TICKET)
        except IamError:
            return None
        payload = json.loads(row["payload"] or "{}")
        if payload.get("conversation_id") != conversation_id:
            return None
        return self.session_by_id(payload.get("session_id", ""))

    # -- roles -------------------------------------------------------------------------------------------------------
    def roles(self, include_system: bool = False) -> list[dict]:
        out = [r.to_dict() for r in seeds.BUILTIN.values() if include_system or not r.system]
        for row in self.store.all("SELECT * FROM roles WHERE deleted_at IS NULL ORDER BY created_at"):
            out.append(self.policy.role(row["id"]))
        return out

    def create_role(
        self, actor: Actor, *, name: str, boundary: str, permissions: list[str], description: str = "", based_on: str | None = None
    ) -> dict:
        self._require(actor, "iam.roles.create")
        name = " ".join((name or "").split())[:60]
        if not name:
            raise IamError("INVALID", "Name the role")
        if boundary not in ("platform", "space"):
            raise IamError("INVALID", "A role is bound at the platform or in a space")
        base = self.policy.role(based_on) if based_on else None
        if based_on and base is None:
            raise IamError("NOT_FOUND", "No such role to start from", 404)
        if base and base.get("protected") and boundary == "space":
            raise IamError("PROTECTED_ROLE", "A protected platform role cannot become a space role", 409)
        keys = self._validated_permissions(permissions, boundary)
        role_id = "custom_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:24] + "_" + secrets.token_hex(3)
        now = self.store.stamp()
        with self.store.transaction():
            self.store.insert(
                "roles",
                {
                    "id": role_id,
                    "name": name,
                    "boundary": boundary,
                    "description": description[:500],
                    "permissions": json.dumps(keys),
                    "grantable": "[]",
                    "version": 1,
                    "based_on": based_on,
                    "created_by": actor.id,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            self._audit(
                actor,
                "role.created",
                target_type="role",
                target_id=role_id,
                target_label=name,
                after={"boundary": boundary, "permissions": keys},
            )
        return self.policy.role(role_id)  # type: ignore[return-value]

    def update_role(
        self, actor: Actor, role_id: str, *, name: str | None = None, description: str | None = None, permissions: list[str] | None = None
    ) -> dict:
        self._require(actor, "iam.roles.update")
        role = self.policy.role(role_id)
        if role is None:
            raise IamError("NOT_FOUND", "No such role", 404)
        if role["builtin"]:
            raise IamError("BUILTIN_ROLE", "A built-in role is not edited; make a custom role from it", 409)
        changes: dict = {}
        if name is not None:
            changes["name"] = " ".join(name.split())[:60] or role["name"]
        if description is not None:
            changes["description"] = description[:500]
        if permissions is not None:
            held = frozenset(json.loads(role["permissions"]) if isinstance(role.get("permissions"), str) else role.get("permissions") or [])
            changes["permissions"] = json.dumps(self._validated_permissions(permissions, role["boundary"], held))
        with self.store.transaction():
            changes.update({"version": role["version"] + 1, "updated_at": self.store.stamp()})
            self.store.update("roles", {"id": role_id}, changes)
            self.store.bump_policy_version()
            self._audit(
                actor,
                "role.updated",
                target_type="role",
                target_id=role_id,
                target_label=role["name"],
                before={"permissions": role["permissions"], "name": role["name"]},
                after={
                    "permissions": json.loads(changes["permissions"]) if "permissions" in changes else role["permissions"],
                    "name": changes.get("name", role["name"]),
                    "version": changes["version"],
                },
            )
        return self.policy.role(role_id)  # type: ignore[return-value]

    def delete_role(self, actor: Actor, role_id: str) -> None:
        self._require(actor, "iam.roles.delete")
        role = self.policy.role(role_id)
        if role is None:
            raise IamError("NOT_FOUND", "No such role", 404)
        if role["builtin"]:
            raise IamError("BUILTIN_ROLE", "A built-in role cannot be deleted", 409)
        if self.store.one("SELECT 1 FROM role_bindings WHERE role_id = ? AND revoked_at IS NULL LIMIT 1", (role_id,)):
            raise IamError("IN_USE", "The role is still given to someone; revoke those first", 409)
        with self.store.transaction():
            self.store.update("roles", {"id": role_id}, {"deleted_at": self.store.stamp()})
            self._audit(actor, "role.deleted", target_type="role", target_id=role_id, target_label=role["name"])

    def _validated_permissions(self, permissions: list[str], boundary: str, held: frozenset[str] = frozenset()) -> list[str]:
        keys: list[str] = []
        for key in permissions or []:
            permission = catalogue.get(key)
            if permission is None:
                raise IamError("UNKNOWN_PERMISSION", f"Not a registered permission: {key}")
            if permission.reserved and key not in held:
                raise IamError("RESERVED_PERMISSION", f"{key} guards nothing yet ({permission.reserved})")
            if boundary == "space" and not permission.in_spaces:
                raise IamError("SCOPE_INVALID", f"{key} is a platform permission and cannot be in a space role")
            if boundary == "platform" and not permission.at_platform and permission.scopes != (catalogue.OWN,):
                raise IamError("SCOPE_INVALID", f"{key} is a space permission and cannot be in a platform role")
            if key not in keys:
                keys.append(key)
        if not keys:
            raise IamError("INVALID", "A role needs at least one permission")
        return keys

    # -- bindings and memberships -----------------------------------------------------------------------------------
    def bindings(
        self,
        actor: Actor,
        *,
        user_id: str | None = None,
        space_id: str | None = None,
        role_id: str | None = None,
        include_system: bool = False,
    ) -> list[dict]:
        if space_id:
            self._require(actor, "spaces.members.read", space_id, alternative=("iam.users.read", None))
        else:
            self._require(actor, "iam.users.read")
        clauses, params = ["revoked_at IS NULL"], []
        if user_id:
            clauses.append("subject_type = 'user' AND subject_id = ?")
            params.append(user_id)
        if space_id:
            clauses.append("scope_type != 'platform' AND space_id = ?")
            params.append(space_id)
        if role_id:
            clauses.append("role_id = ?")
            params.append(role_id)
        rows = self.store.all(f"SELECT * FROM role_bindings WHERE {' AND '.join(clauses)} ORDER BY starts_at", params)
        return [self._binding_view(b) for b in rows if include_system or not b["system"]]

    def _binding_view(self, binding: dict) -> dict:
        role = self.policy.role(binding["role_id"]) or {"name": binding["role_id"], "boundary": "?"}
        subject = None
        if binding["subject_type"] == "user":
            user = self.user(binding["subject_id"])
            subject = {"display_name": user["display_name"], "login": user["login"], "state": user["state"]} if user else None
        else:
            group = self.store.one("SELECT name FROM groups WHERE id = ?", (binding["subject_id"],))
            subject = {"display_name": group["name"], "login": "", "state": "group"} if group else None
        space = self.space(binding["space_id"]) if binding["space_id"] else None
        return {
            **binding,
            "system": bool(binding["system"]),
            "role_name": role["name"],
            "role_boundary": role.get("boundary"),
            "subject": subject,
            "space_name": space["name"] if space else None,
        }

    def grant(
        self,
        actor: Actor,
        *,
        subject_id: str,
        role_id: str,
        scope_type: str,
        scope_id: str = "",
        subject_type: str = "user",
        days: int | None = None,
        reason: str = "",
        request_id: str | None = None,
    ) -> dict:
        """Give a role at a scope. The giver needs the assign permission there, the role must be within what they may
        give, they cannot raise their own authority, and a protected role needs a fresh password."""
        role = self.policy.role(role_id)
        if role is None or role.get("system"):
            raise IamError("NOT_FOUND", "No such role", 404)
        if scope_type == "platform":
            if role["boundary"] != "platform":
                raise IamError("SCOPE_INVALID", "A space role is given in a space")
            space_id = None
        elif scope_type in ("space", "collection", "resource"):
            if role["boundary"] != "space":
                raise IamError("SCOPE_INVALID", "A platform role is given at the platform")
            space_id = scope_id if scope_type == "space" else scope_id.split("/", 1)[0]
            if not self.space(space_id) or self.space(space_id)["status"] != "active":
                raise IamError("NOT_FOUND", "No such space", 404)
        else:
            raise IamError("SCOPE_INVALID", "Unknown scope")
        if subject_type == "user":
            subject = self._existing(subject_id)
            if subject["state"] == "deactivated":
                raise IamError("DEACTIVATED", "That account is deactivated", 409)
            if actor.id == subject_id:
                raise IamError("SELF_GRANT", "You cannot raise your own authority; another administrator must", 409)
        elif subject_type == "group":
            if self.store.one("SELECT 1 FROM groups WHERE id = ? AND deleted_at IS NULL", (subject_id,)) is None:
                raise IamError("NOT_FOUND", "No such group", 404)
        else:
            raise IamError("INVALID", "A role is given to a person or a group")
        self._assert_grantable(actor, role, space_id)
        if role.get("protected") and not actor.fresh:
            raise IamError("REAUTH_REQUIRED", "Giving this role needs your password again", 403)
        with self.store.transaction():
            binding = self._bind(
                subject_id,
                role_id,
                scope_type,
                scope_id,
                issuer=actor.id,
                reason=reason[:200],
                ends_at=self._ends(days),
                subject_type=subject_type,
                request_id=request_id,
            )
            self._audit(
                actor,
                "role.granted",
                target_type=subject_type,
                target_id=subject_id,
                space_id=space_id,
                reason=reason,
                after={"role_id": role_id, "scope_type": scope_type, "scope_id": scope_id, "ends_at": binding["ends_at"]},
            )
        return self._binding_view(binding)

    def _bind(
        self,
        subject_id: str,
        role_id: str,
        scope_type: str,
        scope_id: str,
        *,
        issuer: str | None,
        reason: str,
        ends_at: str | None = None,
        system: bool = False,
        subject_type: str = "user",
        request_id: str | None = None,
    ) -> dict:
        """The binding row (existing if the same grant is already active), with the membership a space grant implies."""
        space_id = None if scope_type == "platform" else scope_id.split("/", 1)[0]
        existing = self.store.one(
            "SELECT * FROM role_bindings WHERE subject_type = ? AND subject_id = ? AND role_id = ? AND scope_type = ? AND scope_id = ? "
            "AND revoked_at IS NULL",
            (subject_type, subject_id, role_id, scope_type, scope_id),
        )
        if existing is not None:
            if ends_at != existing["ends_at"] and not existing["system"]:
                self.store.update("role_bindings", {"id": existing["id"]}, {"ends_at": ends_at})
                existing["ends_at"] = ends_at
            if space_id:
                self._ensure_membership(subject_id, subject_type, space_id, ends_at)
            return existing
        role = self.policy.role(role_id) or {"version": 1}
        row = {
            "id": self.store.new_id("bnd"),
            "subject_type": subject_type,
            "subject_id": subject_id,
            "role_id": role_id,
            "role_version": role["version"],
            "scope_type": scope_type,
            "scope_id": scope_id,
            "space_id": space_id,
            "starts_at": self.store.stamp(),
            "ends_at": ends_at,
            "issuer_id": issuer,
            "reason": reason,
            "request_id": request_id,
            "system": int(system),
        }
        self.store.insert("role_bindings", row)
        if space_id:
            self._ensure_membership(subject_id, subject_type, space_id, ends_at)
        self.store.bump_policy_version()
        return row

    def _ensure_membership(self, subject_id: str, subject_type: str, space_id: str, ends_at: str | None) -> None:
        users = (
            [subject_id]
            if subject_type == "user"
            else [m["user_id"] for m in self.store.all("SELECT user_id FROM group_members WHERE group_id = ?", (subject_id,))]
        )
        for user_id in users:
            row = self.store.one("SELECT * FROM memberships WHERE user_id = ? AND space_id = ? AND status = 'active'", (user_id, space_id))
            if row is None:
                self.store.insert(
                    "memberships",
                    {
                        "id": self.store.new_id("mem"),
                        "user_id": user_id,
                        "space_id": space_id,
                        "status": "active",
                        "joined_at": self.store.stamp(),
                        "expires_at": ends_at,
                    },
                )
            elif row["expires_at"] and (ends_at is None or ends_at > row["expires_at"]):
                self.store.update("memberships", {"id": row["id"]}, {"expires_at": ends_at})

    def revoke_binding(self, actor: Actor, binding_id: str, reason: str = "") -> None:
        binding = self.store.one("SELECT * FROM role_bindings WHERE id = ? AND revoked_at IS NULL", (binding_id,))
        if binding is None:
            raise IamError("NOT_FOUND", "No such grant", 404)
        if binding["system"]:
            raise IamError("SYSTEM_BINDING", "That entitlement follows the account: suspend or deactivate the person instead", 409)
        role = self.policy.role(binding["role_id"]) or {
            "id": binding["role_id"],
            "name": binding["role_id"],
            "boundary": "space",
            "protected": False,
        }
        self._assert_grantable(actor, role, binding["space_id"])
        with self.store.transaction():
            self._protect_last(binding)
            now = self.store.stamp()
            self.store.update(
                "role_bindings", {"id": binding_id}, {"revoked_at": now, "revoked_by": actor.id, "revoked_reason": reason[:200]}
            )
            if (
                binding["space_id"]
                and binding["subject_type"] == "user"
                and not self.store.one(
                    "SELECT 1 FROM role_bindings WHERE subject_type = 'user' AND subject_id = ? AND space_id = ? AND revoked_at IS NULL",
                    (binding["subject_id"], binding["space_id"]),
                )
            ):
                self.store.run(
                    "UPDATE memberships SET status = 'revoked', revoked_at = ?, revoked_by = ? "
                    "WHERE user_id = ? AND space_id = ? AND status = 'active'",
                    (now, actor.id, binding["subject_id"], binding["space_id"]),
                )
            self.store.bump_policy_version()
            self._audit(
                actor,
                "role.revoked",
                target_type=binding["subject_type"],
                target_id=binding["subject_id"],
                space_id=binding["space_id"],
                reason=reason,
                before={"role_id": binding["role_id"], "scope_type": binding["scope_type"], "scope_id": binding["scope_id"]},
            )

    def _protect_last(self, binding: dict) -> None:
        if binding["role_id"] == "platform_administrator" and binding["scope_type"] == "platform":
            if len(self._platform_administrators()) <= 1:
                raise IamError("LAST_ADMINISTRATOR", "That is the last active platform administrator", 409)
        if binding["role_id"] == "space_owner" and binding["scope_type"] == "space":
            owners = self.store.all(
                "SELECT b.id FROM role_bindings b JOIN users u ON u.id = b.subject_id "
                "WHERE b.role_id = 'space_owner' AND b.scope_type = 'space' "
                "AND b.scope_id = ? AND b.revoked_at IS NULL AND b.subject_type = 'user' AND u.state = 'active'",
                (binding["scope_id"],),
            )
            if len(owners) <= 1:
                raise IamError("LAST_OWNER", "That is the last active owner of the space; appoint another first", 409)

    def _protect_last_administrator(self, user_id: str) -> None:
        admins = self._platform_administrators()
        if any(a["id"] == user_id for a in admins) and len(admins) <= 1:
            raise IamError("LAST_ADMINISTRATOR", "That is the last active platform administrator", 409)

    def members(self, actor: Actor, space_id: str) -> list[dict]:
        self._require(actor, "spaces.members.read", space_id, alternative=("iam.users.read", None))
        now = self.store.stamp()
        rows = self.store.all(
            "SELECT m.*, u.display_name, u.login, u.state, u.last_sign_in_at FROM memberships m JOIN users u ON u.id = m.user_id "
            "WHERE m.space_id = ? AND m.status = 'active' ORDER BY u.display_name",
            (space_id,),
        )
        for row in rows:
            row["roles"] = [r for r in self._role_summary(row["user_id"], now) if r["scope_id"] == space_id]
        return rows

    def remove_member(self, actor: Actor, space_id: str, user_id: str, reason: str = "") -> None:
        self._require(actor, "spaces.members.manage", space_id, alternative=("iam.roles.assign", None))
        bindings = self.store.all(
            "SELECT * FROM role_bindings WHERE subject_type = 'user' AND subject_id = ? AND space_id = ? AND revoked_at IS NULL",
            (user_id, space_id),
        )
        with self.store.transaction():
            for binding in bindings:
                if binding["system"]:
                    continue
                self._protect_last(binding)
                self.store.update(
                    "role_bindings",
                    {"id": binding["id"]},
                    {"revoked_at": self.store.stamp(), "revoked_by": actor.id, "revoked_reason": reason[:200]},
                )
            if not any(b["system"] for b in bindings):
                self.store.run(
                    "UPDATE memberships SET status = 'revoked', revoked_at = ?, revoked_by = ? "
                    "WHERE user_id = ? AND space_id = ? AND status = 'active'",
                    (self.store.stamp(), actor.id, user_id, space_id),
                )
            self.store.bump_policy_version()
            self._audit(actor, "member.removed", target_type="user", target_id=user_id, space_id=space_id, reason=reason)

    def _grantable_by(self, actor: Actor, space_id: str | None) -> set[str]:
        if actor.is_host:
            return set(seeds.BUILTIN) | {r["id"] for r in self.roles()}
        now = self.store.stamp()
        allowed: set[str] = set()
        bindings = self.policy.active_bindings(self.policy.subjects_of(actor.id, now), now)
        if self.can(actor.id, "iam.roles.assign"):
            for b in bindings:
                if b["scope_type"] == "platform":
                    allowed |= set((self.policy.role(b["role_id"]) or {}).get("grantable", []))
        if space_id and self.can(actor.id, "iam.roles.assign", space_id):
            for b in bindings:
                if b["scope_type"] == "space" and b["scope_id"] == space_id:
                    allowed |= set((self.policy.role(b["role_id"]) or {}).get("grantable", []))
        if "platform_administrator" in allowed:
            allowed |= {r["id"] for r in self.roles()}  # custom roles too
        elif "space_owner" in allowed or "identity_administrator" in allowed:
            allowed |= {r["id"] for r in self.roles() if not r["builtin"] and r["boundary"] == "space"}
        return allowed

    def grantable_roles(self, actor: Actor, space_id: str | None = None) -> list[dict]:
        allowed = self._grantable_by(actor, space_id)
        return [r for r in self.roles() if r["id"] in allowed]

    def _assert_grantable(self, actor: Actor, role: dict, space_id: str | None) -> None:
        if actor.is_host:
            return
        if role["id"] not in self._grantable_by(actor, space_id):
            raise IamError("ACCESS_DENIED", f"You cannot give the role {role['name']} here", 403)

    def _ends(self, days: int | None) -> str | None:
        if days is None:
            return None
        if not 1 <= int(days) <= 3650:
            raise IamError("INVALID", "Days must be from 1 to 3650")
        return self.store.later(days=int(days))

    # -- groups ------------------------------------------------------------------------------------------------------------
    def groups(self, actor: Actor, space_id: str | None = None) -> list[dict]:
        self._require(actor, "iam.groups.read", space_id) if space_id else self._require(actor, "iam.groups.read")
        rows = self.store.all(
            "SELECT * FROM groups WHERE deleted_at IS NULL " + ("AND space_id = ? " if space_id else "") + "ORDER BY name",
            (space_id,) if space_id else (),
        )
        for row in rows:
            row["members"] = self.store.all(
                "SELECT gm.user_id, gm.added_at, gm.expires_at, u.display_name, u.login, u.state FROM group_members gm "
                "JOIN users u ON u.id = gm.user_id WHERE gm.group_id = ? ORDER BY u.display_name",
                (row["id"],),
            )
            row["bindings"] = [
                self._binding_view(b)
                for b in self.store.all(
                    "SELECT * FROM role_bindings WHERE subject_type = 'group' AND subject_id = ? AND revoked_at IS NULL", (row["id"],)
                )
            ]
        return rows

    def create_group(self, actor: Actor, *, name: str, space_id: str | None = None, description: str = "") -> dict:
        self._require(actor, "iam.groups.create", space_id) if space_id else self._require(actor, "iam.groups.create")
        if space_id and not self.space(space_id):
            raise IamError("NOT_FOUND", "No such space", 404)
        name = " ".join((name or "").split())[:60]
        if not name:
            raise IamError("INVALID", "Name the group")
        row = {
            "id": self.store.new_id("grp"),
            "name": name,
            "boundary": "space" if space_id else "platform",
            "space_id": space_id,
            "description": description[:300],
            "created_by": actor.id,
            "created_at": self.store.stamp(),
        }
        with self.store.transaction():
            self.store.insert("groups", row)
            self._audit(actor, "group.created", target_type="group", target_id=row["id"], target_label=name, space_id=space_id)
        return {**row, "members": [], "bindings": []}

    def delete_group(self, actor: Actor, group_id: str) -> None:
        group = self._group(group_id)
        self._require(actor, "iam.groups.delete", group["space_id"]) if group["space_id"] else self._require(actor, "iam.groups.delete")
        with self.store.transaction():
            now = self.store.stamp()
            self.store.run(
                "UPDATE role_bindings SET revoked_at = ?, revoked_by = ?, revoked_reason = 'group deleted' "
                "WHERE subject_type = 'group' AND subject_id = ? AND revoked_at IS NULL",
                (now, actor.id, group_id),
            )
            self.store.run("DELETE FROM group_members WHERE group_id = ?", (group_id,))
            self.store.update("groups", {"id": group_id}, {"deleted_at": now})
            self.store.bump_policy_version()
            self._audit(
                actor, "group.deleted", target_type="group", target_id=group_id, target_label=group["name"], space_id=group["space_id"]
            )

    def add_group_member(self, actor: Actor, group_id: str, user_id: str) -> None:
        """Membership is checked for its resulting access: every role the group holds must be one the actor may give."""
        group = self._group(group_id)
        self._require(actor, "iam.groups.members.manage", group["space_id"]) if group["space_id"] else self._require(
            actor, "iam.groups.members.manage"
        )
        user = self._existing(user_id)
        if user["state"] == "deactivated":
            raise IamError("DEACTIVATED", "That account is deactivated", 409)
        if actor.id == user_id:
            raise IamError("SELF_GRANT", "You cannot add yourself to a group that carries roles", 409)
        bindings = self.store.all(
            "SELECT * FROM role_bindings WHERE subject_type = 'group' AND subject_id = ? AND revoked_at IS NULL", (group_id,)
        )
        for binding in bindings:
            role = self.policy.role(binding["role_id"])
            if role is not None:
                self._assert_grantable(actor, role, binding["space_id"])
        with self.store.transaction():
            self.store.run(
                "INSERT OR IGNORE INTO group_members (group_id, user_id, added_at, added_by) VALUES (?, ?, ?, ?)",
                (group_id, user_id, self.store.stamp(), actor.id),
            )
            for binding in bindings:
                if binding["space_id"]:
                    self._ensure_membership(user_id, "user", binding["space_id"], binding["ends_at"])
            self.store.bump_policy_version()
            self._audit(
                actor,
                "group.member_added",
                target_type="group",
                target_id=group_id,
                target_label=group["name"],
                space_id=group["space_id"],
                detail={"user_id": user_id},
            )

    def remove_group_member(self, actor: Actor, group_id: str, user_id: str) -> None:
        group = self._group(group_id)
        self._require(actor, "iam.groups.members.manage", group["space_id"]) if group["space_id"] else self._require(
            actor, "iam.groups.members.manage"
        )
        with self.store.transaction():
            self.store.run("DELETE FROM group_members WHERE group_id = ? AND user_id = ?", (group_id, user_id))
            self.store.bump_policy_version()
            self._audit(
                actor,
                "group.member_removed",
                target_type="group",
                target_id=group_id,
                target_label=group["name"],
                space_id=group["space_id"],
                detail={"user_id": user_id},
            )

    def _group(self, group_id: str) -> dict:
        group = self.store.one("SELECT * FROM groups WHERE id = ? AND deleted_at IS NULL", (group_id,))
        if group is None:
            raise IamError("NOT_FOUND", "No such group", 404)
        return group

    # -- denies ----------------------------------------------------------------------------------------------------------
    def denies(self, actor: Actor, space_id: str | None = None) -> list[dict]:
        self._require(actor, "iam.access.deny.manage", space_id) if space_id else self._require(actor, "iam.access.deny.manage")
        rows = self.store.all(
            "SELECT * FROM policy_denies WHERE revoked_at IS NULL " + ("AND scope_id = ? " if space_id else "") + "ORDER BY starts_at DESC",
            (space_id,) if space_id else (),
        )
        for row in rows:
            user = self.user(row["subject_id"]) if row["subject_type"] == "user" else None
            row["subject"] = {"display_name": user["display_name"], "login": user["login"]} if user else None
        return rows

    def deny(
        self,
        actor: Actor,
        *,
        subject_id: str,
        permission: str,
        scope_type: str,
        scope_id: str = "",
        reason: str = "",
        days: int | None = None,
        subject_type: str = "user",
    ) -> dict:
        if catalogue.get(permission) is None:
            raise IamError("UNKNOWN_PERMISSION", "Not a registered permission")
        if scope_type == "space":
            if not self.space(scope_id):
                raise IamError("NOT_FOUND", "No such space", 404)
            self._require(actor, "iam.access.deny.manage", scope_id)
        elif scope_type == "platform":
            self._require(actor, "iam.access.deny.manage")
        else:
            raise IamError("SCOPE_INVALID", "A deny is at the platform or in a space")
        if subject_type == "user":
            self._existing(subject_id)
        row = {
            "id": self.store.new_id("dny"),
            "subject_type": subject_type,
            "subject_id": subject_id,
            "permission": permission,
            "scope_type": scope_type,
            "scope_id": scope_id,
            "starts_at": self.store.stamp(),
            "ends_at": self._ends(days),
            "issuer_id": actor.id,
            "reason": reason[:200],
        }
        with self.store.transaction():
            self.store.insert("policy_denies", row)
            self.store.bump_policy_version()
            self._audit(
                actor,
                "deny.added",
                target_type=subject_type,
                target_id=subject_id,
                space_id=scope_id or None,
                reason=reason,
                after={"permission": permission, "scope_type": scope_type, "scope_id": scope_id},
            )
        return row

    def lift_deny(self, actor: Actor, deny_id: str, reason: str = "") -> None:
        row = self.store.one("SELECT * FROM policy_denies WHERE id = ? AND revoked_at IS NULL", (deny_id,))
        if row is None:
            raise IamError("NOT_FOUND", "No such deny", 404)
        self._require(actor, "iam.access.deny.manage", row["scope_id"] or None)
        with self.store.transaction():
            self.store.update("policy_denies", {"id": deny_id}, {"revoked_at": self.store.stamp(), "revoked_by": actor.id})
            self.store.bump_policy_version()
            self._audit(
                actor,
                "deny.lifted",
                target_type=row["subject_type"],
                target_id=row["subject_id"],
                space_id=row["scope_id"] or None,
                reason=reason,
                before={"permission": row["permission"]},
            )

    # -- access requests ---------------------------------------------------------------------------------------------------
    def request_access(self, actor: Actor, *, role_id: str, space_id: str | None, reason: str, days: int | None = None) -> dict:
        self._require(actor, "iam.access.requests.create", owner_id=actor.id)
        role = self.policy.role(role_id)
        if role is None or role.get("system") or role.get("protected"):
            raise IamError("NOT_FOUND", "That role cannot be requested", 404)
        if role["boundary"] == "space" and (not space_id or not self.space(space_id)):
            raise IamError("SPACE_REQUIRED", "Say which space")
        row = {
            "id": self.store.new_id("req"),
            "user_id": actor.id,
            "space_id": space_id if role["boundary"] == "space" else None,
            "role_id": role_id,
            "reason": reason[:500],
            "status": "pending",
            "requested_at": self.store.stamp(),
            "requested_days": days,
        }
        with self.store.transaction():
            self.store.insert("access_requests", row)
            self._audit(
                actor,
                "access.requested",
                target_type="user",
                target_id=actor.id,
                space_id=row["space_id"],
                reason=reason,
                after={"role_id": role_id, "days": days},
            )
        return row

    def requests(self, actor: Actor, *, own: bool = False) -> list[dict]:
        rows = self.store.all(
            "SELECT r.*, u.display_name, u.login FROM access_requests r JOIN users u ON u.id = r.user_id ORDER BY r.requested_at DESC"
        )
        if own:
            return [r for r in rows if r["user_id"] == actor.id]
        return [
            r
            for r in rows
            if self.can(actor.id, "iam.access.requests.decide", r["space_id"]) or self.can(actor.id, "iam.access.requests.decide")
        ]

    def decide_request(self, actor: Actor, request_id: str, approve: bool, reason: str = "", days: int | None = None) -> dict:
        row = self.store.one("SELECT * FROM access_requests WHERE id = ?", (request_id,))
        if row is None:
            raise IamError("NOT_FOUND", "No such request", 404)
        if row["status"] != "pending":
            raise IamError("DECIDED", "That request has already been decided", 409)
        if row["user_id"] == actor.id:
            raise IamError("SELF_APPROVAL", "You cannot decide your own request", 409)
        self._require(actor, "iam.access.requests.decide", row["space_id"], alternative=("iam.access.requests.decide", None))
        binding = None
        with self.store.transaction():
            if approve:
                role = self.policy.role(row["role_id"])
                span = days if days is not None else row["requested_days"]
                if span is None and role and role["id"] == "external_guest":
                    span = self.setting("guest.days")
                binding = self.grant(
                    actor,
                    subject_id=row["user_id"],
                    role_id=row["role_id"],
                    scope_type="space" if row["space_id"] else "platform",
                    scope_id=row["space_id"] or "",
                    days=span,
                    reason=f"access request {request_id}",
                    request_id=request_id,
                )
            self.store.update(
                "access_requests",
                {"id": request_id},
                {
                    "status": "approved" if approve else "rejected",
                    "decided_by": actor.id,
                    "decided_at": self.store.stamp(),
                    "decision_reason": reason[:500],
                    "binding_id": binding["id"] if binding else None,
                },
            )
            self._audit(
                actor,
                "access.decided",
                target_type="user",
                target_id=row["user_id"],
                space_id=row["space_id"],
                reason=reason,
                after={"request_id": request_id, "approved": approve},
            )
        return self.store.one("SELECT * FROM access_requests WHERE id = ?", (request_id,))  # type: ignore[return-value]

    def cancel_request(self, actor: Actor, request_id: str) -> None:
        row = self.store.one("SELECT * FROM access_requests WHERE id = ? AND status = 'pending'", (request_id,))
        if row is None or row["user_id"] != actor.id:
            raise IamError("NOT_FOUND", "No such pending request of yours", 404)
        self._require(actor, "iam.access.requests.cancel_own", owner_id=actor.id)
        with self.store.transaction():
            self.store.update("access_requests", {"id": request_id}, {"status": "cancelled", "decided_at": self.store.stamp()})
            self._audit(actor, "access.cancelled", target_type="user", target_id=actor.id, after={"request_id": request_id})

    # -- capabilities, explanations, audit ----------------------------------------------------------------------------------
    def capabilities(self, user_id: str) -> dict:
        """What the person can do, for the interface: the platform set, and each visible space's set."""
        spaces = {}
        for space in self.spaces("active"):
            keys = self.policy.effective(user_id, space["id"])
            if keys:
                spaces[space["id"]] = sorted(keys)
        return {"platform": sorted(self.policy.effective(user_id)), "spaces": spaces}

    def visible_spaces(self, user_id: str) -> list[dict]:
        out = []
        for space in self.spaces("active"):
            if "spaces.read" in self.policy.effective(user_id, space["id"]):
                out.append(space)
        return out

    def explain(self, actor: Actor, *, user_id: str, permission: str, space_id: str | None) -> dict:
        self._require(actor, "iam.access.explain", space_id, alternative=("iam.access.explain", None))
        self._existing(user_id)
        return self.policy.explain(user_id, permission, space_id)

    def events(self, actor: Actor, **filters) -> list[dict]:
        if self.can(actor.id, "audit.read"):
            return self.audit.events(**filters)
        space_id = filters.get("space_id")
        if space_id and self.can(actor.id, "audit.read", space_id):
            return self.audit.events(**filters)
        raise IamError("ACCESS_DENIED", "You cannot read the audit", 403)

    def recovery_events(self, actor: Actor) -> list[dict]:
        self._require(actor, "platform.settings.read")
        return self.store.all("SELECT * FROM recovery_events ORDER BY at DESC LIMIT 20")

    # -- authority ----------------------------------------------------------------------------------------------------------
    def context(self, user: dict, session: dict | None, request_id: str = "") -> AuthorizationContext:
        return AuthorizationContext(
            principal_id=user["id"],
            session_id=session["id"] if session else None,
            policy_version=self.store.policy_version(),
            credential_epoch=user["credential_epoch"],
            authenticated_at=parse(session["authenticated_at"]) if session else None,
            request_id=request_id,
        )

    def decide(self, ctx: AuthorizationContext, permission: str, space_id: str | None = None, **conditions) -> Decision:
        return self.policy.evaluate(ctx, permission, space_id=space_id, **conditions)

    def can(self, user_id: str | None, permission: str, space_id: str | None = None, **conditions) -> bool:
        if user_id is None:
            return True  # the host: a local procedure with control of the store
        return bool(self.policy.evaluate(AuthorizationContext(principal_id=user_id), permission, space_id=space_id, **conditions))

    def _require(
        self,
        actor: Actor,
        permission: str,
        space_id: str | None = None,
        *,
        owner_id: str | None = None,
        alternative: tuple[str, str | None] | None = None,
    ) -> None:
        if actor.is_host:
            return
        decision = self.policy.evaluate(AuthorizationContext(principal_id=actor.id), permission, space_id=space_id, owner_id=owner_id)
        if not decision and alternative is not None:
            decision = self.policy.evaluate(AuthorizationContext(principal_id=actor.id), alternative[0], space_id=alternative[1])
        if not decision:
            if decision.hidden:
                raise IamError("NOT_FOUND", "No such space", 404)
            raise IamError("ACCESS_DENIED", decision.reason, 403)

    def _existing(self, user_id: str) -> dict:
        user = self.user(user_id)
        if user is None:
            raise IamError("NOT_FOUND", "No such person", 404)
        return user

    def _audit(self, actor: Actor, action: str, **fields) -> None:
        self.audit.record(
            action=action,
            actor_id=actor.id,
            actor_type=actor.type,
            session_ref=actor.session_id,
            request_id=actor.request_id,
            address=actor.address,
            **fields,
        )


def square_picture(data: bytes) -> bytes:
    """A picture as a PICTURE_SIDE square JPEG: centred and cut square if it is not one already, turned upright,
    transparency laid on the sidebar's slate. PNG, JPEG and WebP only; nothing else that was in the file is kept."""
    if not data:
        raise IamError("INVALID_PICTURE", "Choose a picture first")
    if len(data) > PICTURE_UPLOAD_BYTES:
        raise IamError("INVALID_PICTURE", "Choose a picture under 4 MB", 413)
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in ("PNG", "JPEG", "WEBP"):
                raise IamError("INVALID_PICTURE", "Use a PNG, JPEG or WebP picture")
            if source.width * source.height > PICTURE_MAX_PIXELS:
                raise IamError("INVALID_PICTURE", "That picture is too large; choose a smaller one")
            image = ImageOps.exif_transpose(source)
            side = min(image.size)
            left, top = (image.width - side) // 2, (image.height - side) // 2
            image = image.crop((left, top, left + side, top + side)).resize((PICTURE_SIDE, PICTURE_SIDE), Image.Resampling.LANCZOS)
            if image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGBA")
                flat = Image.new("RGB", image.size, PICTURE_BACKGROUND)
                flat.paste(image, mask=image.getchannel("A"))
                image = flat
            out = io.BytesIO()
            image.convert("RGB").save(out, "JPEG", quality=88, optimize=True)
            return out.getvalue()
    except IamError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
        raise IamError("INVALID_PICTURE", "That file is not a picture that can be used") from error
