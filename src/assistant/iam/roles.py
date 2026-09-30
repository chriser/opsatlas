"""The built-in roles (IAM F1): named, versioned sets of registered permissions, and what each may grant.

A role only acts through a binding at a scope. Sets below are expanded into exact permission keys; a permission not
listed is off. The role's name adds nothing: the test suite checks every key is registered and valid for the role's
boundary. Editing a built-in role is not possible; a custom role starts from one of these.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import catalogue

SEED_VERSION = 1


@dataclass(frozen=True)
class Role:
    id: str
    name: str
    boundary: str  # "platform" or "space"
    description: str
    permissions: tuple[str, ...]
    excluded: str = ""  # what the role deliberately does not allow, shown in the editor
    grantable: tuple[str, ...] = field(default_factory=tuple)  # roles a holder may give to others, within their scope
    protected: bool = False  # cannot be cloned into a space role; giving it needs fresh authentication
    system: bool = False  # bound by the system (activation), not offered in the editor
    version: int = SEED_VERSION

    @property
    def builtin(self) -> bool:
        return True

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "boundary": self.boundary, "description": self.description,
                "permissions": list(self.permissions), "excluded": self.excluded, "grantable": list(self.grantable),
                "protected": self.protected, "system": self.system, "version": self.version, "builtin": True}


def _keys(*parts: str) -> tuple[str, ...]:
    out: list[str] = []
    for part in parts:
        for key in part.split():
            if key not in catalogue.PERMISSIONS:
                raise ValueError(f"Unregistered permission in a role seed: {key}")
            if key not in out:
                out.append(key)
    return tuple(out)


READ = """spaces.read collections.read documents.read assets.read comments.read knowledge.search knowledge.ask
knowledge.citations.read processes.read eam.read ontology.read ontology.query analytics.read external_sources.read
regulatory.read tibi.use tibi.voice.use avatar.use avatar.session.create conversations.read_own conversations.delete_own
jobs.read_own jobs.cancel_own"""
CONTRIBUTE = """sources.register sources.upload sources.metadata.update sources.ingest sources.reindex documents.create
documents.edit documents.submit documents.withdraw documents.draft.read documents.versions.read documents.versions.restore
comments.create comments.update_own comments.delete_own collections.create collections.update collections.move
assets.upload assets.delete processes.capture.create processes.edit processes.diagrams.generate external_sources.register
external_sources.refresh"""
APPROVE = """documents.draft.read documents.versions.read documents.approve documents.reject documents.publish
comments.moderate governance.read governance.scan.run governance.reviews.run governance.reviews.cancel
governance.findings.resolve governance.exceptions.accept regulatory.reviews.run regulatory.decisions.approve
agent.proposals.read agent.proposals.approve agent.proposals.reject"""
ADMINISTER_SPACE = """spaces.update spaces.archive spaces.restore spaces.export spaces.members.read spaces.members.invite
spaces.members.manage spaces.policy.manage iam.roles.read iam.roles.assign iam.groups.read iam.groups.create iam.groups.update
iam.groups.delete iam.groups.members.manage iam.access.explain iam.access.review iam.access.requests.decide
iam.access.deny.manage resources.permissions.read resources.permissions.manage resources.classification.manage
resources.ownership.transfer collections.delete sources.archive sources.restore sources.delete documents.transfer
documents.download audit.read ontology.edit ontology.rebuild ontology.export eam.export processes.export
processes.stress.run analytics.export analytics.improvements.create analytics.improvements.manage analytics.value.manage
jobs.read_all jobs.cancel_all exports.create exports.download exports.revoke external_sources.delete agent.run
agent.actions.execute conversations.review diagnostics.read diagnostics.simulator.run"""
ANALYSE = """analytics.export analytics.improvements.create analytics.improvements.manage analytics.value.manage eam.export
processes.export exports.create exports.download"""
AUDIT = "spaces.read audit.read governance.read iam.access.review iam.access.explain analytics.read"
GUEST = """spaces.read collections.read documents.read assets.read comments.read knowledge.search knowledge.ask
knowledge.citations.read conversations.read_own conversations.delete_own"""
TIBI_MAINTAIN = """tibi.knowledge.read tibi.knowledge.edit tibi.knowledge.approve tibi.spoken.edit tibi.spoken.approve
tibi.rehearsal.use ontology.edit ontology.rebuild"""
BASELINE = """account.read_self account.update_self account.password.change account.sessions.read_self
account.sessions.revoke_self iam.access.requests.create iam.access.requests.read_own iam.access.requests.cancel_own"""
IDENTITY_ADMIN = """iam.users.read iam.users.invite iam.users.update iam.users.suspend iam.users.reactivate
iam.users.recovery.initiate iam.users.deactivate iam.sessions.read iam.sessions.revoke iam.roles.read iam.roles.create
iam.roles.update iam.roles.delete iam.roles.assign iam.groups.read iam.groups.create iam.groups.update iam.groups.delete
iam.groups.members.manage iam.access.explain iam.access.review iam.access.requests.decide iam.access.deny.manage
iam.services.read audit.read platform.settings.read spaces.create"""

SPACE_ROLE_IDS = ("space_reader", "space_contributor", "space_approver", "analyst", "auditor", "external_guest")

BUILTIN: dict[str, Role] = {r.id: r for r in [
    Role("platform_administrator", "Platform administrator", "platform",
         "Every registered platform permission, and explicit bindings for every space permission in every space, "
         "including the All organisations view.",
         tuple(catalogue.KEYS),
         excluded="Restriction bypass, unlogged access, reading secrets. Self-approval only in a space's solo-operator "
                  "mode. Emergency recovery only through the local procedure.",
         grantable=("platform_administrator", "identity_administrator", "product_owner", "sales_user", "space_owner")
                   + SPACE_ROLE_IDS,
         protected=True),
    Role("identity_administrator", "Identity administrator", "platform",
         "People, sessions, groups, invitations, recovery and role administration within a grant ceiling.",
         _keys(IDENTITY_ADMIN),
         excluded="Business content, services, models and secrets. Creating platform administrators.",
         grantable=("identity_administrator", "product_owner", "sales_user", "space_owner") + SPACE_ROLE_IDS,
         protected=True),
    Role("product_owner", "Product owner", "space",
         "Reads, contributes to and approves the Product Guide and the Sales Playbook; maintains Tibi's product and "
         "spoken knowledge.",
         _keys(READ, CONTRIBUTE, APPROVE, TIBI_MAINTAIN, "documents.download"),
         excluded="Organisation memberships, platform administration, persona and system changes."),
    Role("sales_user", "Sales user", "space",
         "Reads and asks the Product Guide and the Sales Playbook; uses rehearsal mode.",
         _keys(READ, "tibi.rehearsal.use"),
         excluded="Organisation data unless separately assigned; product approval; persona changes."),
    Role("space_owner", "Space owner", "space",
         "Reader, contributor and approver for one organisation, plus its members, approved space roles, policies, "
         "governance, audit and lifecycle.",
         _keys(READ, CONTRIBUTE, APPROVE, ADMINISTER_SPACE),
         excluded="Platform authority, hard deletion of the space, self-approval, raw conversations and prompts.",
         grantable=SPACE_ROLE_IDS + ("space_owner",)),
    Role("space_reader", "Space reader", "space",
         "Approved documents and their images; search, questions and citations; process, activity-model and facts-map "
         "views; aggregate analytics; Tibi and the reader's own conversations.",
         _keys(READ),
         excluded="Drafts, changes, downloads and exports, other people's conversations, traces."),
    Role("space_contributor", "Space contributor", "space",
         "Reader, plus uploads, drafts, submissions, comments, version review and folder organisation.",
         _keys(READ, CONTRIBUTE),
         excluded="Approval and publication, members and policies, archive, delete and transfer."),
    Role("space_approver", "Space approver", "space",
         "Reader, plus draft and version review, approve, reject and publish, governance decisions and proposals.",
         _keys(READ, APPROVE),
         excluded="Role and access administration; approving own work; editing a submitted revision while approving it."),
    Role("analyst", "Analyst", "space",
         "Reader, plus report exports and improvement and value modelling.",
         _keys(READ, ANALYSE),
         excluded="Raw question text, data dumps, document editing, IAM changes."),
    Role("auditor", "Auditor", "space",
         "Space audit and governance decision metadata; access-review evidence.",
         _keys(AUDIT),
         excluded="Document bodies, raw prompts, conversation contents, any change."),
    Role("external_guest", "External guest", "space",
         "Reads named documents and folders only, for a limited time.",
         _keys(GUEST),
         excluded="Whole-space discovery, export, drafts, access administration, other people's activity."),
    Role("signed_in_user", "Signed-in user", "platform",
         "What every active person can do for themselves: their account, sessions and access requests.",
         _keys(BASELINE), system=True),
]}

# What a space owner may give inside the space; a further owner is a protected grant (fresh authentication).
PLATFORM_ROLE_IDS = tuple(r.id for r in BUILTIN.values() if r.boundary == "platform" and not r.system)
PRODUCT_GUIDE_ROLE = "space_reader"  # every active person, in the Product Guide (an explicit binding, not a bypass)


def seed_json() -> dict:
    return {"version": SEED_VERSION, "roles": [r.to_dict() for r in BUILTIN.values()]}
