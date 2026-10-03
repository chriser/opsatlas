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

from assistant.storage import locked, write_json

KEEP_SECONDS = 400 * 24 * 3600  # longer than the conversation log shows a conversation (365 days); then pruned


class TibiOwners:
    def __init__(self, root: Path) -> None:
        self.path = Path(root) / 'tibi-owners.json'
        self.lock = threading.Lock()

    def _read(self) -> dict:
        """For a lookup: an unreadable record reads as empty, which only narrows access (no owner: only those who may
        read everyone's conversations)."""
        try:
            return self._read_strictly()
        except (OSError, ValueError):
            return {}

    def _read_strictly(self) -> dict:
        """For a change: a record that cannot be read is an error, so a recording never writes over everyone else's
        lines after a failed read (red team, REF F10)."""
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text())
        if not isinstance(data, dict):
            raise ValueError(f'{self.path}: expected an object')
        return data

    def record(self, conversation_id: str, owner_id: str, kind: str) -> None:
        with self.lock, locked(self.path):  # one writer at a time, across store objects and processes (red team, REF F10)
            try:
                rows = self._read_strictly()
            except ValueError:
                # Corrupt, not unreadable for a moment: kept aside as evidence, and recording starts afresh. Access only
                # narrows (conversations without an owner are for those who read everyone's). A failed read (OSError)
                # is raised instead, so a passing fault never writes over everyone's lines.
                self.path.rename(self.path.with_name(f'{self.path.name}.corrupt-{int(time.time())}'))
                rows = {}
            now = time.time()

            def kept(row) -> bool:
                at = row.get('at') if isinstance(row, dict) else None
                # A malformed line is dropped rather than stopping every later recording; a line exactly the keep
                # period old is not older than it, so it stays (red team, REF F10).
                return isinstance(at, (int, float)) and now - at <= KEEP_SECONDS
            rows = {k: v for k, v in rows.items() if kept(v)}
            rows[conversation_id] = {'owner': owner_id, 'kind': kind, 'at': now}
            write_json(self.path, rows)

    def owner(self, conversation_id: str) -> str | None:
        row = self._read().get(conversation_id)
        return row['owner'] if row else None

    def kind(self, conversation_id: str) -> str | None:
        """How the conversation was started: 'text' (the Digital SME, typed) or 'interview' (voice and interviews)."""
        row = self._read().get(conversation_id)
        return row.get('kind') if row else None

    def all(self) -> dict[str, str]:
        """Every conversation's owner, read once: the usage analytics name the person behind each Tibi turn (REF S20)."""
        return {k: v['owner'] for k, v in self._read().items() if isinstance(v, dict) and v.get('owner')}

    def may(self, actor, conversation_id: str, space_id: str | None) -> bool:
        owner = self.owner(conversation_id)
        if owner is not None and owner == actor.id:
            return True
        return actor.can('conversations.read_all', space_id)
