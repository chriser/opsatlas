"""Bug #2205 (REF S13): a restriction's audience names only its own space's groups.

A group of another space is managed by that space's owner, and a platform group by whoever holds the platform's group
permission, so naming either in an audience would let them decide who reads the document. IAM's one writer
(``Identity.restrict``) accepts a group only if it is live and belongs to the path's space; any other answers 404 "No such
group", as an unknown group does, with nothing changed and no audit event. A group never changes space: the store
refuses it. The design: docs/benchmark/evidence/2026-10-05-bug-2205.md. Hermetic: no network, no live service, no model.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from assistant.iam.service import Actor, IamError, Identity
from assistant.iam.store import IamStore
from tests.scenarios import Run, explore
from tests.test_restriction_space import (
    GUIDE,
    _allowed,
    admin_id,
    audit_count,
    guide_document,
    person,
    put,
    reads,
    row,
)

NO_GROUP, NOT_HELD, NO_SPACE = "No such group", "No such document or folder in this space", "No such space"


# ---- through the app ------------------------------------------------------------------------------------------------

def test_another_spaces_group_cannot_join_a_restriction(sales_workspace):
    """The probe (DI9): Acme's group cannot be named in a guide document's audience, so Acme's owner cannot decide who
    reads it."""
    ws = sales_workspace
    iam = ws.app.state.auth.iam
    me = admin_id(ws)
    doc = guide_document(ws)
    assert put(ws, GUIDE, "document", doc, [f"user:{me}"]).status_code == 200
    group = iam.create_group(Actor(me, fresh=True), name="Acme readers", space_id=ws.space)["id"]
    pia_id, pia = person(ws, "pia@example.test", "Pia", GUIDE, "product_owner")
    trail = audit_count(iam)
    refused = put(ws, GUIDE, "document", doc, [f"user:{me}", f"group:{group}"])
    assert refused.status_code == 404 and NO_GROUP in refused.text, refused.text
    assert row(ws, "document", doc)["restricted_to"] == f'["user:{me}"]' and audit_count(iam) == trail
    iam.add_group_member(Actor(me, fresh=True), group, pia_id)  # what Acme's owner could do
    assert reads(ws, pia, GUIDE, doc) == 404  # still outside the audience


def test_the_spaces_own_group_is_accepted_and_its_member_reads(sales_workspace):
    ws = sales_workspace
    iam = ws.app.state.auth.iam
    me = admin_id(ws)
    doc = guide_document(ws)
    group = iam.create_group(Actor(me, fresh=True), name="Guide readers", space_id=GUIDE)["id"]
    pia_id, pia = person(ws, "pia@example.test", "Pia", GUIDE, "product_owner")
    assert put(ws, GUIDE, "document", doc, [f"group:{group}"]).status_code == 200
    assert reads(ws, pia, GUIDE, doc) == 404
    iam.add_group_member(Actor(me, fresh=True), group, pia_id)
    assert reads(ws, pia, GUIDE, doc) == 200


def test_a_folders_audience_keeps_the_same_rule(sales_workspace):
    ws = sales_workspace
    iam = ws.app.state.auth.iam
    me = admin_id(ws)
    made = ws.client.post("/api/content/groups", json={"title": "Guide plans"})  # no space header: the guide's
    assert made.status_code == 200, made.text
    folder = made.json()["id"]
    acme = iam.create_group(Actor(me, fresh=True), name="Acme readers", space_id=ws.space)["id"]
    guide = iam.create_group(Actor(me, fresh=True), name="Guide readers", space_id=GUIDE)["id"]
    assert put(ws, GUIDE, "folder", folder, [f"group:{acme}"]).status_code == 404
    assert put(ws, GUIDE, "folder", folder, [f"group:{guide}"]).status_code == 200


# ---- IAM alone -------------------------------------------------------------------------------------------------------

def _iam(tmp_path):
    iam = Identity(IamStore(tmp_path / "iam.db"), origin="http://127.0.0.1:8780", guide_space="a")
    for space in ("a", "b", "c"):
        iam.register_space(space, space.upper(), "organisation")
    admin, _ = iam.bootstrap_admin("kris@example.test", "Kris", password="the quiet river runs east")
    iam.holds = lambda space, kind, rid: rid == f"d-{space}"  # each space holds its own document
    return iam, Actor(admin["id"], fresh=True)


def test_which_groups_an_audience_may_name(tmp_path):
    iam, admin = _iam(tmp_path)
    own = iam.create_group(admin, name="A team", space_id="a")["id"]
    other = iam.create_group(admin, name="B team", space_id="b")["id"]
    platform = iam.create_group(admin, name="Everyone's auditors")["id"]
    blank = iam.create_group(admin, name="Platform, stored with an empty space", space_id="")["id"]
    gone = iam.create_group(admin, name="Gone", space_id="a")["id"]
    iam.delete_group(admin, gone)
    for entry, ok in ((f"group:{own}", True), (f"user:{admin.id}", True), (f"group:{other}", False),
                      (f"group:{platform}", False), (f"group:{blank}", False), (f"group:{gone}", False),
                      ("group:grp_nothing", False)):
        trail, version = audit_count(iam), iam.store.policy_version()
        try:
            iam.restrict(admin, "a", "document", "d-a", [entry])
            done = True
        except IamError as refused:
            assert (refused.status, refused.message) == (404, NO_GROUP), entry
            done = False
        assert done == ok, entry
        assert (audit_count(iam) - trail, iam.store.policy_version() - version) == ((1, 1) if ok else (0, 0)), entry


def test_one_foreign_group_refuses_the_whole_audience(tmp_path):
    iam, admin = _iam(tmp_path)
    own = iam.create_group(admin, name="A team", space_id="a")["id"]
    other = iam.create_group(admin, name="B team", space_id="b")["id"]
    iam.restrict(admin, "a", "document", "d-a", [f"group:{own}"])
    with pytest.raises(IamError):
        iam.restrict(admin, "a", "document", "d-a", [f"user:{admin.id}", f"group:{own}", f"group:{other}"])
    assert iam.store.one("SELECT restricted_to FROM resource_policies WHERE resource_id = 'd-a'")["restricted_to"] == \
        f'["group:{own}"]'


def test_a_holder_taking_back_a_row_cannot_name_the_old_spaces_group(tmp_path):
    """Bug #2202 (a): the row follows its holder, with an audience validated for the holder's space."""
    iam, admin = _iam(tmp_path)
    b_group = iam.create_group(admin, name="B team", space_id="b")["id"]
    a_group = iam.create_group(admin, name="A team", space_id="a")["id"]
    iam.holds = lambda space, kind, rid: space == "b"
    iam.restrict(admin, "b", "document", "d1", [f"group:{b_group}"])
    iam.holds = lambda space, kind, rid: space == "a"  # moved to a
    with pytest.raises(IamError) as refused:
        iam.restrict(admin, "a", "document", "d1", [f"group:{b_group}"])
    assert refused.value.message == NO_GROUP
    assert iam.store.one("SELECT space_id FROM resource_policies WHERE resource_id = 'd1'")["space_id"] == "b"
    iam.restrict(admin, "a", "document", "d1", [f"group:{a_group}"])  # its own group: the row follows
    assert iam.store.one("SELECT space_id FROM resource_policies WHERE resource_id = 'd1'")["space_id"] == "a"


def test_a_deleted_documents_row_is_changed_by_its_own_space_with_its_own_groups_only(tmp_path):
    """Bug #2202 (c): with no holder left, the row's own space may still change it, and only with its own groups."""
    iam, admin = _iam(tmp_path)
    a_group = iam.create_group(admin, name="A team", space_id="a")["id"]
    b_group = iam.create_group(admin, name="B team", space_id="b")["id"]
    iam.restrict(admin, "a", "document", "d-a", [f"user:{admin.id}"])
    iam.holds = lambda space, kind, rid: False  # deleted everywhere
    with pytest.raises(IamError) as refused:
        iam.restrict(admin, "a", "document", "d-a", [f"group:{b_group}"])
    assert refused.value.message == NO_GROUP
    iam.restrict(admin, "a", "document", "d-a", [f"group:{a_group}"])
    assert json.loads(iam.store.one("SELECT restricted_to FROM resource_policies WHERE resource_id = 'd-a'")
                      ["restricted_to"]) == [f"group:{a_group}"]


def test_a_group_never_changes_space(tmp_path):
    """I2 rests on it: the store refuses to move a group to another space or boundary, whatever writes to it; deleting a
    group still works."""
    iam, admin = _iam(tmp_path)
    group = iam.create_group(admin, name="A team", space_id="a")["id"]
    for change in ("UPDATE groups SET space_id = 'b' WHERE id = ?", "UPDATE groups SET space_id = NULL WHERE id = ?",
                   "UPDATE groups SET boundary = 'platform' WHERE id = ?"):
        with pytest.raises(sqlite3.IntegrityError, match="a group never changes space"):
            iam.store.run(change, (group,))
    assert iam.store.one("SELECT space_id, boundary FROM groups WHERE id = ?", (group,)) == {"space_id": "a",
                                                                                              "boundary": "space"}
    iam.delete_group(admin, group)
    assert iam.store.one("SELECT deleted_at FROM groups WHERE id = ?", (group,))["deleted_at"]


def test_audiences_keep_the_rule_over_random_scenarios(tmp_path):
    """Seeded (tests/scenarios.py, 2,000 runs by default). Documents move between three spaces, so rows follow their
    holders; spaces are archived and restored; and every space tries audiences mixing people with live, deleted and
    foreign groups, platform groups (stored with NULL or '') and unknown ones. After every step: the answer and its
    message match an independent statement of both rules, the stored audience is the accepted one, a refusal leaves no
    audit event or policy change, and no row names a group outside its own space (I2). The suite asserts it reached the
    paths it exists for."""
    iam, admin = _iam(tmp_path)
    holdings: dict[str, set[str]] = {"a": set(), "b": set(), "c": set()}
    archived: set[str] = set()
    iam.holds = lambda space, kind, rid: rid in holdings[space]
    where: dict[str, str | None] = {}  # every group made: its space (None or '' for the platform)
    deleted: set[str] = set()
    for space in ("a", "b", "c", None, ""):
        for n in range(3 if space else 1):
            made = iam.create_group(admin, name=f"{space or 'platform'} {n}", space_id=space)["id"]
            where[made] = space
            if n == 2:
                iam.delete_group(admin, made)
                deleted.add(made)
    pool = [f"user:{admin.id}", *(f"group:{g}" for g in where), "group:grp_nothing"]
    reached = {"followed with groups": 0, "group refused": 0, "not held": 0, "archived": 0, "accepted": 0}

    def audience_ok(space: str, audience: list[str]) -> bool:
        groups = [e.split(":", 1)[1] for e in audience if e.startswith("group:")]
        return all(g in where and g not in deleted and where[g] == space for g in groups)

    def one_run(run: Run) -> None:
        for held in holdings.values():
            held.clear()
        for space in archived:
            iam.register_space(space, space.upper(), "organisation")
        archived.clear()
        iam.store.run("DELETE FROM resource_policies")
        rows: dict[str, str] = {}
        for _ in range(20):
            rid, space = run.rng.choice(["d1", "d2"]), run.rng.choice("abc")
            kind = run.rng.choice(["move", "move", "archive", "restore", "restrict", "restrict", "restrict", "restrict"])
            run.step(kind, f"{space} {rid}")
            if kind == "move":
                for held in holdings.values():
                    held.discard(rid)
                holdings[space].add(rid)
            elif kind in ("archive", "restore"):
                iam.register_space(space, space.upper(), "organisation", "archived" if kind == "archive" else "active")
                (archived.add if kind == "archive" else archived.discard)(space)
            else:
                audience = [run.rng.choice(pool) for _ in range(run.rng.randint(0, 3))]
                if space in archived:
                    expected = NO_SPACE
                elif not audience_ok(space, audience):
                    expected = NO_GROUP
                elif not _allowed(holdings, set(), archived, rows, space, rid):
                    expected = NOT_HELD
                else:
                    expected = None
                before = iam.store.one("SELECT space_id, restricted_to FROM resource_policies WHERE resource_id = ?",
                                       (rid,))
                trail, version = audit_count(iam), iam.store.policy_version()
                try:
                    iam.restrict(admin, space, "document", rid, audience)
                    answer = None
                except IamError as refused:
                    run.promise("a refusal is 404", refused.status == 404, refused.message)
                    answer = refused.message
                run.promise("the answer follows both rules", answer == expected,
                            f"{space} {rid} {audience}: {answer!r}, expected {expected!r}; held {holdings}; rows {rows}")
                changed = int(answer is None)
                run.promise("one audit event and one policy change for a change, none for a refusal",
                            (audit_count(iam) - trail, iam.store.policy_version() - version) == (changed, changed))
                if answer is None:
                    reached["accepted"] += 1
                    if before and before["space_id"] != space and any(e.startswith("group:") for e in audience):
                        reached["followed with groups"] += 1
                    rows[rid] = space
                    stored = iam.store.one("SELECT restricted_to FROM resource_policies WHERE resource_id = ?", (rid,))
                    run.promise("the stored audience is the accepted one",
                                json.loads(stored["restricted_to"]) == list(dict.fromkeys(audience)))
                else:
                    reached[{NO_GROUP: "group refused", NOT_HELD: "not held", NO_SPACE: "archived"}[answer]] += 1
            for found in iam.store.all("SELECT space_id, restricted_to FROM resource_policies"):
                outside = [e for e in json.loads(found["restricted_to"])
                           if e.startswith("group:") and where.get(e.split(":", 1)[1]) != found["space_id"]]
                run.promise("no row names a group outside its own space (I2)", not outside, f"{found}: {outside}")

    assert explore("audiences name their own space's groups (Bug #2205)", one_run) > 0
    assert all(reached.values()), reached  # every path the suite exists for was taken
