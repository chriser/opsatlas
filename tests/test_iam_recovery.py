"""The host's emergency recovery (REF S68): the recovery command's transaction, moved into IAM unchanged. A one-time
reset link for an active account, every session of it ended, the recovery recorded and audited, all in one transaction.
"""
from __future__ import annotations

import argparse
import json

import pytest

from assistant.iam import __main__ as command
from assistant.iam.service import Identity
from assistant.iam.store import IamStore

EMAIL, PASSWORD = "kris@example.test", "the quiet river runs east"


def _iam(root):
    iam = Identity(IamStore(root / "iam.db"), origin="http://127.0.0.1:8780", guide_space="product-guide")
    iam.register_space("product-guide", "Product guide", "product")
    user, _ = iam.bootstrap_admin(EMAIL, "Kris", password=PASSWORD)
    return iam, user


def _live_sessions(iam, user_id):
    return iam.store.all("SELECT * FROM sessions WHERE user_id = ? AND revoked_at IS NULL", (user_id,))


def test_emergency_recovery_issues_a_reset_link_ends_every_session_and_records_it(tmp_path):
    iam, user = _iam(tmp_path)
    iam.login(EMAIL, PASSWORD)
    iam.login(EMAIL, PASSWORD)
    assert len(_live_sessions(iam, user["id"])) == 2
    token = iam.emergency_recovery(user, "lost the password", "host-person")
    assert token
    assert _live_sessions(iam, user["id"]) == []
    reasons = {r["revoked_reason"] for r in iam.store.all("SELECT revoked_reason FROM sessions WHERE user_id = ?", (user["id"],))}
    assert reasons == {"emergency recovery"}
    tokens = iam.store.all("SELECT * FROM lifecycle_tokens WHERE user_id = ? AND purpose = 'reset'", (user["id"],))
    assert len(tokens) == 1 and json.loads(tokens[0]["payload"]) == {"recovery": True, "reason": "lost the password"}
    assert tokens[0]["issuer_id"] is None
    events = iam.store.all("SELECT kind, reason, host_user FROM recovery_events WHERE user_id = ?", (user["id"],))
    assert [(e["kind"], e["reason"], e["host_user"]) for e in events] == [("password reset", "lost the password", "host-person")]
    audit = [e for e in iam.audit.events(limit=20) if e["action"] == "recovery.emergency"]
    assert len(audit) == 1 and audit[0]["target_id"] == user["id"] and audit[0]["actor_type"] == "host"
    assert iam.preview(token, "reset")["email"] == EMAIL  # the link is a usable reset token for that account


def test_emergency_recovery_changes_nothing_when_a_step_fails(tmp_path, monkeypatch):
    iam, user = _iam(tmp_path)
    iam.login(EMAIL, PASSWORD)

    def failing_audit(**kwargs):
        raise RuntimeError("the audit cannot be written")
    monkeypatch.setattr(iam.audit, "record", failing_audit)
    with pytest.raises(RuntimeError):
        iam.emergency_recovery(user, "lost the password", "host-person")
    assert len(_live_sessions(iam, user["id"])) == 1  # one transaction: nothing was ended
    assert iam.store.all("SELECT * FROM recovery_events") == []
    assert iam.store.all("SELECT * FROM lifecycle_tokens WHERE user_id = ? AND purpose = 'reset'", (user["id"],)) == []


def test_the_recover_command_prints_the_link_once(tmp_path, capsys):
    iam, user = _iam(tmp_path)
    args = argparse.Namespace(root=str(tmp_path), origin="http://127.0.0.1:8780", login=EMAIL, reason="lost the password")
    assert command.recover(args) == 0
    out = capsys.readouterr().out
    assert "sessions ended" in out and "#reset:" in out
    assert command.recover(argparse.Namespace(root=str(tmp_path), origin="http://127.0.0.1:8780", login="nobody@example.test",
                                              reason="x")) == 2
