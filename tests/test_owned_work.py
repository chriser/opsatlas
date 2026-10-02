"""REF S14: conversations and jobs belong to a person. In the conversation log a person sees, opens and exports only
the conversations they started; those who may read everyone's see them all. A governance review job is read by its id
only by the person who started it; colleagues read the space's latest review. Guessing another person's id answers
404, as an id that does not exist."""
import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from iam_helpers import sign_in

PW = "walnut harbour lantern seventeen"


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    from assistant.iam.service import Actor
    from services.opsatlas_sales import conversations
    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    os.environ.update({"SME_TIBI_VOICE_URL": "http://127.0.0.1:9", "SALES_GOVERNANCE_AUTO_REVIEW": "0"})
    root = tmp_path / "sales"
    app = create_sales_app(root)
    with TestClient(app) as client:
        admin = {"Authorization": f"Bearer {sign_in(client, app)}"}
        iam = app.state.auth.iam
        admin_id = iam.store.one("SELECT id FROM users WHERE login = ?", ("operator@example.test",))["id"]
        people = {}
        for name, role, space in (("sam", "sales_user", "product-guide"), ("ola", "sales_user", "product-guide"),
                                  ("ana", "space_approver", "product-guide"), ("ben", "space_approver", "product-guide")):
            invited = iam.invite(Actor(admin_id, fresh=True), email=f"{name}@example.test", display_name=name.title(),
                                 role_id=role, space_id=space)
            user = iam.accept_invitation(invited["token"], PW)
            people[name] = (user["id"], {"Authorization": f"Bearer {sign_in(client, app, f'{name}@example.test', PW)}"})
        now = datetime.now(timezone.utc).isoformat()
        for session, words in (("s-sam", "What does OpsAtlas do?"), ("s-ola", "Ola's private question")):
            conversations.append(root, {"session": session, "turn": 0, "at": now, "heard": words, "reply": "An answer."})
        app.state.tibi_owners.record("s-sam", people["sam"][0], "text")
        app.state.tibi_owners.record("s-ola", people["ola"][0], "text")
        yield client, admin, people


def test_a_person_sees_and_opens_only_their_own_conversations(workspace):
    client, admin, people = workspace
    sam = people["sam"][1]
    listing = client.get("/api/conversations", headers=sam)
    assert listing.status_code == 200, listing.text
    assert [s["session"] for s in listing.json()["sessions"]] == ["s-sam"] and listing.json()["everyone"] is False
    assert client.get("/api/conversations/s-sam", headers=sam).status_code == 200
    theirs = client.get("/api/conversations/s-ola", headers=sam)
    assert theirs.status_code == 404 and "private" not in theirs.text
    assert client.get("/api/conversations/flagged", headers=sam).status_code == 403  # the improvement list is everyone's
    everyone = client.get("/api/conversations", headers=admin).json()
    assert everyone["everyone"] is True and {s["session"] for s in everyone["sessions"]} == {"s-sam", "s-ola"}


def test_a_conversation_is_exported_as_a_transcript_by_who_may_export(workspace):
    client, admin, people = workspace
    sam = people["sam"][1]
    assert client.get("/api/conversations/s-sam/export", headers=sam).status_code == 403  # sales users do not export
    exported = client.get("/api/conversations/s-ola/export", headers=admin)
    assert exported.status_code == 200 and "Ola's private question" in exported.text and "**Tibi:** An answer." in exported.text
    assert client.get("/api/conversations/s-none/export", headers=admin).status_code == 404


def test_a_review_job_is_read_by_its_id_only_by_who_started_it(workspace):
    client, admin, people = workspace
    ana, ben = people["ana"][1], people["ben"][1]
    started = client.post("/api/governance/internal-review/reviews", json={}, headers=ana)
    assert started.status_code == 200, started.text
    job = started.json()["status"]["job_id"]
    assert started.json()["status"]["started_by"] == people["ana"][0]
    assert client.get(f"/api/governance/internal-review/reviews/{job}", headers=ana).status_code == 200
    assert client.get(f"/api/governance/internal-review/reviews/{job}", headers=ben).status_code == 404
    assert client.get("/api/governance/internal-review/latest", headers=ben).status_code == 200  # the space's review
