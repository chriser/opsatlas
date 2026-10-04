"""Red team, REF S23 round 12 (commit 5a357f3): the core only (the door, the staged publish, the register's decision)."""
from __future__ import annotations

import hashlib
import os
import socket
import threading
import time

import pytest

from tests.door_helpers import as_job, writing
from tests.iam_helpers import sign_in
from tests.test_space_leaks import hermetic, refuse

STATED_LIMIT = pytest.mark.xfail(strict=True, reason="REF S23 stated limit (low), round 12: recorded under the exit rule")

TEXT = "# Handbook\n\nThe pump is inspected every week by the duty engineer.\n\nValves are checked monthly.\n"


def sha(data) -> str:
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()


@pytest.fixture
def acme(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    os.environ["SME_TIBI_VOICE_URL"] = "http://127.0.0.1:9"
    os.environ["SALES_GOVERNANCE_AUTO_REVIEW"] = "0"
    app = create_sales_app(tmp_path / "sales")
    hermetic(app)
    with TestClient(app, raise_server_exceptions=False) as client:
        client.headers.update({"Authorization": f"Bearer {sign_in(client, app)}"})
        assert client.post("/api/spaces", json={"name": "Acme"}).status_code == 200
        core = app.state.cores["acme"]
        hermetic(core)
        head = {"X-OpsAtlas-Space": "acme"}
        client.headers.update(head)
        up = client.post("/api/sources/upload", files={"file": ("handbook.md", TEXT.encode(), "text/markdown")})
        assert up.status_code == 200, up.text
        sid = up.json()["id"]
        assert client.post(f"/api/sources/{sid}/ingest").status_code == 200
        yield client, app, core, sid


def _activity_actions(core, sid) -> list[str]:
    return [row.get("action") for row in core.state.content.activity(sid)]


# ---- S8 / S5: a decision that took effect is reported refused when the action log's write fails -------------------

@STATED_LIMIT
def test_s23_round12_content_approve_reported_failed_after_it_took_effect(acme, monkeypatch):
    """One ordinary fault (the action log's append fails) after the approve_source handler has decided: the content
    route reports an error, yet the document is approved, and its activity never records the approval."""
    client, app, core, sid = acme
    engine = core.state.content.actions

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(engine.action_log, "append", boom)
    response = client.post(f"/api/content/documents/{sid}/approve", json={"expected_sha": sha(TEXT)})
    record = core.state.register.get(sid)
    if response.status_code >= 400:
        assert record.approval_status != "approved", (
            f"reported {response.status_code} ({response.text[:120]}) but the approval landed; "
            f"activity: {_activity_actions(core, sid)}")


@STATED_LIMIT
def test_s23_round12_governance_approve_reported_failed_after_it_took_effect(acme, monkeypatch):
    """The same fault on the governance route (the reviewer's page): an error is shown for a change that was made."""
    client, app, core, sid = acme
    engine = core.state.content.actions

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(engine.action_log, "append", boom)
    response = client.post(f"/api/governance/sources/{sid}/approve", json={"sha": sha(TEXT)})
    record = core.state.register.get(sid)
    if response.status_code >= 400:
        assert record.approval_status != "approved", f"reported {response.status_code} but the approval landed"


# ---- S8: update accepts a change of approval that names no new text -------------------------------------------------

@STATED_LIMIT
def test_s23_round12_update_changes_approval_naming_the_same_text(acme):
    """The register's update lets a write carrying the record's own content_sha256 change the approval: not a commit
    (no new text), not decide (no check that the text is stored), so a file replaced on disk is approved."""
    client, app, core, sid = acme
    register = core.state.register
    record = register.get(sid)
    register.file_path(sid).write_bytes(b"# Handbook\n\nReplaced on disk, outside content management.\n")
    assert register.names_text(sid, record.content_sha256) is not None  # decide would refuse this text
    from assistant.sources.register import ApprovalOutsideDecide
    with writing(core):
        try:
            register.update(sid, approval_status="approved", content_sha256=record.content_sha256)
        except ApprovalOutsideDecide:
            return
    assert register.get(sid).approval_status != "approved", "approval changed outside decide, on a replaced file"


# ---- S7: readers and passes never wait while a writer holds the door ------------------------------------------------

def test_s23_round12_readers_never_wait_for_the_door(acme):
    client, app, core, sid = acme
    held, release = threading.Event(), threading.Event()

    def job():
        with writing(core):
            held.set()
            release.wait(10)
    holder = threading.Thread(target=job, daemon=True)
    holder.start()
    assert held.wait(5)
    paths = [("GET", "/api/content/documents"), ("GET", f"/api/content/documents/{sid}"),
             ("GET", f"/api/content/documents/{sid}/versions"), ("GET", "/api/content/library"),
             ("GET", "/api/sources"), ("GET", f"/api/content/documents/{sid}/activity"),
             ("POST", "/api/answers/nope/feedback"), ("POST", "/api/ask")]
    results: dict = {}

    def call(method, path):
        started = time.monotonic()
        body = {"q": "How often is the pump inspected?"} if path == "/api/ask" else {"verdict": "odd"}
        r = client.request(method, path, json=body if method == "POST" else None)
        results[path] = (r.status_code, time.monotonic() - started, r.text[:160])
    threads = [threading.Thread(target=call, args=p, daemon=True) for p in paths]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(4)
        stuck = [p for _, p in paths if p not in results]
        assert not stuck, f"waited for the door: {stuck}"
        errors = {p: v for p, v in results.items() if v[0] >= 500}
        assert not errors, f"a reader failed while a writer held the door: {errors}"
        bad = {p: v for p, v in results.items() if v[0] >= 400 and "feedback" not in p}
        assert not bad, f"a reader was refused while a writer held the door: {bad}"
    finally:
        release.set()
        holder.join(5)


# ---- S8 / S7: a rejection naming the old text races a draft publish -------------------------------------------------

def test_s23_round12_reject_old_text_races_publish(acme):
    client, app, core, sid = acme
    content = core.state.content
    for i in range(4):
        live = core.state.register.get(sid)
        old_sha = live.content_sha256
        draft = TEXT + f"\nRevision {i}: the pump is inspected daily.\n"
        as_job(core, content.save_draft, sid, draft)
        as_job(core, content.submit, sid, "")
        out: dict = {}

        def publish():
            out["publish"] = client.post(f"/api/content/documents/{sid}/publish", json={"draft_sha": sha(draft), "note": ""})

        def reject():
            out["reject"] = client.post(f"/api/governance/sources/{sid}/reject", json={"sha": old_sha})
        threads = [threading.Thread(target=publish, daemon=True), threading.Thread(target=reject, daemon=True)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        assert set(out) == {"publish", "reject"}, "a request hung"
        record = core.state.register.get(sid)
        stored = core.state.register.read_content(sid, sha=record.content_sha256)
        if out["publish"].status_code == 200:
            assert record.content_sha256 != old_sha
            assert record.approval_status == "approved", (
                f"the rejection of {old_sha[:8]} landed on the published text {record.content_sha256[:8]}")
        assert sha(stored) == record.content_sha256
