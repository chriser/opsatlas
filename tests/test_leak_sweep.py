"""REF S16, the planted-sentence sweep: a document restricted to the administrator carries a code and a title word that
exist nowhere else. Every built-in role that does not administer the space is given to a person outside the document's
audience, and each of them calls every read route of the space twice, ids filled once with the public document's and
once with the restricted one's (as someone guessing would), asks and searches, opens Governance's overview and review
report, and downloads the analytics exports. Neither marker may come back, nor be written to the activity log. The
administrator worked first, so an answer, a search or a review prepared for someone who may read the document is there
to be served from a cache; and the same calls made as the administrator do return the markers, so the paths are real.

Nothing leaves the test: outbound connections are refused and the model echoes its prompt, so any evidence it was given
would be in the answer."""
import os
import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from iam_helpers import sign_in
from test_space_leaks import fill, hermetic, refuse

from assistant.api.access import manifest
from tests.door_helpers import decide

CODE, TITLE = "Wombat-Ledger-5528", "Kestrel-Quill"
MARKERS = (CODE, TITLE)
PUBLIC_DOC = "# Ordering\n\nThe buyer raises a purchase order for every supplier and records it in the order book.\n"
RESTRICTED_DOC = (f"# {TITLE} payroll exceptions\n\nThe payroll officer signs every payroll exception with the code {CODE}.\n\n"
                  f"## Process steps\n\n1. The payroll officer checks the exception.\n2. The payroll officer signs it with {CODE}.\n")
QUESTION = "What code does the payroll officer sign payroll exceptions with?"
PW = "walnut harbour lantern seventeen"
# Every built-in space role except the space owner, who administers the space and so reads everything.
ROLES = ("space_reader", "space_contributor", "space_approver", "analyst", "auditor", "product_owner", "sales_user",
         "external_guest")
POSTS = (("/api/ask", {"q": QUESTION}), ("/api/query", {"q": "payroll exception code", "top_k": 5}))


@pytest.fixture(scope="module")
def acme(tmp_path_factory):
    from assistant.iam.service import Actor
    from services.opsatlas_sales.app import create_sales_app
    saved = dict(os.environ)
    real = (socket.create_connection, socket.socket.connect)
    socket.create_connection, socket.socket.connect = refuse, refuse
    os.environ.update({"SME_TIBI_VOICE_URL": "http://127.0.0.1:9", "SALES_GOVERNANCE_AUTO_REVIEW": "0"})
    root = Path(os.path.realpath(tmp_path_factory.mktemp("sweep"))) / "sales"
    try:
        app = create_sales_app(root)
        hermetic(app)
        with TestClient(app) as client:
            admin = {"Authorization": f"Bearer {sign_in(client, app)}"}
            assert client.post("/api/spaces", json={"name": "Acme"}, headers=admin).status_code == 200
            hermetic(app.state.cores["acme"])
            head = {**admin, "X-OpsAtlas-Space": "acme"}
            ids = {}
            for name, text in (("ordering.md", PUBLIC_DOC), ("payroll.md", RESTRICTED_DOC)):
                up = client.post("/api/sources/upload", files={"file": (name, text.encode(), "text/markdown")}, headers=head).json()
                sid = up["id"] if "id" in up else up["source"]["id"]
                client.post(f"/api/sources/{sid}/ingest", headers=head)
                assert decide(client, sid, headers=head).status_code == 200
                ids[name] = sid
            iam = app.state.auth.iam
            admin_id = iam.store.one("SELECT id FROM users WHERE login = ?", ("operator@example.test",))["id"]
            restricted = client.put(f"/api/iam/spaces/acme/restrictions/document/{ids['payroll.md']}", headers=admin,
                                    json={"audience": [f"user:{admin_id}"], "reason": "payroll only"})
            assert restricted.status_code == 200, restricted.text
            # The administrator works first: an answer, a search and a governance review that all hold the markers.
            for path, body in POSTS:
                client.post(path, json=body, headers=head)
            client.post("/api/governance/internal-review/reviews", json={}, headers=head)
            assert client.post("/api/governance/reanalysis", headers=head).status_code == 200
            ids["datasets"] = [d["dataset"] for d in client.get("/api/analytics/export", headers=head).json()["datasets"]]
            people = {}
            for role in ROLES:
                email = f"{role.replace('_', '-')}@example.test"
                invited = iam.invite(Actor(admin_id, fresh=True), email=email, display_name=role.replace("_", " ").title(),
                                     role_id=role, space_id="acme")
                iam.accept_invitation(invited["token"], PW)
                people[role] = {"Authorization": f"Bearer {sign_in(client, app, email, PW)}", "X-OpsAtlas-Space": "acme"}
            yield client, app, root, head, people, ids
    finally:
        socket.create_connection, socket.socket.connect = real
        os.environ.clear()
        os.environ.update(saved)


def sweep(client, app, ids, headers) -> tuple[list[str], int]:
    """Every read route, filled with each document's ids, plus the posts: the urls whose reply holds a marker, and how
    many replies were 200."""
    core = app.state.cores["acme"]
    routes = sorted({r["path"] for r in manifest(core) if r["method"] == "GET"
                     and not r["path"].startswith(("/api/iam/", "/api/auth/", "/{", "/docs", "/openapi", "/redoc"))})
    urls = set()
    for source in (ids["ordering.md"], ids["payroll.md"]):
        for dataset in ids["datasets"]:
            own = {"source": source, "process": source, "dataset": dataset, "metric": "coverage_score"}
            urls |= {url for url in (fill(path, client, headers, own) for path in routes) if url}
    urls.add(f"/api/governance/remediation/{ids['ordering.md']}/{ids['payroll.md']}")
    found, ok = [], 0
    for url in sorted(urls):
        response = client.get(url, headers=headers)
        ok += response.status_code == 200
        if any(marker in response.text for marker in MARKERS):
            found.append(url)
    for path, body in POSTS:
        response = client.post(path, json=body, headers=headers)
        ok += response.status_code == 200
        if any(marker in response.text.replace(body.get("q", ""), "") for marker in MARKERS):
            found.append(path)
    return found, ok


def test_the_administrator_meets_the_markers_on_the_swept_paths(acme):
    """The positive control: the same sweep, as someone who may read the document, does return the markers."""
    client, app, root, head, people, ids = acme
    found, _ = sweep(client, app, ids, head)
    assert len(found) >= 8 and "/api/ask" in found and "/api/query" in found, found


@pytest.mark.parametrize("role", ROLES)
def test_no_role_outside_the_audience_receives_a_marker(acme, role):
    client, app, root, head, people, ids = acme
    found, ok = sweep(client, app, ids, people[role])
    assert ok >= 3, (role, ok)  # the role does reach the space's reads, so the sweep exercised it
    assert not found, (role, found)


def test_the_activity_log_never_holds_a_marker(acme):
    client, app, root, head, people, ids = acme
    logs = [p for p in (root / "logs").rglob("*") if p.is_file()]
    assert logs
    assert not [str(p.relative_to(root)) for p in logs if any(m in p.read_text(errors="ignore") for m in MARKERS)]
