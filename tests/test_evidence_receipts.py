"""REF S18: evidence receipts. A source has a version from the moment it is registered; every written answer stores a
receipt naming, for each citation, the source, the version of its text and that text's SHA-256, the passage's place and
hash, and the model, prompt version, space and person; the answer returns the receipt's id. After the document changes,
yesterday's receipt still names yesterday's version, and a new answer names the new one. Only the person who asked, or
someone who may read traces, can open a receipt."""
import hashlib
import os
import socket

import pytest
from fastapi.testclient import TestClient
from iam_helpers import sign_in
from test_space_leaks import hermetic, refuse

from tests.door_helpers import decide

DOC = "# Returns\n\nA customer may return goods within 30 days with a receipt. The store manager approves refunds.\n"
QUESTION = "Who approves refunds?"


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
        admin = {"Authorization": f"Bearer {sign_in(client, app)}"}
        assert client.post("/api/spaces", json={"name": "Acme"}, headers=admin).status_code == 200
        hermetic(app.state.cores["acme"])
        head = {**admin, "X-OpsAtlas-Space": "acme"}
        up = client.post("/api/sources/upload", files={"file": ("returns.md", DOC.encode(), "text/markdown")}, headers=head).json()
        sid = up["id"] if "id" in up else up["source"]["id"]
        client.post(f"/api/sources/{sid}/ingest", headers=head)
        assert decide(client, sid, headers=head).status_code == 200
        yield client, app, head, sid


def test_a_source_has_a_version_from_registration(acme):
    client, app, head, sid = acme
    versions = app.state.cores["acme"].state.content.store.versions(sid)  # nobody has opened it in content management
    assert [v["n"] for v in versions] == [1] and versions[0]["sha"] == hashlib.sha256(DOC.encode()).hexdigest()


def test_an_answer_carries_a_receipt_of_the_exact_version_it_rested_on(acme):
    client, app, head, sid = acme
    answer = client.post("/api/ask", json={"q": QUESTION}, headers=head).json()
    assert answer["receipt_id"].startswith("rcpt-")
    cited = [c for c in answer["citations"] if c["source_id"] == sid]
    assert cited and cited[0]["version"] == 1 and cited[0]["sha256"] == hashlib.sha256(DOC.encode()).hexdigest()
    assert cited[0]["passage_sha256"]
    receipt = client.get(f"/api/answers/receipts/{answer['receipt_id']}", headers=head).json()
    assert receipt["space"] == "acme" and receipt["person"] and receipt["prompt_version"]
    assert receipt["question_sha256"] == hashlib.sha256(QUESTION.encode()).hexdigest()
    assert receipt["evidence"][0]["version"] == 1 and receipt["evidence"][0]["sha256"] == cited[0]["sha256"]
    # The trace names the source and version too.
    trace = app.state.cores["acme"].state.answer.audit_trace.recent(1)[0]
    assert trace["receipt_id"] == answer["receipt_id"] and trace["evidence"][0]["version"] == 1


def test_yesterdays_receipt_still_names_yesterdays_version(acme):
    client, app, head, sid = acme
    before = client.post("/api/ask", json={"q": QUESTION}, headers=head).json()
    content = app.state.cores["acme"].state.content
    changed = DOC.replace("30 days", "14 days")
    draft = client.put(f"/api/content/documents/{sid}/draft", json={"text": changed}, headers=head)
    assert draft.status_code == 200, draft.text
    assert client.post(f"/api/content/documents/{sid}/submit", json={"note": "shorter window"}, headers=head).status_code == 200
    published = client.post(f"/api/content/documents/{sid}/publish", headers=head,
                            json={"draft_sha": draft.json()["draft"]["sha"], "note": "shorter window"})
    assert published.status_code == 200, published.text
    after = client.post("/api/ask", json={"q": QUESTION}, headers=head).json()
    new_version = content.current_version(sid)
    assert new_version["n"] > 1 and new_version["sha"] == hashlib.sha256(changed.encode()).hexdigest()
    assert next(c for c in after["citations"] if c["source_id"] == sid)["version"] == new_version["n"]
    old = client.get(f"/api/answers/receipts/{before['receipt_id']}", headers=head).json()
    assert old["evidence"][0]["version"] == 1 and old["evidence"][0]["sha256"] == hashlib.sha256(DOC.encode()).hexdigest()
    assert content.version(sid, 1)["text"] == DOC  # and that version's words are still there to show


def test_only_the_asker_or_a_trace_reader_opens_a_receipt(acme):
    from assistant.iam.service import Actor
    client, app, head, sid = acme
    answer = client.post("/api/ask", json={"q": QUESTION}, headers=head).json()
    iam = app.state.auth.iam
    admin_id = iam.store.one("SELECT id FROM users WHERE login = ?", ("operator@example.test",))["id"]
    invited = iam.invite(Actor(admin_id, fresh=True), email="rita@example.test", display_name="Rita",
                         role_id="space_reader", space_id="acme")
    iam.accept_invitation(invited["token"], "walnut harbour lantern seventeen")
    rita = {"Authorization": f"Bearer {sign_in(client, app, 'rita@example.test', 'walnut harbour lantern seventeen')}",
            "X-OpsAtlas-Space": "acme"}
    assert client.get(f"/api/answers/receipts/{answer['receipt_id']}", headers=rita).status_code == 404
    own = client.post("/api/ask", json={"q": QUESTION}, headers=rita).json()
    assert client.get(f"/api/answers/receipts/{own['receipt_id']}", headers=rita).status_code == 200
    assert client.get("/api/answers/receipts/rcpt-0000000000000000", headers=head).status_code == 404
