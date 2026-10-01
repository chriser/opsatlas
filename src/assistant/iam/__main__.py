"""Local procedures for the host (IAM F8): ``python -m assistant.iam <command>``.

    bootstrap  --root <workspace> --email <address> --name "<name>" [--password-stdin]
               Initial set-up: one platform administrator. Without a password, a one-time invitation link is printed
               once; the person sets their own password through it. Refused once an administrator is active.
    recover    --root <workspace> --login <address> --reason "<why>"
               Emergency recovery: a 30-minute, one-use password-reset link for that account, its sessions ended,
               a durable security event written and shown to administrators afterwards. Trusts whoever controls
               the host, who controls the store anyway; it is not a second factor.
    status     --root <workspace>            People, sessions and the audit chain.
    verify-audit --root <workspace>          Check the audit chain end to end.
    catalogue  [--typescript | --json | --markdown]   The permission registry and role seeds, generated.

The store is ``<workspace>/iam.db``; secrets never go into arguments (a password is read from stdin).
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

from .. import settings
from . import catalogue
from . import roles as seeds
from .service import IamError, Identity
from .store import IamStore


def _identity(root: str, origin: str) -> Identity:
    root_path = Path(root).expanduser()
    if not root_path.is_dir():
        raise SystemExit(f"No such workspace: {root_path}")
    return Identity(IamStore(root_path / "iam.db"), origin=origin, guide_space="product-guide")


def bootstrap(args: argparse.Namespace) -> int:
    iam = _identity(args.root, args.origin)
    password = None
    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\n") if not sys.stdin.isatty() else getpass.getpass("Password for the administrator: ")
    try:
        user, token = iam.bootstrap_admin(args.email, args.name, password=password, host_user=getpass.getuser())
    except IamError as exc:
        print(f"Refused: {exc.message}", file=sys.stderr)
        return 2
    print(f"Platform administrator: {user['display_name']} <{user['email']}> ({user['state']})")
    if token:
        hours = iam.setting("invitation.hours")
        print(f"One-time invitation link, valid {hours} hours, shown once (it is not kept anywhere):")
        print(f"  {iam.link('invitation', token)}")
    return 0


def recover(args: argparse.Namespace) -> int:
    iam = _identity(args.root, args.origin)
    user = iam.user_by_login(args.login)
    if user is None or user["state"] != "active":
        print("No active account with that login.", file=sys.stderr)
        return 2
    store = iam.store
    with store.transaction():
        token = iam._issue(
            "reset", user, issuer=None, minutes=iam.setting("reset.minutes"), payload={"recovery": True, "reason": args.reason}
        )
        iam._revoke_sessions(user["id"], "emergency recovery")
        store.insert(
            "recovery_events",
            {
                "id": store.new_id("rec"),
                "at": store.stamp(),
                "user_id": user["id"],
                "kind": "password reset",
                "reason": args.reason[:500],
                "host_user": getpass.getuser(),
            },
        )
        iam.audit.record(
            action="recovery.emergency",
            actor_type="host",
            target_type="user",
            target_id=user["id"],
            target_label=user["display_name"],
            reason=args.reason,
            detail={"host_user": getpass.getuser()},
        )
    print(
        f"Recovery for {user['display_name']} <{user['email']}>: sessions ended. One-time reset link, valid "
        f"{iam.setting('reset.minutes')} minutes, shown once:"
    )
    print(f"  {iam.link('reset', token)}")
    return 0


def status(args: argparse.Namespace) -> int:
    iam = _identity(args.root, args.origin)
    store = iam.store
    now = store.stamp()
    people = store.all("SELECT display_name, email, state, last_sign_in_at FROM users ORDER BY created_at")
    print(f"People: {len(people)}")
    for person in people:
        print(f"  {person['display_name']:28s} {person['email']:32s} {person['state']:12s} last sign-in {person['last_sign_in_at'] or '-'}")
    live = store.one("SELECT COUNT(*) AS n FROM sessions WHERE revoked_at IS NULL AND absolute_expires_at > ?", (now,))["n"]
    print(f"Live sessions: {live}")
    print(f"Spaces: {', '.join(s['id'] + ('' if s['status'] == 'active' else ' (archived)') for s in iam.spaces()) or '-'}")
    ok, checked = iam.audit.verify_chain()
    print(f"Audit chain: {'intact' if ok else 'BROKEN'} ({checked} events); policy version {store.policy_version()}")
    return 0 if ok else 1


def verify_audit(args: argparse.Namespace) -> int:
    iam = _identity(args.root, args.origin)
    ok, checked = iam.audit.verify_chain()
    print(f"Audit chain {'intact' if ok else 'BROKEN'} after {checked} events")
    return 0 if ok else 1


def catalogue_command(args: argparse.Namespace) -> int:
    if args.typescript:
        print(catalogue.typescript(), end="")
    elif args.markdown:
        print(markdown_matrix())
    else:
        print(json.dumps({"catalogue": catalogue.registry(), "roles": seeds.seed_json()}, indent=2))
    return 0


def markdown_matrix() -> str:
    """The permission matrix: every permission against every built-in role."""
    roles = [r for r in seeds.BUILTIN.values() if not r.system]
    lines = [f"| Permission | Scopes | {' | '.join(r.name for r in roles)} |", f"|---|---|{'---|' * len(roles)}"]
    for namespace in catalogue.NAMESPACES:
        for permission in namespace.permissions:
            marks = " | ".join("●" if permission.key in r.permissions else "" for r in roles)
            lines.append(
                f"| `{permission.key}`{' ⚠' if permission.risky else ''} | {'/'.join(s[0].upper() for s in permission.scopes)} | {marks} |"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m assistant.iam", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn in (("bootstrap", bootstrap), ("recover", recover), ("status", status), ("verify-audit", verify_audit)):
        p = sub.add_parser(name)
        p.add_argument("--root", default=settings.get("OPSATLAS_WORKSPACE"))
        p.add_argument("--origin", default=settings.get("OPSATLAS_ORIGIN"))
        p.set_defaults(fn=fn)
    sub.choices["bootstrap"].add_argument("--email", required=True)
    sub.choices["bootstrap"].add_argument("--name", required=True)
    sub.choices["bootstrap"].add_argument(
        "--password-stdin", action="store_true", help="read the password from stdin instead of issuing a link"
    )
    sub.choices["recover"].add_argument("--login", required=True)
    sub.choices["recover"].add_argument("--reason", required=True)
    p = sub.add_parser("catalogue")
    p.add_argument("--typescript", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--markdown", action="store_true")
    p.set_defaults(fn=catalogue_command)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
