"""Where content management keeps its state: one SQLite database beside the source register (CM E1).

The published text of a source stays in the register. This store holds what is not the published text: the working
draft and its status, every version, comments and their replies, and the activity log.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    source_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'published',         -- published | draft | submitted
    draft_text TEXT,
    draft_sha TEXT,
    base_sha TEXT,                                    -- the published text the draft started from
    draft_updated_at TEXT,
    draft_author TEXT,
    submitted_at TEXT,
    submitted_by TEXT,
    submitted_note TEXT
);
CREATE TABLE IF NOT EXISTS versions (
    source_id TEXT NOT NULL,
    n INTEGER NOT NULL,
    text TEXT NOT NULL,
    sha TEXT NOT NULL,
    label TEXT NOT NULL,                              -- imported | approved | restored
    author TEXT NOT NULL,
    role TEXT NOT NULL,
    at TEXT NOT NULL,
    note TEXT,
    source_version INTEGER,
    PRIMARY KEY (source_id, n)
);
CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    quote TEXT NOT NULL,
    prefix TEXT NOT NULL DEFAULT '',
    suffix TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    author TEXT NOT NULL,
    role TEXT NOT NULL,
    at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',              -- open | resolved
    resolved_at TEXT,
    resolved_by TEXT
);
CREATE TABLE IF NOT EXISTS replies (
    id TEXT PRIMARY KEY,
    comment_id TEXT NOT NULL,
    text TEXT NOT NULL,
    author TEXT NOT NULL,
    role TEXT NOT NULL,
    at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    at TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT
);
CREATE INDEX IF NOT EXISTS comments_by_source ON comments (source_id);
CREATE INDEX IF NOT EXISTS activity_by_source ON activity (source_id, id);
-- The library: groups (categories that are not documents) and where each document sits. A parent is
-- "group:<id>", "source:<id>" or NULL for the top level.
CREATE TABLE IF NOT EXISTS groups (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    parent TEXT,
    position INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS placements (
    source_id TEXT PRIMARY KEY,
    parent TEXT,
    position INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
-- Governance suggestions: the open ones last seen on each document, and the ones settled (corrected by an edit,
-- accepted as they are, or resolved another way), kept as the document's record.
CREATE TABLE IF NOT EXISTS suggestions_seen (
    source_id TEXT NOT NULL,
    key TEXT NOT NULL,
    data TEXT NOT NULL,
    content_sha TEXT,
    first_seen_at TEXT NOT NULL,
    PRIMARY KEY (source_id, key)
);
CREATE TABLE IF NOT EXISTS suggestions_settled (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    key TEXT NOT NULL,
    outcome TEXT NOT NULL,
    data TEXT NOT NULL,
    version INTEGER,
    actor TEXT,
    role TEXT,
    at TEXT NOT NULL,
    note TEXT
);
CREATE INDEX IF NOT EXISTS settled_by_source ON suggestions_settled (source_id, at);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ContentStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.dir = Path(base_dir) / "content"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.assets = self.dir / "assets"
        self.path = self.dir / "content.db"
        self.lock = threading.RLock()
        with self._db() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        finally:
            db.close()

    # ---- documents -----------------------------------------------------------------------

    def document(self, source_id: str) -> dict | None:
        with self._db() as db:
            row = db.execute("SELECT * FROM documents WHERE source_id = ?", (source_id,)).fetchone()
        return dict(row) if row else None

    def documents(self) -> list[dict]:
        """Documents with a draft or awaiting approval."""
        with self._db() as db:
            rows = db.execute("SELECT source_id, status, draft_updated_at, submitted_at FROM documents "
                              "WHERE status != 'published'").fetchall()
        return [dict(r) for r in rows]

    def save_document(self, source_id: str, **fields) -> None:
        columns = ["source_id", *fields]
        with self._db() as db:
            db.execute(f"INSERT INTO documents ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)}) "
                       f"ON CONFLICT(source_id) DO UPDATE SET {', '.join(f'{k} = excluded.{k}' for k in fields) or 'status = status'}",
                       [source_id, *fields.values()])

    def clear_draft(self, source_id: str) -> None:
        self.save_document(source_id, status="published", draft_text=None, draft_sha=None, base_sha=None, draft_updated_at=None,
                           draft_author=None, submitted_at=None, submitted_by=None, submitted_note=None)

    # ---- versions --------------------------------------------------------------------------

    def versions(self, source_id: str) -> list[dict]:
        with self._db() as db:
            rows = db.execute("SELECT source_id, n, sha, label, author, role, at, note, source_version, length(text) AS chars "
                              "FROM versions WHERE source_id = ? ORDER BY n DESC", (source_id,)).fetchall()
        return [dict(r) for r in rows]

    def version(self, source_id: str, n: int) -> dict | None:
        with self._db() as db:
            row = db.execute("SELECT * FROM versions WHERE source_id = ? AND n = ?", (source_id, n)).fetchone()
        return dict(row) if row else None

    def add_version(self, source_id: str, text: str, sha: str, label: str, author: str, role: str, note: str | None = None,
                    source_version: int | None = None) -> int:
        with self.lock, self._db() as db:
            n = (db.execute("SELECT MAX(n) FROM versions WHERE source_id = ?", (source_id,)).fetchone()[0] or 0) + 1
            db.execute("INSERT INTO versions (source_id, n, text, sha, label, author, role, at, note, source_version) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (source_id, n, text, sha, label, author, role, now(), note, source_version))
        return n

    # ---- comments ------------------------------------------------------------------------

    def comments(self, source_id: str) -> list[dict]:
        with self._db() as db:
            rows = [dict(r) for r in db.execute("SELECT * FROM comments WHERE source_id = ? ORDER BY at", (source_id,))]
            replies = {}
            for r in db.execute("SELECT replies.* FROM replies JOIN comments ON comments.id = replies.comment_id "
                                "WHERE comments.source_id = ? ORDER BY replies.at", (source_id,)):
                replies.setdefault(r["comment_id"], []).append(dict(r))
        for row in rows:
            row["replies"] = replies.get(row["id"], [])
        return rows

    def comment(self, comment_id: str) -> dict | None:
        with self._db() as db:
            row = db.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()
        return dict(row) if row else None

    def add_comment(self, source_id: str, quote: str, prefix: str, suffix: str, text: str, author: str, role: str) -> str:
        comment_id = uuid.uuid4().hex
        with self._db() as db:
            db.execute("INSERT INTO comments (id, source_id, quote, prefix, suffix, text, author, role, at) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (comment_id, source_id, quote, prefix, suffix, text, author, role, now()))
        return comment_id

    def add_reply(self, comment_id: str, text: str, author: str, role: str) -> str:
        reply_id = uuid.uuid4().hex
        with self._db() as db:
            db.execute("INSERT INTO replies (id, comment_id, text, author, role, at) VALUES (?, ?, ?, ?, ?, ?)",
                       (reply_id, comment_id, text, author, role, now()))
        return reply_id

    def set_comment_status(self, comment_id: str, status: str, actor: str) -> None:
        with self._db() as db:
            db.execute("UPDATE comments SET status = ?, resolved_at = ?, resolved_by = ? WHERE id = ?",
                       (status, now() if status == "resolved" else None, actor if status == "resolved" else None, comment_id))

    def delete_comment(self, comment_id: str) -> None:
        with self._db() as db:
            db.execute("DELETE FROM replies WHERE comment_id = ?", (comment_id,))
            db.execute("DELETE FROM comments WHERE id = ?", (comment_id,))

    # ---- activity --------------------------------------------------------------------------

    def log(self, source_id: str, actor: str, action: str, detail: str = "", coalesce: bool = False) -> None:
        """Record an event. With ``coalesce``, a repeat of the same action by the same actor within ten minutes only
        moves the earlier entry's time, so autosaving does not flood the log."""
        with self.lock, self._db() as db:
            if coalesce:
                last = db.execute("SELECT id, at, actor, action FROM activity WHERE source_id = ? ORDER BY id DESC LIMIT 1",
                                  (source_id,)).fetchone()
                if last and last["actor"] == actor and last["action"] == action:
                    age = datetime.now(timezone.utc) - datetime.fromisoformat(last["at"])
                    if age.total_seconds() < 600:
                        db.execute("UPDATE activity SET at = ?, detail = ? WHERE id = ?", (now(), detail, last["id"]))
                        return
            db.execute("INSERT INTO activity (source_id, at, actor, action, detail) VALUES (?, ?, ?, ?, ?)",
                       (source_id, now(), actor, action, detail))

    # ---- the library -------------------------------------------------------------------------

    def groups(self) -> list[dict]:
        with self._db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM groups ORDER BY position, created_at")]

    def placements(self) -> dict:
        with self._db() as db:
            return {r["source_id"]: {"parent": r["parent"], "position": r["position"]}
                    for r in db.execute("SELECT * FROM placements")}

    def next_position(self, parent: str | None) -> int:
        with self._db() as db:
            a = db.execute("SELECT MAX(position) FROM groups WHERE parent IS ?", (parent,)).fetchone()[0]
            b = db.execute("SELECT MAX(position) FROM placements WHERE parent IS ?", (parent,)).fetchone()[0]
        return max(a or 0, b or 0) + 1

    def add_group(self, title: str, parent: str | None, position: int | None = None) -> str:
        group_id = uuid.uuid4().hex[:12]
        with self.lock, self._db() as db:
            db.execute("INSERT INTO groups (id, title, parent, position, created_at) VALUES (?, ?, ?, ?, ?)",
                       (group_id, title, parent, position if position is not None else self.next_position(parent), now()))
        return group_id

    def update_group(self, group_id: str, **fields) -> None:
        with self._db() as db:
            db.execute(f"UPDATE groups SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?", [*fields.values(), group_id])

    def delete_group(self, group_id: str, parent: str | None) -> None:
        """Remove a group; what was in it moves up to the group's own parent."""
        node = f"group:{group_id}"
        with self.lock, self._db() as db:
            db.execute("UPDATE groups SET parent = ? WHERE parent = ?", (parent, node))
            db.execute("UPDATE placements SET parent = ? WHERE parent = ?", (parent, node))
            db.execute("DELETE FROM groups WHERE id = ?", (group_id,))

    def place(self, source_id: str, parent: str | None, position: int | None = None) -> None:
        with self.lock, self._db() as db:
            db.execute("INSERT INTO placements (source_id, parent, position) VALUES (?, ?, ?) "
                       "ON CONFLICT(source_id) DO UPDATE SET parent = excluded.parent, position = excluded.position",
                       (source_id, parent, position if position is not None else self.next_position(parent)))

    def arrange(self, parent: str | None, keys: list[str]) -> None:
        """Put each "group:<id>" or "source:<id>" in ``keys`` under ``parent``, numbered in that order."""
        with self.lock, self._db() as db:
            for position, key in enumerate(keys, 1):
                kind, _, ident = key.partition(":")
                if kind == "group":
                    db.execute("UPDATE groups SET parent = ?, position = ? WHERE id = ?", (parent, position, ident))
                else:
                    db.execute("INSERT INTO placements (source_id, parent, position) VALUES (?, ?, ?) "
                               "ON CONFLICT(source_id) DO UPDATE SET parent = excluded.parent, position = excluded.position",
                               (ident, parent, position))

    def meta(self, key: str) -> str | None:
        with self._db() as db:
            row = db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self._db() as db:
            db.execute("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))

    # ---- governance suggestions -------------------------------------------------------------

    def seen(self) -> dict:
        with self._db() as db:
            return {(r["source_id"], r["key"]): {**dict(r), "data": json.loads(r["data"])}
                    for r in db.execute("SELECT * FROM suggestions_seen")}

    def see(self, source_id: str, suggestion: dict, content_sha: str | None) -> None:
        with self._db() as db:
            db.execute("INSERT OR IGNORE INTO suggestions_seen (source_id, key, data, content_sha, first_seen_at) "
                       "VALUES (?, ?, ?, ?, ?)", (source_id, suggestion["key"], json.dumps(suggestion), content_sha, now()))

    def unsee(self, source_id: str, key: str) -> None:
        with self._db() as db:
            db.execute("DELETE FROM suggestions_seen WHERE source_id = ? AND key = ?", (source_id, key))

    def settle(self, source_id: str, suggestion: dict, outcome: str, version: int | None, actor: str, role: str,
               note: str | None = None, at: str | None = None) -> str:
        settled_id = uuid.uuid4().hex[:16]
        with self._db() as db:
            db.execute("INSERT INTO suggestions_settled (id, source_id, key, outcome, data, version, actor, role, at, note) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (settled_id, source_id, suggestion["key"], outcome,
                                                                json.dumps(suggestion), version, actor, role, at or now(), note))
        return settled_id

    def settled(self, source_id: str | None = None) -> list[dict]:
        query = "SELECT * FROM suggestions_settled" + (" WHERE source_id = ?" if source_id else "") + " ORDER BY at DESC"
        with self._db() as db:
            rows = db.execute(query, (source_id,) if source_id else ()).fetchall()
        return [{**dict(r), "data": json.loads(r["data"])} for r in rows]

    def settled_row(self, settled_id: str) -> dict | None:
        with self._db() as db:
            row = db.execute("SELECT * FROM suggestions_settled WHERE id = ?", (settled_id,)).fetchone()
        return {**dict(row), "data": json.loads(row["data"])} if row else None

    def unsettle(self, settled_id: str) -> None:
        with self._db() as db:
            db.execute("DELETE FROM suggestions_settled WHERE id = ?", (settled_id,))

    def activity(self, source_id: str, limit: int = 200) -> list[dict]:
        with self._db() as db:
            rows = db.execute("SELECT at, actor, action, detail FROM activity WHERE source_id = ? ORDER BY id DESC LIMIT ?",
                              (source_id, limit)).fetchall()
        return [dict(r) for r in rows]
