"""Red team, round 1, for REF S23 (staged publish). Hermetic: no network, no live services, no models.

Each test names the promise it tries to break (S1-S6 on #2140). A failing test is a break; a passing one is a control.
"""

from __future__ import annotations

import hashlib
import os
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the harness helpers live in tests/

from iam_helpers import sign_in  # noqa: E402
from test_space_leaks import hermetic, refuse  # noqa: E402

from tests.door_helpers import as_job, decide, writing

V1 = b"# Vault procedure\n\n## Steps\n\nThe clerk checks the vault using the code word ALPHA-ONE before release.\n"
V2 = b"# Vault procedure\n\n## Steps\n\nThe clerk checks the vault using the code word BRAVO-TWO before release.\n"
QUESTION = "Which code word does the clerk use to check the vault before release?"
HEAD = {"X-OpsAtlas-Space": "acme"}


def h(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Crash(BaseException):
    """The process dies here (a kill, a power cut): no ``except Exception`` runs."""


@pytest.fixture
def acme(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    os.environ["SME_TIBI_VOICE_URL"] = "http://127.0.0.1:9"
    os.environ["SALES_GOVERNANCE_AUTO_REVIEW"] = "0"
    os.environ.pop("KP_SCOPE_EVIDENCE", None)
    app = create_sales_app(tmp_path / "sales")
    hermetic(app)
    with TestClient(app) as client:
        client.headers.update({"Authorization": f"Bearer {sign_in(client, app)}"})
        assert client.post("/api/spaces", json={"name": "Acme"}).status_code == 200
        core = app.state.cores["acme"]
        hermetic(core)
        yield client, app, core


def add_doc(client, approve=True, head=HEAD, content=V1, name="vault.md") -> str:
    up = client.post("/api/sources/upload", files={"file": (name, content, "text/markdown")}, headers=head)
    assert up.status_code == 200, up.text
    sid = up.json()["id"] if "id" in up.json() else up.json()["source"]["id"]
    assert client.post(f"/api/sources/{sid}/ingest", headers=head).status_code == 200
    if approve:
        assert decide(client, sid, headers=head).status_code == 200
    return sid


def apart(read, seconds: float = 10):
    """Run ``read`` as another request would: in its own daemon thread, holding no lock (a reader never takes the
    workspace's lock), and return what it returned (REF S23, the door)."""
    out: dict = {}

    def body():
        try:
            out["value"] = read()
        except BaseException as exc:  # noqa: BLE001 - raised again in the caller
            out["error"] = exc
    thread = threading.Thread(target=body, daemon=True)
    thread.start()
    thread.join(seconds)
    if "error" in out:
        raise out["error"]
    return out.get("value")


class PublishDuring:
    """A model that, while it writes the answer, lets a publish land (another request, in production); then echoes."""

    def __init__(self, during=None):
        self.during, self.prompts = during, []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.during is not None:
            during, self.during = self.during, None
            during()
        return prompt + "\n[1]"


# ---- S6 / S2: the receipt names the version the answer rested on ------------------------------------------------

@pytest.mark.parametrize("scope", ["0", "1"])
def test_s23_round1_receipt_names_the_version_the_answer_read(acme, scope):
    """S6, S2: an answer reads v1's passages; v2 is published while the model writes. ``_stamp`` asks for the version
    *now*, so the citation names v2 (number and SHA-256), and the delivery recheck passes against v2: v1's words are
    delivered under v2's name. Restated for the door (REF S23, the Human's decision after round 7): the publish that
    lands mid-answer is a job holding the workspace's lock, as its request would; the ask passes the door and does not
    wait, so the publish still lands while the model writes."""
    client, app, core = acme
    os.environ["KP_SCOPE_EVIDENCE"] = scope
    sid = add_doc(client)
    content, register = core.state.content, core.state.register
    v1 = content.current_version(sid)
    core.state.answer.generator = PublishDuring(
        lambda: as_job(core, lambda: content._write_version(register.get(sid), V2, approve=True)))
    response = client.post("/api/ask", json={"q": QUESTION}, headers=HEAD)
    assert register.get(sid).content_sha256 == h(V2)  # the publish landed during the answer
    if response.status_code == 409:
        return  # withheld at delivery: acceptable
    body = response.json()
    assert "ALPHA-ONE" in body["answer"] and "BRAVO-TWO" not in body["answer"]  # the answer rests on v1's words
    cited = [c for c in body["citations"] if c["source_id"] == sid]
    assert cited
    assert cited[0]["sha256"] == h(V1), "the citation names v2's text, though the answer used v1's passage"
    assert cited[0]["version"] == v1["n"]


def test_s23_round1_receipt_control_without_publish(acme):
    """Control: with nothing published meanwhile, the citation names v1."""
    client, app, core = acme
    sid = add_doc(client)
    core.state.answer.generator = PublishDuring()
    body = client.post("/api/ask", json={"q": QUESTION}, headers=HEAD).json()
    cited = [c for c in body["citations"] if c["source_id"] == sid]
    assert cited and cited[0]["sha256"] == h(V1) and "ALPHA-ONE" in body["answer"]


# ---- S1: the content views during the swap -----------------------------------------------------------------------

def test_s23_round1_content_view_during_swap_shows_unapproved_text(acme, monkeypatch):
    """S1: between the swap's text write and its record write, the document view (GET /api/content/documents/{id})
    reads the file unchecked (``published_text(source)``), so it shows v2's text as the published text of version 1.
    Restated for the door (REF S23, the Human's decision after round 7): the publish is a job holding the workspace's
    lock, and the document view is another request, in its own thread holding no lock, as a reader is."""
    client, app, core = acme
    sid = add_doc(client)
    content = core.state.content
    store, seen = content.section_store, {}
    original = store.stage_for_source  # restated to the staged publish (fixed after this round): the new version staged

    def replace(source_id, sections, sha=None):
        original(source_id, sections, sha=sha)
        if sha == h(V2) and not seen:
            doc = apart(lambda: client.get(f"/api/content/documents/{sid}", headers=HEAD).json())
            seen.update(text=doc["published"]["text"], version=doc["source"]["version"])

    monkeypatch.setattr(store, "stage_for_source", replace)
    as_job(core, lambda: content._write_version(core.state.register.get(sid), V2, approve=True))
    assert seen["version"] == 1
    assert "BRAVO-TWO" not in seen["text"], "the content view showed v2's unapproved text as version 1's"


def test_s23_round1_governance_desk_reads_other_version_during_swap(acme, monkeypatch):
    """S2: the governance desk's ``text`` holds the record (v1) and, on ContentReplaced, deliberately reads the file
    'as it is': mid-swap it returns v2's text for a reader holding v1's record. (Home space, where the desk works.)
    Restated for the door (REF S23, the Human's decision after round 7): the publish is a job holding the workspace's
    lock, and the desk reads in its own thread holding no lock, as a reader is."""
    client, app, _ = acme
    desk = app.state.governance_desk
    sid = add_doc(client, head={}, name="vault-home.md")
    core = next(c for c in [*app.state.cores.values(), app]
                if getattr(c.state, "content", None) is not None and c.state.content.register.get(sid) is not None
                and c.state.content.section_store.list_for_source(sid))
    content, seen = core.state.content, {}
    store = content.section_store
    original = store.stage_for_source  # restated to the staged publish (fixed after this round): the new version staged

    def replace(source_id, sections, sha=None):
        original(source_id, sections, sha=sha)
        if sha == h(V2) and not seen:
            seen.update(record_sha=desk.register.get(sid).content_sha256, text=apart(lambda: desk.text(sid)))

    monkeypatch.setattr(store, "stage_for_source", replace)
    as_job(core, lambda: content._write_version(content.register.get(sid), V2, approve=True))
    assert seen["record_sha"] == h(V1)
    assert "BRAVO-TWO" not in seen["text"], "a reader holding v1's record got v2's text"


# ---- S3: a crash (or restart) in the middle of the swap ------------------------------------------------------------

def test_s23_round1_crash_between_writes_leaves_live_version_unreadable(acme, monkeypatch):
    """S3, S1: the process dies after the swap wrote v2's text and passages but before the record (a kill is not an
    ``Exception``, so ``_put_back`` never runs, and nothing repairs it at restart). The live record still names v1,
    but its text and passages are gone: the content view shows v2's text as v1, and v1 has no passages. Restated for
    the door (REF S23, the Human's decision after round 7): the publish is a job holding the workspace's lock (a
    process that dies releases it)."""
    from assistant.ingestion.store import SectionStore
    from assistant.sources.register import SourceRegister

    client, app, core = acme
    sid = add_doc(client)
    content = core.state.content
    register = content.register
    original = register.update

    def update(source_id, **fields):
        if fields.get("content_sha256") == h(V2):
            raise Crash()
        return original(source_id, **fields)

    monkeypatch.setattr(register, "update", update)
    with pytest.raises(Crash):
        as_job(core, lambda: content._write_version(register.get(sid), V2, approve=True))
    monkeypatch.setattr(register, "update", original)
    # As a restarted process finds it: fresh objects over the same files.
    fresh = SourceRegister(core.state.register.base_dir)
    live = fresh.get(sid)
    assert live.content_sha256 == h(V1) and live.version == 1  # the record never changed
    sections_dir = getattr(core.state.section_store, "dir", None)
    if sections_dir is not None:
        # (SectionStore takes the folder that holds "sections"; the red team's draft passed "sections" itself.)
        assert SectionStore(sections_dir.parent).list_for_source(sid, sha=live.content_sha256), "v1 lost its passages"
    doc = client.get(f"/api/content/documents/{sid}", headers=HEAD).json()
    assert "BRAVO-TWO" not in doc["published"]["text"], "the content view shows the unapproved v2 text as version 1"
    assert fresh.read_content(sid) == V1, "the live version's text was replaced by a publish that never happened"


# ---- S1: a version written without approval inherits an approval given to the previous one ----------------------

def _write_unapproved_with_approval_between(client, core, monkeypatch, approve_between: bool):
    import assistant.content.service as content_service

    sid = add_doc(client, approve=False)
    register, content = core.state.register, core.state.content
    stale = register.get(sid)  # what rename() read: pending, so the new version is written without approval
    assert stale.approval_status != "approved"
    original = content_service.stage_sections
    review: dict = {}

    def approve_v1():  # the reviewer's request, naming version 1's text, which they read (REF S23, S8)
        review["status"] = client.post(f"/api/governance/sources/{sid}/approve", json={"sha": stale.content_sha256},
                                       headers=HEAD).status_code

    def stage(*args, **kwargs):
        staged = original(*args, **kwargs)
        if approve_between and "thread" not in review:  # the reviewer approves version 1 before the swap
            review["thread"] = threading.Thread(target=approve_v1, daemon=True)
            review["thread"].start()
            time.sleep(0.5)
            review["waited"] = "status" not in review and register.get(sid).approval_status != "approved"
        return staged

    monkeypatch.setattr(content_service, "stage_sections", stage)
    as_job(core, lambda: content._write_version(stale, V2, approve=False))  # the rename: a job, as its request is
    if approve_between:
        review["thread"].join(10)
        assert review.get("waited"), "the reviewer's approval went in while the rename held the workspace's lock"
        assert review.get("status") == 409, review  # it names version 1's text, which is no longer live (S8)
    return sid, register.get(sid)


def test_s23_round1_unapproved_version_inherits_concurrent_approval(acme, monkeypatch):
    """S1: rename() of a pending document writes v2 with ``approve=False``; ``_swap`` keeps whatever approval the
    record has *at swap time*. An approval of v1 landing between rename's read and the swap makes v2 approved and
    live, though nobody approved v2 (before S23, the stale approval was written back, so v2 stayed pending).
    Restated for the door (REF S23, the Human's decision after round 7): the rename is a job holding the workspace's
    lock, so the reviewer's approval, a request naming v1's text, waits at the door while the rename is paused, and is
    then refused because v1 is no longer the live text (S8); v2 must still not be approved."""
    client, app, core = acme
    sid, record = _write_unapproved_with_approval_between(client, core, monkeypatch, approve_between=True)
    assert record.content_sha256 == h(V2)
    assert record.approval_status != "approved", "v2 went live as approved on an approval given to v1"


def test_s23_round1_unapproved_version_control(acme, monkeypatch):
    """Control: without the approval in between, v2 stays pending. Restated for the door (REF S23, the Human's
    decision after round 7): the rename is a job holding the workspace's lock."""
    client, app, core = acme
    sid, record = _write_unapproved_with_approval_between(client, core, monkeypatch, approve_between=False)
    assert record.content_sha256 == h(V2) and record.approval_status != "approved"


# ---- S2: an ingest that read the old text writes its passages over the new version's ------------------------------

def test_s23_round1_ingest_during_publish_strands_new_version(acme, monkeypatch):
    """S2: POST /api/sources/{id}/ingest reads v1's text, then a publish swaps v2 in, then the ingest writes v1's
    passages (fingerprint v1) and v1's section count. The ingest takes no publish lock, so the approved v2 is left
    with no passages: the register names v2, the passages are v1's, and v2 never answers. Restated for the door (REF
    S23, the Human's decision after round 7): the ingest request holds the workspace's lock from the door, so the
    publish, a job, waits while the ingest is paused after reading v1, and goes in once the ingest is done; v2 must
    then have its own passages."""
    import assistant.ingestion.service as ingestion

    client, app, core = acme
    sid = add_doc(client)
    register, content = core.state.register, core.state.content
    armed, read, go = threading.Event(), threading.Event(), threading.Event()
    armed.set()
    original = ingestion.build_sections

    def build(source_id, text):
        sections = original(source_id, text)
        if armed.is_set():
            armed.clear()
            read.set()
            go.wait(10)
        return sections

    monkeypatch.setattr(ingestion, "build_sections", build)
    outcome = {}
    worker = threading.Thread(target=lambda: outcome.update(
        status=client.post(f"/api/sources/{sid}/ingest", headers=HEAD).status_code), daemon=True)
    worker.start()
    assert read.wait(10)  # the ingest has read v1's text
    publisher = threading.Thread(target=lambda: outcome.update(published=as_job(
        core, lambda: content._write_version(register.get(sid), V2, approve=True))), daemon=True)
    publisher.start()
    time.sleep(0.5)
    assert "published" not in outcome and register.get(sid).content_sha256 == h(V1), \
        "the publish went in while the ingest held the workspace's lock"
    go.set()
    worker.join(10)
    publisher.join(10)
    assert not worker.is_alive() and not publisher.is_alive() and "published" in outcome, outcome
    live = register.get(sid)
    assert live.content_sha256 == h(V2) and live.approval_status == "approved"
    passages = core.state.section_store.list_for_source(sid, sha=live.content_sha256)
    assert passages, "the approved v2 has no passages: the ingest wrote v1's over them"
    assert any("BRAVO-TWO" in p.text for p in passages)


# ---- S6: an answer during a publish gives the new text a second version number -----------------------------------

def test_s23_round1_answer_during_publish_duplicates_version(acme, monkeypatch):
    """S6: after the swap and before publish() records its version, an answer's receipt asks ``current_version``; the
    store has no row for v2's text, so it adds an 'imported' row (waiting on the store lock publish holds). The new
    text gets two version numbers, and receipts name a different number from the one publish reported. Restated for
    the door (REF S23, the Human's decision after round 7): the draft's set-up and the publish are jobs holding the
    workspace's lock; the receipt's reader holds none and never waits, and tells the paused publish when it has read."""
    from assistant.content.service import sha as text_sha

    client, app, core = acme
    sid = add_doc(client)
    content = core.state.content
    text = V2.decode()
    with writing(core):
        content.save_draft(sid, text)
        content.submit(sid)
    swapped, arrived, result = threading.Event(), threading.Event(), {}
    write_version, add_version = content._write_version, content.store.add_version

    def write(*args, **kwargs):
        record = write_version(*args, **kwargs)
        swapped.set()
        arrived.wait(5)
        return record

    def add(*args, **kwargs):
        if threading.current_thread().name == "reader":
            arrived.set()
        return add_version(*args, **kwargs)

    monkeypatch.setattr(content, "_write_version", write)
    monkeypatch.setattr(content.store, "add_version", add)
    publisher = threading.Thread(target=lambda: result.update(
        published=as_job(core, content.publish, sid, text_sha(text))), daemon=True)
    publisher.start()
    assert swapped.wait(10)

    def read():
        result.update(current=content.current_version(sid))
        arrived.set()  # the receipt has read (it adds nothing now, so it never reaches add_version)

    reader = threading.Thread(target=read, name="reader", daemon=True)
    reader.start()
    publisher.join(10)
    reader.join(10)
    rows = [r for r in content.store.versions(sid) if r["sha"] == text_sha(text)]
    assert len(rows) == 1, f"v2's text has {len(rows)} version numbers: {[(r['n'], r['label']) for r in rows]}"
    assert result["current"]["n"] == result["published"]["version"]


# ---- S2 / S5: a step after the swap fails; only the facts map is tried again ---------------------------------------

P1 = (b"# Release procedure\n\n## Steps\n\n1. The clerk checks the vault using the code word ALPHA-ONE.\n"
      b"2. The clerk releases the order.\n\n## Key business rules\n\n- The vault code word is ALPHA-ONE.\n")
P2 = P1.replace(b"ALPHA-ONE", b"BRAVO-TWO")


def test_s23_round1_failed_process_refresh_after_swap_is_never_retried(acme, monkeypatch):
    """S2 (and S5's 'tried again rather than ignored'): publish_version's first side effect, refresh_process_registry,
    fails after the swap. The publish is reported as done (right), and only the facts map is rebuilt again; the
    persisted process registry (GET /api/processes/registry/{id}) keeps v1's steps while the register names v2.
    Restated for the door (REF S23, the Human's decision after round 7): the publish is a job holding the workspace's
    lock."""
    import json

    client, app, core = acme
    sid = add_doc(client, content=P1, name="release.md")
    content, register = core.state.content, core.state.register
    registry = core.state.answer.process_registry
    before = [r for r in registry.list() if r.source_id == sid]
    assert before and "ALPHA-ONE" in json.dumps(before[0].model_dump())  # control: persisted when v1 was approved
    original, calls = registry.build_from_sources, {"n": 0}

    def refresh(source_register):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("disk full while writing the process registry")
        return original(source_register)

    monkeypatch.setattr(registry, "build_from_sources", refresh)
    record = as_job(core, lambda: content._write_version(register.get(sid), P2, approve=True))
    assert record.content_sha256 == h(P2) and record.approval_status == "approved"  # live, not reported failed
    after = json.dumps([r.model_dump() for r in registry.list() if r.source_id == sid])
    assert "BRAVO-TWO" in after and "ALPHA-ONE" not in after, "the process registry still holds v1 after v2 went live"
