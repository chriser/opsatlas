"""Red team, REF S23 round 10 (commit 6eeacda): a person's dispute of a Tibi claim changes a document's approval on a
text the decision did not name, or through the workspace's own withdrawal (S8)."""
from __future__ import annotations

import gc
import hashlib
import os
import socket

import pytest
from fastapi.testclient import TestClient

from tests.door_helpers import decide, writing
from tests.iam_helpers import sign_in
from tests.test_space_leaks import hermetic, refuse

pytestmark = pytest.mark.xfail(strict=True, reason="REF S23 round 10: the stop rule on approvals; awaiting the Human's decision")


def sha(data) -> str:
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()


@pytest.fixture
def sales(tmp_path, monkeypatch):
    from services.opsatlas_sales.app import create_sales_app
    from services.opsatlas_sales.knowledge import Knowledge
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    os.environ["SME_TIBI_VOICE_URL"] = "http://127.0.0.1:9"
    os.environ["SALES_GOVERNANCE_AUTO_REVIEW"] = "0"
    root = tmp_path / "sales"
    app = create_sales_app(root)
    hermetic(app)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {sign_in(client, app)}"}
    knowledge = next(o for o in gc.get_objects() if isinstance(o, Knowledge) and str(o.path).startswith(str(root)))
    if not knowledge.topics():
        pytest.skip("no seeded topic records in the hermetic workspace")
    return app, client, headers, knowledge


def _claim(app, knowledge, text="Exports finish within one minute."):
    topic = knowledge.topics()[0]
    with writing(app):
        return knowledge.propose({
            "session_id": "s-r10", "turn_id": "t-1", "contributor": "Pat Reviewer", "topic": topic,
            "question": "How long do exports take?", "raw_text": text, "text": text, "status": "available",
            "expected_hash": None, "wording_confirmed": True, "issue": None})


def _related(knowledge, row_id):
    rows = knowledge.records()
    row = next(r for r in rows if r["id"] == row_id)
    return row, {r["id"]: r["sha256"] for r in knowledge.overlaps(row, rows)}


def test_s23_round10_dispute_rejects_a_text_nobody_named(sales, monkeypatch):
    """S8: a dispute names the claim's text as the page shows it (its record's sha256); after a publish whose records
    step failed (S5's accepted fault), the rejection lands on the newer text, which the decision never named."""
    from services.opsatlas_sales.knowledge import Knowledge
    app, client, headers, knowledge = sales
    claim = _claim(app, knowledge)
    sid = claim["source_id"]
    row, related = _related(knowledge, claim["id"])
    with writing(app):  # set-up: the scope decision that lets the claim be enabled, then its approval
        knowledge.adjudicate(row["id"], row["sha256"], "distinct_scope", related, "Different product edition, separate")
        knowledge.decide(row["id"], row["sha256"], True)
    assert app.state.family_register.get(sid).approval_status == "approved"
    named = row["sha256"]  # the text the claim's page shows and the dispute names

    # A new version is published through content management; the workspace's records step after the commit fails
    # (one ordinary write failure; S5: published whatever fails after it).
    content = app.state.content
    original = Knowledge._save

    def failing(self, rows):
        raise OSError("disk full")
    new_text = f"# {row['title']}\n\nCurrently: Exports finish within ten minutes.\n"
    with writing(app):
        content.save_draft(sid, new_text)
        content.submit(sid, "")
        monkeypatch.setattr(Knowledge, "_save", failing)
        content.publish(sid, sha(new_text))
        monkeypatch.setattr(Knowledge, "_save", original)
    record = app.state.family_register.get(sid)
    assert record.approval_status == "approved"
    assert record.content_sha256 != named  # live: the newer text, approved by its publish

    # The person disputes the claim they read: its page names the record's text, the older one.
    row, related = _related(knowledge, claim["id"])
    assert row["sha256"] == named
    response = client.post(f"/api/tibi/knowledge/{row['id']}/resolve", headers=headers, json={
        "expected_hash": named, "decision": "dispute", "related": related,
        "reason": "A later account contradicts this claim"})
    after = app.state.family_register.get(sid)
    # S8: a decision on any other text is refused, and nothing changes. Here the newer text, never named, is rejected.
    assert not (response.status_code == 200 and after.approval_status == "rejected"
                and after.content_sha256 != named), (
        f"the dispute named {named[:12]} and rejected {after.content_sha256[:12]} ({response.status_code})")


def test_s23_round10_dispute_withdraws_a_file_replaced_on_disk(sales):
    """S8: a file replaced on disk outside content management cannot be decided on, and the workspace's own withdrawal
    is reachable by no person; a person's dispute reaches it, and the document's approval changes."""
    app, client, headers, knowledge = sales
    claim = _claim(app, knowledge)
    sid = claim["source_id"]
    assert decide(client, sid, headers).status_code == 200
    register = app.state.family_register
    named = register.get(sid).content_sha256
    assert register.get(sid).approval_status == "approved"

    register.file_path(sid).write_bytes(b"# Replaced\n\nA file put in place outside content management.\n")
    # The register's own check refuses a decision on it, and so does the governance route:
    assert register.names_text(sid, named) is not None
    refused = client.post(f"/api/governance/sources/{sid}/reject", headers=headers, json={"sha": named})
    assert refused.status_code == 409, refused.text
    assert register.get(sid).approval_status == "approved"

    row, related = _related(knowledge, claim["id"])
    response = client.post(f"/api/tibi/knowledge/{row['id']}/resolve", headers=headers, json={
        "expected_hash": row["sha256"], "decision": "dispute", "related": related,
        "reason": "A later account contradicts this claim"})
    after = register.get(sid).approval_status
    assert after == "approved", (
        f"a person's dispute changed the approval of a replaced file to {after!r} ({response.status_code}: "
        f"{response.text[:200]}); names_text said: {register.names_text(sid, named)}")
