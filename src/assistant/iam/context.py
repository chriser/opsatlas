"""The principal of the current request, for services that record who acted (IAM F5).

The API boundary sets it once a session is resolved; a service reads it when it needs a name for a log line or a
version's author. It is per request (a context variable), never a shared setting that a later request could inherit.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    id: str
    display_name: str
    role_label: str


_current: ContextVar[Principal | None] = ContextVar("iam_principal", default=None)


def set_principal(principal: Principal | None) -> None:
    _current.set(principal)


def current_principal() -> Principal | None:
    return _current.get()


# Who acted, for a record a workspace writes when no person is signed in: a call with the workspace's service key
# (Tibi, a host script). Service principals of their own come with REF S12.
SERVICE_ACTOR = "workspace service key"


def acting_name(fallback: str = SERVICE_ACTOR) -> str:
    """The signed-in person's name, or ``fallback`` (REF S3: records name the person, not a fixed 'operator')."""
    principal = _current.get()
    return principal.display_name if principal else fallback


def acting_id(fallback: str = "service:workspace-key") -> str:
    """The signed-in person's stable id, or ``fallback``."""
    principal = _current.get()
    return principal.id if principal else fallback
