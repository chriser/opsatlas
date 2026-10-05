"""Bug #2202 (REF S13): a restriction belongs to the space that holds its document or folder.

IAM's one writer of restrictions (``Identity.restrict``) writes a resource's row only for a space that holds the resource
now: (a) a holder may set, change or lift it, and the row follows the holder; (b) but may not take it from another space
that also still holds it; (c) a space that does not hold it is refused, except the row's own space when no space holds
the resource any more. A refusal is 404, as for a resource that does not exist, with nothing changed and no audit event.
The design: docs/benchmark/evidence/2026-10-05-bug-2202.md. Hermetic: no network, no live service, no model.
"""
from __future__ import annotations

import ast
import random
import re
from pathlib import Path

import pytest

from assistant.iam.service import Actor, IamError, Identity
from assistant.iam.store import IamStore
from tests.door_helpers import decide
from tests.iam_helpers import sign_in

PW = "walnut harbour lantern seventeen"
GUIDE, PLAYBOOK = "product-guide", "sales-playbook"
ROOT = Path(__file__).resolve().parents[1]


def admin_id(ws) -> str:
    return ws.app.state.auth.iam.store.one("SELECT id FROM users WHERE login = ?", ("operator@example.test",))["id"]


def person(ws, email: str, name: str, space: str, role: str) -> tuple[str, dict]:
    iam = ws.app.state.auth.iam
    invited = iam.invite(Actor(admin_id(ws), fresh=True), email=email, display_name=name, role_id=role, space_id=space)
    user = iam.accept_invitation(invited["token"], PW)
    return user["id"], {"Authorization": f"Bearer {sign_in(ws.client, ws.app, email, PW)}"}


def put(ws, space: str, kind: str, resource_id: str, audience: list[str], headers: dict | None = None):
    return ws.client.put(f"/api/iam/spaces/{space}/restrictions/{kind}/{resource_id}", headers=headers,
                         json={"audience": audience, "reason": "Bug #2202"})


def row(ws, kind: str, resource_id: str) -> dict | None:
    return ws.app.state.auth.iam.store.one("SELECT space_id, restricted_to FROM resource_policies WHERE resource_type = ? "
                                           "AND resource_id = ?", (kind, resource_id))


def guide_document(ws, text: bytes = b"# Overview\n\nAlpha is the first plan.\n") -> str:
    up = ws.client.post("/api/sources/upload", files={"file": ("overview.md", text, "text/markdown")})
    assert up.status_code == 200, up.text
    source_id = up.json()["id"] if "id" in up.json() else up.json()["source"]["id"]
    assert ws.client.post(f"/api/sources/{source_id}/ingest").status_code == 200
    assert decide(ws.client, source_id).status_code == 200
    return source_id


def reads(ws, headers: dict, space: str, source_id: str) -> int:
    return ws.client.get(f"/api/content/documents/{source_id}", headers={**headers, "X-OpsAtlas-Space": space}).status_code


# ---- through the app ------------------------------------------------------------------------------------------------

def test_another_spaces_owner_cannot_lift_a_restriction(sales_workspace):
    """The bug as found: Acme's owner lifting a Product Guide document's restriction from Acme's path."""
    ws = sales_workspace
    doc = guide_document(ws)
    assert put(ws, GUIDE, "document", doc, [f"user:{admin_id(ws)}"]).status_code == 200
    _, pia = person(ws, "pia@example.test", "Pia", GUIDE, "product_owner")
    _, olga = person(ws, "olga@example.test", "Olga", ws.space, "space_owner")
    assert reads(ws, pia, GUIDE, doc) == 404
    lifted = put(ws, ws.space, "document", doc, [], headers=olga)
    assert lifted.status_code == 404
    assert row(ws, "document", doc)["space_id"] == GUIDE
    assert reads(ws, pia, GUIDE, doc) == 404  # the restriction stands


def test_another_space_cannot_restrict_a_resource_it_does_not_hold(sales_workspace):
    ws = sales_workspace
    doc = guide_document(ws)
    _, olga = person(ws, "olga@example.test", "Olga", ws.space, "space_owner")
    assert put(ws, ws.space, "document", doc, [], headers=olga).status_code == 404
    assert put(ws, ws.space, "folder", "no-such-folder", []).status_code == 404
    assert row(ws, "document", doc) is None


def test_a_space_restricts_its_own_document_as_before(sales_workspace):
    """Set, change and lift in the space that holds it: each answers 200 and leaves its audit event, as before. Acme is
    created after the app starts (the fixture posts it), so the workspace's resolver knows a space created at run time."""
    ws = sales_workspace
    doc = ws.document(b"# Pricing\n\nAlpha is the first plan.\n")
    iam = ws.app.state.auth.iam
    for audience in ([f"user:{admin_id(ws)}"], [f"user:{admin_id(ws)}"], []):
        assert put(ws, ws.space, "document", doc, audience, headers=ws.headers).status_code == 200
    assert row(ws, "document", doc)["space_id"] == ws.space
    actions = [e["action"] for e in iam.audit.events(limit=50) if e.get("target_id") == doc]
    assert actions.count("resource.restricted") == 2 and actions.count("resource.unrestricted") == 1


def test_a_request_served_by_another_core_answers_for_the_path_space(sales_workspace):
    """No space header: the guide's core serves the request, and the workspace's resolver answers for Acme."""
    ws = sales_workspace
    doc = ws.document(b"# Pricing\n\nAlpha is the first plan.\n")
    assert put(ws, ws.space, "document", doc, [f"user:{admin_id(ws)}"]).status_code == 200
    assert row(ws, "document", doc)["space_id"] == ws.space


def test_after_a_transfer_the_new_space_restricts_and_the_old_cannot(sales_workspace):
    ws = sales_workspace
    doc = guide_document(ws)
    assert put(ws, GUIDE, "document", doc, [f"user:{admin_id(ws)}"]).status_code == 200
    moved = ws.client.post("/api/spaces/transfer", json={"source_id": doc, "to": ws.space})
    assert moved.status_code == 200, moved.text
    assert put(ws, GUIDE, "document", doc, []).status_code == 404  # the guide no longer holds it
    assert put(ws, ws.space, "document", doc, [f"user:{admin_id(ws)}"]).status_code == 200  # the row follows its holder
    assert row(ws, "document", doc)["space_id"] == ws.space


def test_a_misfiled_row_is_taken_back_by_the_space_that_holds_the_document(sales_workspace):
    ws = sales_workspace
    doc = guide_document(ws)
    iam = ws.app.state.auth.iam
    iam.store.insert("resource_policies", {"resource_type": "document", "resource_id": doc, "space_id": ws.space,
                                           "restricted_to": "[]", "updated_at": iam.store.stamp(), "updated_by": None})
    assert put(ws, GUIDE, "document", doc, [f"user:{admin_id(ws)}"]).status_code == 200
    assert row(ws, "document", doc)["space_id"] == GUIDE


def test_a_deleted_documents_restriction_is_lifted_by_its_own_space_only(sales_workspace):
    ws = sales_workspace
    doc = ws.document(b"# Pricing\n\nAlpha is the first plan.\n")
    assert put(ws, ws.space, "document", doc, [f"user:{admin_id(ws)}"], headers=ws.headers).status_code == 200
    assert ws.client.delete(f"/api/sources/{doc}", headers=ws.headers).status_code in (200, 204)
    assert put(ws, GUIDE, "document", doc, []).status_code == 404  # not the guide's
    assert put(ws, ws.space, "document", doc, [], headers=ws.headers).status_code == 200  # its own space lifts it



def test_another_spaces_folder_and_a_non_empty_audience_are_refused(sales_workspace):
    ws = sales_workspace
    doc = guide_document(ws)
    made = ws.client.post("/api/content/groups", json={"title": "Guide plans"})  # no space header: the guide's
    assert made.status_code == 200, made.text
    folder = made.json()["id"]
    _, olga = person(ws, "olga@example.test", "Olga", ws.space, "space_owner")
    for kind, resource_id in (("document", doc), ("folder", folder)):
        assert put(ws, ws.space, kind, resource_id, [f"user:{admin_id(ws)}"], headers=olga).status_code == 404
        assert row(ws, kind, resource_id) is None
    assert put(ws, GUIDE, "folder", folder, [f"user:{admin_id(ws)}"]).status_code == 200  # its own space may
    assert row(ws, "folder", folder)["space_id"] == GUIDE


def test_a_deleted_folders_restriction_is_lifted_by_its_own_space_only(sales_workspace):
    ws = sales_workspace
    made = ws.client.post("/api/content/groups", json={"title": "Pricing"}, headers=ws.headers)
    assert made.status_code == 200, made.text
    folder = made.json()["id"]
    assert put(ws, ws.space, "folder", folder, [f"user:{admin_id(ws)}"], headers=ws.headers).status_code == 200
    assert ws.client.delete(f"/api/content/groups/{folder}", headers=ws.headers).status_code == 200
    assert put(ws, GUIDE, "folder", folder, []).status_code == 404  # not the guide's
    assert put(ws, ws.space, "folder", folder, [], headers=ws.headers).status_code == 200  # its own space lifts it
    assert row(ws, "folder", folder) == {"space_id": ws.space, "restricted_to": "[]"}


def test_an_archived_space_cannot_tell_so_a_deleted_documents_restriction_waits(sales_workspace):
    """An archived space keeps its data but has no core, so the workspace cannot tell what it holds; that counts against
    the change (R2-5). Restored, it can tell again."""
    ws = sales_workspace
    assert ws.client.post("/api/spaces", json={"name": "Beta"}).status_code == 200
    doc = ws.document(b"# Pricing\n\nAlpha is the first plan.\n")
    assert put(ws, ws.space, "document", doc, [f"user:{admin_id(ws)}"], headers=ws.headers).status_code == 200
    assert ws.client.delete(f"/api/sources/{doc}", headers=ws.headers).status_code in (200, 204)
    assert ws.client.patch("/api/spaces/beta", json={"status": "archived"}).status_code == 200
    assert put(ws, ws.space, "document", doc, [], headers=ws.headers).status_code == 404
    assert ws.client.patch("/api/spaces/beta", json={"status": "active"}).status_code == 200
    assert put(ws, ws.space, "document", doc, [], headers=ws.headers).status_code == 200


def test_a_lone_core_restricts_only_its_own_spaces_documents_and_folders(tmp_path, monkeypatch):
    """create_app sets the own-space resolver when none is set: its register for documents, its folders, and nothing in
    any other space, so a deleted document's restriction can still be lifted by its own space."""
    import os
    import socket

    from fastapi.testclient import TestClient

    from assistant.api.app import create_app
    from assistant.api.auth import AuthService
    from assistant.sources.register import SourceRegister
    from tests.test_space_leaks import hermetic, refuse
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    iam = Identity(IamStore(tmp_path / "iam.db"), origin="http://testserver", guide_space="default")
    iam.register_space("default", "Knowledge base", "product")
    iam.register_space("other", "Other", "organisation")
    app = create_app(SourceRegister(tmp_path / "data"), AuthService(iam=iam), space_id="default")
    hermetic(app)
    assert iam.holds is not None
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {sign_in(client, app)}"})
    up = client.post("/api/sources/upload", files={"file": ("pricing.md", b"# Pricing\n\nAlpha.\n", "text/markdown")})
    assert up.status_code == 200, up.text
    doc = up.json()["id"] if "id" in up.json() else up.json()["source"]["id"]
    folder = client.post("/api/content/groups", json={"title": "Plans"}).json()["id"]
    me = iam.store.one("SELECT id FROM users WHERE login = ?", ("operator@example.test",))["id"]
    for space, kind, resource_id, status in (("other", "document", doc, 404), ("other", "folder", folder, 404),
                                             ("default", "document", doc, 200), ("default", "folder", folder, 200)):
        answered = client.put(f"/api/iam/spaces/{space}/restrictions/{kind}/{resource_id}",
                              json={"audience": [f"user:{me}"], "reason": "Bug #2202"})
        assert answered.status_code == status, (space, kind, answered.text)
    assert client.delete(f"/api/sources/{doc}").status_code in (200, 204)
    lifted = client.put(f"/api/iam/spaces/default/restrictions/document/{doc}", json={"audience": [], "reason": "gone"})
    assert lifted.status_code == 200, lifted.text

# ---- IAM alone: the rule, held twice, no resolver, and a seeded scenario suite -----------------------------------

def _iam(tmp_path, holdings: dict[str, set[str]] | None):
    iam = Identity(IamStore(tmp_path / "iam.db"), origin="http://127.0.0.1:8780", guide_space="a")
    for space in ("a", "b", "c"):
        iam.register_space(space, space.upper(), "organisation")
    admin, _ = iam.bootstrap_admin("kris@example.test", "Kris", password="the quiet river runs east")
    if holdings is not None:
        iam.holds = lambda space, kind, rid: rid in holdings.get(space, set())
    return iam, Actor(admin["id"], fresh=True)


def test_a_document_held_twice_keeps_its_row_with_the_space_that_wrote_it(tmp_path):
    holdings = {"a": {"d1"}, "b": {"d1"}}
    iam, admin = _iam(tmp_path, holdings)
    iam.restrict(admin, "a", "document", "d1", [f"user:{admin.id}"])
    with pytest.raises(IamError) as refused:
        iam.restrict(admin, "b", "document", "d1", [])  # (b): no taking it from a space that still holds it
    assert refused.value.status == 404
    assert iam.store.one("SELECT space_id FROM resource_policies WHERE resource_id = 'd1'")["space_id"] == "a"


def test_without_a_resolver_every_change_is_refused(tmp_path):
    iam, admin = _iam(tmp_path, None)
    with pytest.raises(IamError):
        iam.restrict(admin, "a", "document", "d1", [])
    assert iam.store.all("SELECT * FROM resource_policies") == []



def test_a_space_that_cannot_tell_counts_against_the_change(tmp_path):
    """A resolver that answers None, or fails, cannot tell (R2-5): the path's space is refused, a row is not taken from
    a space that might still hold it, and a deleted resource's row is not changed while any space cannot tell."""
    answers: dict[str, object] = {}

    def holds(space, kind, rid):
        answer = answers.get(space, False)
        if answer == "fail":
            raise OSError("the store cannot be read")
        return answer

    iam, admin = _iam(tmp_path, {})
    iam.holds = holds
    answers.update(a=True)
    iam.restrict(admin, "a", "document", "d1", [f"user:{admin.id}"])
    for case in ({"a": None}, {"a": "fail"}, {"b": True, "a": None}, {"b": True, "a": "fail"}, {"c": None},
                 {"c": "fail"}):
        answers.clear()
        answers.update(case)
        target = "b" if case.get("b") else "a"  # the holder tries to take the row; otherwise its own space changes it
        with pytest.raises(IamError) as refused:
            iam.restrict(admin, target, "document", "d1", [])
        assert refused.value.status == 404, case
        assert iam.store.one("SELECT space_id FROM resource_policies WHERE resource_id = 'd1'")["space_id"] == "a"


def test_a_row_written_between_the_check_and_the_write_answers_conflict(tmp_path):
    """The check runs before IAM's transaction (R2-2): a row another space writes meanwhile, or a row whose space changes
    meanwhile, makes the write answer 409 and change nothing."""
    iam, admin = _iam(tmp_path, None)

    def meanwhile(write):
        done = []

        def holds(space, kind, rid):
            if not done:
                done.append(write())
            return space == "a"
        return holds

    stamp = iam.store.stamp
    iam.holds = meanwhile(lambda: iam.store.insert("resource_policies", {
        "resource_type": "document", "resource_id": "d1", "space_id": "b", "restricted_to": "[]",
        "updated_at": stamp(), "updated_by": None}))
    with pytest.raises(IamError) as inserted:
        iam.restrict(admin, "a", "document", "d1", [f"user:{admin.id}"])
    assert inserted.value.status == 409
    iam.holds = lambda space, kind, rid: space == "a"
    iam.restrict(admin, "a", "document", "d1", [f"user:{admin.id}"])  # the holder takes it: b no longer holds it
    iam.holds = meanwhile(lambda: iam.store.run("UPDATE resource_policies SET space_id = 'c' WHERE resource_id = 'd1'"))
    with pytest.raises(IamError) as moved:
        iam.restrict(admin, "a", "document", "d1", [])
    assert moved.value.status == 409
    assert iam.store.one("SELECT space_id, restricted_to FROM resource_policies WHERE resource_id = 'd1'") == {
        "space_id": "c", "restricted_to": f'["user:{admin.id}"]'}

def _allowed(holdings, rows, space, rid) -> bool:
    """The rule, written independently of IAM's code: (a), (b), (c)."""
    holder = rid in holdings[space]
    owner = rows.get(rid)
    if holder:
        return not (owner is not None and owner != space and rid in holdings[owner])
    return owner == space and not any(rid in held for held in holdings.values())


@pytest.mark.parametrize("seed", range(40))
def test_restrictions_keep_the_rule_over_random_scenarios(tmp_path, seed):
    """Seeded: documents appear, move, are held twice and are deleted across three spaces, and every space tries to
    restrict or lift them. After each try, IAM's answer and the row's space match the rule (REF S13, Bug #2202)."""
    rnd = random.Random(seed)
    holdings = {"a": set(), "b": set(), "c": set()}
    iam, admin = _iam(tmp_path / str(seed), holdings)
    rows: dict[str, str] = {}
    for _ in range(60):
        rid = rnd.choice(["d1", "d2", "d3"])
        step = rnd.choice(["add", "move", "copy", "delete", "restrict", "restrict", "restrict"])
        if step == "add":
            holdings[rnd.choice("abc")].add(rid)
        elif step == "move":
            for held in holdings.values():
                held.discard(rid)
            holdings[rnd.choice("abc")].add(rid)
        elif step == "copy":
            holdings[rnd.choice("abc")].add(rid)  # held twice, as an interrupted move leaves it
        elif step == "delete":
            for held in holdings.values():
                held.discard(rid)
        else:
            space, audience = rnd.choice("abc"), rnd.choice([[], [f"user:{admin.id}"]])
            expected = _allowed(holdings, rows, space, rid)
            try:
                iam.restrict(admin, space, "document", rid, audience)
                done = True
            except IamError as refused:
                assert refused.status == 404, refused.message
                done = False
            assert done == expected, (seed, step, space, rid, holdings, rows)
            if done:
                rows[rid] = space
            stored = iam.store.one("SELECT space_id FROM resource_policies WHERE resource_id = ?", (rid,))
            assert (stored["space_id"] if stored else None) == rows.get(rid)


# ---- one writer, one rule ---------------------------------------------------------------------------------------------

def test_restrict_is_the_only_writer_of_restrictions_and_consults_the_resolver(tmp_path):
    """Inventory (rule 8): no production module writes resource_policies but IAM's service, and its one writer asks the
    resolver before writing."""
    write = re.compile(r"\b(INSERT\s+(OR\s+\w+\s+)?INTO|REPLACE\s+INTO|UPDATE|DELETE\s+FROM)\s+resource_policies\b",
                       re.IGNORECASE)
    writers = []
    for base in (ROOT / "src", ROOT / "services"):
        for path in base.rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Call) and getattr(node.func, "attr", "") in ("insert", "update", "delete", "upsert") \
                        and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "resource_policies":
                    writers.append(str(path.relative_to(ROOT)))
                elif isinstance(node, ast.Constant) and isinstance(node.value, str) and write.search(node.value):
                    writers.append(str(path.relative_to(ROOT)))
    assert sorted(set(writers)) == ["src/assistant/iam/service.py"], writers
    asked = []
    iam, admin = _iam(tmp_path, None)
    iam.holds = lambda space, kind, rid: asked.append((space, kind, rid)) or True
    iam.restrict(admin, "a", "document", "d1", [])
    assert asked and asked[0] == ("a", "document", "d1")
