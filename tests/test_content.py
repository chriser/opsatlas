"""Content management (CM E1): governed drafts, publishing, versions, comments, details and images on any source."""
import base64
import json

import pytest
from fastapi.testclient import TestClient

from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.content.text import diff, find_anchor, plain, stats
from assistant.ingestion.service import ingest_source
from assistant.ingestion.store import SectionStore
from assistant.sources.register import SourceRegister
from assistant.sources.service import register_upload
from tests.door_helpers import as_job, decided

PASSWORD = "content-test-pass"
GUIDE = b"# Supplier guide\n\n## Checks\n\nCredit checks are done before the supplier is created.\n"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("KP_OPERATOR_NAME", "Kris Pochopien")
    register = SourceRegister(tmp_path)
    sections = SectionStore(tmp_path)
    source = register_upload(register, "guide.md", GUIDE, "Supplier guide")
    ingest_source(register, sections, source.id)
    decided(register, source.id, approval_status="approved")
    client = TestClient(create_app(register, AuthService(PASSWORD)))
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client, register, sections, source.id


def edit(text):
    return text.replace("before the supplier is created", "after the supplier is created, within two days")


def test_a_draft_changes_nothing_live_until_the_human_approves_it(workspace, tmp_path):
    client, register, sections, sid = workspace
    doc = client.get(f"/api/content/documents/{sid}").json()
    assert doc["status"] == "published" and doc["source"]["editable"] and doc["versions"] == 1
    assert doc["published"]["text"] == GUIDE.decode() and doc["operator"]["name"] == "Operator"  # signed in (REF S3)
    new = edit(doc["published"]["text"])
    doc = client.put(f"/api/content/documents/{sid}/draft", json={"text": new, "base_sha": doc["published"]["sha"]}).json()
    assert doc["status"] == "draft" and doc["draft"]["text"] == new and not doc["draft"]["stale"]
    # Answers, Tibi and search still use the approved text.
    assert register.read_content(sid) == GUIDE
    assert "before the supplier" in sections.list_for_source(sid)[-1].text
    assert client.post(f"/api/content/documents/{sid}/publish", json={"draft_sha": doc["draft"]["sha"]}).status_code == 409
    doc = client.post(f"/api/content/documents/{sid}/submit", json={"note": "Checks move after setup"}).json()
    assert doc["status"] == "submitted" and doc["submitted"]["note"] == "Checks move after setup"
    assert client.post(f"/api/content/documents/{sid}/publish", json={"draft_sha": "wrong"}).status_code == 409
    published = client.post(f"/api/content/documents/{sid}/publish", json={"draft_sha": doc["draft"]["sha"], "note": "Approved"}).json()
    source = register.get(sid)
    assert register.read_content(sid).decode() == new and source.version == 2 and source.approval_status == "approved"
    assert "within two days" in sections.list_for_source(sid)[-1].text
    assert published["source_version"] == 2 and published["document"]["status"] == "published"
    assert published["document"]["draft"] is None
    # The approval went through the audited ontology action.
    log = json.loads((tmp_path / "action_log.json").read_text())
    assert any(e["action"] == "publish_version" and e["outcome"] == "ok" for e in log)  # the staged publish (REF S23)
    versions = client.get(f"/api/content/documents/{sid}/versions").json()["versions"]
    assert [(v["n"], v["label"], v["current"]) for v in versions] == [(2, "approved", True), (1, "imported", False)]
    assert versions[0]["author"] == "Operator" and versions[0]["note"] == "Approved"
    actions = [a["action"] for a in client.get(f"/api/content/documents/{sid}/activity").json()["activity"]]
    assert actions[:3] == ["approved and published", "submitted for approval", "edited"]


def test_a_version_that_cannot_be_ingested_leaves_the_previous_one_live(workspace):
    client, register, _, sid = workspace
    doc = client.put(f"/api/content/documents/{sid}/draft", json={"text": "# Only a heading\n"}).json()
    client.post(f"/api/content/documents/{sid}/submit", json={})
    failed = client.post(f"/api/content/documents/{sid}/publish", json={"draft_sha": doc["draft"]["sha"]})
    assert failed.status_code == 409 and "previous one stays live" in failed.json()["detail"]
    source = register.get(sid)
    assert register.read_content(sid) == GUIDE and source.version == 1 and source.approval_status == "approved"
    assert source.processing_state == "ingested"
    assert client.get(f"/api/content/documents/{sid}").json()["status"] == "submitted"  # the draft is kept


def test_versions_compare_and_restore_into_the_draft(workspace):
    client, register, _, sid = workspace
    doc = client.get(f"/api/content/documents/{sid}").json()
    doc = client.put(f"/api/content/documents/{sid}/draft", json={"text": edit(doc["published"]["text"])}).json()
    client.post(f"/api/content/documents/{sid}/submit", json={})
    client.post(f"/api/content/documents/{sid}/publish", json={"draft_sha": doc["draft"]["sha"]})
    changes = client.get(f"/api/content/documents/{sid}/diff", params={"base": "1", "target": "published"}).json()
    assert {"op": "delete", "text": "before"} in changes["ops"] and changes["inserted_words"] >= 5
    restored = client.post(f"/api/content/documents/{sid}/versions/1/restore").json()
    assert restored["status"] == "draft" and restored["draft"]["text"] == GUIDE.decode()
    assert register.read_content(sid) != GUIDE  # restoring never publishes
    assert client.get(f"/api/content/documents/{sid}/versions/9").status_code == 404
    # Editing back to the published text leaves no draft; a draft can also be discarded.
    same = client.put(f"/api/content/documents/{sid}/draft", json={"text": register.read_content(sid).decode()}).json()
    assert same["draft"] is None and same["status"] == "published"
    client.put(f"/api/content/documents/{sid}/draft", json={"text": "# Supplier guide\n\nSomething else entirely here.\n"})
    assert client.delete(f"/api/content/documents/{sid}/draft").json()["draft"] is None
    assert client.delete(f"/api/content/documents/{sid}/draft").status_code == 409


def test_editing_a_submitted_draft_returns_it_to_draft(workspace):
    client, _, _, sid = workspace
    doc = client.get(f"/api/content/documents/{sid}").json()
    client.put(f"/api/content/documents/{sid}/draft", json={"text": edit(doc["published"]["text"])})
    client.post(f"/api/content/documents/{sid}/submit", json={})
    assert client.post(f"/api/content/documents/{sid}/submit", json={}).status_code == 409
    doc = client.put(f"/api/content/documents/{sid}/draft", json={"text": edit(doc["published"]["text"]) + "\nMore.\n"}).json()
    assert doc["status"] == "draft"
    client.post(f"/api/content/documents/{sid}/submit", json={})
    submitted = client.get(f"/api/content/documents/{sid}").json()["draft"]["sha"]  # a return names the draft (S8)
    assert client.post(f"/api/content/documents/{sid}/return", json={"note": "Not yet", "draft_sha": submitted}).json()["status"] == "draft"


def test_a_draft_overtaken_by_another_edit_cannot_be_published(workspace):
    client, register, _, sid = workspace
    doc = client.get(f"/api/content/documents/{sid}").json()
    doc = client.put(f"/api/content/documents/{sid}/draft", json={"text": edit(doc["published"]["text"])}).json()
    client.post(f"/api/content/documents/{sid}/submit", json={})
    # The published text changes outside the workflow (a file restored on disk) while the draft waits.
    as_job(register, register.write_content, sid, b"# Supplier guide\n\nChanged elsewhere, in place.\n")
    doc = client.get(f"/api/content/documents/{sid}").json()
    assert doc["draft"]["stale"]
    refused = client.post(f"/api/content/documents/{sid}/publish", json={"draft_sha": doc["draft"]["sha"]})
    assert refused.status_code == 409 and "changed after this draft was started" in refused.json()["detail"]


def test_comments_follow_their_passage_through_edits(workspace):
    client, _, _, sid = workspace
    added = client.post(f"/api/content/documents/{sid}/comments", json={
        "quote": "Credit checks are done", "prefix": "", "suffix": " before", "text": "Is this still true?"}).json()
    assert added["anchored"] and added["author"] == "Operator" and added["status"] == "open"
    cid = added["id"]
    replied = client.post(f"/api/content/comments/{cid}/replies", json={"text": "Yes, per the supplier pack."}).json()
    assert [r["text"] for r in replied["replies"]] == ["Yes, per the supplier pack."]
    assert client.post(f"/api/content/comments/{cid}/resolve").json()["status"] == "resolved"
    assert client.post(f"/api/content/comments/{cid}/reopen").json()["status"] == "open"
    client.put(f"/api/content/documents/{sid}/draft", json={"text": "# Supplier guide\n\n## Checks\n\nVetting happens first.\n"})
    [comment] = client.get(f"/api/content/documents/{sid}/comments").json()["comments"]
    assert not comment["anchored"]  # its text is gone from the draft
    assert client.get(f"/api/content/documents/{sid}").json()["comments"] == {"open": 1, "resolved": 0}
    for bad in ({"quote": " ", "text": "x"}, {"quote": "Credit", "text": " "}):
        assert client.post(f"/api/content/documents/{sid}/comments", json=bad).status_code == 409
    assert client.delete(f"/api/content/comments/{cid}").json() == {"deleted": cid}
    assert client.post(f"/api/content/comments/{cid}/resolve").status_code == 404


def test_other_formats_open_read_only_and_details_are_governed(workspace):
    client, register, sections, sid = workspace
    data = as_job(register, register_upload, register, "facts.json", b'{"fact": "Suppliers need contracts"}', "Facts")
    as_job(register, ingest_source, register, sections, data.id)
    doc = client.get(f"/api/content/documents/{data.id}").json()
    assert not doc["source"]["editable"] and doc["source"]["format"] == "json"
    refused = client.put(f"/api/content/documents/{data.id}/draft", json={"text": "{}"})
    assert refused.status_code == 409 and "read-only" in refused.json()["detail"]
    fields = {"title": "Supplier guide 2027", "effective_from": "2027-01-01", "phases": ["real_deployment"],
              "applies_to": ["pilot sites"]}
    details = client.patch(f"/api/content/documents/{sid}/details", json={"fields": fields}).json()
    assert details["source"]["title"] == "Supplier guide 2027" and details["source"]["phases"] == ["real_deployment"]
    assert register.get(sid).effective_from == "2027-01-01"
    for fields in ({"effective_to": "soon"}, {"phases": ["someday"]}, {"title": " "}, {},
                   {"effective_from": "2027-05-01", "effective_to": "2027-01-01"}):
        assert client.patch(f"/api/content/documents/{sid}/details", json={"fields": fields}).status_code == 409, fields
    logged = next(a for a in client.get(f"/api/content/documents/{sid}/activity").json()["activity"] if a["action"] == "changed details")
    assert "phases: a real deployment" in logged["detail"] and "applies to: pilot sites" in logged["detail"]
    assert client.get("/api/content/documents/nope").status_code == 404
    assert client.get("/api/content/documents").json()["documents"] == {}


def test_images_are_kept_in_the_workspace_by_content_hash(workspace):
    client, _, _, _ = workspace
    stored = client.post("/api/content/assets", files={"file": ("dot.png", PNG, "image/png")}).json()
    assert stored["url"].startswith("/api/content/assets/") and stored["name"].endswith(".png")
    served = client.get(stored["url"])  # an <img> sends the session cookie; the route is guarded like the document
    assert served.status_code == 200 and served.headers["content-type"] == "image/png" and served.content == PNG
    assert TestClient(client.app).get(stored["url"]).status_code == 401  # and nothing without a session
    assert client.post("/api/content/assets", files={"file": ("x.svg", b"<svg/>", "image/svg+xml")}).status_code == 409
    assert client.get("/api/content/assets/..%2Fcontent.db").status_code == 404
    assert client.get("/api/content/assets/missing.png").status_code == 404


def test_every_content_route_needs_the_operator_sign_in(workspace):
    client, _, _, sid = workspace
    anonymous = TestClient(client.app)
    for method, path in (("get", "/api/content/documents"), ("get", f"/api/content/documents/{sid}"),
                         ("put", f"/api/content/documents/{sid}/draft"), ("post", f"/api/content/documents/{sid}/publish"),
                         ("get", f"/api/content/documents/{sid}/versions"), ("post", "/api/content/comments/x/resolve"),
                         ("patch", f"/api/content/documents/{sid}/details"), ("post", "/api/content/assets"),
                         ("get", "/api/content/library"), ("post", "/api/content/groups"), ("delete", "/api/content/groups/x"),
                         ("put", f"/api/content/documents/{sid}/parent"), ("post", f"/api/content/documents/{sid}/rename")):
        assert getattr(anonymous, method)(path).status_code == 401, path


def test_text_helpers():
    md = "# Title\n\nThe proof of concept runs **locally**. It is [documented](x.md).\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
    assert plain(md) == "Title\nThe proof of concept runs locally. It is documented.\nA B\n1 2"
    counted = stats(md)
    assert counted["words"] == 14 and counted["readability"] and counted["reading_minutes"] == 1
    assert stats("")["words"] == 0 and stats("")["flesch"] is None
    changes = diff("a b c", "a x c")
    assert [o["op"] for o in changes["ops"]] == ["equal", "delete", "insert", "equal"]
    text = "one two three two four"
    assert find_anchor(text, "two", "three ", " four") == text.rindex("two")
    assert find_anchor(text, "five") is None


def test_the_published_version_can_be_approved_or_rejected_from_the_document(workspace, tmp_path):
    client, register, sections, sid = workspace
    pending = as_job(register, register_upload, register, "notes.md", b"# Notes\n\nSupplier notes for the approval test.\n", "Notes")
    as_job(register, ingest_source, register, sections, pending.id)
    doc = client.get(f"/api/content/documents/{pending.id}").json()
    stale = client.post(f"/api/content/documents/{pending.id}/approve", json={"expected_sha": "old"})
    assert stale.status_code == 409 and "changed since you opened it" in stale.json()["detail"]
    approved = client.post(f"/api/content/documents/{pending.id}/approve", json={"expected_sha": doc["published"]["sha"]}).json()
    assert approved["source"]["approval_status"] == "approved" and register.get(pending.id).approval_status == "approved"
    again = client.post(f"/api/content/documents/{pending.id}/approve", json={"expected_sha": doc["published"]["sha"]})
    assert again.status_code == 409 and "already approved" in again.json()["detail"]
    rejected = client.post(f"/api/content/documents/{pending.id}/reject", json={"expected_sha": doc["published"]["sha"]}).json()
    assert rejected["source"]["approval_status"] == "rejected"
    log = json.loads((tmp_path / "action_log.json").read_text())
    assert {("approve_source", "ok"), ("reject_source", "ok")} <= {(e["action"], e["outcome"]) for e in log}
    actions = [a["action"] for a in client.get(f"/api/content/documents/{pending.id}/activity").json()["activity"]]
    assert actions[:2] == ["rejected", "approved"]
    assert client.get("/api/content/documents").json()["suggestions"] == {}


def test_documents_sit_in_groups_and_nothing_can_sit_inside_itself(workspace):
    client, register, sections, sid = workspace
    other = as_job(register, register_upload, register, "notes.md", b"# Notes\n\nSome notes.\n", "Notes").id
    assert client.get("/api/content/library").json() == {"groups": [], "placements": {}}  # no starting library here
    sales = client.post("/api/content/groups", json={"title": "  Sales  "}).json()
    policies = client.post("/api/content/groups", json={"title": "Policies", "parent": f"group:{sales['id']}"}).json()
    top, inner = f"group:{sales['id']}", f"group:{policies['id']}"
    moved = client.put(f"/api/content/documents/{sid}/parent", json={"parent": inner}).json()
    assert moved["placements"][sid]["parent"] == inner
    # A document can sit under another document.
    assert client.put(f"/api/content/documents/{other}/parent", json={"parent": f"source:{sid}"}).status_code == 200
    for node, parent in ((f"documents/{sid}/parent", f"source:{other}"), (f"documents/{sid}/parent", f"source:{sid}")):
        refused = client.put(f"/api/content/{node}", json={"parent": parent})
        assert refused.status_code == 409 and "inside itself" in refused.json()["detail"]
    refused = client.patch(f"/api/content/groups/{sales['id']}", json={"fields": {"parent": inner}})
    assert refused.status_code == 409 and "inside itself" in refused.json()["detail"]
    assert client.put(f"/api/content/documents/{sid}/parent", json={"parent": "group:gone"}).status_code == 409
    assert client.post("/api/content/groups", json={"title": "   "}).status_code == 409
    renamed = client.patch(f"/api/content/groups/{policies['id']}", json={"fields": {"title": "Supplier policies"}}).json()
    assert [g["title"] for g in renamed["groups"]] == ["Sales", "Supplier policies"]
    # Removing a group moves what it held up a level; nothing is deleted.
    after = client.delete(f"/api/content/groups/{policies['id']}").json()
    assert after["placements"][sid]["parent"] == top and after["placements"][other]["parent"] == f"source:{sid}"
    assert register.get(sid) and client.get(f"/api/content/documents/{sid}").status_code == 200
    moved_to_top = client.put(f"/api/content/documents/{sid}/parent", json={"parent": None}).json()
    assert moved_to_top["placements"][sid]["parent"] is None
    actions = [a["action"] for a in client.get(f"/api/content/documents/{sid}/activity").json()["activity"]]
    assert actions.count("moved") >= 2


def test_drag_and_drop_reorders_moves_between_groups_and_out_of_them(workspace):
    client, register, sections, sid = workspace
    a = as_job(register, register_upload, register, "a.md", b"# A\n\nA.\n", "Alpha").id
    b = as_job(register, register_upload, register, "b.md", b"# B\n\nB.\n", "Bravo").id
    one = client.post("/api/content/groups", json={"title": "One"}).json()["id"]
    two = client.post("/api/content/groups", json={"title": "Two"}).json()["id"]
    g1, g2 = f"group:{one}", f"group:{two}"

    def move(node, parent, before=None):
        return client.post("/api/content/library/move", json={"node": node, "parent": parent, "before": before})

    def order(library, parent):
        nodes = [(g["position"], f"group:{g['id']}") for g in library["groups"] if g["parent"] == parent]
        nodes += [(at["position"], f"source:{k}") for k, at in library["placements"].items() if at["parent"] == parent]
        return [k for _, k in sorted(nodes)]

    for doc in (sid, a, b):
        assert move(f"source:{doc}", g1).status_code == 200  # each goes last
    library = client.get("/api/content/library").json()
    assert order(library, g1) == [f"source:{sid}", f"source:{a}", f"source:{b}"]
    # Reorder within the group: Bravo before the guide.
    library = move(f"source:{b}", g1, f"source:{sid}").json()
    assert order(library, g1) == [f"source:{b}", f"source:{sid}", f"source:{a}"] and library["moved"] == f"source:{b}"
    # Dropped where it already is: nothing changes.
    assert order(move(f"source:{b}", g1, f"source:{b}").json(), g1) == [f"source:{b}", f"source:{sid}", f"source:{a}"]
    # Into another group, and out of every group, before a group at the top level.
    library = move(f"source:{a}", g2).json()
    assert order(library, g2) == [f"source:{a}"] and order(library, g1) == [f"source:{b}", f"source:{sid}"]
    library = move(f"source:{sid}", None, g2).json()
    assert order(library, None) == [g1, f"source:{sid}", g2]
    # Groups move the same way, but never into themselves or what they hold.
    library = move(g2, g1, f"source:{b}").json()
    assert order(library, g1) == [g2, f"source:{b}"]
    refused = move(g1, g2)
    assert refused.status_code == 409 and "inside itself" in refused.json()["detail"]
    # A stale drop (the sibling moved elsewhere meanwhile) and unknown nodes are refused.
    assert move(f"source:{b}", None, f"source:{a}").status_code == 409
    assert move("source:gone", None).status_code == 404 and move("group:gone", None).status_code == 404
    assert move("nonsense", None).status_code == 404
    activity = [e for e in client.get(f"/api/content/documents/{a}/activity").json()["activity"] if e["action"] == "moved"]
    assert activity and "Two" in activity[0]["detail"]  # a document's history says where it went, not each reorder
    assert len([e for e in client.get(f"/api/content/documents/{b}/activity").json()["activity"] if e["action"] == "moved"]) == 1


def test_renaming_a_document_changes_its_title_and_nothing_else(workspace):
    client, register, sections, sid = workspace
    before = register.get(sid)
    doc = client.post(f"/api/content/documents/{sid}/rename", json={"title": "  Supplier   onboarding guide "}).json()
    assert doc["source"]["title"] == "Supplier onboarding guide" and doc["versions"] == 1
    after = register.get(sid)
    assert after.version == before.version and after.approval_status == "approved" and register.read_content(sid) == GUIDE
    activity = client.get(f"/api/content/documents/{sid}/activity").json()["activity"][0]
    assert activity["action"] == "renamed" and "Supplier guide" in activity["detail"]
    for title in ("", "Supplier onboarding guide"):
        assert client.post(f"/api/content/documents/{sid}/rename", json={"title": title}).status_code == 409


def test_suggestions_are_settled_as_corrected_accepted_or_resolved(workspace):
    client, register, sections, sid = workspace
    content = client.app.state.content
    other = as_job(register, register_upload, register, "notes.md", b"# Notes\n\nSome notes.\n", "Notes").id
    kyc = {"key": "acronym:KYC", "label": "Acronym not spelled out", "text": "KYC is used without being spelled out.", "quote": "KYC"}
    style = {"key": "readability", "label": "Hard to read", "text": "3 long sentences may be hard to read."}
    link = {"key": "broken_link", "label": "Broken link", "text": "An empty link."}
    conflict = {"key": "k9", "label": "Possible conflict", "text": "Local against cloud.", "other": {"title": "Notes"}}
    raised = {sid: [kyc, style], other: [link, conflict]}
    kept = []
    content.hooks.update(all_suggestions=lambda: {k: [s for s in v if (k, s["key"]) not in kept] for k, v in raised.items()},
                         keep=lambda source, s, note: kept.append((source.id, s["key"])),
                         unkeep=lambda source, s: kept.remove((source.id, s["key"])))
    url = f"/api/content/documents/{sid}/suggestions"
    state = client.get(url).json()
    assert [s["key"] for s in state["suggestions"]] == ["acronym:KYC", "readability"] and state["settled"] == []
    # An edit that removes a suggestion corrects it, in the version that went live.
    doc = client.put(f"/api/content/documents/{sid}/draft", json={"text": edit(GUIDE.decode())}).json()
    client.post(f"/api/content/documents/{sid}/submit", json={"note": ""})
    client.post(f"/api/content/documents/{sid}/publish", json={"draft_sha": doc["draft"]["sha"]})
    raised[sid] = [style]
    state = client.get(url).json()
    [corrected] = state["settled"]
    assert (corrected["outcome"], corrected["version"], corrected["actor"]) == ("corrected", 2, "Operator")
    assert corrected["key"] == "acronym:KYC"
    assert corrected["words"] == "Corrected in version 2" and [s["key"] for s in state["suggestions"]] == ["readability"]
    # Kept as it is: accepted, with the reason, and no longer open.
    state = client.post(f"{url}/accept", json={"key": "readability", "note": " House style  allows it "}).json()
    assert state["suggestions"] == [] and kept == [(sid, "readability")]
    accepted = next(s for s in state["settled"] if s["outcome"] == "accepted")
    assert accepted["note"] == "House style allows it" and accepted["words"] == "Accepted as it is"
    summary = client.get("/api/content/documents").json()
    assert sid not in summary["suggestions"]
    assert {k: summary["settled"][sid][k] for k in ("corrected", "accepted", "resolved")} == {"corrected": 1, "accepted": 1, "resolved": 0}
    assert summary["settled"][sid]["notes"][0].startswith(("Corrected in version 2: ", "Accepted as it is: "))
    # Accepting can be undone; a correction cannot.
    reopened = client.post(f"{url}/settled/{accepted['id']}/reopen").json()
    assert [s["key"] for s in reopened["suggestions"]] == ["readability"] and kept == []
    assert client.post(f"{url}/settled/{corrected['id']}/reopen").status_code == 409
    assert client.post(f"{url}/accept", json={"key": "gone"}).status_code == 404
    # A conflict involves another record: it is settled with Tibi or by an edit, not kept from one side.
    refused = client.post(f"/api/content/documents/{other}/suggestions/accept", json={"key": "k9"})
    assert refused.status_code == 409 and "Tibi" in refused.json()["detail"]
    # Gone without an edit to the document: resolved.
    client.get(f"/api/content/documents/{other}/suggestions")
    raised[other] = [conflict]
    [resolved] = client.get(f"/api/content/documents/{other}/suggestions").json()["settled"]
    assert resolved["outcome"] == "resolved" and resolved["key"] == "broken_link" and resolved["actor"] == "OpsAtlas"
    actions = [a["action"] for a in client.get(f"/api/content/documents/{sid}/activity").json()["activity"]]
    assert {"corrected a suggestion", "accepted a suggestion as it is", "reopened a suggestion"} <= set(actions)


def test_deleting_a_source_removes_everything_it_left(workspace, tmp_path):
    """REF S4, the Human's decision of 2 October 2026: deletion removes the sections, drafts, versions, comments,
    activity and the images no other document uses; the record of the deletion keeps no text."""
    client, register, sections, sid = workspace
    planted = "Zanzibar-quokka-7731"
    other = client.post("/api/content/assets", files={"file": ("a.png", PNG, "image/png")}).json()["url"]
    own = client.post("/api/content/assets", files={"file": ("b.png", PNG + b"own", "image/png")}).json()["url"]
    # Another document uses the first image; the deleted one uses both.
    from assistant.sources.service import register_upload
    kept = as_job(register, register_upload, register, "kept.md", f"# Kept\n\n![a]({other})\n".encode(), "Kept")
    as_job(register, ingest_source, register, sections, kept.id)
    doc = client.get(f"/api/content/documents/{sid}").json()
    text = doc["published"]["text"] + f"\n{planted} ![a]({other}) ![b]({own})\n"
    draft = client.put(f"/api/content/documents/{sid}/draft", json={"text": text}).json()
    client.post(f"/api/content/documents/{sid}/submit", json={})
    assert client.post(f"/api/content/documents/{sid}/publish", json={"draft_sha": draft["draft"]["sha"]}).status_code == 200
    client.post(f"/api/content/documents/{sid}/comments", json={"quote": planted, "text": f"About {planted}."})
    assert sections.list_for_source(sid)

    assert client.delete(f"/api/sources/{sid}").status_code == 200

    assert sections.list_for_source(sid) == []
    assert client.get(f"/api/content/documents/{sid}").status_code == 404
    assets = tmp_path / "content" / "assets"
    assert (assets / other.rsplit("/", 1)[1]).is_file() and not (assets / own.rsplit("/", 1)[1]).exists()
    found = [str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*")
             if path.is_file() and planted.encode() in path.read_bytes()]
    assert found == []  # nowhere on disk, databases included
    from assistant.analytics.event_store import AnalyticsEventStore
    deleted = AnalyticsEventStore(tmp_path).events(event_type="source_deleted")
    assert len(deleted) == 1 and deleted[0].actor_id
    assert set(deleted[0].metadata) == {"version", "content_sha256", "approval_status"}
