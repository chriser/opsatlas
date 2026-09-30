"""The Sales workspace in the secured mode (IAM F5, F6): no shared-key sign-in, one organisation cannot reach another,
a space owner administers only their space, every person reads the Product Guide, the voice socket takes a ticket."""
import os

import pytest
from fastapi.testclient import TestClient
from iam_helpers import EMAIL, sign_in

READER_PW, OWNER_PW = "reads a great many documents daily", "keeps the acme organisation tidy"


@pytest.fixture
def sales(tmp_path, monkeypatch):
    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    os.environ["SME_TIBI_VOICE_URL"] = "http://127.0.0.1:9"
    root = tmp_path / "sales"
    app = create_sales_app(root)
    app.state.retrieval.embedder = None
    with TestClient(app) as client:
        admin = {"Authorization": f"Bearer {sign_in(client, app)}"}
        for name in ("Acme", "Bolt"):
            assert client.post("/api/spaces", json={"name": name}, headers=admin).status_code == 200
        yield client, app, root, admin


def accept(client, email, password, link):
    token = link.split("#invitation:", 1)[1]
    assert client.post("/api/auth/invitations/accept", json={"token": token, "password": password}).status_code == 200
    response = client.post("/api/auth/login", json={"login": email, "password": password})
    client.cookies.clear()
    return {"Authorization": f"Bearer {response.json()['token']}"}


def invite(client, headers, email, role, space):
    body = {"email": email, "display_name": email.split("@")[0].title(), "role_id": role, "space_id": space}
    return client.post("/api/iam/users/invite", json=body, headers=headers)


def upload(client, headers, space, name="doc.md", text="# Doc\n\nA line of text.\n"):
    response = client.post("/api/sources/upload", files={"file": (name, text.encode(), "text/markdown")}, data={"title": name},
                           headers={**headers, "X-OpsAtlas-Space": space})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_the_workspace_key_is_a_service_credential_not_a_sign_in(sales):
    client, app, root, admin = sales
    key = (root / "local-access.key").read_text().strip()
    assert client.post("/api/auth/login", json={"password": key}).status_code == 401
    assert client.post("/api/auth/login", json={"login": EMAIL, "password": key}).status_code == 401
    assert client.get("/api/sales/knowledge", headers={"x-sales-token": key}).status_code == 200
    assert client.get("/api/tibi/knowledge", headers={"x-sales-token": key}).status_code == 401
    reference = client.get("/openapi.json")  # no API reference in the secured mode (the page route answers instead)
    assert reference.status_code != 200 or '"openapi"' not in reference.text


def test_a_reader_of_one_organisation_gets_nothing_from_another_not_even_its_name(sales):
    client, app, root, admin = sales
    rita = accept(client, "rita@example.test", READER_PW, invite(client, admin, "rita@example.test", "space_reader", "acme").json()["link"])
    upload(client, admin, "bolt", "secret-plans.md", "# Bolt plans\n\nThe canary word is ptarmigan.\n")
    assert client.get("/api/sources", headers={**rita, "X-OpsAtlas-Space": "acme"}).status_code == 200
    for selector in ({"X-OpsAtlas-Space": "bolt"}, {"X-OpsAtlas-Space": "sales-playbook"}, {"X-OpsAtlas-Space": "system"}):
        refused = client.get("/api/sources", headers={**rita, **selector})
        assert refused.status_code == 404 and "bolt" not in refused.text.lower() and "ptarmigan" not in refused.text, selector
    assert client.get("/api/sources?space=bolt", headers=rita).status_code == 404
    assert client.get("/api/content/documents", headers={**rita, "X-OpsAtlas-Space": "bolt"}).status_code == 404
    assert client.get("/api/sources", headers=rita).status_code == 200  # no selector: the Product Guide, hers to read
    listed = client.get("/api/spaces", headers=rita).json()["spaces"]
    assert {s["id"] for s in listed} == {"product-guide", "acme"}
    me = client.get("/api/auth/me", headers=rita).json()
    assert {s["id"] for s in me["spaces"]} == {"product-guide", "acme"} and me["platform_permissions"] == sorted(me["platform_permissions"])
    assert client.post("/api/spaces", json={"name": "Mine"}, headers=rita).status_code == 403
    assert client.patch("/api/spaces/acme", json={"name": "Renamed"}, headers=rita).status_code == 403
    assert client.patch("/api/spaces/bolt", json={"name": "Renamed"}, headers=rita).status_code == 404
    for path in ("/api/iam/users", "/api/conversations", "/api/iam/audit"):
        assert client.get(path, headers=rita).status_code == 403, path
    assert client.post("/api/services/restart", json={"which": "tibi"}, headers=rita).status_code == 403
    assert client.get("/api/tibi/status", headers=rita).status_code == 200  # Tibi is part of reading the guide
    assert client.get("/api/tibi/knowledge", headers=rita).status_code == 403  # its knowledge base is not


def test_a_space_owner_administers_that_space_and_nothing_beyond_it(sales):
    client, app, root, admin = sales
    olga = accept(client, "olga@example.test", OWNER_PW, invite(client, admin, "olga@example.test", "space_owner", "acme").json()["link"])
    inside = invite(client, olga, "rita@example.test", "space_reader", "acme")
    assert inside.status_code == 200
    assert invite(client, olga, "sam@example.test", "space_reader", "bolt").status_code in (403, 404)
    assert invite(client, olga, "sam@example.test", "identity_administrator", None).status_code == 403
    assert client.post("/api/iam/bindings", json={"subject_id": inside.json()["user"]["id"], "role_id": "platform_administrator",
                                                  "scope_type": "platform"}, headers=olga).status_code == 403
    grantable = {r["id"] for r in client.get("/api/iam/grantable?space_id=acme", headers=olga).json()["roles"]}
    assert "space_reader" in grantable and "space_owner" in grantable and "platform_administrator" not in grantable
    rita = accept(client, "rita@example.test", READER_PW, inside.json()["link"])
    members = client.get("/api/iam/spaces/acme/members", headers=olga).json()["members"]
    assert {m["login"] for m in members} >= {"olga@example.test", "rita@example.test"}
    assert client.get("/api/iam/spaces/bolt/members", headers=olga).status_code in (403, 404)
    assert client.get("/api/sources", headers={**rita, "X-OpsAtlas-Space": "acme"}).status_code == 200
    assert client.delete("/api/iam/spaces/acme/members/" + inside.json()["user"]["id"], headers=olga).status_code == 200
    assert client.get("/api/sources", headers={**rita, "X-OpsAtlas-Space": "acme"}).status_code == 404
    assert client.get("/api/sources", headers=rita).status_code == 200  # the Product Guide entitlement stays
    explained = client.post("/api/iam/access/explain", json={"user_id": inside.json()["user"]["id"], "permission": "documents.read",
                                                              "space_id": "acme"}, headers=olga).json()
    assert explained["allowed"] is False and explained["membership_active"] is False


def test_transfers_need_authority_in_both_spaces_and_the_reader_never_learns_of_the_other(sales):
    client, app, root, admin = sales
    sid = upload(client, admin, "acme")
    rita = accept(client, "rita@example.test", READER_PW, invite(client, admin, "rita@example.test", "space_reader", "acme").json()["link"])
    assert client.post("/api/spaces/transfer", json={"source_id": sid, "to": "bolt"}, headers=rita).status_code == 404
    olga = accept(client, "olga@example.test", OWNER_PW, invite(client, admin, "olga@example.test", "space_owner", "acme").json()["link"])
    assert client.post("/api/spaces/transfer", json={"source_id": sid, "to": "bolt"}, headers=olga).status_code == 404  # bolt is hidden
    moved = client.post("/api/spaces/transfer", json={"source_id": sid, "to": "bolt"}, headers=admin)
    assert moved.status_code == 200 and moved.json()["to"] == "bolt" and moved.json()["actor"] == "Test Operator"


def test_the_voice_socket_ticket_goes_to_those_allowed_the_voice_and_works_once(sales):
    client, app, root, admin = sales
    ticket = client.post("/api/tibi/ws-ticket", json={"conversation_id": "s1"}, headers=admin).json()["ticket"]
    iam = app.state.auth.iam
    assert iam.consume_ticket("wrong", "s1") is None and iam.consume_ticket(ticket, "other") is None
    assert iam.consume_ticket(ticket, "s1") is None  # the wrong conversation above used it up: single use, no second chance
    ticket = client.post("/api/tibi/ws-ticket", json={"conversation_id": "s1"}, headers=admin).json()["ticket"]
    user, session = iam.consume_ticket(ticket, "s1")
    assert user["login"] == EMAIL and iam.session_by_id(session["id"]) is not None
    assert client.post("/api/auth/logout", headers=admin).status_code == 200
    assert iam.session_by_id(session["id"]) is None  # the gateway's watchdog closes the socket on this


def test_activity_records_sign_ins_and_the_audit_records_them_too(sales):
    client, app, root, admin = sales
    from services.opsatlas_sales.activity import read
    assert client.post("/api/auth/login", json={"login": EMAIL, "password": "definitely not the password"}).status_code == 401
    events = [e for e in read(root) if e.get("kind") == "auth"]
    assert {e["event"] for e in events} >= {"signed in", "sign-in refused"}
    audit = client.get("/api/iam/audit", params={"action": "sign_in"}, headers=admin).json()["events"]
    assert {e["outcome"] for e in audit} >= {"success", "refused"} and all("password" not in str(e.get("detail")) for e in audit)
