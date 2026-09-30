"""The permission catalogue and the built-in roles (IAM F1): one registry, exact keys, generated copies in step."""
from pathlib import Path

from assistant.iam import catalogue
from assistant.iam import roles as seeds

ROOT = Path(__file__).resolve().parents[1]


def test_every_permission_has_a_namespace_scopes_and_a_description():
    assert len(catalogue.PERMISSIONS) > 150
    for key, permission in catalogue.PERMISSIONS.items():
        assert key == f"{permission.namespace}.{permission.action}"
        assert permission.scopes and set(permission.scopes) <= {"platform", "space", "collection", "resource", "own"}
        assert permission.description and not permission.description.startswith("!")
    assert catalogue.get("documents.read").scopes == ("space", "collection", "resource")
    assert catalogue.get("spaces.create").platform_only and catalogue.get("tibi.persona.manage").platform_only
    assert catalogue.get("account.read_self").scopes == ("own",)
    assert catalogue.get("iam.users.deactivate").risky and not catalogue.get("documents.read").risky
    assert catalogue.get("no.such") is None and not catalogue.valid_at("documents.read", "platform")


def test_every_role_is_made_of_registered_permissions_valid_for_its_boundary():
    for role in seeds.BUILTIN.values():
        assert role.permissions, role.id
        for key in role.permissions:
            permission = catalogue.get(key)
            assert permission is not None, (role.id, key)
            if role.boundary == "space":
                assert permission.in_spaces, (role.id, key)
            elif role.id != "platform_administrator":
                assert permission.at_platform or permission.scopes == ("own",), (role.id, key)
        for grantable in role.grantable:
            assert grantable in seeds.BUILTIN, (role.id, grantable)


def test_the_roles_exclude_what_they_say_they_exclude():
    reader, contributor, approver, owner = (seeds.BUILTIN[r].permissions for r in
                                            ("space_reader", "space_contributor", "space_approver", "space_owner"))
    assert set(reader) < set(contributor) < set(owner) and set(reader) < set(approver) < set(owner)
    assert "documents.edit" not in reader and "documents.draft.read" not in reader and "documents.download" not in reader
    assert "documents.approve" not in contributor and "spaces.members.manage" not in contributor
    assert "documents.approve" in approver and "iam.roles.assign" not in approver and "governance.self_approve" not in approver
    assert "spaces.delete" not in owner and "conversations.read_all" not in owner and "analytics.raw.read" not in owner
    assert "governance.self_approve" not in owner
    guest = seeds.BUILTIN["external_guest"].permissions
    assert "documents.read" in guest and "documents.download" not in guest and "processes.read" not in guest
    auditor = seeds.BUILTIN["auditor"].permissions
    assert "audit.read" in auditor and "documents.read" not in auditor
    identity = seeds.BUILTIN["identity_administrator"].permissions
    assert "iam.users.invite" in identity and "documents.read" not in identity and "platform.secrets.rotate" not in identity
    assert "platform_administrator" not in seeds.BUILTIN["identity_administrator"].grantable
    assert set(seeds.BUILTIN["platform_administrator"].permissions) == set(catalogue.KEYS)
    assert seeds.BUILTIN["signed_in_user"].system and seeds.BUILTIN["platform_administrator"].protected
    assert set(seeds.BUILTIN["space_owner"].grantable) == set(seeds.SPACE_ROLE_IDS) | {"space_owner"}


def test_the_frontend_copy_of_the_catalogue_is_generated_from_the_registry():
    generated = (ROOT / "frontend/src/iam/permissions.ts").read_text()
    assert generated == catalogue.typescript(), "run: python -m assistant.iam catalogue --typescript > frontend/src/iam/permissions.ts"
    assert f"export const CATALOGUE_VERSION = {catalogue.VERSION};" in generated
    for key in catalogue.KEYS:
        assert f'"{key}"' in generated


def test_the_registry_and_seed_are_serialisable_and_versioned():
    registry = catalogue.registry()
    assert registry["version"] == catalogue.VERSION and len(registry["permissions"]) == len(catalogue.PERMISSIONS)
    seed = seeds.seed_json()
    assert seed["version"] == seeds.SEED_VERSION and {r["id"] for r in seed["roles"]} == set(seeds.BUILTIN)
