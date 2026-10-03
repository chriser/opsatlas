"""Publishing a new version of a document (REF H3b, P9; the Human's decision after the red team's fifth round): no reader
ever finds new text under the old approval, and a failed publish leaves nothing of the new text behind, in the
register, the passages or the facts map. This holds with scope on or off."""
import os
import socket

import pytest
from fastapi.testclient import TestClient
from iam_helpers import sign_in
from test_space_leaks import hermetic, refuse

HEAD = {"X-OpsAtlas-Space": "acme"}
V1 = b"# Purchase orders\n\nThe procurement manager approves every purchase order.\n"
V2 = b"# Purchase orders\n\nThe finance director approves every purchase order.\n"


@pytest.fixture
def acme(tmp_path, monkeypatch):
    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    os.environ.update({"SME_TIBI_VOICE_URL": "http://127.0.0.1:9", "SALES_GOVERNANCE_AUTO_REVIEW": "0"})
    app = create_sales_app(tmp_path / "sales")
    hermetic(app)
    with TestClient(app) as client:
        client.headers.update({"Authorization": f"Bearer {sign_in(client, app)}"})
        assert client.post("/api/spaces", json={"name": "Acme"}).status_code == 200
        core = app.state.cores["acme"]
        hermetic(core)
        up = client.post("/api/sources/upload", files={"file": ("po.md", V1, "text/markdown")}, headers=HEAD)
        sid = up.json()["id"] if "id" in up.json() else up.json()["source"]["id"]
        assert client.post(f"/api/sources/{sid}/ingest", headers=HEAD).status_code == 200
        assert client.post(f"/api/governance/sources/{sid}/approve", headers=HEAD).status_code == 200
        yield core, sid


def test_the_record_is_pending_at_its_new_version_before_the_new_text_is_written(acme):
    core, sid = acme
    register, seen = core.state.register, []
    real_write = register.write_content

    def write(source_id, data):
        if data == V2:
            record = register.get(source_id)
            seen.append((record.version, record.approval_status))
        real_write(source_id, data)
    register.write_content = write
    try:
        core.state.content._write_version(register.get(sid), V2, approve=True)
    finally:
        register.write_content = real_write
    assert seen == [(2, "pending")], "the new text was written while the record still showed the old approval"
    assert (register.get(sid).version, register.get(sid).approval_status) == (2, "approved")


def test_a_failed_publish_leaves_nothing_of_the_new_text(acme):
    import assistant.content.service as content_module
    core, sid = acme
    register, real_ingest, calls = core.state.register, content_module.ingest_source, {"n": 0}

    def ingest_fails_once(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            core.state.rebuild_ontology()  # another approval's rebuild lands while the new text is there
            raise RuntimeError("disk full")
        return real_ingest(*args, **kwargs)
    content_module.ingest_source = ingest_fails_once
    try:
        with pytest.raises(content_module.ContentError):
            core.state.content._write_version(register.get(sid), V2, approve=True)
    finally:
        content_module.ingest_source = real_ingest
    record = register.get(sid)
    assert (record.version, record.approval_status) == (1, "approved") and register.read_content(sid) == V1
    assert "finance director" not in " ".join(s.text for s in core.state.section_store.list_for_source(sid)).lower()
    approved = [r for r in register.list() if r.approval_status == "approved"]
    assert core.state.answer._facts_in_step(approved), "the facts map was not rebuilt after the failed publish"
