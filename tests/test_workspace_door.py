"""The workspace's door (REF S23, S7, the Human's decision of 4 October 2026) and approvals that name their text (S8).

Promises:
- S7 Every request that may change something takes the workspace's one lock at the door, once, before any handler
  runs; every job that writes (start-up, a new space) holds it from its start. The governed stores (each space's
  register, passages and content store, the Sales knowledge store and the governance desk) refuse a write from
  anything that does not hold it. Requests that only read never take it and never wait.
- S8 Every approval names the text it approves (its SHA-256); an approval of any other text is refused, and nothing
  changes.

Hermetic: the full Sales app on a temporary workspace, sockets refused, models faked. Every thread is a daemon thread
and every join has a timeout.
"""
from __future__ import annotations

import ast
import inspect
import os
import socket
import threading
from pathlib import Path

import pytest

from assistant.storage import NotHolding, WriteDoor, holds, locked
from tests.door_helpers import as_job, decide, writing
from tests.test_space_leaks import refuse

REPO = Path(__file__).resolve().parents[1]
ACME = {"X-OpsAtlas-Space": "acme"}
TEXT = b"# Pricing\n\nAlpha is the first plan.\n"


@pytest.fixture
def sales(sales_workspace):
    """The shared builder's workspace (REF S59): set-up goes through the routes, never by writing stores."""
    return sales_workspace


def _document(workspace, approval="approved", text=TEXT):
    """A document uploaded, ingested and (unless pending) approved through the routes, as a person would."""
    return workspace.core, workspace.document(text, title="Pricing", approve=approval == "approved")


def _hold(root):
    """Another writer: a daemon thread holding the workspace's lock until released."""
    held, release = threading.Event(), threading.Event()

    def holder():
        with locked(root / "workspace"):
            held.set()
            release.wait(10)
    thread = threading.Thread(target=holder, daemon=True)
    thread.start()
    assert held.wait(5)
    return release, thread


def _within(seconds, function):
    """Whether ``function`` finished within ``seconds`` (it runs on in a daemon thread if not)."""
    done, out = threading.Event(), {}

    def run():
        out["value"] = function()
        done.set()
    threading.Thread(target=run, daemon=True).start()
    return done.wait(seconds), out


# ---- S7: the stores check the lock -----------------------------------------------------------------------------

def test_every_governed_write_refuses_without_the_lock(sales):
    app, client, root = sales
    core = app.state.cores["acme"]
    for store in (core.state.register, core.state.section_store, app.state.sales, app.state.governance_desk):
        marked = [name for name, member in inspect.getmembers(type(store)) if getattr(member, "__writes__", False)]
        assert marked, f"{type(store).__name__} declares no writes"
        for name in marked:
            method = getattr(store, name)
            needed = [p for p in inspect.signature(method).parameters.values()
                      if p.default is p.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
            with pytest.raises(NotHolding):
                method(*["x"] * len(needed))
    content = core.state.content.store  # the content store: refused at its connection, whichever statement
    for write in (lambda: content.save_document("x", status="draft"), lambda: content.log("x", "someone", "edited"),
                  lambda: content.add_group("Group", None), lambda: content.set_meta("key", "value"),
                  lambda: content.forget_document("x"), lambda: content.see("x", {"key": "k"}, None)):
        with pytest.raises(NotHolding):
            write()
    assert content.meta("key") is None
    with writing(app):
        content.set_meta("key", "value")
    assert content.meta("key") == "value"


WRITES = {"write_json", "atomic_write_bytes", "atomic_write_text", "write_text", "write_bytes", "unlink", "rmtree",
          "copy2", "move"}
STORES = {"src/assistant/sources/register.py": "SourceRegister", "src/assistant/ingestion/store.py": "SectionStore",
          "services/opsatlas_sales/knowledge.py": "Knowledge", "services/opsatlas_sales/governance.py": "GovernanceDesk"}


def _writes_directly(function) -> bool:
    for node in ast.walk(function):
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if name in WRITES or (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                                  and node.func.value.id == "os" and name == "replace"):
                return True
            if name == "open" and any(isinstance(a, ast.Constant) and str(a.value)[:1] in "aw" for a in node.args):
                return True
    return False


def test_no_write_in_a_governed_store_is_left_unmarked():
    """Every function of a governed store that writes is marked (it checks the lock), or is a helper called only from
    marked ones. The content store writes only through its one connection, which checks the lock."""
    for path, cls in STORES.items():
        tree = ast.parse((REPO / path).read_text())
        body = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls).body
        functions = {f.name: f for f in body if isinstance(f, ast.FunctionDef)}
        marked = {name for name, f in functions.items() if any(getattr(d, "id", None) == "writes" for d in f.decorator_list)}

        def callers(helper):
            return [name for name, f in functions.items() for n in ast.walk(f) if isinstance(n, ast.Attribute)
                    and n.attr == helper and name != helper]
        for name, function in functions.items():
            if name == "__init__" or name in marked or not _writes_directly(function):
                continue
            calling = callers(name)
            assert calling and all(c in marked for c in calling), f"{cls}.{name} writes without checking the lock"
    store = ast.parse((REPO / "src/assistant/content/store.py").read_text())
    connecting = {f.name for f in ast.walk(store) if isinstance(f, ast.FunctionDef)
                  for n in ast.walk(f) if isinstance(n, ast.Attribute) and n.attr == "connect"}
    assert connecting == {"_db", "forget_document"}, connecting


# ---- S7: the door ------------------------------------------------------------------------------------------------

def test_a_request_that_may_change_something_holds_the_lock_and_a_read_does_not(sales):
    app, client, root = sales
    lock = root / "workspace"

    @app.post("/api/door-test")
    def changes():
        return {"holds": holds(lock)}

    @app.get("/api/door-test")
    def reads():
        return {"holds": holds(lock)}
    app.router.routes[:0] = [app.router.routes.pop(), app.router.routes.pop()]  # ahead of the page's catch-all
    assert client.post("/api/door-test").json() == {"holds": True}
    assert client.get("/api/door-test").json() == {"holds": False}
    door = WriteDoor(None, lock, passes=("/api/ask", "/api/auth"))
    scope = {"type": "http", "method": "POST"}
    assert door.opens_for({**scope, "path": "/api/ask"}) is None
    assert door.opens_for({**scope, "path": "/api/auth/login"}) is None
    assert door.opens_for({**scope, "path": "/api/asking"}) == lock  # a pass names a route, not a prefix of a word
    assert door.opens_for({**scope, "method": "GET", "path": "/api/content/documents"}) is None


def test_a_space_request_writes_through_the_door_and_a_direct_write_is_refused(sales):
    app, client, root = sales
    core, source_id = _document(sales)
    draft = "# Pricing\n\nBeta is the first plan.\n"
    with pytest.raises(NotHolding):
        core.state.content.save_draft(source_id, draft)
    response = client.put(f"/api/content/documents/{source_id}/draft", json={"text": draft}, headers=ACME)
    assert response.status_code == 200, response.text
    assert core.state.content.store.document(source_id)["draft_text"] == draft


def test_a_reader_never_waits_while_a_writer_holds_the_lock(sales):
    app, client, root = sales
    core, source_id = _document(sales, approval="pending")
    client.get("/api/content/documents")  # warm the governance scan, so only the lock could make a read slow
    release, holder = _hold(root)
    try:
        for path, headers in ((f"/api/content/documents/{source_id}", ACME), ("/api/content/documents", ACME),
                              ("/api/content/documents", {}), ("/api/content/library", ACME), ("/api/sources", ACME)):
            finished, out = _within(5, lambda p=path, h=headers: client.get(p, headers=h).status_code)
            assert finished, f"GET {path} waited for the writer's lock"
            assert out["value"] == 200, path
    finally:
        release.set()
        holder.join(5)


def test_writes_take_turns(sales):
    app, client, root = sales
    core, source_id = _document(sales)
    draft = "# Pricing\n\nGamma is the first plan.\n"
    release, holder = _hold(root)
    try:
        finished, out = _within(1.5, lambda: client.put(f"/api/content/documents/{source_id}/draft", json={"text": draft},
                                                        headers=ACME).status_code)
        assert not finished, "a write went in while another writer held the workspace's lock"
        assert (core.state.content.store.document(source_id) or {}).get("draft_text") is None
    finally:
        release.set()
        holder.join(5)
    for _ in range(100):  # once the lock is free the write goes in
        if out.get("value") is not None:
            break
        threading.Event().wait(0.05)
    assert out.get("value") == 200
    assert core.state.content.store.document(source_id)["draft_text"] == draft


def test_the_workspace_builds_under_its_lock(tmp_path, monkeypatch):
    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    os.environ["SME_TIBI_VOICE_URL"] = "http://127.0.0.1:9"
    os.environ["SALES_GOVERNANCE_AUTO_REVIEW"] = "0"
    app = create_sales_app(tmp_path / "sales")  # seeding writes the governed stores: refused without the lock
    assert app.state.sales.records(), "the workspace was not seeded"
    assert not holds(tmp_path / "sales" / "workspace"), "start-up kept the lock"


# ---- S8: an approval names the text it approves --------------------------------------------------------------------

def test_an_approval_names_the_text_it_approves(sales):
    app, client, root = sales
    core, source_id = _document(sales, approval="pending")
    register = core.state.register
    sha = register.get(source_id).content_sha256
    assert client.post(f"/api/governance/sources/{source_id}/approve", headers=ACME).status_code == 422
    refused = client.post(f"/api/governance/sources/{source_id}/approve", json={"sha": "0" * 64}, headers=ACME)
    assert refused.status_code == 409, refused.text
    assert register.get(source_id).approval_status == "pending"
    approved = client.post(f"/api/governance/sources/{source_id}/approve", json={"sha": sha}, headers=ACME)
    assert approved.status_code == 200, approved.text
    assert register.get(source_id).approval_status == "approved"
    rejected = client.post(f"/api/governance/sources/{source_id}/reject", json={"sha": "0" * 64}, headers=ACME)
    assert rejected.status_code == 409 and register.get(source_id).approval_status == "approved"


def test_an_approval_of_the_version_read_is_refused_once_another_is_written(sales):
    app, client, root = sales
    core, source_id = _document(sales, approval="pending")
    register, content = core.state.register, core.state.content
    read = register.get(source_id).content_sha256  # the reviewer reads this version
    as_job(core, content._write_version, register.get(source_id), b"# Pricing\n\nDelta is the first plan.\n",
           approve=False)  # a new version lands, unapproved
    assert register.get(source_id).content_sha256 != read
    refused = client.post(f"/api/governance/sources/{source_id}/approve", json={"sha": read}, headers=ACME)
    assert refused.status_code == 409, refused.text
    assert register.get(source_id).approval_status != "approved", "the approval landed on a text nobody read"


def test_the_approve_action_names_the_text_too(sales):
    app, client, root = sales
    core, source_id = _document(sales, approval="pending")
    register = core.state.register
    url = "/api/ontology/actions/approve_source"
    unnamed = client.post(url, json={"params": {"source_id": source_id}}, headers=ACME).json()
    assert unnamed["outcome"] != "ok"
    stale = client.post(url, json={"params": {"source_id": source_id, "sha": "0" * 64}}, headers=ACME).json()
    assert stale["outcome"] != "ok" and stale["failed_rule"] == "names_current_text"
    assert register.get(source_id).approval_status == "pending"
    named = client.post(url, json={"params": {"source_id": source_id, "sha": register.get(source_id).content_sha256}},
                        headers=ACME).json()
    assert named["outcome"] == "ok", named
    assert register.get(source_id).approval_status == "approved"


def test_a_rename_that_would_change_the_text_is_refused(sales):
    """A rename changes the title and nothing else (S1, S8, red team round 8): where the workspace's title hook would
    write a different body (a stale copy of the record), the rename is refused and the live approved text stands."""
    app, client, root = sales
    core, source_id = _document(sales)
    register, content = core.state.register, core.state.content
    before = register.read_content(source_id)
    content.hooks["retitle"] = lambda source, title: f"# {title}\n\nAn older body nobody approved.\n"
    try:
        refused = client.post(f"/api/content/documents/{source_id}/rename", json={"title": "Prices"}, headers=ACME)
    finally:
        content.hooks["retitle"] = None
    assert refused.status_code == 409, refused.text
    assert register.read_content(source_id) == before and register.get(source_id).approval_status == "approved"


def test_an_approval_cannot_be_written_around_decide(sales):
    """The register changes a document's approval only through decide, naming its text, or a commit naming a new
    text (S8, the Human's decision after round 9): a plain update of the approval is refused, even under the lock."""
    from assistant.sources.register import ApprovalOutsideDecide
    app, client, root = sales
    core, source_id = _document(sales, approval="pending")
    register = core.state.register
    with writing(core):
        with pytest.raises(ApprovalOutsideDecide):
            register.update(source_id, approval_status="approved")
        assert register.get(source_id).approval_status == "pending"
        register.update(source_id, approval_status="pending", title="Pricing")  # no change of approval: allowed
        register.decide(source_id, "approved", register.get(source_id).content_sha256)
    assert register.get(source_id).approval_status == "approved"


def test_a_return_names_the_draft_returned(sales):
    """A return to the author names the draft the reviewer read (S8): once the author resubmits a newer draft, a
    return naming the older one is refused, and one naming the newer is applied."""
    app, client, root = sales
    core, source_id = _document(sales)
    content = core.state.content
    url = f"/api/content/documents/{source_id}"
    with writing(core):
        content.save_draft(source_id, "# Pricing\n\nBeta is the first plan.\n")
        content.submit(source_id)
    read = content.store.document(source_id)["draft_sha"]  # the reviewer reads this draft
    with writing(core):
        content.save_draft(source_id, "# Pricing\n\nGamma is the first plan.\n")
        content.submit(source_id)
    stale = client.post(f"{url}/return", json={"draft_sha": read, "note": "About Beta"}, headers=ACME)
    assert stale.status_code == 409, stale.text
    assert content.store.document(source_id)["status"] == "submitted"
    current = content.store.document(source_id)["draft_sha"]
    assert client.post(f"{url}/return", json={"draft_sha": current}, headers=ACME).status_code == 200
    assert content.store.document(source_id)["status"] == "draft"


def test_a_decision_stands_when_a_step_after_it_fails(sales):
    """An action's handler is its decision; its side effects are the steps after it (S5, S8, red team round 11). When
    one fails, the approval stands, the caller is told it took effect, and the step is noted in the action log."""
    app, client, root = sales
    core, source_id = _document(sales, approval="pending")
    engine = core.state.actions
    real = engine._side_effects["record_analytics_event"]
    engine._side_effects["record_analytics_event"] = lambda context, result: (_ for _ in ()).throw(OSError("events down"))
    try:
        response = decide(client, source_id, headers=ACME)
    finally:
        engine._side_effects["record_analytics_event"] = real
    assert response.status_code == 200, response.text
    assert core.state.register.get(source_id).approval_status == "approved"
    noted = client.get("/api/ontology/actions/log", headers=ACME).json()["executions"][0]
    assert noted["outcome"] == "ok" and "record_analytics_event" in noted["message"]


def test_tibis_check_of_a_governance_answer_passes_the_door(sales):
    """Tibi checks a governance answer before proposing it; the check only reads, so it passes the door and never waits
    behind a writer (the independent review's R3)."""
    from assistant.api.app import DOOR_PASSES
    app, client, root = sales
    door = WriteDoor(None, root / "workspace", passes=DOOR_PASSES)
    assert door.opens_for({"type": "http", "method": "POST", "path": "/api/sales/governance/verify"}) is None
    release, holder = _hold(root)
    try:
        finished, out = _within(5, lambda: client.post("/api/sales/governance/verify", json={
            "issue_key": "none", "resolution": {}, "answer": "x"}).status_code)
        assert finished, "the check waited for a writer's lock"
        assert out["value"] in (403, 409), out
    finally:
        release.set()
        holder.join(5)
