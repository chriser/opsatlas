"""Red team, REF S68: S16's recheck before delivery (``still_allowed``) decides exactly as before the change.

The old recheck is copied verbatim from 3e51749:src/assistant/api/access.py:153-168 (the store read, the revoked test and
``_check_session(touch=False)``). Each scenario is built twice, on twin stores with the same clock, and the old and the
new recheck run one on each. Then compare the outcome (status, code, message), the session row given to the decision,
and every session row afterwards (the revocations ``_check_session`` writes). Hermetic: in-memory stores, no network.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from assistant.api import access
from assistant.api.access import AccessError, Actor, _space_for, still_allowed
from assistant.iam.service import Identity
from assistant.iam.store import IamStore

EMAIL, PASSWORD = "kris@example.test", "the quiet river runs east"
START = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
ROW_KEYS = ("created_at", "authenticated_at", "last_seen_at", "absolute_expires_at", "revoked_at", "revoked_reason",
            "privileged", "credential_epoch", "device", "address")


def old_still_allowed(request, permission):  # verbatim, 3e51749
    actor = getattr(request.state, "actor", None)
    if actor is None:
        raise AccessError(401, "AUTH_REQUIRED", "Sign in to continue")
    iam = request.app.state.auth.iam
    session = iam.store.one("SELECT * FROM sessions WHERE id = ?", (actor.session["id"],))
    if session is None or session["revoked_at"] or iam._check_session(session, touch=False) is None:
        raise AccessError(401, "AUTH_REQUIRED", "Your session ended while the answer was prepared; sign in again")
    decision = iam.decide(iam.context(actor.user, session, actor.request_id), permission,
                          _space_for(request, permission, "auto"))
    if not decision:
        raise AccessError(404 if decision.hidden else 403, "ACCESS_DENIED", "Your access changed while the answer was prepared")


def world():
    clock = {"now": START}
    iam = Identity(IamStore(None, clock=lambda: clock["now"]), origin="http://testserver", guide_space="product-guide")
    iam.register_space("product-guide", "Product guide", "product")
    iam.register_space(access.DEFAULT_SPACE, "Knowledge base", "product")
    iam.bootstrap_admin(EMAIL, "Kris", password=PASSWORD)
    session, _ = iam.login(EMAIL, PASSWORD)
    user, session = iam.resolve(session["secret"], touch=False)
    seen = []
    real_context = iam.context

    def spy(user_, session_, request_id):
        seen.append(dict(session_))
        return real_context(user_, session_, request_id)
    iam.context = spy
    actor = Actor(user, dict(session), SimpleNamespace(iam=iam), "req-1", False)
    request = SimpleNamespace(state=SimpleNamespace(actor=actor), path_params={},
                              app=SimpleNamespace(state=SimpleNamespace(auth=SimpleNamespace(iam=iam), space_id=None)))
    return SimpleNamespace(iam=iam, clock=clock, request=request, actor=actor, seen=seen, user=user, session=session)


def _set(w, sql, *params):
    w.iam.store.run(sql, params)


def _wrap_check(w, before):
    real = w.iam._check_session

    def wrapped(session, *, touch):
        before(w)
        return real(session, touch=touch)
    w.iam._check_session = wrapped


class Denied:
    def __init__(self, hidden):
        self.hidden = hidden

    def __bool__(self):
        return False


SCENARIOS = {
    "alive": lambda w: None,
    "alive, the actor's copy is stale (the row was seen later)": lambda w: (
        w.clock.update(now=START + timedelta(minutes=3)),
        _set(w, "UPDATE sessions SET last_seen_at = ? WHERE id = ?", w.iam.store.stamp(), w.session["id"])),
    "signed out": lambda w: w.iam.logout(w.session),
    "revoked by the column only": lambda w: _set(w, "UPDATE sessions SET revoked_at = ?, revoked_reason = 'x' WHERE id = ?",
                                                 w.iam.store.stamp(), w.session["id"]),
    "past its absolute life": lambda w: w.clock.update(now=START + timedelta(days=60)),
    "exactly at its absolute expiry": lambda w: w.clock.update(
        now=datetime.fromisoformat(w.session["absolute_expires_at"])),
    "idle": lambda w: w.clock.update(now=START + timedelta(minutes=w.iam.idle_minutes(w.session), seconds=1)),
    "exactly at the idle limit": lambda w: w.clock.update(now=START + timedelta(minutes=w.iam.idle_minutes(w.session))),
    "a second inside the idle limit": lambda w: w.clock.update(
        now=START + timedelta(minutes=w.iam.idle_minutes(w.session), seconds=-1)),
    "credentials changed": lambda w: _set(w, "UPDATE users SET credential_epoch = credential_epoch + 1 WHERE id = ?",
                                          w.user["id"]),
    "account suspended": lambda w: _set(w, "UPDATE users SET state = 'suspended' WHERE id = ?", w.user["id"]),
    "account gone": lambda w: (_set(w, "PRAGMA foreign_keys=OFF"), _set(w, "DELETE FROM users WHERE id = ?", w.user["id"])),
    "session row gone": lambda w: _set(w, "DELETE FROM sessions WHERE id = ?", w.session["id"]),
    "row deleted between the read and the check": lambda w: _wrap_check(
        w, lambda w: _set(w, "DELETE FROM sessions WHERE id = ?", w.session["id"])),
    "revoked between the read and the check": lambda w: _wrap_check(
        w, lambda w: _set(w, "UPDATE sessions SET revoked_at = ?, revoked_reason = 'late' WHERE id = ?",
                          w.iam.store.stamp(), w.session["id"])),
    "suspended between the read and the check": lambda w: _wrap_check(
        w, lambda w: _set(w, "UPDATE users SET state = 'suspended' WHERE id = ?", w.user["id"])),
    "decision denies, hidden": lambda w: setattr(w.iam, "decide", lambda *a, **k: Denied(True)),
    "decision denies, visible": lambda w: setattr(w.iam, "decide", lambda *a, **k: Denied(False)),
    "no actor": lambda w: setattr(w.request.state, "actor", None),
}


def run(check, scenario):
    w = world()
    SCENARIOS[scenario](w)
    try:
        check(w.request, "knowledge.ask")
        outcome = ("allowed",)
    except AccessError as exc:
        outcome = (exc.status, exc.code, exc.message) if hasattr(exc, "status") else (exc.args, exc.code)
    rows = [tuple(r[k] for k in ROW_KEYS) for r in w.iam.store.all("SELECT * FROM sessions ORDER BY created_at")]
    given = [tuple(s.get(k) for k in ROW_KEYS) for s in w.seen]
    audit = [(e["action"], e["outcome"]) for e in w.iam.store.all("SELECT action, outcome FROM audit_events ORDER BY seq")]
    return outcome, given, rows, audit


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_the_recheck_decides_and_writes_exactly_as_before(scenario):
    old, new = run(old_still_allowed, scenario), run(still_allowed, scenario)
    assert new == old, f"{scenario}:\n old {old}\n new {new}"


def test_the_decision_sees_the_row_read_afresh_not_the_actors_copy():
    w = world()
    SCENARIOS["alive, the actor's copy is stale (the row was seen later)"](w)
    still_allowed(w.request, "knowledge.ask")
    assert w.seen[0]["last_seen_at"] != w.actor.session["last_seen_at"]
    assert w.seen[0]["last_seen_at"] == w.iam.store.one("SELECT last_seen_at FROM sessions WHERE id = ?",
                                                         (w.session["id"],))["last_seen_at"]
