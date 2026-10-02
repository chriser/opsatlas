"""Which documents the person of a request may read in a space (REF S13, per-document grants).

A space reader reads every document unless it, or a folder it sits in, is restricted to an audience they are not in;
those who administer the space read everything. A person without a reader role in the space (an external guest, say)
reads only the documents or folders granted to them. Worked out once per request and kept in a context variable, so
the routes, retrieval and answers of the request filter by it. Derived stores (the index, the facts map, the process
registry) stay complete and are filtered when read, so one person's request never changes what another sees.
"""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar

from .policy import AuthorizationContext


class Visibility:
    def __init__(self, iam, principal_id: str, space_id: str, folders_of: Callable[[str], list[str]] | None = None) -> None:
        self.iam, self.principal_id, self.space_id = iam, principal_id, space_id
        self.folders_of = folders_of or (lambda source_id: [])
        self._cache: dict[str, bool] = {}
        self._loaded = False

    def _load(self) -> None:
        """Worked out on first use, so a request that never reads a document pays nothing."""
        if self._loaded:
            return
        self.restricted = {(r["resource_type"], r["resource_id"]) for r in self.iam.restrictions(self.space_id)}
        ctx = AuthorizationContext(principal_id=self.principal_id)
        self.reader = bool(self.iam.policy.evaluate(ctx, "documents.read", space_id=self.space_id))
        self.administers = bool(self.restricted) and self.iam.policy.administers(self.principal_id, self.space_id)
        self._loaded = True

    @property
    def unrestricted(self) -> bool:
        """Nothing in this space is hidden from this person: the fast path."""
        self._load()
        return self.administers or (self.reader and not self.restricted)

    def can_read(self, source_id: str) -> bool:
        if self.unrestricted:
            return True
        if source_id not in self._cache:
            chain = [("document", source_id), *(("folder", f) for f in self.folders_of(source_id))]
            if self.reader and not any(link in self.restricted for link in chain):
                self._cache[source_id] = True
            else:
                decision = self.iam.policy.evaluate(AuthorizationContext(principal_id=self.principal_id), "documents.read",
                                                    space_id=self.space_id, resource=chain)
                self._cache[source_id] = bool(decision)
        return self._cache[source_id]

    def hides_any(self, source_ids) -> bool:
        return not self.unrestricted and any(not self.can_read(s) for s in source_ids)


_current: ContextVar[Visibility | None] = ContextVar("iam_visibility", default=None)


def set_visibility(visibility: Visibility | None) -> None:
    _current.set(visibility)


def current_visibility() -> Visibility | None:
    return _current.get()


def visible(source_id: str) -> bool:
    """Whether the person of this request may read this source. Outside a request (start-up, a rebuild, a script) and
    under the legacy single-operator sign-in, everything is visible."""
    current = _current.get()
    return current is None or current.can_read(source_id)


def hides_any(source_ids) -> bool:
    current = _current.get()
    return current is not None and current.hides_any(source_ids)
