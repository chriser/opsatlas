"""REF S69, from S68's independent review (IR1): the host recovery command answers IAM's refusal with its own.

R1 put an active-account check inside ``Identity.emergency_recovery`` (in its BEGIN IMMEDIATE transaction), and the command
(``python -m assistant.iam recover``) keeps its own check before the call. When the account stops being active between the
command's read and the transaction (an administrator suspends it at that moment), the method refuses and writes nothing,
as R1 intends; but the command does not catch the refusal, so ``IamError`` escapes ``recover()`` and ``main()`` (a traceback,
exit status 1) instead of the command's "No active account with that login." and status 2. Before S68 the same race wrote
a recovery for the suspended account. It failed at 8a08a2c on the last two assertions; fixed in REF S69.
Hermetic: SQLite under tmp_path, no network, no live service.
"""
from __future__ import annotations

import argparse

from assistant.iam import __main__ as command
from assistant.iam.service import IamError, Identity

EMAIL, PASSWORD, ORIGIN = "kris@example.test", "the quiet river runs east", "http://127.0.0.1:8780"
TABLES = ("sessions", "lifecycle_tokens", "recovery_events", "audit_events")


def _rows(root):
    iam = command._identity(str(root), ORIGIN)
    return {t: iam.store.all(f"SELECT * FROM {t} ORDER BY rowid") for t in TABLES}


def test_the_command_refuses_cleanly_when_the_account_is_suspended_during_the_recovery(tmp_path, monkeypatch, capsys):
    iam = command._identity(str(tmp_path), ORIGIN)
    iam.register_space("product-guide", "Product guide", "product")
    iam.bootstrap_admin(EMAIL, "Kris", password=PASSWORD)
    iam.login(EMAIL, PASSWORD)
    before = _rows(tmp_path)
    real = Identity.user_by_login

    def read_then_suspended(self, login):
        row = real(self, login)  # the command's read: the account is active
        self.store.run("UPDATE users SET state = 'suspended' WHERE id = ?", (row["id"],))  # an administrator suspends it now
        return row

    monkeypatch.setattr(Identity, "user_by_login", read_then_suspended)
    args = argparse.Namespace(root=str(tmp_path), origin=ORIGIN, login=EMAIL, reason="lost the password")
    try:
        code = command.recover(args)
    except IamError as exc:
        code = f"IamError {getattr(exc, 'code', exc)} escaped the command"
    # What R1 secures, and holds: nothing is written for the suspended account (no link, no ended session, no record).
    assert _rows(tmp_path) == before
    # What fails: the command does not turn the refusal into its own answer.
    assert code == 2, code
    assert "No active account" in capsys.readouterr().err
