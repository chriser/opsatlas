"""The permission catalogue (IAM F1): every permission OpsAtlas checks, by exact key, with the scopes it is valid at.

One registry: the backend checks these keys, the role seeds are made of them, the frontend's types and the role
editor's labels are generated from them (``python -m assistant.iam catalogue --typescript``), and so is the
permission matrix in the IAM guide. There are no wildcards: a permission that is not registered is denied.

Scope codes: P platform, S space, C collection, R resource, O the actor's own objects.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

VERSION = 3  # v3 (2 Oct 2026): permissions that guard nothing yet are marked reserved (REF S5)
# v2 (30 Sep 2026): stress-lab, simulator, value-modelling and review-cancel permissions retired with their features
PLATFORM, SPACE, COLLECTION, RESOURCE, OWN = "platform", "space", "collection", "resource", "own"
_CODES = {"P": PLATFORM, "S": SPACE, "C": COLLECTION, "R": RESOURCE, "O": OWN}


@dataclass(frozen=True)
class Permission:
    key: str
    namespace: str
    action: str
    scopes: tuple[str, ...]
    description: str
    risky: bool = False
    reserved: str = ""  # why it guards nothing yet, and the backlog item that will use it (REF S5)

    @property
    def platform_only(self) -> bool:
        return self.scopes == (PLATFORM,)

    @property
    def at_platform(self) -> bool:
        return PLATFORM in self.scopes

    @property
    def in_spaces(self) -> bool:
        return any(s in self.scopes for s in (SPACE, COLLECTION, RESOURCE, OWN))


@dataclass(frozen=True)
class Namespace:
    key: str
    label: str
    note: str
    permissions: tuple[Permission, ...]


# (namespace, label, default scopes, note, actions). An action is (name, description) or (name, description, scopes)
# and a description starting with "!" marks the permission as one the role editor shows as risky.
_SPEC = [
    ("account", "My account", "O", "Self-service only: nothing here changes a person's authority.", [
        ("read_self", "See my own account"),
        ("update_self", "Change my own name and profile"),
        ("password.change", "Change my own password"),
        ("sessions.read_self", "See where I am signed in"),
        ("sessions.revoke_self", "Sign out my other sessions"),
    ]),
    ("iam.users", "People", "P", "Accounts on this installation. Recovery never exposes or sets a password.", [
        ("read", "See the people on this installation"),
        ("invite", "Invite a person"),
        ("update", "Change a person's account details"),
        ("suspend", "Suspend a person's account"),
        ("reactivate", "Reactivate a suspended account"),
        ("recovery.initiate", "!Start password recovery for a person"),
        ("deactivate", "!Deactivate (offboard) a person"),
    ]),
    ("iam.sessions", "Sessions", "P", "Session metadata only; never a session's secret.", [
        ("read", "See everyone's sessions"),
        ("revoke", "Sign someone out"),
    ]),
    ("iam.roles", "Roles", "P/S", "Platform roles at the platform; space roles within a space owner's grant ceiling.", [
        ("read", "See roles and what they allow"),
        ("create", "Create a custom role"),
        ("update", "Change a custom role"),
        ("delete", "Delete a custom role"),
        ("assign", "!Give or take a role"),
    ]),
    ("iam.groups", "Groups", "P/S", "A group grants nothing until a role is bound to it.", [
        ("read", "See groups"),
        ("create", "Create a group"),
        ("update", "Change a group"),
        ("delete", "Delete a group"),
        ("members.manage", "Add and remove group members"),
    ]),
    ("iam.access", "Access decisions", "P/S", "Explanations never reveal a resource the asker cannot see.", [
        ("explain", "Explain why someone can or cannot do something"),
        ("review", "Run an access review"),
        ("requests.create", "Ask for access", "O"),
        ("requests.read_own", "See my own access requests", "O"),
        ("requests.cancel_own", "Cancel my own access request", "O"),
        ("requests.decide", "Approve or reject access requests"),
        ("deny.manage", "!Add or lift an explicit deny"),
    ]),
    ("iam.services", "Service accounts", "P/S", "Exact scope, a human owner and an expiry are required.", [
        ("read", "See service accounts"),
        ("create", "Create a service account"),
        ("update", "Change a service account"),
        ("credentials.rotate", "!Issue or rotate a service credential"),
        ("revoke", "Revoke a service account"),
    ]),
    ("platform", "Platform", "P", "Secrets are write-only; restore and recovery have their own procedures.", [
        ("settings.read", "See platform settings"),
        ("settings.manage", "!Change platform and security settings"),
        ("services.read", "See the services and their state"),
        ("services.restart", "!Start or restart a service"),
        ("models.manage", "!Change the models in use"),
        ("integrations.manage", "!Change integrations"),
        ("secrets.rotate", "!Replace a secret"),
        ("backup.manage", "!Make and manage backups"),
        ("restore.execute", "!Restore from a backup"),
        ("cross_space.read", "!Read across all organisations"),
        ("emergency.recover", "!Emergency recovery (local procedure only)"),
    ]),
    ("spaces", "Spaces", "S", "Creating a space is a platform action; the rest belong to the space.", [
        ("create", "Create a space", "P"),
        ("read", "See the space and its name"),
        ("update", "Rename or describe the space"),
        ("archive", "Archive the space"),
        ("restore", "Restore an archived space"),
        ("delete", "!Delete the space"),
        ("export", "!Export the whole space"),
        ("members.read", "See the space's members"),
        ("members.invite", "Invite people to the space"),
        ("members.manage", "Change or remove the space's members"),
        ("policy.manage", "!Change the space's access policies"),
    ]),
    ("resources", "Resource permissions", "S/C/R", "Never across a space boundary.", [
        ("permissions.read", "See who can reach a resource"),
        ("permissions.manage", "!Change who can reach a resource"),
        ("classification.manage", "Classify a resource"),
        ("ownership.transfer", "Transfer ownership of a resource"),
    ]),
    ("collections", "Folders", "S/C", "Moving a folder can change who sees what is in it.", [
        ("read", "See folders"),
        ("create", "Create a folder"),
        ("update", "Rename a folder"),
        ("move", "Move a folder or document"),
        ("delete", "Delete a folder"),
    ]),
    ("sources", "Sources", "S/C/R", "Derived data shares the source's policy.", [
        ("register", "Register a source"),
        ("upload", "Upload a source"),
        ("metadata.update", "Change a source's details"),
        ("ingest", "Ingest a source"),
        ("reindex", "Reindex a source"),
        ("archive", "Archive a source"),
        ("restore", "Restore an archived source"),
        ("delete", "!Delete a source"),
    ]),
    ("documents", "Documents", "S/C/R", "Reading means approved content; drafts, versions and downloads are separate.", [
        ("read", "Read approved documents"),
        ("draft.read", "Read drafts and review material"),
        ("create", "Create a document"),
        ("edit", "Edit a document"),
        ("submit", "Submit a draft for review"),
        ("withdraw", "Withdraw a submission"),
        ("approve", "Approve a revision"),
        ("reject", "Reject a revision"),
        ("publish", "Publish an approved revision"),
        ("versions.read", "See a document's history"),
        ("versions.restore", "Restore an earlier version as a draft"),
        ("download", "Download the original file"),
        ("transfer", "!Transfer a document to another space"),
    ]),
    ("comments", "Comments", "S/C/R/O", "The parent document's permission is always required as well.", [
        ("read", "Read comments"),
        ("create", "Comment"),
        ("update_own", "Edit my own comments", "O"),
        ("delete_own", "Delete my own comments", "O"),
        ("moderate", "Edit or remove anyone's comments"),
    ]),
    ("assets", "Images", "R", "An image is only served with readable parent content.", [
        ("upload", "Insert an image"),
        ("read", "See images in documents"),
        ("delete", "Remove an image"),
    ]),
    ("knowledge", "Knowledge", "S/C/R", "Search and answers use approved, permitted evidence only.", [
        ("search", "Search"),
        ("ask", "Ask questions"),
        ("citations.read", "Open cited evidence"),
        ("retrieval_trace.read", "!See retrieval traces"),
    ]),
    ("governance", "Governance", "S/R", "Independent review applies unless a space is in solo-operator mode.", [
        ("read", "See governance findings"),
        ("scan.run", "Run a quick scan"),
        ("reviews.run", "Run a review"),
        ("findings.resolve", "Resolve findings"),
        ("exceptions.accept", "Accept an exception"),
        ("self_approve", "!Approve my own work (solo-operator mode)"),
    ]),
    ("external_sources", "External sources", "S/R", "Registration cannot reach arbitrary internal addresses.", [
        ("read", "See external sources"),
        ("register", "Register an external source"),
        ("refresh", "Refresh an external source"),
        ("delete", "Remove an external source"),
    ]),
    ("regulatory", "Regulatory", "S/R", "Approval does not widen source access.", [
        ("read", "See regulatory reviews"),
        ("reviews.run", "Run a regulatory review"),
        ("decisions.approve", "Approve a regulatory decision"),
    ]),
    ("processes", "Processes", "S/R", "Outputs inherit the evidence they were made from.", [
        ("read", "See processes and maps"),
        ("diagrams.generate", "Generate process maps"),
        ("capture.create", "Capture a process (interviews)"),
        ("edit", "Edit a process"),
        ("export", "Export processes"),
    ]),
    ("eam", "Enterprise Activity Model", "S/R", "Hidden nodes, edges and totals are filtered.", [
        ("read", "See the activity model"),
        ("export", "Export the activity model"),
    ]),
    ("ontology", "Facts map", "S/R", "Traversal cannot cross unauthorised evidence.", [
        ("read", "See the facts map"),
        ("query", "Query the facts map"),
        ("edit", "Edit the facts map"),
        ("rebuild", "Rebuild the facts map"),
        ("export", "Export the facts map"),
    ]),
    ("agent", "Ontology agent", "S/R", "Executing an action also needs that action's own permission.", [
        ("run", "Run the agent"),
        ("proposals.read", "See proposals"),
        ("proposals.approve", "Approve a proposal"),
        ("proposals.reject", "Reject a proposal"),
        ("actions.execute", "!Execute an approved action"),
    ]),
    ("analytics", "Analytics", "S/R", "Aggregates and raw question text are controlled separately.", [
        ("read", "See analytics"),
        ("raw.read", "!Read raw questions and prompts"),
        ("export", "Export reports"),
        ("improvements.create", "Propose improvements"),
        ("improvements.manage", "Manage improvement actions"),
    ]),
    ("tibi", "Tibi", "S/R", "No implicit family-wide evidence; the persona is a platform setting.", [
        ("use", "Talk with Tibi"),
        ("voice.use", "Use the voice"),
        ("rehearsal.use", "Use rehearsal mode"),
        ("knowledge.read", "See Tibi's knowledge"),
        ("knowledge.edit", "Edit Tibi's knowledge"),
        ("knowledge.approve", "Approve Tibi's knowledge"),
        ("spoken.edit", "Edit spoken answers"),
        ("spoken.approve", "Approve spoken answers"),
        ("persona.manage", "!Change Tibi's persona", "P"),
    ]),
    ("avatar", "Digital SME", "S", "Rendered by a managed service: the reply text leaves the machine. "
     "It answers from the OpsAtlas family only; no organisation's content reaches it.", [
        ("use", "Use the Digital SME"),
        ("session.create", "Start an avatar session"),
    ]),
    ("conversations", "Conversations", "S", "read_all means the space, never the installation.", [
        ("read_own", "See my own conversations", "O"),
        ("delete_own", "Delete my own conversations", "O"),
        ("read_all", "!Read everyone's conversations in the space"),
        ("review", "Review conversation turns"),
        ("export", "!Export conversations"),
        ("delete_all", "!Delete conversations"),
    ]),
    ("jobs", "Jobs", "S", "The underlying operation's permission is still required.", [
        ("read_own", "See my own jobs", "O"),
        ("cancel_own", "Cancel my own jobs", "O"),
        ("read_all", "See everyone's jobs in the space"),
        ("cancel_all", "Cancel anyone's jobs in the space"),
    ]),
    ("exports", "Exports", "S/R/O", "Also require the domain's export permission and current read access.", [
        ("create", "Create an export"),
        ("download", "Download an export"),
        ("revoke", "Revoke an export"),
    ]),
    ("audit", "Audit", "P/S", "IAM metadata; never document content or conversation text.", [
        ("read", "Read the security audit"),
        ("export", "!Export the security audit"),
    ]),
    ("diagnostics", "Diagnostics", "P/S", "Secrets are redacted and data scope holds even for debug tools.", [
        ("read", "See diagnostics"),
        ("traces.read", "!Read traces"),
    ]),
]


# Permissions registered ahead of the routes that will check them (REF S5). They are listed in the catalogue and kept
# by the built-in roles, so nothing changes when their routes arrive, but they guard nothing yet: a custom role cannot
# be given one, and a test fails if a permission that is not reserved guards nothing.
RESERVED = {
    "account.read_self": "implied: every signed-in person reads their own account (the signed-in marker)",
    "iam.groups.update": "groups are not built",
    "iam.access.review": "access reviews are deferred (IAM guide, section 5)",
    "iam.access.requests.read_own": "access requests are deferred (IAM guide, section 5)",
    "iam.services.read": "service principals: REF S12",
    "iam.services.create": "service principals: REF S12",
    "iam.services.update": "service principals: REF S12",
    "iam.services.credentials.rotate": "service principals: REF S12",
    "iam.services.revoke": "service principals: REF S12",
    "platform.services.read": "no route yet; the Settings page reads service health without it",
    "platform.models.manage": "model changes as controlled product changes: REF S41",
    "platform.integrations.manage": "no integrations are built",
    "platform.secrets.rotate": "managed secrets come with the network profile: REF S47",
    "platform.backup.manage": "backup and tested restore: REF S30",
    "platform.restore.execute": "backup and tested restore: REF S30",
    "platform.cross_space.read": "the All organisations mode is deferred (IAM guide, section 5)",
    "platform.emergency.recover": "a host procedure only (python -m assistant.iam recover), never an API",
    "spaces.delete": "deletion of an organisation, proven complete: REF S31",
    "spaces.export": "export of an organisation: REF S31",
    "spaces.policy.manage": "per-space policy (solo-operator mode): REF S15",
    "resources.permissions.read": "grants on documents and folders: REF S13",
    "resources.permissions.manage": "grants on documents and folders: REF S13",
    "resources.classification.manage": "enforced classification: REF S13, REF S23",
    "resources.ownership.transfer": "an owner on every source: REF S23",
    "sources.register": "registering a source is an upload (sources.upload)",
    "sources.reindex": "no reindex route; publishing re-ingests",
    "sources.archive": "archive and restore: REF S24",
    "sources.restore": "archive and restore: REF S24",
    "documents.create": "documents are created by upload (sources.upload)",
    "documents.withdraw": "withdrawing one's own submission is not built",
    "documents.download": "no download route",
    "comments.update_own": "editing a comment is not built",
    "comments.delete_own": "deleting a comment needs comments.moderate; deleting one's own is not built",
    "assets.delete": "images are removed with the documents that use them (REF S4)",
    "knowledge.citations.read": "citations come with the answer; evidence receipts: REF S18",
    "knowledge.retrieval_trace.read": "traces are part of the answer today; a separate grant: REF S18",
    "governance.self_approve": "author apart from approver, with an audited exception: REF S15",
    "external_sources.register": "every change to a public source needs external_sources.refresh today; REF S46",
    "processes.edit": "processes are derived from approved documents; nothing edits them directly",
    "processes.export": "no process export",
    "eam.export": "no activity-model export",
    "ontology.query": "facts-map queries run inside answering (knowledge.ask) and its views (ontology.read)",
    "ontology.edit": "the facts map is derived and rebuilt; nothing edits it directly",
    "ontology.export": "no facts-map export",
    "tibi.knowledge.edit": "Tibi's knowledge is edited as documents (documents.edit)",
    "tibi.persona.manage": "personas as governed packages: REF S55",
    "conversations.read_own": "conversations belong to a person: REF S14",
    "conversations.delete_own": "conversations belong to a person: REF S14",
    "conversations.export": "conversation export: REF S14",
    "conversations.delete_all": "retention and deletion of conversations: REF S32",
    "jobs.read_own": "jobs belong to a person: REF S14, durable jobs: REF S33",
    "jobs.cancel_own": "jobs belong to a person: REF S14, durable jobs: REF S33",
    "jobs.read_all": "durable jobs: REF S33",
    "jobs.cancel_all": "durable jobs: REF S33",
    "exports.create": "export of an organisation: REF S31",
    "exports.download": "export of an organisation: REF S31",
    "exports.revoke": "export of an organisation: REF S31",
    "audit.export": "an audit export with chain verification: REF S17",
}


def _scopes(codes: str) -> tuple[str, ...]:
    return tuple(_CODES[c] for c in codes.split("/"))


def _build() -> tuple[list[Namespace], dict[str, Permission]]:
    namespaces, permissions = [], {}
    for key, label, default, note, actions in _SPEC:
        rows = []
        for entry in actions:
            action, description = entry[0], entry[1]
            scopes = _scopes(entry[2] if len(entry) > 2 else default)
            risky = description.startswith("!")
            reserved = RESERVED.get(f"{key}.{action}", "")
            permission = Permission(f"{key}.{action}", key, action, scopes, description.lstrip("!"), risky, reserved)
            rows.append(permission)
            permissions[permission.key] = permission
        namespaces.append(Namespace(key, label, note, tuple(rows)))
    return namespaces, permissions


NAMESPACES, PERMISSIONS = _build()
KEYS = tuple(PERMISSIONS)


def get(key: str) -> Permission | None:
    return PERMISSIONS.get(key)


def valid_at(key: str, scope_type: str) -> bool:
    permission = PERMISSIONS.get(key)
    return permission is not None and scope_type in permission.scopes


def platform_keys() -> tuple[str, ...]:
    return tuple(k for k, p in PERMISSIONS.items() if p.at_platform)


def space_keys() -> tuple[str, ...]:
    return tuple(k for k, p in PERMISSIONS.items() if p.in_spaces)


def registry() -> dict:
    return {
        "version": VERSION,
        "namespaces": [{"key": n.key, "label": n.label, "note": n.note} for n in NAMESPACES],
        "permissions": [
            {"key": p.key, "namespace": p.namespace, "action": p.action, "scopes": list(p.scopes),
             "description": p.description, "risky": p.risky, "reserved": p.reserved}
            for p in PERMISSIONS.values()
        ],
    }


def typescript() -> str:
    """The frontend's copy: a union type of the keys, the labels and the namespaces (generated, never edited)."""
    lines = ["// Generated from the permission catalogue (python -m assistant.iam catalogue --typescript). Do not edit.",
             f"export const CATALOGUE_VERSION = {VERSION};", "", "export const PERMISSION_KEYS = ["]
    lines += [f'  "{k}",' for k in PERMISSIONS]
    lines += ["] as const;", "", "export type Permission = (typeof PERMISSION_KEYS)[number];", "",
              "export interface PermissionInfo {",
              "  namespace: string;", "  description: string;", "  scopes: string[];", "  risky: boolean;",
              "  /** Why it guards nothing yet; a custom role cannot be given it (REF S5). */", "  reserved: string;", "}", "",
              "export const PERMISSIONS: Record<Permission, PermissionInfo> = {"]
    for p in PERMISSIONS.values():
        lines.append(f'  "{p.key}": {{ namespace: "{p.namespace}", description: {json.dumps(p.description)}, '
                     f"scopes: {json.dumps(list(p.scopes))}, risky: {str(p.risky).lower()}, reserved: {json.dumps(p.reserved)} }},")
    lines += ["};", "", "export const NAMESPACES: { key: string; label: string; note: string }[] = ["]
    lines += [f"  {{ key: {json.dumps(n.key)}, label: {json.dumps(n.label)}, note: {json.dumps(n.note)} }}," for n in NAMESPACES]
    lines += ["];", ""]
    return "\n".join(lines)
