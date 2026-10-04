"""Red team, REF S23 round 9 (S8): a file replaced on disk outside content management cannot be decided on until it
is published as a new version. The content route refuses it (round 8); the governance route and the declared
approve_source / reject_source actions check only the record's SHA-256, never that the record's text is still there."""
from __future__ import annotations

import hashlib
import os
import socket

import pytest
from fastapi.testclient import TestClient

from tests.iam_helpers import sign_in
from tests.test_space_leaks import hermetic, refuse

HEAD = {"X-OpsAtlas-Space": "acme"}
ORIGINAL = "# Pricing guide\n\nThe Acme plan costs ten pounds a month.\n\nIt includes support.\n"
REPLACED = "# Pricing guide\n\nThe Acme plan is free for everyone, forever.\n\nIt includes support.\n"


@pytest.fixture
def acme(tmp_path, monkeypatch):
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
        assert client.post("/api/spaces", json={"name": "Acme"}).status_code == 200
        core = app.state.cores["acme"]
        hermetic(core)
        up = client.post("/api/sources/upload", files={"file": ("pricing.md", ORIGINAL.encode(), "text/markdown")},
                         headers=HEAD)
        assert up.status_code == 200, up.text
        sid = up.json()["id"]
        client.post(f"/api/sources/{sid}/ingest", headers=HEAD)
        yield client, core, sid


def _replace_on_disk(core, sid: str) -> str:
    """An operator restores or edits the file on disk, outside content management. The record still names the old
    text; the view shows the file as it is."""
    register = core.state.register
    record = register.get(sid)
    assert record.content_sha256 == hashlib.sha256(ORIGINAL.encode()).hexdigest()
    register.file_path(sid).write_bytes(REPLACED.encode())
    return record.content_sha256


def _status(client, sid: str) -> str:
    rows = client.get("/api/sources", headers=HEAD).json()
    return next(r["approval_status"] for r in rows if r["id"] == sid)


def test_s23_round9_control_content_route_refuses_replaced_file(acme):
    """Control: the content route refuses a decision on a replaced file (round 8's fix), and nothing changes."""
    client, core, sid = acme
    record_sha = _replace_on_disk(core, sid)
    before = _status(client, sid)
    assert before != "approved"
    r = client.post(f"/api/content/documents/{sid}/approve", json={"expected_sha": record_sha}, headers=HEAD)
    assert r.status_code >= 400, r.text
    assert _status(client, sid) == before


def test_s23_round9_governance_route_approves_replaced_file(acme):
    """S8: the governance page's approve, naming the record's SHA-256 as the page does (s.content_sha256), approves a
    document whose file was replaced on disk. The reviewer read the replaced file (the governance document view
    shows it as it is); answers keep using the record's old passages."""
    client, core, sid = acme
    record_sha = _replace_on_disk(core, sid)
    shown = client.get(f"/api/governance/sources/{sid}/document", headers=HEAD).json()["text"]
    assert "free for everyone" in shown  # what the reviewer reads on the governance page
    before = _status(client, sid)
    assert before != "approved"
    r = client.post(f"/api/governance/sources/{sid}/approve", json={"sha": record_sha}, headers=HEAD)
    assert r.status_code == 409, f"a replaced file was decided on: {r.status_code} {r.text[:200]}"
    assert _status(client, sid) == before


def test_s23_round9_governance_route_rejects_replaced_file(acme):
    """S8: the same for a rejection."""
    client, core, sid = acme
    record_sha = _replace_on_disk(core, sid)
    before = _status(client, sid)
    r = client.post(f"/api/governance/sources/{sid}/reject", json={"sha": record_sha}, headers=HEAD)
    assert r.status_code == 409, f"a replaced file was decided on: {r.status_code} {r.text[:200]}"
    assert _status(client, sid) == before


def test_s23_round9_actions_route_approves_replaced_file(acme):
    """S8: the declared approve_source action, run through the ontology actions route, checks only the record's
    SHA-256 (names_current_text), so it approves a replaced file too."""
    client, core, sid = acme
    record_sha = _replace_on_disk(core, sid)
    before = _status(client, sid)
    r = client.post("/api/ontology/actions/approve_source", json={"params": {"source_id": sid, "sha": record_sha}},
                    headers=HEAD)
    assert _status(client, sid) == before, f"a replaced file was decided on: {r.status_code} {r.text[:200]}"
