"""REF S68, from its red team (R1, failing on ed7023d, fixed): emergency recovery refuses an account that is not active.
Hermetic: SQLite under tmp_path.

R1 (Low): ``Identity.emergency_recovery`` is now a public way in, documented as "a one-time reset link for an active
account", but it does not check that the account is active; only the host command does, before calling it. Called for a
suspended account it still ends sessions, revokes the account's open reset link, and writes a "password reset" recovery
event and a ``recovery.emergency`` audit record for a link that ``reset_password`` will refuse (410). No caller does this
today, so nothing behaves differently; the precondition lives one call away from the method that states it.
"""
from __future__ import annotations

import pytest

from assistant.iam.service import IamError, Identity
from assistant.iam.store import IamStore

EMAIL, PASSWORD = "kris@example.test", "the quiet river runs east"


def test_r1_emergency_recovery_refuses_an_account_that_is_not_active(tmp_path):
    iam = Identity(IamStore(tmp_path / "iam.db"), origin="http://127.0.0.1:8780", guide_space="product-guide")
    iam.register_space("product-guide", "Product guide", "product")
    user, _ = iam.bootstrap_admin(EMAIL, "Kris", password=PASSWORD)
    earlier = iam._issue("reset", user, issuer=None, minutes=30)
    iam.store.run("UPDATE users SET state = 'suspended' WHERE id = ?", (user["id"],))
    suspended = iam.user(user["id"])
    try:
        token = iam.emergency_recovery(suspended, "lost the password", "host-person")
    except IamError:
        token = None
    # What it did instead, for the record: the new link cannot be used, and the earlier one was revoked.
    if token is not None:
        with pytest.raises(IamError):
            iam.reset_password(token, "a brand new passphrase for kris")
        with pytest.raises(IamError):
            iam.preview(earlier, "reset")
    assert token is None, "a reset link was issued, and a recovery recorded, for a suspended account"
    assert iam.store.all("SELECT * FROM recovery_events") == []
