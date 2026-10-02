"""Service principals (REF S12): each sidecar that calls the workspace is a principal of its own, with its own credential
and exactly the service permissions its routes need. A credential that belongs to no principal is refused; a principal
calling a route outside its permissions is refused; every call is recorded as that service, and, when Tibi names the
conversation it serves, as acting for that conversation's owner (REF S10).

There is one such sidecar today: Tibi's voice service, whose credential is the workspace's ``local-access.key`` (Tibi
reads that file as it starts, so the file keeps its name). The process-diagram service is not a principal: it is called
by the workspace, never calls it, holds no data and acts on nothing, so it has no credential to steal; OpsAtlas Classic
calls the same renderer without one. Writes that approve, withdraw or settle knowledge are never service routes: they
name a person (REF S12, phase 1b).

Built-in principals are owned by the platform administrators. Their credentials do not expire: replacing one is a host
procedure (write a new key file, restart the sidecar), recorded in the guide, not an API.
"""
from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path

# What a service route may be called for. Each route of /api/sales/* names one.
PERMISSIONS = {
    'sales.read': "Read the evidence Tibi answers from: records, product facts, spoken answers, sources and search",
    'sales.spoken.propose': 'Propose a spoken answer for review (a person approves it)',
    'sales.proposals.create': 'Propose a record from a contribution for review (a person approves it)',
    'sales.governance.interview': "Read the governance agenda, record an interview's answers and verify a statement",
}


@dataclass
class ServicePrincipal:
    id: str
    name: str
    credential_file: str
    permissions: tuple[str, ...]
    purpose: str
    owner: str = 'the platform administrators'
    last_used: float | None = field(default=None, compare=False)


BUILT_IN = (
    ServicePrincipal('tibi', "Tibi's voice service", 'local-access.key', tuple(PERMISSIONS),
                     'Answers by voice, the Digital SME and interviews; reads evidence as the person it serves'),
)


class ServicePrincipals:
    def __init__(self, root: Path, principals=BUILT_IN) -> None:
        self.root = Path(root)
        self.principals = {p.id: ServicePrincipal(**{**p.__dict__}) for p in principals}
        self._keys = {p.id: (self.root / p.credential_file).read_text().strip() for p in self.principals.values()}

    def identify(self, presented: str) -> ServicePrincipal | None:
        """The principal a presented credential belongs to, or None. Every key is compared, in constant time."""
        found = None
        for principal_id, key in self._keys.items():
            if secrets.compare_digest(presented.encode(), key.encode()):
                found = self.principals[principal_id]
        if found is not None:
            found.last_used = time.time()
        return found

    def credentials(self) -> tuple[str, ...]:
        """The credentials, for the activity log to keep out of every line it writes."""
        return tuple(self._keys.values())

    def fingerprint(self, principal_id: str) -> str:
        """A short, one-way fingerprint of the credential, to tell a replaced key from the old one; never the key."""
        return hashlib.sha256(self._keys[principal_id].encode()).hexdigest()[:12]

    def describe(self, routes: dict[str, list[str]]) -> list[dict]:
        return [{'id': p.id, 'name': p.name, 'purpose': p.purpose, 'owner': p.owner, 'credential': p.credential_file,
                 'fingerprint': self.fingerprint(p.id), 'expires': None,
                 'last_used': time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(p.last_used)) if p.last_used else None,
                 'permissions': [{'key': k, 'label': PERMISSIONS[k], 'routes': routes.get(k, [])} for k in p.permissions]}
                for p in self.principals.values()]


def build_router(app):
    """GET /api/iam/services: the service principals, what each may call, its credential's fingerprint (never the key)
    and when it was last used; and the sidecar that needs none."""
    from fastapi import APIRouter

    from assistant.api.access import _walk, need

    router = APIRouter()

    def routes() -> dict[str, list[str]]:
        found: dict[str, list[str]] = {}
        for path, route, _ in _walk(app.routes):  # the walk the route manifest makes, through included routers
            for dependency in getattr(route, 'dependencies', None) or []:
                permission = getattr(dependency.dependency, 'service_permission', None)
                if permission:
                    found.setdefault(permission, []).extend(f'{m} {path}' for m in sorted(route.methods))
        return found

    @router.get('/api/iam/services', dependencies=[need('iam.services.read', scope='platform')])
    def services():
        return {'principals': app.state.service_principals.describe(routes()),
                'without_credential': [{'name': 'Process diagram service', 'port': 5300,
                                        'why': 'Called by the workspace, never calls it; holds no data and acts on nothing.'}]}
    return router
