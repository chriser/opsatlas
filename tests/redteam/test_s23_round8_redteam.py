"""Red team, round 8 (REF S23, the door): hermetic tests that try to break S1-S8 of the staged publish.

No network, no live services, no model: a hermetic Sales workspace in a TestClient, every writer a real HTTP request
through the door.
"""
from __future__ import annotations

import hashlib
import os
import socket

import pytest
from fastapi.testclient import TestClient

from tests.iam_helpers import sign_in
from tests.test_space_leaks import hermetic, refuse


def sha(data) -> str:
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()


@pytest.fixture
def sales(tmp_path, monkeypatch):
    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    os.environ["SME_TIBI_VOICE_URL"] = "http://127.0.0.1:9"
    os.environ["SALES_GOVERNANCE_AUTO_REVIEW"] = "0"
    app = create_sales_app(tmp_path / "sales")
    hermetic(app)
    with TestClient(app) as client:
        client.headers.update({"Authorization": f"Bearer {sign_in(client, app)}"})
        yield client, app


def _acme(client, app):
    assert client.post("/api/spaces", json={"name": "Acme"}).status_code == 200
    core = app.state.cores["acme"]
    hermetic(core)
    return core, {"X-OpsAtlas-Space": "acme"}


def _upload(client, head, name, data):
    up = client.post("/api/sources/upload", files={"file": (name, data, "text/markdown")}, headers=head)
    assert up.status_code == 200, up.text
    body = up.json()
    sid = body["id"] if "id" in body else body["source"]["id"]
    client.post(f"/api/sources/{sid}/ingest", headers=head)
    return sid


def _approved_record(client, app):
    """A Sales Knowledge record whose document is in the Product Guide's core and approved (approved here if needed,
    through the content view, naming the text read)."""
    register = app.state.register
    rows = [r for r in app.state.sales.records() if register.get(r["source_id"]) is not None]
    for row in rows:
        if register.get(row["source_id"]).approval_status == "approved":
            return row["source_id"]
    for row in rows:
        sid = row["source_id"]
        shown = client.get(f"/api/content/documents/{sid}").json()["published"]
        if client.post(f"/api/content/documents/{sid}/approve", json={"expected_sha": shown["sha"]}).status_code == 200:
            return sid
    pytest.skip("no Knowledge record could be approved in this seed")


def test_s23_round8_rename_after_a_lost_records_step_rewrites_the_live_approved_version_from_the_stale_record(sales):
    """S5 lets the workspace's own records fail after a commit ("published whatever fails after it"). The record then
    still holds the previous body, and a later rename builds its new, approved version from that stale record: the
    approved version B is replaced by the old body under a new heading, approved by nobody (S1, S8)."""
    client, app = sales
    from services.opsatlas_sales.spaces import PRODUCT
    r = client.post(f"/api/iam/spaces/{PRODUCT}/solo-operator", json={"enabled": True, "reason": "red team, one operator"})
    assert r.status_code == 200, r.text
    sid = _approved_record(client, app)
    content = app.state.content

    doc = client.get(f"/api/content/documents/{sid}").json()
    published = doc["published"]["text"]
    heading = published.split("\n", 1)[0]
    new_body = "RED-TEAM-B: the widget now ships in green, never in blue."
    draft = f"{heading}\n\n{new_body}\n"
    r = client.put(f"/api/content/documents/{sid}/draft", json={"text": draft, "base_sha": doc["published"]["sha"]})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/content/documents/{sid}/submit", json={"note": ""})
    assert r.status_code == 200, r.text

    original = content.hooks["published"]

    def lost(*args, **kwargs):  # one ordinary fault: the workspace's records file is not written
        raise OSError("the workspace's records could not be written")

    content.hooks["published"] = lost
    try:
        r = client.post(f"/api/content/documents/{sid}/publish", json={"draft_sha": sha(draft)})
        assert r.status_code == 200, r.text  # S5: the version is live whatever fails after the commit
    finally:
        content.hooks["published"] = original
    live = client.get(f"/api/content/documents/{sid}").json()["published"]["text"]
    assert new_body in live
    assert app.state.register.get(sid).approval_status == "approved"
    old_body_line = next((line for line in published.splitlines()[1:] if line.strip()), "")

    r = client.post(f"/api/content/documents/{sid}/rename", json={"title": "Renamed by the red team"})
    assert r.status_code == 200, r.text
    after = client.get(f"/api/content/documents/{sid}").json()["published"]["text"]
    record = app.state.register.get(sid)
    assert new_body in after, (
        "the rename wrote a new approved version from the workspace's stale record: the approved version B is gone "
        f"and the old body is live again (approval={record.approval_status}, old line back={old_body_line in after})")


def test_s23_round8_an_approval_naming_the_shown_text_approves_the_records_other_text(sales):
    """S1 shows a file replaced on disk as it is; the reviewer reads it and approves naming its SHA-256. The content
    route checks that SHA against the shown text, then approves the record's own SHA instead: a text nobody named is
    approved and its passages are served (S8)."""
    client, app = sales
    core, head = _acme(client, app)
    first = b"# Pricing\n\nThe Acme widget costs 10 pounds.\n"
    sid = _upload(client, head, "pricing.md", first)
    register = core.state.register
    assert register.get(sid).approval_status != "approved"

    register.file_path(sid).write_bytes(b"# Pricing\n\nThe Acme widget costs 99 pounds.\n")  # outside content management
    shown = client.get(f"/api/content/documents/{sid}", headers=head).json()["published"]
    assert "99 pounds" in shown["text"]

    r = client.post(f"/api/content/documents/{sid}/approve", json={"expected_sha": shown["sha"]}, headers=head)
    record = register.get(sid)
    served = " ".join(s.text for s in core.state.section_store.list_for_source(sid, sha=record.content_sha256))
    assert not (record.approval_status == "approved" and record.content_sha256 != shown["sha"]), (
        f"approval named {shown['sha'][:12]} (the text shown, 99 pounds) but the record approved is "
        f"{record.content_sha256[:12]} (status {r.status_code}); passages now served: {served[:120]!r}")


def test_s23_round8_a_persons_rejection_through_the_actions_route_names_no_text(sales):
    """The registry says a person's rejection names the text rejected; only a withdrawal by the workspace names none.
    Through the ontology actions route a signed-in person rejects a document without naming any text (S8)."""
    client, app = sales
    core, head = _acme(client, app)
    sid = _upload(client, head, "terms.md", b"# Terms\n\nPayment is due in 30 days.\n")
    rows = client.get("/api/sources", headers=head).json()
    sha_now = next(r["content_sha256"] for r in rows if r["id"] == sid)
    assert client.post(f"/api/governance/sources/{sid}/approve", json={"sha": sha_now}, headers=head).status_code == 200
    r = client.post("/api/ontology/actions/reject_source", json={"params": {"source_id": sid}}, headers=head)
    assert core.state.register.get(sid).approval_status == "approved", (
        f"a person's rejection naming no text was accepted ({r.status_code}): {r.text[:160]}")
