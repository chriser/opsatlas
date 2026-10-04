"""The Sales records' copy of a document's text stays in step with it (REF S23, S5, S8; the Human's decision after the
red team's tenth round): a records step that failed after a publish is tried again, and a decision on a record out of
step is refused until it is, so a person decides only on the text they read.

Hermetic: the full Sales app on a temporary workspace, sockets refused, models faked.
"""
from __future__ import annotations

import hashlib
import os
import socket

import pytest
from fastapi.testclient import TestClient

from tests.door_helpers import writing
from tests.iam_helpers import sign_in
from tests.test_space_leaks import hermetic, refuse


@pytest.fixture
def sales(tmp_path, monkeypatch):
    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    os.environ.update({"SME_TIBI_VOICE_URL": "http://127.0.0.1:9", "SALES_GOVERNANCE_AUTO_REVIEW": "0"})
    app = create_sales_app(tmp_path / "sales")
    hermetic(app)
    client = TestClient(app)
    return app, client, {"Authorization": f"Bearer {sign_in(client, app)}"}, app.state.sales


def _row(knowledge, identifier):
    rows = knowledge.records()
    row = next(r for r in rows if r["id"] == identifier)
    return row, {r["id"]: r["sha256"] for r in knowledge.overlaps(row, rows)}


def test_a_failed_records_step_is_tried_again_and_a_dispute_waits_for_it(sales, monkeypatch):
    from services.opsatlas_sales.knowledge import Knowledge
    app, client, headers, knowledge = sales
    text = "Exports finish within one minute."
    with writing(app):
        claim = knowledge.propose({
            "session_id": "s-step", "turn_id": "t-1", "contributor": "Pat Reviewer", "topic": knowledge.topics()[0],
            "question": "How long do exports take?", "raw_text": text, "text": text, "status": "available",
            "expected_hash": None, "wording_confirmed": True, "issue": None})
        row, related = _row(knowledge, claim["id"])
        knowledge.adjudicate(row["id"], row["sha256"], "distinct_scope", related, "Different product edition, separate")
        knowledge.decide(row["id"], row["sha256"], True)
    sid, register, content = claim["source_id"], app.state.family_register, app.state.content
    new_text = f"# {row['title']}\n\nCurrently: Exports finish within ten minutes.\n"
    with writing(app):  # a publish whose records step fails (S5: published whatever fails after it)
        content.save_draft(sid, new_text)
        content.submit(sid, "")
        original = Knowledge._save
        monkeypatch.setattr(Knowledge, "_save", lambda self, rows: (_ for _ in ()).throw(OSError("disk full")))
        content.publish(sid, hashlib.sha256(new_text.encode()).hexdigest())
        monkeypatch.setattr(Knowledge, "_save", original)
    row, related = _row(knowledge, claim["id"])
    assert row["sha256"] != register.get(sid).content_sha256  # the record's copy is out of step
    url = f"/api/tibi/knowledge/{row['id']}/resolve"
    body = {"decision": "dispute", "related": related, "reason": "A later account contradicts this claim"}
    refused = client.post(url, headers=headers, json={**body, "expected_hash": row["sha256"]})
    assert refused.status_code in (400, 409), refused.text
    assert register.get(sid).approval_status == "approved"  # nothing changed
    row, related = _row(knowledge, claim["id"])
    assert row["sha256"] == register.get(sid).content_sha256, "the failed records step was not tried again"
    agreed = client.post(url, headers=headers, json={**body, "related": related, "expected_hash": row["sha256"]})
    assert agreed.status_code == 200, agreed.text
    assert register.get(sid).approval_status == "rejected"
