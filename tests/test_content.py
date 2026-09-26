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
    register.update(source.id, approval_status="approved")
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
    assert doc["published"]["text"] == GUIDE.decode() and doc["operator"]["name"] == "Kris Pochopien"
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
    assert any(e["action"] == "approve_source" and e["outcome"] == "ok" for e in log)
    versions = client.get(f"/api/content/documents/{sid}/versions").json()["versions"]
    assert [(v["n"], v["label"], v["current"]) for v in versions] == [(2, "approved", True), (1, "imported", False)]
    assert versions[0]["author"] == "Kris Pochopien" and versions[0]["note"] == "Approved"
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
    assert client.post(f"/api/content/documents/{sid}/return", json={"note": "Not yet"}).json()["status"] == "draft"


def test_a_draft_overtaken_by_another_edit_cannot_be_published(workspace):
    client, _, _, sid = workspace
    doc = client.get(f"/api/content/documents/{sid}").json()
    doc = client.put(f"/api/content/documents/{sid}/draft", json={"text": edit(doc["published"]["text"])}).json()
    client.post(f"/api/content/documents/{sid}/submit", json={})
    # The published text changes by another route while the draft waits.
    client.put(f"/api/governance/sources/{sid}/document", json={"text": "# Supplier guide\n\nChanged elsewhere, in place.\n"})
    doc = client.get(f"/api/content/documents/{sid}").json()
    assert doc["draft"]["stale"]
    refused = client.post(f"/api/content/documents/{sid}/publish", json={"draft_sha": doc["draft"]["sha"]})
    assert refused.status_code == 409 and "changed after this draft was started" in refused.json()["detail"]


def test_comments_follow_their_passage_through_edits(workspace):
    client, _, _, sid = workspace
    added = client.post(f"/api/content/documents/{sid}/comments", json={
        "quote": "Credit checks are done", "prefix": "", "suffix": " before", "text": "Is this still true?"}).json()
    assert added["anchored"] and added["author"] == "Kris Pochopien" and added["status"] == "open"
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
    data = register_upload(register, "facts.json", b'{"fact": "Suppliers need contracts"}', "Facts")
    ingest_source(register, sections, data.id)
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
    served = TestClient(client.app).get(stored["url"])  # an <img> sends no sign-in header
    assert served.status_code == 200 and served.headers["content-type"] == "image/png" and served.content == PNG
    assert client.post("/api/content/assets", files={"file": ("x.svg", b"<svg/>", "image/svg+xml")}).status_code == 409
    assert TestClient(client.app).get("/api/content/assets/..%2Fcontent.db").status_code == 404
    assert TestClient(client.app).get("/api/content/assets/missing.png").status_code == 404


def test_every_content_route_needs_the_operator_sign_in(workspace):
    client, _, _, sid = workspace
    anonymous = TestClient(client.app)
    for method, path in (("get", "/api/content/documents"), ("get", f"/api/content/documents/{sid}"),
                         ("put", f"/api/content/documents/{sid}/draft"), ("post", f"/api/content/documents/{sid}/publish"),
                         ("get", f"/api/content/documents/{sid}/versions"), ("post", "/api/content/comments/x/resolve"),
                         ("patch", f"/api/content/documents/{sid}/details"), ("post", "/api/content/assets")):
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
    pending = register_upload(register, "notes.md", b"# Notes\n\nSupplier notes for the approval test.\n", "Notes")
    ingest_source(register, sections, pending.id)
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
