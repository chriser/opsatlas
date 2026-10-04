"""REF S23 red team, round 11 (commit fec0bdf): "no exception".

Each test is hermetic: a Sales app in a temporary folder, no network, no live service, no model. Writers go through
real HTTP requests at the door; set-up and the content workflow's publish run as jobs holding the door's lock
(``writing``), with no person signed in, as the brief allows.
"""
from __future__ import annotations

import os
import socket

import pytest
from fastapi.testclient import TestClient

from tests.door_helpers import writing
from tests.iam_helpers import sign_in
from tests.test_space_leaks import hermetic, refuse

S24 = pytest.mark.xfail(strict=True, reason="REF S58 #2158 (open; labelled S24 before 4 Oct): the Sales knowledge layer's own governance")


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
    for core in app.state.cores.values():
        hermetic(core)
    with TestClient(app) as client:
        client.headers.update({"Authorization": f"Bearer {sign_in(client, app)}"})
        yield app, client


def knowledge_of(app):
    return app.state.governance_desk.knowledge


def row_of(knowledge, identifier):
    return next(r for r in knowledge.records() if r["id"] == identifier)


def propose_claim(app, topic="overview", text="OpsAtlas answers questions from approved documents only."):
    knowledge = knowledge_of(app)
    data = {"session_id": "s-r11", "turn_id": "t-1", "contributor": "Red Team", "topic": topic,
            "question": "What does it do?", "raw_text": text, "text": text, "status": "available",
            "expected_hash": None, "wording_confirmed": True, "issue": "none"}
    with writing(app):
        return knowledge.propose(data)


def related_of(knowledge, row):
    rows = knowledge.records()
    return {r["id"]: r["sha256"] for r in knowledge.overlaps(row_of(knowledge, row["id"]), rows)}


def content_of(app, source_id):
    space = knowledge_of(app).register.space_of(source_id)
    return app.state.cores[space].state.content


def publish_as_job(app, source_id, text, fail_records_step=False):
    """The content workflow: draft, submit, publish (the Human's approval of the draft). With ``fail_records_step`` the
    workspace's records step after the commit fails once (one ordinary fault, the case this change handles)."""
    content = content_of(app, source_id)
    original = content.hooks["published"]
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if fail_records_step and calls["n"] == 1:
            raise OSError("disk full while writing sales-records.json")
        return original(*args, **kwargs)

    content.hooks["published"] = flaky
    try:
        with writing(app):
            content.save_draft(source_id, text)
            content.submit(source_id, "red team")
            draft_sha = content.store.document(source_id)["draft_sha"] if "draft_sha" in (
                content.store.document(source_id) or {}) else None
            if draft_sha is None:
                import hashlib
                draft_sha = hashlib.sha256(content.store.document(source_id)["draft_text"].encode()).hexdigest()
            return content.publish(source_id, draft_sha, "red team publish")
    finally:
        content.hooks["published"] = original


def out_of_step_claim(app, client):
    """A contributed claim whose scope was decided, then published as new wording with the records step failing: the
    Sales store's copy (text A) is out of step with its document (text B)."""
    knowledge = knowledge_of(app)
    claim = propose_claim(app)
    related = related_of(knowledge, claim)
    assert related, "the claim should overlap the curated record of its topic"
    r = client.post(f"/api/tibi/knowledge/{claim['id']}/resolve",
                    json={"expected_hash": claim["sha256"], "decision": "distinct_scope", "related": related,
                          "reason": "Different scope: contributed account of the product overview."})
    assert r.status_code == 200, r.text
    title = row_of(knowledge, claim["id"])["title"]
    publish_as_job(app, claim["source_id"],
                   f"# {title}\n\nCurrently: OpsAtlas also answers from unreviewed drafts when asked.\n",
                   fail_records_step=True)
    row = row_of(knowledge, claim["id"])
    assert row["sha256"] == claim["sha256"], "the records step failed: the copy still names text A"
    assert knowledge.register.names_text(row["source_id"], row["sha256"]) is not None, "copy is out of step"
    return claim, row


# ---- S8: a Sales decision on a record whose copy is out of step is refused, and nothing changes -------------------

@S24
def test_s23_round11_scope_decision_on_out_of_step_claim_is_refused(sales):
    app, client = sales
    knowledge = knowledge_of(app)
    claim, row = out_of_step_claim(app, client)
    before = row.get("resolution")
    related = related_of(knowledge, row)
    r = client.post(f"/api/tibi/knowledge/{claim['id']}/resolve",
                    json={"expected_hash": row["sha256"], "decision": "distinct_scope", "related": related,
                          "reason": "Still a distinct scope, judged on the wording shown (text A)."})
    after = row_of(knowledge, claim["id"])
    assert r.status_code != 200 and after.get("resolution") == before, (
        f"a scope decision naming text A was taken on a record whose document says text B: {r.status_code}")


@S24
def test_s23_round11_supersession_by_out_of_step_claim_is_refused(sales):
    app, client = sales
    knowledge = knowledge_of(app)
    claim, row = out_of_step_claim(app, client)
    related = related_of(knowledge, row)
    statuses = {i: knowledge.register.get(row_of(knowledge, i)["source_id"]).approval_status for i in related}
    r = client.post(f"/api/tibi/knowledge/{claim['id']}/resolve",
                    json={"expected_hash": row["sha256"], "decision": "supersede", "related": related,
                          "reason": "The contributed account (text A as shown) replaces the curated record."})
    now = {i: knowledge.register.get(row_of(knowledge, i)["source_id"]).approval_status for i in related}
    assert r.status_code != 200 and now == statuses, (
        f"the claim (copy A, document B) superseded {list(related)}: {statuses} -> {now}, status {r.status_code}")


# ---- S8: the whole decision is refused, or nothing changes, under one ordinary fault -------------------------------

def test_s23_round11_dispute_refused_after_a_side_effect_fault_changes_nothing(sales):
    app, client = sales
    knowledge = knowledge_of(app)
    claim = propose_claim(app)
    related = related_of(knowledge, claim)
    space = knowledge.register.space_of(claim["source_id"])
    engine = app.state.cores[space].state.actions
    effects = engine._side_effects
    name = "record_analytics_event"
    original = effects[name]
    calls = {"n": 0}

    def flaky(context, result):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("analytics event store is locked")
        return original(context, result)

    effects[name] = flaky
    try:
        r = client.post(f"/api/tibi/knowledge/{claim['id']}/resolve",
                        json={"expected_hash": claim["sha256"], "decision": "dispute", "related": related,
                              "reason": "The two accounts disagree about the product overview."})
    finally:
        effects[name] = original
    status = knowledge.register.get(claim["source_id"]).approval_status
    row = row_of(knowledge, claim["id"])
    assert not (r.status_code != 200 and status == "rejected"), (
        f"the dispute was refused ({r.status_code}: {r.text[:120]}) yet the claim's document is now {status}; "
        f"the Sales record says disputed={row.get('disputed')}, resolution={row.get('resolution')}")


# ---- S8: a refused decision changes nothing (the retry runs before the check) -------------------------------------

def test_s23_round11_refused_content_decision_changes_records(sales):
    app, client = sales
    knowledge = knowledge_of(app)
    claim, row = out_of_step_claim(app, client)
    space = knowledge.register.space_of(claim["source_id"])
    r = client.post(f"/api/content/documents/{claim['source_id']}/reject", json={"expected_sha": "0" * 64},
                    headers={"X-OpsAtlas-Space": space})
    after = row_of(knowledge, claim["id"])
    assert r.status_code != 200, r.text
    assert after == row, "a decision refused for naming another text changed the Sales record (copy, history)"


# ---- tried without success (kept as a check that holds): a dispute on an out-of-step claim -------------------------

def test_s23_round11_holds_dispute_on_out_of_step_claim_refused_and_retried(sales):
    app, client = sales
    knowledge = knowledge_of(app)
    claim, row = out_of_step_claim(app, client)
    related = related_of(knowledge, row)
    statuses = {i: knowledge.register.get(row_of(knowledge, i)["source_id"]).approval_status for i in [claim["id"], *related]}
    r = client.post(f"/api/tibi/knowledge/{claim['id']}/resolve",
                    json={"expected_hash": row["sha256"], "decision": "dispute", "related": related,
                          "reason": "The two accounts disagree about the product overview."})
    assert r.status_code == 409, r.text
    now = {i: knowledge.register.get(row_of(knowledge, i)["source_id"]).approval_status for i in [claim["id"], *related]}
    assert now == statuses
    after = row_of(knowledge, claim["id"])
    assert knowledge.register.names_text(after["source_id"], after["sha256"]) is None, "the retry brought it in step"
    assert after["approval"] == row["approval"] and after["review"] == row["review"], "the retry records no approval"


# ---- "keep an approval on a text that changed": a record's evidence reworded, then reformatted --------------------

@S24
def test_s23_round11_reformat_after_reword_carries_a_stale_evidence_approval(sales):
    from assistant.content.service import ContentService

    app, client = sales
    knowledge = knowledge_of(app)
    pick = None
    for row in knowledge.records():
        if row.get("provenance") or row.get("kind") == "conversation" or not row.get("references"):
            continue
        for ref in row["references"]:
            source = knowledge.register.get(ref["source_id"])
            if source and ContentService.editable(source) and source.approval_status != "rejected":
                pick = (row, ref)
                break
        if pick:
            break
    assert pick, "a curated record citing an editable evidence document"
    row, ref = pick
    r = client.post(f"/api/tibi/knowledge/{row['id']}/review", json={"expected_hash": row["sha256"], "approve": True})
    assert r.status_code == 200, r.text
    assert knowledge.eligible(row_of(knowledge, row["id"])), "approved against evidence A"
    evidence = ref["source_id"]
    a = content_of(app, evidence).record_text(knowledge.register.get(evidence))
    reworded = a.rstrip("\n") + "\n\nThis capability was withdrawn and is no longer offered to customers.\n"
    publish_as_job(app, evidence, reworded)
    assert not knowledge.eligible(row_of(knowledge, row["id"])), "evidence reworded: unavailable until reconfirmed"
    reformatted = reworded.replace("no longer offered", "no longer **offered**")
    publish_as_job(app, evidence, reformatted)
    after = row_of(knowledge, row["id"])
    assert not knowledge.eligible(after), (
        "nobody confirmed the record against the reworded evidence (B), yet a reformat of B (C) carried the approval "
        "made against A over to C: the record is in answers again")
