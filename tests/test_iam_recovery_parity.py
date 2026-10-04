"""Red team, REF S68: ``python -m assistant.iam recover`` writes and prints exactly what it did before the change.

The old command is copied verbatim from 3e51749:src/assistant/iam/__main__.py:57-94. Twin workspaces get the same set-up
(an administrator, two sessions, an earlier open reset link) under a fixed clock and a fixed host user; the old command
runs on one, the new one on the other. Then compare every row of the IAM tables (ids normalised; secrets' digests and
the audit hashes, which follow from the ids, left out), the audit chain's verification, and the printed output (the
link's secret masked). Hermetic: SQLite files under tmp_path, no network.
"""
from __future__ import annotations

import argparse
import getpass
import re
import sys
from datetime import datetime, timezone

import pytest

import assistant.iam.store as store_module
from assistant.iam import __main__ as command

EMAIL, PASSWORD, ORIGIN = "kris@example.test", "the quiet river runs east", "http://127.0.0.1:8780"
FIXED = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
TABLES = ("users", "sessions", "lifecycle_tokens", "recovery_events", "audit_events", "credentials")
SECRET_COLUMNS = {"digest", "csrf", "hash", "prev_hash"}
_ID = re.compile(r"\b([a-z]+)_[0-9a-f]{20}\b")


def old_recover(args: argparse.Namespace) -> int:  # verbatim, 3e51749 (the noqa marks dropped)
    iam = command._identity(args.root, args.origin)
    user = iam.user_by_login(args.login)
    if user is None or user["state"] != "active":
        print("No active account with that login.", file=sys.stderr)
        return 2
    store = iam.store
    with store.transaction():
        token = iam._issue(
            "reset", user, issuer=None, minutes=iam.setting("reset.minutes"), payload={"recovery": True, "reason": args.reason}
        )
        iam._revoke_sessions(user["id"], "emergency recovery")
        store.insert(
            "recovery_events",
            {
                "id": store.new_id("rec"),
                "at": store.stamp(),
                "user_id": user["id"],
                "kind": "password reset",
                "reason": args.reason[:500],
                "host_user": getpass.getuser(),
            },
        )
        iam.audit.record(
            action="recovery.emergency",
            actor_type="host",
            target_type="user",
            target_id=user["id"],
            target_label=user["display_name"],
            reason=args.reason,
            detail={"host_user": getpass.getuser()},
        )
    print(
        f"Recovery for {user['display_name']} <{user['email']}>: sessions ended. One-time reset link, valid "
        f"{iam.setting('reset.minutes')} minutes, shown once:"
    )
    print(f"  {iam.link('reset', token)}")
    return 0


@pytest.fixture(autouse=True)
def fixed(monkeypatch):
    monkeypatch.setattr(store_module, "utcnow", lambda: FIXED)
    monkeypatch.setattr(getpass, "getuser", lambda: "host-person")


def workspace(root, *, state="active"):
    root.mkdir()
    iam = command._identity(str(root), ORIGIN)
    iam.register_space("product-guide", "Product guide", "product")
    user, _ = iam.bootstrap_admin(EMAIL, "Kris", password=PASSWORD)
    iam.login(EMAIL, PASSWORD)
    iam.login(EMAIL, PASSWORD)
    iam._issue("reset", user, issuer=None, minutes=5)  # an earlier open link: the recovery revokes it
    if state != "active":
        iam.store.run("UPDATE users SET state = ? WHERE id = ?", (state, user["id"]))
    return root


def snapshot(root):
    iam = command._identity(str(root), ORIGIN)

    def norm(v):
        return _ID.sub(r"\1_<id>", v) if isinstance(v, str) else v
    out = {t: [{k: norm(v) for k, v in row.items() if k not in SECRET_COLUMNS}
               for row in iam.store.all(f"SELECT * FROM {t} ORDER BY rowid")] for t in TABLES}
    out["audit chain"] = iam.audit.verify_chain()
    return out


def args(root, reason="lost the password", login=EMAIL):
    return argparse.Namespace(root=str(root), origin=ORIGIN, login=login, reason=reason)


def both(tmp_path, capsys, *, reason="lost the password", runs=1, state="active", login=EMAIL):
    results = []
    for name, fn in (("old", old_recover), ("new", command.recover)):
        root = workspace(tmp_path / name, state=state)
        codes = [fn(args(root, reason, login)) for _ in range(runs)]
        printed = capsys.readouterr()
        results.append((codes, re.sub(r"#reset:\S+", "#reset:<secret>", printed.out), printed.err, snapshot(root)))
    return results


@pytest.mark.parametrize("reason", ["lost the password", "x" * 600 + "\n\x07 the rest", ""])
def test_the_command_writes_and_prints_exactly_as_before(tmp_path, capsys, reason):
    old, new = both(tmp_path, capsys, reason=reason)
    assert old[0] == [0]
    assert new == old


def test_running_it_twice_leaves_the_same_records_as_before(tmp_path, capsys):
    old, new = both(tmp_path, capsys, runs=2)
    assert new == old


@pytest.mark.parametrize("state", ["suspended", "deactivated", "invited"])
def test_an_account_that_is_not_active_is_refused_as_before(tmp_path, capsys, state):
    old, new = both(tmp_path, capsys, state=state)
    assert old[0] == [2] and "No active account" in old[2]
    assert new == old


def test_an_unknown_login_is_refused_as_before(tmp_path, capsys):
    old, new = both(tmp_path, capsys, login="nobody@example.test")
    assert new == old


def test_when_the_audit_cannot_be_written_nothing_is_written_as_before(tmp_path, capsys, monkeypatch):
    from assistant.iam.audit import Audit
    real = Audit.record

    def failing(self, **kwargs):
        if kwargs.get("action") == "recovery.emergency":
            raise RuntimeError("the audit cannot be written")
        return real(self, **kwargs)
    results = []
    for name, fn in (("old", old_recover), ("new", command.recover)):
        root = workspace(tmp_path / name)
        before = snapshot(root)
        monkeypatch.setattr(Audit, "record", failing)
        with pytest.raises(RuntimeError):
            fn(args(root))
        monkeypatch.setattr(Audit, "record", real)
        results.append((before, snapshot(root), capsys.readouterr().out))
    (old_before, old_after, old_out), (new_before, new_after, new_out) = results
    assert old_after == old_before and new_after == new_before  # the token and the ended sessions rolled back too
    assert (new_before, new_after, new_out) == (old_before, old_after, old_out)


def test_when_the_host_user_cannot_be_read_nothing_is_written_as_before(tmp_path, capsys, monkeypatch):
    def no_user():
        raise OSError("No username set in the environment")
    results = []
    for name, fn in (("old", old_recover), ("new", command.recover)):
        root = workspace(tmp_path / name)
        before = snapshot(root)
        monkeypatch.setattr(getpass, "getuser", no_user)
        with pytest.raises(OSError):
            fn(args(root))
        monkeypatch.setattr(getpass, "getuser", lambda: "host-person")
        results.append((before, snapshot(root), capsys.readouterr().out))
    (old_before, old_after, old_out), (new_before, new_after, new_out) = results
    assert old_after == old_before and new_after == new_before  # one transaction either way: nothing written
    assert (new_before, new_after, new_out) == (old_before, old_after, old_out)
