"""REF S13, per-document grants (the Human's decision, 2 Oct 2026): a document restricted to an audience is invisible to
a reader outside it on every path: listings, the document and its sections, comments, search, answers, the facts map,
the activity model and process views. Those who administer the space keep access; lifting the restriction restores it."""
import os
import socket

import pytest
from fastapi.testclient import TestClient
from iam_helpers import sign_in
from test_space_leaks import hermetic, refuse

SECRET = "Quokka-Vault-9931"
PUBLIC_DOC = "# Ordering\n\nThe buyer raises a purchase order for every supplier.\n"
SECRET_DOC = f"# Payroll exceptions\n\nThe payroll officer signs every exception with the code {SECRET}.\n"
PW = "a reader's own long password"


@pytest.fixture
def acme(tmp_path, monkeypatch):
    from assistant.iam.service import Actor
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
        ids = {}
        for name, text in (("ordering.md", PUBLIC_DOC), ("payroll.md", SECRET_DOC)):
            up = client.post("/api/sources/upload", files={"file": (name, text.encode(), "text/markdown")}, headers=head).json()
            sid = up["id"] if "id" in up else up["source"]["id"]
            client.post(f"/api/sources/{sid}/ingest", headers=head)
            assert client.post(f"/api/governance/sources/{sid}/approve", headers=head).status_code == 200
            ids[name] = sid
        client.post(f"/api/content/documents/{ids['payroll.md']}/comments", headers=head,
                    json={"quote": "payroll officer", "text": f"Check {SECRET} yearly."})
        iam = app.state.auth.iam
        admin_id = iam.store.one("SELECT id FROM users WHERE login = ?", ("operator@example.test",))["id"]
        invited = iam.invite(Actor(admin_id, fresh=True), email="rita@example.test", display_name="Rita",
                             role_id="space_reader", space_id="acme")
        iam.accept_invitation(invited["token"], PW)
        reader = {"Authorization": f"Bearer {sign_in(client, app, 'rita@example.test', PW)}", "X-OpsAtlas-Space": "acme"}
        restricted = client.put(f"/api/iam/spaces/acme/restrictions/document/{ids['payroll.md']}", headers=admin,
                                json={"audience": [f"user:{admin_id}"], "reason": "payroll only"})
        assert restricted.status_code == 200, restricted.text
        yield client, app, head, reader, ids


def _leaks(response) -> bool:
    return SECRET in response.text


def test_a_restricted_document_is_invisible_to_a_reader_outside_its_audience(acme):
    client, app, head, reader, ids = acme
    secret, public = ids["payroll.md"], ids["ordering.md"]
    listing = client.get("/api/sources", headers=reader)
    assert [s["id"] for s in listing.json()] == [public]
    for path in (f"/api/content/documents/{secret}", f"/api/content/documents/{secret}/versions",
                 f"/api/content/documents/{secret}/comments", f"/api/governance/sources/{secret}/document",
                 f"/api/sources/{secret}/sections"):
        response = client.get(path, headers=reader)
        # 404 from the guard, or 403 where the reader's role does not reach the route at all (governance)
        assert response.status_code in (403, 404) and not _leaks(response), path
    assert client.get(f"/api/content/documents/{secret}", headers=reader).status_code == 404
    library = client.get("/api/content/library", headers=reader)
    assert secret not in library.text
    search = client.post("/api/query", json={"q": "payroll exception code", "top_k": 5}, headers=reader)
    assert search.status_code == 200 and not _leaks(search)
    answer = client.post("/api/ask", json={"q": "What code does the payroll officer use?"}, headers=reader)
    assert answer.status_code == 200 and not _leaks(answer)  # the echo model would repeat any evidence it was given
    for path in ("/api/ontology/objects", "/api/eam/svg?view=activity", "/api/process/registry"):
        response = client.get(path, headers=reader)
        assert response.status_code in (403, 404) and not _leaks(response), path
    # The reader still uses everything else.
    assert client.get(f"/api/content/documents/{public}", headers=reader).status_code == 200


def test_the_administrator_keeps_access_and_lifting_the_restriction_restores_it(acme):
    client, app, head, reader, ids = acme
    secret = ids["payroll.md"]
    assert client.get(f"/api/content/documents/{secret}", headers=head).status_code == 200
    assert SECRET in client.post("/api/ask", json={"q": "What code does the payroll officer use?"}, headers=head).text
    admin = {k: v for k, v in head.items() if k != "X-OpsAtlas-Space"}
    assert client.put(f"/api/iam/spaces/acme/restrictions/document/{secret}", headers=admin, json={"audience": []}).status_code == 200
    assert client.get(f"/api/content/documents/{secret}", headers=reader).status_code == 200
    assert {s["id"] for s in client.get("/api/sources", headers=reader).json()} == set(ids.values())


def test_a_restricted_folder_hides_what_it_holds(acme):
    client, app, head, reader, ids = acme
    secret = ids["payroll.md"]
    admin = {k: v for k, v in head.items() if k != "X-OpsAtlas-Space"}
    client.put(f"/api/iam/spaces/acme/restrictions/document/{secret}", headers=admin, json={"audience": []})
    group = client.post("/api/content/groups", json={"title": "HR"}, headers=head).json()
    group_id = group.get("id") or group["group"]["id"]
    assert client.post("/api/content/library/move", json={"node": f"source:{secret}", "parent": f"group:{group_id}"},
                       headers=head).status_code == 200
    me = client.get("/api/auth/me", headers=admin).json()["user"]["id"]
    assert client.put(f"/api/iam/spaces/acme/restrictions/folder/{group_id}", headers=admin,
                      json={"audience": [f"user:{me}"]}).status_code == 200
    assert client.get(f"/api/content/documents/{secret}", headers=reader).status_code == 404
    assert not _leaks(client.post("/api/ask", json={"q": "What code does the payroll officer use?"}, headers=reader))
