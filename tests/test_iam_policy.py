"""The policy evaluator (IAM F4), table-driven: roles at scopes, denies, expiry, ownership, restrictions, hiding."""

from datetime import datetime, timedelta, timezone

import pytest

from assistant.iam.policy import AuthorizationContext
from assistant.iam.service import HOST, Actor, IamError, Identity
from assistant.iam.store import IamStore


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta) -> None:
        self.now += timedelta(**delta)


@pytest.fixture
def world(tmp_path):
    clock = Clock()
    iam = Identity(IamStore(tmp_path / "iam.db", clock=clock), origin="http://127.0.0.1:8780", guide_space="product-guide")
    for space, kind in (("product-guide", "product"), ("sales-playbook", "playbook"), ("org-a", "organisation"), ("org-b", "organisation")):
        iam.register_space(space, space.title(), kind)
    admin, _ = iam.bootstrap_admin("admin@example.test", "Ada Admin", password="an administrator's long password", enforce_policy=False)
    people = {}
    for login, role, space in (
        ("reader@a.test", "space_reader", "org-a"),
        ("contributor@a.test", "space_contributor", "org-a"),
        ("approver@a.test", "space_approver", "org-a"),
        ("owner@a.test", "space_owner", "org-a"),
        ("readerb@b.test", "space_reader", "org-b"),
        ("sales@x.test", "sales_user", "sales-playbook"),
        ("identity@x.test", "identity_administrator", None),
    ):
        invited = iam.invite(
            Actor(admin["id"], fresh=True), email=login, display_name=login.split("@")[0].title(), role_id=role, space_id=space
        )
        people[login.split("@")[0]] = iam.accept_invitation(invited["token"], "a long enough password for tests")
    return iam, clock, admin, people


def can(iam, user, permission, space=None, **conditions):
    return bool(iam.policy.evaluate(AuthorizationContext(principal_id=user["id"]), permission, space_id=space, **conditions))


@pytest.mark.parametrize(
    "person,permission,space,expected",
    [
        ("reader", "documents.read", "org-a", True),
        ("reader", "documents.edit", "org-a", False),
        ("reader", "documents.draft.read", "org-a", False),
        ("reader", "documents.read", "org-b", False),
        ("reader", "documents.read", "product-guide", True),  # the Product Guide entitlement of every active person
        ("reader", "documents.read", "sales-playbook", False),  # no implicit access from the Product Guide
        ("contributor", "documents.edit", "org-a", True),
        ("contributor", "documents.approve", "org-a", False),
        ("approver", "documents.approve", "org-a", True),
        ("approver", "iam.roles.assign", "org-a", False),
        ("owner", "iam.roles.assign", "org-a", True),
        ("owner", "spaces.delete", "org-a", False),
        ("owner", "spaces.create", None, False),  # platform capabilities never come from a space role
        ("owner", "documents.read", "org-b", False),
        ("sales", "tibi.rehearsal.use", "sales-playbook", True),
        ("sales", "documents.edit", "sales-playbook", False),
        ("identity", "iam.users.invite", None, True),
        ("identity", "documents.read", "org-a", False),  # a platform role grants no space content
        ("reader", "account.read_self", None, True),
    ],
)
def test_roles_grant_exactly_what_the_seed_says(world, person, permission, space, expected):
    iam, _, _, people = world
    user = people[person]
    conditions = {"owner_id": user["id"]} if permission.startswith("account.") else {}
    assert can(iam, user, permission, space, **conditions) is expected


def test_the_platform_administrator_holds_platform_and_every_space_including_new_ones(world):
    iam, _, admin, _ = world
    assert can(iam, admin, "spaces.create") and can(iam, admin, "documents.approve", "org-b")
    iam.register_space("org-c", "Org C", "organisation")
    assert can(iam, admin, "documents.approve", "org-c")


def test_unknown_permissions_wrong_scopes_and_inactive_principals_are_denied(world):
    iam, _, admin, people = world
    reader = people["reader"]
    assert (
        iam.policy.evaluate(AuthorizationContext(principal_id=reader["id"]), "documents.nothing", space_id="org-a").code
        == "UNKNOWN_PERMISSION"
    )
    assert iam.policy.evaluate(AuthorizationContext(principal_id=reader["id"]), "spaces.create", space_id="org-a").code == "SCOPE_INVALID"
    assert iam.policy.evaluate(AuthorizationContext(principal_id=reader["id"]), "documents.read").code == "SCOPE_INVALID"
    assert iam.policy.evaluate(AuthorizationContext(principal_id="nobody"), "documents.read", space_id="org-a").code == "PRINCIPAL_INACTIVE"
    iam.suspend(Actor(admin["id"]), reader["id"], "test")
    assert (
        iam.policy.evaluate(AuthorizationContext(principal_id=reader["id"]), "documents.read", space_id="org-a").code
        == "PRINCIPAL_INACTIVE"
    )


def test_a_space_the_person_cannot_see_is_hidden_and_an_archived_one_only_restores(world):
    iam, _, admin, people = world
    reader = people["reader"]
    decision = iam.policy.evaluate(AuthorizationContext(principal_id=reader["id"]), "documents.read", space_id="org-b")
    assert not decision and decision.hidden
    decision = iam.policy.evaluate(AuthorizationContext(principal_id=reader["id"]), "documents.edit", space_id="org-a")
    assert not decision and not decision.hidden  # visible space, missing permission: forbidden, not hidden
    assert iam.policy.evaluate(AuthorizationContext(principal_id=reader["id"]), "documents.read", space_id="nowhere").hidden
    iam.register_space("org-a", "Org A", "organisation", status="archived")
    assert not can(iam, admin, "documents.read", "org-a") and can(iam, admin, "spaces.restore", "org-a")


def test_an_explicit_deny_wins_over_any_grant_including_a_groups(world):
    iam, _, admin, people = world
    owner, reader = people["owner"], people["reader"]
    group = iam.create_group(Actor(admin["id"]), name="Editors", space_id="org-a")
    iam.grant(
        Actor(admin["id"], fresh=True),
        subject_id=group["id"],
        subject_type="group",
        role_id="space_contributor",
        scope_type="space",
        scope_id="org-a",
    )
    iam.add_group_member(Actor(admin["id"]), group["id"], reader["id"])
    assert can(iam, reader, "documents.edit", "org-a")  # through the group
    iam.deny(
        Actor(owner["id"]), subject_id=reader["id"], permission="documents.edit", scope_type="space", scope_id="org-a", reason="probation"
    )
    decision = iam.policy.evaluate(AuthorizationContext(principal_id=reader["id"]), "documents.edit", space_id="org-a")
    assert decision.code == "EXPLICIT_DENY" and "probation" in decision.reason
    assert can(iam, reader, "documents.read", "org-a")  # the deny is exact
    iam.remove_group_member(Actor(admin["id"]), group["id"], reader["id"])
    assert not can(iam, reader, "documents.edit", "org-a")


def test_grants_and_memberships_expire_on_the_clock_not_on_a_cleanup_job(world):
    iam, clock, admin, people = world
    reader = people["reader"]
    assert not can(iam, reader, "documents.read", "org-b")
    iam.grant(
        Actor(admin["id"], fresh=True), subject_id=reader["id"], role_id="external_guest", scope_type="space", scope_id="org-b", days=3
    )
    assert can(iam, reader, "documents.read", "org-b")
    clock.advance(days=3, seconds=1)
    assert not can(iam, reader, "documents.read", "org-b")
    assert can(iam, reader, "documents.read", "org-a")  # the permanent grant is untouched


def test_own_permissions_need_the_owner_and_restricted_resources_need_the_audience(world):
    iam, _, admin, people = world
    reader, owner = people["reader"], people["owner"]
    assert can(iam, reader, "conversations.read_own", "org-a", owner_id=reader["id"])
    assert not can(iam, reader, "conversations.read_own", "org-a", owner_id=owner["id"])
    assert not can(iam, reader, "account.read_self", owner_id=owner["id"])
    iam.store.insert(
        "resource_policies",
        {
            "resource_type": "document",
            "resource_id": "d1",
            "space_id": "org-a",
            "restricted_to": '["user:%s"]' % owner["id"],
            "updated_at": iam.store.stamp(),
        },
    )
    assert can(iam, owner, "documents.read", "org-a", resource=("document", "d1"))
    denied = iam.policy.evaluate(
        AuthorizationContext(principal_id=reader["id"]), "documents.read", space_id="org-a", resource=("document", "d1")
    )
    assert denied.code == "RESTRICTED" and denied.hidden
    assert can(iam, reader, "documents.read", "org-a", resource=("document", "d2"))  # no policy: the space grant applies


def test_no_self_escalation_grant_ceilings_and_the_last_owner_and_administrator(world):
    iam, _, admin, people = world
    owner, reader, approver = people["owner"], people["reader"], people["approver"]
    with pytest.raises(IamError, match="own authority"):
        iam.grant(Actor(owner["id"]), subject_id=owner["id"], role_id="space_owner", scope_type="space", scope_id="org-a")
    with pytest.raises(IamError, match="cannot give"):  # a space owner cannot make platform administrators
        iam.grant(Actor(owner["id"], fresh=True), subject_id=reader["id"], role_id="platform_administrator", scope_type="platform")
    with pytest.raises(IamError, match="cannot give"):  # nor give anything in another space
        iam.grant(Actor(owner["id"]), subject_id=reader["id"], role_id="space_reader", scope_type="space", scope_id="org-b")
    given = iam.grant(Actor(owner["id"]), subject_id=reader["id"], role_id="space_approver", scope_type="space", scope_id="org-a")
    assert can(iam, reader, "documents.approve", "org-a")
    iam.revoke_binding(Actor(owner["id"]), given["id"], "done")
    assert not can(iam, reader, "documents.approve", "org-a")
    with pytest.raises(IamError, match="password again"):  # a protected role needs fresh authentication
        iam.grant(Actor(admin["id"], fresh=False), subject_id=approver["id"], role_id="identity_administrator", scope_type="platform")
    owner_binding = next(b for b in iam.bindings(Actor(admin["id"]), user_id=owner["id"]) if b["role_id"] == "space_owner")
    with pytest.raises(IamError, match="last active owner"):
        iam.revoke_binding(Actor(admin["id"]), owner_binding["id"])
    with pytest.raises(IamError, match="last active platform administrator"):
        iam.suspend(Actor(people["identity"]["id"]), admin["id"])
    with pytest.raises(IamError, match="cannot decide your own"):
        request = iam.request_access(Actor(reader["id"]), role_id="space_contributor", space_id="org-a", reason="please")
        iam.decide_request(Actor(reader["id"]), request["id"], True)
    decided = iam.decide_request(Actor(owner["id"]), request["id"], True, "welcome", days=7)
    assert decided["status"] == "approved" and can(iam, reader, "documents.edit", "org-a")


def test_explanations_capabilities_and_the_audit_chain(world):
    iam, _, admin, people = world
    reader = people["reader"]
    explained = iam.explain(Actor(admin["id"]), user_id=reader["id"], permission="documents.read", space_id="org-a")
    assert explained["allowed"] and any(b["applies_here"] and b["grants_permission"] for b in explained["bindings"])
    with pytest.raises(IamError, match="No role allows"):
        iam.explain(Actor(reader["id"]), user_id=admin["id"], permission="documents.read", space_id="org-a")
    capabilities = iam.capabilities(reader["id"])
    assert set(capabilities["spaces"]) == {"org-a", "product-guide"} and "account.read_self" in capabilities["platform"]
    assert [s["id"] for s in iam.visible_spaces(reader["id"])] == ["product-guide", "org-a"]
    intact, checked = iam.audit.verify_chain()
    assert intact and checked > 10
    iam.store.run("UPDATE audit_events SET reason = 'tampered' WHERE seq = 3")
    assert iam.audit.verify_chain() == (False, 2)
    assert HOST.is_host and iam.can(None, "anything.at.all")


def test_an_administrator_invited_before_the_spaces_exist_holds_them_all_once_active(tmp_path):
    """The live order: bootstrap on the host first, the spaces registered when the core starts, the invitation accepted last."""
    iam = Identity(IamStore(tmp_path / "iam.db"), origin="http://127.0.0.1:8780", guide_space="product-guide")
    admin, token = iam.bootstrap_admin("kris@example.test", "Kris")
    iam.register_space("product-guide", "Product Guide", "product")
    iam.register_space("acme", "Acme", "organisation")
    assert iam.capabilities(admin["id"]) == {"platform": [], "spaces": {}}  # invited: nothing yet
    iam.accept_invitation(token, "a long and quiet password for kris")
    capabilities = iam.capabilities(admin["id"])
    assert set(capabilities["spaces"]) == {"product-guide", "acme"} and "spaces.create" in capabilities["platform"]
    assert "documents.approve" in capabilities["spaces"]["acme"] and "documents.approve" in capabilities["spaces"]["product-guide"]
    iam.register_space("bolt", "Bolt", "organisation")
    assert "documents.approve" in iam.capabilities(admin["id"])["spaces"]["bolt"]
