"""REF S12: each service route accepts only a service principal holding its permission. Tibi's credential reaches
Tibi's routes and is recorded as Tibi, acting for the conversation's owner; a credential that belongs to no principal
(a stolen or invented one) reaches no service route and no person's route; a principal holding only some permissions
is refused the rest. The Security page lists the principals with a fingerprint, never the key."""
import json
import os
import secrets

import pytest
from fastapi.testclient import TestClient
from iam_helpers import sign_in

from assistant.api.access import manifest

SERVICE_ROUTES_EXPECTED = 12


@pytest.fixture
def sales(tmp_path, monkeypatch):
    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    os.environ.update({"SME_TIBI_VOICE_URL": "http://127.0.0.1:9", "SALES_GOVERNANCE_AUTO_REVIEW": "0"})
    root = tmp_path / "sales"
    app = create_sales_app(root)
    app.state.retrieval.embedder = None
    with TestClient(app) as client:
        admin = {"Authorization": f"Bearer {sign_in(client, app)}"}
        yield client, app, root, admin


def service_routes(app):
    return [(r["method"], r["path"]) for r in manifest(app) if r["kind"] == "service"]


def call(client, method, path, headers):
    url = path.replace("{identifier}", "overview")
    return client.request(method, url, headers=headers, json={} if method == "POST" else None)


def test_a_credential_that_belongs_to_no_principal_reaches_nothing(sales):
    client, app, root, admin = sales
    routes = service_routes(app)
    assert len(routes) == SERVICE_ROUTES_EXPECTED, routes
    stolen = {"x-sales-token": secrets.token_urlsafe(32)}
    for method, path in routes:
        assert call(client, method, path, stolen).status_code == 403, (method, path)
        assert call(client, method, path, {}).status_code == 403, (method, path)
    # Nor does any key open a person's route: approving a source needs a person.
    tibi = {"x-sales-token": (root / "local-access.key").read_text().strip()}
    for headers in (stolen, tibi):
        assert client.post("/api/governance/sources/anything/approve", headers=headers).status_code == 401


def test_tibi_reaches_its_routes_and_is_recorded_as_acting_for_the_owner(sales):
    client, app, root, admin = sales
    admin_id = app.state.auth.iam.store.one("SELECT id FROM users WHERE login = ?", ("operator@example.test",))["id"]
    app.state.tibi_owners.record("c-1", admin_id, "text")
    tibi = {"x-sales-token": (root / "local-access.key").read_text().strip(), "x-tibi-conversation": "c-1"}
    for method, path in service_routes(app):
        assert call(client, method, path, tibi).status_code != 403, (method, path)
    lines = [json.loads(line) for f in (root / "logs" / "activity").glob("*.jsonl") for line in f.read_text().splitlines()]
    calls = [line for line in lines if line.get("path") == "/api/sales/knowledge"]
    assert calls and calls[-1]["service"] == "tibi" and calls[-1]["acting_for"] == admin_id and calls[-1]["person"] is None
    assert tibi["x-sales-token"] not in "".join(f.read_text() for f in (root / "logs" / "activity").glob("*.jsonl"))


def test_a_principal_is_refused_the_routes_outside_its_permissions(sales):
    client, app, root, admin = sales
    from services.opsatlas_sales.service_principals import ServicePrincipal, ServicePrincipals
    (root / "reader.key").write_text(secrets.token_urlsafe(32))
    principals = ServicePrincipals(root, (ServicePrincipal("reader", "A read-only sidecar", "reader.key", ("sales.read",), "tests"),))
    app.state.service_principals.principals.update(principals.principals)
    app.state.service_principals._keys.update(principals._keys)
    reader = {"x-sales-token": (root / "reader.key").read_text()}
    assert client.get("/api/sales/knowledge", headers=reader).status_code == 200
    for method, path in (("POST", "/api/sales/spoken"), ("POST", "/api/sales/proposals"), ("GET", "/api/sales/governance/agenda"),
                         ("POST", "/api/sales/governance/answers"), ("POST", "/api/sales/governance/verify")):
        response = call(client, method, path, reader)
        assert response.status_code == 403 and "may not call this route" in response.text, (method, path)


def test_the_security_page_lists_principals_with_a_fingerprint_never_the_key(sales):
    client, app, root, admin = sales
    listed = client.get("/api/iam/services", headers=admin)
    assert listed.status_code == 200, listed.text
    tibi = next(p for p in listed.json()["principals"] if p["id"] == "tibi")
    assert len(tibi["fingerprint"]) == 12 and (root / "local-access.key").read_text().strip() not in listed.text
    routes = {r for p in tibi["permissions"] for r in p["routes"]}
    assert "GET /api/sales/knowledge" in routes and len(routes) == SERVICE_ROUTES_EXPECTED
    assert listed.json()["without_credential"][0]["name"] == "Process diagram service"
