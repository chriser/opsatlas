"""Who started each Tibi conversation (REF S14): the workspace's own record, kept beside Tibi rather than inside it.

The gateway records the signed-in person when it forwards the start of a conversation (a voice session, an interview,
a Digital SME text session) and Tibi answers with its id. Later calls about that conversation, and the voice socket's
one-use ticket, are allowed for its owner, or for those who may read everyone's conversations in the space. A
conversation with no recorded owner (one started before this record existed, or directly against Tibi) is only for
the latter. Tibi's searches name their conversation, so the workspace answers them as its owner (REF S10, S11).
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from assistant.storage import write_json

KEEP_SECONDS = 30 * 24 * 3600  # an ownership line outlives any conversation; old lines are pruned


class TibiOwners:
    def __init__(self, root: Path) -> None:
        self.path = Path(root) / 'tibi-owners.json'
        self.lock = threading.Lock()

    def _read(self) -> dict:
        try:
            return json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}

    def record(self, conversation_id: str, owner_id: str, kind: str) -> None:
        with self.lock:
            rows = self._read()
            now = time.time()
            rows = {k: v for k, v in rows.items() if now - v.get('at', now) < KEEP_SECONDS}
            rows[conversation_id] = {'owner': owner_id, 'kind': kind, 'at': now}
            write_json(self.path, rows)

    def owner(self, conversation_id: str) -> str | None:
        row = self._read().get(conversation_id)
        return row['owner'] if row else None

    def may(self, actor, conversation_id: str, space_id: str | None) -> bool:
        owner = self.owner(conversation_id)
        if owner is not None and owner == actor.id:
            return True
        return actor.can('conversations.read_all', space_id)
