"""Red team, round 6, REF H3b (scope). Hermetic: no network, no live services, no models.

Theme of this round: after a failed publish the record goes back to the SAME version number and SHA it had before
(``_restore`` writes ``before["fields"]``). Every guard that asks "is the register still at the reading's version?"
(``_still_as_read``) or "was the facts map built from these ids and versions?" (``_facts_in_step``) compares only
(version, sha) or (id, version), so text read while the failed publish was in flight passes as the old approved text
(an A-B-A). Each break below is a real interleaving of the real code, forced deterministically.
"""
from __future__ import annotations

import os
import socket
import sqlite3
import threading

import pytest
from iam_helpers import sign_in
from test_space_leaks import hermetic, refuse

from assistant.content.service import ContentError

# A failed publish restored the same version and fingerprint (A, B, A), so the version checks could not see B. The
# Human chose a staged publish (REF S23 #2140): every reader takes only the text and passages of the record it holds,
# and a failed publish never changes the record. The interleavings are restated to the staged publish's steps.

APPROVED = "# Refund policy\n\nThe refund window is 30 days for every order (APPROVEDTEXT).\n"
UNAPPROVED = ("# Refund policy\n\nThe refund window is 90 days for every order (NEVERAPPROVED).\n\n"
              "## Key business rules\n- Refunds over 90 days need NEVERAPPROVED sign-off.\n")
OTHER = "# Delivery guide\n\nParcels are delivered within five working days (OTHERDOC).\n"


class Capture:
    """What the model was given: the prompt, echoed with a citation."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return prompt + "\n[1]"


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
    os.environ.pop("KP_SCOPE_TODAY", None)
    app = create_sales_app(tmp_path / "sales")
    hermetic(app)
    with TestClient(app) as client:
        client.headers.update({"Authorization": f"Bearer {sign_in(client, app)}"})
        assert client.post("/api/spaces", json={"name": "Acme"}).status_code == 200
        core = app.state.cores["acme"]
        hermetic(core)
        head = {"X-OpsAtlas-Space": "acme"}
        ids = {}
        for name, text in (("refund.md", APPROVED), ("delivery.md", OTHER)):
            up = client.post("/api/sources/upload", files={"file": (name, text.encode(), "text/markdown")}, headers=head)
            assert up.status_code == 200, up.text
            sid = up.json()["id"] if "id" in up.json() else up.json()["source"]["id"]
            assert client.post(f"/api/sources/{sid}/ingest", headers=head).status_code == 200
            assert client.post(f"/api/governance/sources/{sid}/approve", headers=head).status_code == 200
            ids[name] = sid
        capture = Capture()
        core.state.answer.generator = capture
        yield core, ids["refund.md"], capture


def _publish_midway(core, sid, monkeypatch, *, fail: bool):
    """The answer reads the document's passages at the instant a publish of UNAPPROVED has put its text and passages in
    place and is about to write the record. Restated for the staged publish (REF S23, the Human's decision after this
    round): with ``fail``, the record's write fails and the old text and passages go back; otherwise it completes."""
    store = core.state.answer.retrieval.section_store
    content, register = core.state.content, core.state.register
    original = store.list_for_source
    state = {"done": False}

    def read_during_publish(source_id, sha=None):
        if source_id != sid or state["done"]:
            return original(source_id, sha=sha)
        state["done"] = True
        seen = {}
        real_update = register.update

        def update(changed_id, **fields):
            if changed_id == sid and "content_sha256" in fields and "sections" not in seen:
                seen["sections"] = original(sid, sha=sha)  # what this reader, holding its record, takes at this instant
                if fail:
                    raise OSError("disk full")
            return real_update(changed_id, **fields)
        monkeypatch.setattr(register, "update", update)
        try:
            content._write_version(register.get(sid), UNAPPROVED.encode(), approve=True)
        except ContentError:
            pass
        finally:
            monkeypatch.setattr(register, "update", real_update)
        return seen["sections"]

    monkeypatch.setattr(store, "list_for_source", read_during_publish)


# ---- Break 1: P6 / P9 with scope on — text never approved passes _still_as_read after a failed publish ----------

def test_scope_h3b_round6_control_pending_publish_midway_is_left_out(acme, monkeypatch):
    """Control: the publish lands midway and stays pending; _still_as_read sees the new version and drops the document."""
    core, sid, capture = acme
    os.environ["KP_SCOPE_EVIDENCE"] = "1"
    _publish_midway(core, sid, monkeypatch, fail=False)
    core.state.answer.answer("What is the refund window?", routing_mode="rag_only")
    prompt = "\n".join(capture.prompts)
    assert "NEVERAPPROVED" not in prompt


def test_scope_h3b_round6_failed_publish_text_read_midway_reaches_answer_scope_on(acme, monkeypatch):
    """Break (P6, P9): an answer begins (reading: v1 approved), reads the passages while a publish has written v2 and
    is approving it; the approval fails, _restore puts back v1's version and SHA, so _still_as_read (version, sha
    unchanged) keeps v2's passages: text never approved reaches the model under v1's approval."""
    core, sid, capture = acme
    os.environ["KP_SCOPE_EVIDENCE"] = "1"
    before = core.state.register.get(sid)
    _publish_midway(core, sid, monkeypatch, fail=True)
    core.state.answer.answer("What is the refund window?", routing_mode="rag_only")
    after = core.state.register.get(sid)
    assert (after.version, after.content_sha256, after.approval_status) == (
        before.version, before.content_sha256, "approved")  # the failed swap never changed the record
    prompt = "\n".join(capture.prompts)
    assert "NEVERAPPROVED" not in prompt, "text from a failed (never approved) publish reached the answer"


# ---- Break 2: P9 with scope off — the same interleaving, no guard at all ------------------------------------------

def test_scope_h3b_round6_failed_publish_text_read_midway_reaches_answer_scope_off(acme, monkeypatch):
    """Break (P9, 'this holds with scope on or off'): with scope off the answer lists the register once and reads the
    passages later; a publish writing v2 meanwhile (record pending) is read as the approved v1, and the failed
    publish leaves that answer resting on text never approved."""
    core, sid, capture = acme
    _publish_midway(core, sid, monkeypatch, fail=True)
    core.state.answer.answer("What is the refund window?", routing_mode="rag_only")
    prompt = "\n".join(capture.prompts)
    assert "NEVERAPPROVED" not in prompt, "a reader saw new text under the old approval (scope off)"


# ---- Break 3: P9 / P6 — a facts-map rebuild racing the failed publish keeps unapproved facts, and the gate admits them

def _race_rebuild_with_failed_publish(core, sid, monkeypatch):
    """A facts-map rebuild lists the register (v1 approved) just before a publish of UNAPPROVED, then reads the text
    after the publish wrote it; the publish then fails (a write that fails). Restated for the staged publish (REF S23):
    the new text is written in the swap, the rebuild reads it against v1's fingerprint, and the swap puts v1 back."""
    register, content, answer = core.state.register, core.state.content, core.state.answer
    approved = [r for r in register.list() if r.approval_status == "approved"]
    assert answer._facts_in_step(approved)  # in step before anything happens

    listed, written, finished = threading.Event(), threading.Event(), threading.Event()
    rebuild_thread: dict = {}
    original_read, original_write = register.read_content, register.stage_content  # the staged publish (REF S23)

    def read_content(source_id, sha=None):
        if source_id == sid and threading.get_ident() == rebuild_thread.get("id") and not written.is_set():
            listed.set()  # the rebuild has listed the register (v1 approved) and now reads this document's text
            assert written.wait(10)
        return original_read(source_id, sha=sha)

    def write_content(source_id, data):
        original_write(source_id, data)
        if source_id == sid and b"NEVERAPPROVED" in data and not written.is_set():
            written.set()  # the swap has written v2's text: the racing rebuild reads on
            assert finished.wait(10)
            raise OSError("disk full")  # then the swap fails, and puts v1's text and passages back

    def rebuild_fails():
        raise sqlite3.OperationalError("disk I/O error")  # no rebuild is needed after a failed swap; if tried, it fails

    monkeypatch.setattr(register, "read_content", read_content)
    monkeypatch.setattr(register, "stage_content", write_content)

    def rebuild():
        rebuild_thread["id"] = threading.get_ident()
        try:
            core.state.rebuild_ontology()
        finally:
            finished.set()

    worker = threading.Thread(target=rebuild)
    worker.start()
    assert listed.wait(10)
    monkeypatch.setattr(content, "rebuild_facts", rebuild_fails)
    with pytest.raises(ContentError):
        content._write_version(register.get(sid), UNAPPROVED.encode(), approve=True)
    worker.join(10)
    monkeypatch.setattr(register, "read_content", original_read)
    monkeypatch.setattr(register, "stage_content", original_write)


def test_scope_h3b_round6_rebuild_racing_failed_publish_keeps_unapproved_facts(acme, monkeypatch):
    """Break (P9, P6): after the race above the map keeps facts from v2 (never approved) under 'v1 approved', which
    matches the register exactly, so _facts_in_step admits them; P9 says no such fact stays in the map."""
    core, sid, _ = acme
    os.environ["KP_SCOPE_EVIDENCE"] = "1"
    register, answer = core.state.register, core.state.answer
    _race_rebuild_with_failed_publish(core, sid, monkeypatch)
    reading = register.list()
    assert register.get(sid).approval_status == "approved"
    store = answer.ontology_query.store
    conn = sqlite3.connect(store.db_path) if hasattr(store, "db_path") else store._connect()
    dump = " ".join(str(row) for row in conn.execute("SELECT * FROM objects").fetchall())
    in_step = answer._facts_in_step([r for r in reading if r.approval_status == "approved"])
    assert not ("NEVERAPPROVED" in dump and in_step), (
        "the facts map holds facts from text never approved and the scope gate says it is in step with the register")


def test_scope_h3b_round6_rebuild_racing_failed_publish_unapproved_fact_reaches_answer(acme, monkeypatch):
    """Break (P9, P6), at the answer: after the same race, a later answer with scope on (the register shows v1 approved,
    its passages are v1's again) is given a fact that exists only in the never-approved v2 text, through the facts map."""
    core, sid, capture = acme
    os.environ["KP_SCOPE_EVIDENCE"] = "1"
    _race_rebuild_with_failed_publish(core, sid, monkeypatch)
    assert "NEVERAPPROVED" not in "".join(s.text for s in core.state.section_store.list_for_source(sid))
    seen = []
    for question in ("What are the key business rules of the refund policy?", "Which business rules apply to refunds?",
                     "List the business rules for the Refund policy process."):
        result = core.state.answer.answer(question)
        seen.append(result.answer)
    assert "NEVERAPPROVED" not in "\n".join(capture.prompts + seen), "a fact from text never approved reached an answer"


# ---- Probe: P7 — nothing scoped, facts map in step: scope on gives the evidence of scope off -------------------------

def test_scope_h3b_round6_control_nothing_scoped_same_prompt(acme):
    core, _, capture = acme
    question = "Who approves refunds and what is the refund window?"
    path_off = core.state.answer.answer(question).answer_path
    off = list(capture.prompts)
    capture.prompts.clear()
    os.environ["KP_SCOPE_EVIDENCE"] = "1"
    path_on = core.state.answer.answer(question).answer_path
    assert (capture.prompts, path_on) == (off, path_off)
