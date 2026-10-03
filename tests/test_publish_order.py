"""Publishing a new version of a document as a staged publish (REF S23, the Human's decision of 3 October 2026): the
new text and passages are staged beside the live ones, the record's write commits them, and they are moved into place;
until the commit nothing live changes, and a reader holding a record takes only that record's text and passages (one
holding the new record moves anything not yet moved). A publish that fails leaves the live version whole; one whose
follow-up steps fail afterwards is still published. Scope on or off."""
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
    real_stage = store.stage_for_source

    def stage(source_id, sections, sha=None):  # the new text and passages are staged; the record is about to be written
        real_stage(source_id, sections, sha=sha)
        record = register.get(source_id)
        try:
            text = register.read_content(source_id, sha=record.content_sha256)
        except ContentReplaced:
            text = b""
        passages = " ".join(s.text for s in store.list_for_source(source_id, sha=record.content_sha256)).lower()
        seen.append((record.version, record.approval_status, text == V1, "procurement manager" in passages))
    store.stage_for_source = stage
    try:
        core.state.content._write_version(register.get(sid), V2, approve=True)
    finally:
        store.stage_for_source = real_stage
    assert seen == [(1, "approved", True, True)], seen  # a reader holding version 1 still takes version 1, whole
    record = register.get(sid)
    assert (record.version, record.approval_status) == (2, "approved") and "finance director" in _texts(core, sid, record)


def test_a_failed_swap_leaves_the_live_version_whole(acme):
    from assistant.content.service import ContentError
    core, sid = acme
    register = core.state.register
    real_update, calls = register.update, {"n": 0}

    def commit_fails_once(source_id, **fields):  # everything is staged; the record's write (the commit) fails
        if "content_sha256" in fields and not calls["n"]:
            calls["n"] += 1
            core.state.rebuild_ontology()  # another approval's rebuild lands while the new version is staged
            raise OSError("disk full")
        return real_update(source_id, **fields)
    register.update = commit_fails_once
    try:
        with pytest.raises(ContentError):
            core.state.content._write_version(register.get(sid), V2, approve=True)
    finally:
        register.update = real_update
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
    register, calls, content = core.state.register, {"n": 0}, core.state.content
    real = content.rebuild_facts

    def fails_once():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("database is locked")
        return real()
    content.rebuild_facts = fails_once
    try:
        record = content._write_version(register.get(sid), V2, approve=True)
    finally:
        content.rebuild_facts = real
    assert (record.version, record.approval_status) == (2, "approved")  # published, not reported as failed
    approved = [r for r in register.list() if r.approval_status == "approved"]
    assert core.state.answer._facts_in_step(approved), "the rebuild was not tried again"


def test_a_search_while_a_committed_version_cannot_be_moved_does_not_lose_the_document(acme):
    """The record is written (the new version committed) but its passages cannot be moved into place for a while, so a
    search finds none for the record it holds. That snapshot is not kept: once the move succeeds, the next search
    finds the document's new passages, although no fingerprint changed in between (REF S23)."""
    core, sid = acme
    register, store, index = core.state.register, core.state.content.section_store, core.state.answer.retrieval.index
    real_promote = store.promote_for_source
    store.promote_for_source = lambda source_id: (_ for _ in ()).throw(OSError("busy"))
    try:
        core.state.content._write_version(register.get(sid), V2, approve=True)  # committed; the move failed
        assert not [s for r, s in index.current().items if r.id == sid]  # no passages for version 2 yet
    finally:
        store.promote_for_source = real_promote
    found = [s.text for r, s in index.current().items if r.id == sid]
    assert found and "finance director" in " ".join(found).lower(), "the document stayed out of search"


def test_a_reader_holding_the_previous_record_gets_none_of_the_new_text(acme):
    """After a publish, a reader that still holds the previous record (taken before the commit) asks for its text and
    passages and gets none: never the new version's under the old record (REF S23, S2)."""
    core, sid = acme
    register, store = core.state.register, core.state.section_store
    held = register.get(sid)
    core.state.content._write_version(held, V2, approve=True)
    with pytest.raises(ContentReplaced):
        register.read_content(sid, sha=held.content_sha256)
    assert store.list_for_source(sid, sha=held.content_sha256) == []
