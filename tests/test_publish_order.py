"""Publishing a new version of a document as a staged publish (REF S23, the Human's decision of 3 October 2026): the
new text is prepared in memory and put in place only on approval, text then passages then the record; until the record
is written the live version stands, and a reader holding a record takes only that record's text and passages. A publish
that fails leaves the live version whole; one whose rebuild fails afterwards is still published. Scope on or off."""
import os
import socket

import pytest
from fastapi.testclient import TestClient
from iam_helpers import sign_in
from test_space_leaks import hermetic, refuse

from assistant.sources.register import ContentReplaced

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


def _texts(core, sid, record):
    return " ".join(s.text for s in core.state.section_store.list_for_source(sid, sha=record.content_sha256)).lower()


def test_the_live_version_stands_until_the_record_is_written(acme):
    core, sid = acme
    register, store, seen = core.state.register, core.state.content.section_store, []
    real_replace = store.replace_for_source

    def replace(source_id, sections, sha=None):  # the new text is in place; its passages are about to be
        record = register.get(source_id)
        try:
            register.read_content(source_id, sha=record.content_sha256)
            text = "the record's own text"
        except ContentReplaced:
            text = "none (being replaced)"
        seen.append((record.version, record.approval_status, text))
        real_replace(source_id, sections, sha=sha)
    store.replace_for_source = replace
    try:
        core.state.content._write_version(register.get(sid), V2, approve=True)
    finally:
        store.replace_for_source = real_replace
    assert seen == [(1, "approved", "none (being replaced)")], seen  # a reader holding version 1 takes nothing else
    record = register.get(sid)
    assert (record.version, record.approval_status) == (2, "approved") and "finance director" in _texts(core, sid, record)


def test_a_failed_swap_leaves_the_live_version_whole(acme):
    from assistant.content.service import ContentError
    core, sid = acme
    register, store = core.state.register, core.state.content.section_store
    real_replace, calls = store.replace_for_source, {"n": 0}

    def fails_once(source_id, sections, sha=None):
        calls["n"] += 1
        if calls["n"] == 1:
            core.state.rebuild_ontology()  # another approval's rebuild lands while the new text is in place
            raise OSError("disk full")
        real_replace(source_id, sections, sha=sha)
    store.replace_for_source = fails_once
    try:
        with pytest.raises(ContentError):
            core.state.content._write_version(register.get(sid), V2, approve=True)
    finally:
        store.replace_for_source = real_replace
    record = register.get(sid)
    assert (record.version, record.approval_status) == (1, "approved") and register.read_content(sid) == V1
    assert "procurement manager" in _texts(core, sid, record) and "finance director" not in _texts(core, sid, record)
    approved = [r for r in register.list() if r.approval_status == "approved"]
    assert core.state.answer._facts_in_step(approved)  # the record never changed, so the map never left it


def test_a_text_that_cannot_be_split_fails_before_anything_live_is_touched(acme):
    from assistant.content.service import ContentError
    core, sid = acme
    register = core.state.register
    with pytest.raises(ContentError):
        core.state.content._write_version(register.get(sid), b"   \n", approve=True)
    record = register.get(sid)
    assert (record.version, record.approval_status) == (1, "approved") and register.read_content(sid) == V1
    assert "procurement manager" in _texts(core, sid, record)


def test_a_rebuild_failing_after_the_swap_still_publishes(acme):
    core, sid = acme
    register, calls = core.state.register, {"n": 0}
    actions = core.state.content.actions
    real = actions._side_effects["rebuild_ontology"]

    def fails_once(context, result):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("database is locked")
        return real(context, result)
    actions._side_effects["rebuild_ontology"] = fails_once
    try:
        record = core.state.content._write_version(register.get(sid), V2, approve=True)
    finally:
        actions._side_effects["rebuild_ontology"] = real
    assert (record.version, record.approval_status) == (2, "approved")  # published, not reported as failed
    approved = [r for r in register.list() if r.approval_status == "approved"]
    assert core.state.answer._facts_in_step(approved), "the rebuild was not tried again"


def test_a_search_during_a_failed_swap_does_not_lose_the_document(acme):
    """The search index builds while the swap has put the new passages in place, so it finds none for the record it
    holds; the swap then fails and puts everything back, changing no fingerprint. That snapshot is not kept, so the
    next search finds the document again (REF S23)."""
    from assistant.content.service import ContentError
    core, sid = acme
    register, store, index = core.state.register, core.state.content.section_store, core.state.answer.retrieval.index
    real_replace, calls = store.replace_for_source, {"n": 0}

    def search_then_fail(source_id, sections, sha=None):
        real_replace(source_id, sections, sha=sha)
        calls["n"] += 1
        if calls["n"] == 1:
            index.current()  # a search lands now: the record is version 1, the passages are version 2's
            raise OSError("disk full")
    store.replace_for_source = search_then_fail
    try:
        with pytest.raises(ContentError):
            core.state.content._write_version(register.get(sid), V2, approve=True)
    finally:
        store.replace_for_source = real_replace
    found = [s.text for r, s in index.current().items if r.id == sid]
    assert found and "procurement manager" in " ".join(found).lower(), "the document dropped out of search"
