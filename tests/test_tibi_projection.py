"""REF S10, S11: Tibi's searches name their conversation, and OpsAtlas answers as its owner: records from the family
spaces that person may read, without restricted documents. Conversation-style records always apply. An unknown
conversation gets the Product Guide; no conversation named (Tibi itself) keeps the whole family."""
import os

import pytest
from fastapi.testclient import TestClient
from iam_helpers import sign_in


@pytest.fixture
def family(tmp_path, monkeypatch):
    from assistant.iam.service import Actor
    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    os.environ.update({"SME_TIBI_VOICE_URL": "http://127.0.0.1:9", "SALES_GOVERNANCE_AUTO_REVIEW": "0"})
    root = tmp_path / "sales"
    app = create_sales_app(root)
    app.state.retrieval.embedder = None
    service = {"x-sales-token": (root / "local-access.key").read_text()}
    with TestClient(app) as c:
        admin = {"Authorization": f"Bearer {sign_in(c, app)}"}
        rows = {r["id"]: r for r in c.get("/api/sales/knowledge", headers=service).json()["records"]}
        for record in ("overview", "commercial", "conv-persona"):
            reviewed = c.post(f"/api/tibi/knowledge/{record}/review", headers=admin,
                              json={"approve": True, "expected_hash": rows[record]["sha256"]})
            assert reviewed.status_code == 200, reviewed.text
        iam = app.state.auth.iam
        admin_id = iam.store.one("SELECT id FROM users WHERE login = ?", ("operator@example.test",))["id"]
        invited = iam.invite(Actor(admin_id, fresh=True), email="guide@example.test", display_name="Gita")
        reader = iam.accept_invitation(invited["token"], "walnut harbour lantern seventeen")
        app.state.tibi_owners.record("c-reader", reader["id"], "interview")
        app.state.tibi_owners.record("c-admin", admin_id, "interview")
        yield c, service


def ids(c, headers):
    return {r["id"] for r in c.get("/api/sales/knowledge", headers=headers).json()["records"] if r["eligible"]}


def test_tibi_answers_a_guide_reader_from_the_guide_only(family):
    c, service = family
    assert ids(c, service) == {"overview", "commercial", "conv-persona"}  # Tibi itself: the whole family
    assert ids(c, {**service, "x-tibi-conversation": "c-admin"}) == {"overview", "commercial", "conv-persona"}
    assert ids(c, {**service, "x-tibi-conversation": "c-reader"}) == {"overview", "conv-persona"}  # no playbook
    assert ids(c, {**service, "x-tibi-conversation": "c-unknown"}) == {"overview", "conv-persona"}
    found = c.post("/api/sales/search", headers={**service, "x-tibi-conversation": "c-reader"},
                   json={"q": "What does OpsAtlas cost, and what is the commercial model?"}).json()
    assert "commercial" not in {r["id"] for r in found["results"]}
    spoken = c.get("/api/sales/spoken", headers={**service, "x-tibi-conversation": "c-reader"}).json()
    assert all(v["record_id"] != "commercial" for v in spoken["variants"])


def test_the_digest_tibi_checks_before_speaking_is_the_callers_own(family):
    c, service = family
    reader = {**service, "x-tibi-conversation": "c-reader"}
    admin = {**service, "x-tibi-conversation": "c-admin"}
    assert c.get("/api/sales/digest", headers=reader).json()["digest"] == c.get("/api/sales/knowledge", headers=reader).json()["digest"]
    assert c.get("/api/sales/digest", headers=reader).json()["digest"] != c.get("/api/sales/digest", headers=admin).json()["digest"]


def test_the_service_key_can_no_longer_approve_anything(family):
    c, service = family
    for path in ("/api/sales/knowledge/overview/review", "/api/sales/spoken/x/review",
                 "/api/sales/governance/answers/x/review", "/api/sales/knowledge/overview/resolve"):
        assert c.post(path, headers=service, json={"approve": True, "expected_hash": "x"}).status_code in (404, 405), path


def test_a_document_restricted_inside_the_playbook_never_reaches_a_playbook_readers_tibi(family):
    """REF S16: per-document restriction (REF S13) holds on Tibi's channel too, not only the space's own pages."""
    from assistant.iam.service import Actor
    c, service = family
    app = c.app
    iam = app.state.auth.iam
    admin_id = iam.store.one("SELECT id FROM users WHERE login = ?", ("operator@example.test",))["id"]
    invited = iam.invite(Actor(admin_id, fresh=True), email="pat@example.test", display_name="Pat",
                         role_id="space_reader", space_id="sales-playbook")
    pat = iam.accept_invitation(invited["token"], "walnut harbour lantern seventeen")
    app.state.tibi_owners.record("c-pat", pat["id"], "interview")
    pats = {**service, "x-tibi-conversation": "c-pat"}
    assert "commercial" in ids(c, pats)  # a playbook reader hears the playbook
    source = next(r["source_id"] for r in c.get("/api/sales/knowledge", headers=service).json()["records"] if r["id"] == "commercial")
    admin = {"Authorization": f"Bearer {sign_in(c, app)}"}
    restricted = c.put(f"/api/iam/spaces/sales-playbook/restrictions/document/{source}", headers=admin,
                       json={"audience": [f"user:{admin_id}"], "reason": "pricing only"})
    assert restricted.status_code == 200, restricted.text
    assert "commercial" not in ids(c, pats)
    assert "commercial" in ids(c, {**service, "x-tibi-conversation": "c-admin"})
    found = c.post("/api/sales/search", headers=pats, json={"q": "What does OpsAtlas cost, and what is the commercial model?"})
    assert "commercial" not in {r["id"] for r in found.json()["results"]}
