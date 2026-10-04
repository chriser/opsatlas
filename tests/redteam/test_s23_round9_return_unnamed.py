"""Red team, REF S23 round 9 (S8): a reviewer's return of a submitted draft (the documents.reject permission) names no
text. A draft edited and resubmitted after the reviewer read it is returned on the reviewer's note about the earlier
text, which the reviewer never saw."""
from __future__ import annotations

import pytest

from tests.redteam.test_s23_round9_replaced_file import HEAD, acme  # noqa: F401  (the hermetic Sales space fixture)

PENDING = pytest.mark.xfail(strict=True, reason="REF S23 round 9: the stop rule on approvals; awaiting the Human's design decision")

D1 = "# Pricing guide\n\nThe Acme plan costs twelve pounds a month.\n\nIt includes support.\n"
D2 = "# Pricing guide\n\nThe Acme plan costs eleven pounds a month.\n\nIt includes support.\n"


def _doc(client, sid):
    return client.get(f"/api/content/documents/{sid}", headers=HEAD).json()


@PENDING
def test_s23_round9_return_names_no_text(acme):  # noqa: F811
    client, core, sid = acme
    assert client.put(f"/api/content/documents/{sid}/draft", json={"text": D1}, headers=HEAD).status_code == 200
    assert client.post(f"/api/content/documents/{sid}/submit", json={"note": "first"}, headers=HEAD).status_code == 200
    read = _doc(client, sid)["draft"]  # the reviewer opens the submitted draft D1
    assert "twelve" in read["text"]
    # Meanwhile the author changes it and submits again.
    assert client.put(f"/api/content/documents/{sid}/draft", json={"text": D2}, headers=HEAD).status_code == 200
    assert client.post(f"/api/content/documents/{sid}/submit", json={"note": "second"}, headers=HEAD).status_code == 200
    # The reviewer returns what they read; the request cannot say which text that was.
    r = client.post(f"/api/content/documents/{sid}/return", json={"note": "twelve pounds is wrong"}, headers=HEAD)
    after = _doc(client, sid)
    assert after["draft"]["sha"] != read["sha"]
    assert r.status_code >= 400 or after.get("status") == "submitted" or after["draft"].get("status") == "submitted", (
        f"D2, never read, was returned on a note about D1: {r.status_code} {str(after.get('status'))}")
