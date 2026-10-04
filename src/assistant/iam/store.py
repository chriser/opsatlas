"""The IAM store (IAM F2): one SQLite database, ``iam.db``, for identities, sessions and policy metadata.

Business data stays in its space partitions; this database holds only what routing and authorisation need. One
connection, one lock: the deployment is single-host and single-process (several API workers would need a shared
store and a fresh concurrency test). Writes are transactions; the file is readable by the service user only.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, login TEXT NOT NULL, login_canonical TEXT NOT NULL UNIQUE, email TEXT NOT NULL,
  display_name TEXT NOT NULL, state TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'human',
  credential_epoch INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  activated_at TEXT, deactivated_at TEXT, last_sign_in_at TEXT, note TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS credentials (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), type TEXT NOT NULL, hash TEXT NOT NULL,
  params TEXT NOT NULL, changed_at TEXT NOT NULL, compromised INTEGER NOT NULL DEFAULT 0, revoked_at TEXT);
CREATE INDEX IF NOT EXISTS credentials_user ON credentials(user_id);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, digest TEXT NOT NULL UNIQUE, user_id TEXT NOT NULL REFERENCES users(id),
  credential_epoch INTEGER NOT NULL, csrf TEXT NOT NULL, privileged INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL, authenticated_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
  absolute_expires_at TEXT NOT NULL, revoked_at TEXT, revoked_reason TEXT, device TEXT NOT NULL DEFAULT '',
  address TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS lifecycle_tokens (
  id TEXT PRIMARY KEY, digest TEXT NOT NULL UNIQUE, purpose TEXT NOT NULL, user_id TEXT REFERENCES users(id),
  email TEXT NOT NULL DEFAULT '', issuer_id TEXT, payload TEXT NOT NULL DEFAULT '{}', issued_at TEXT NOT NULL,
  expires_at TEXT NOT NULL, consumed_at TEXT, revoked_at TEXT);
CREATE INDEX IF NOT EXISTS lifecycle_user ON lifecycle_tokens(user_id, purpose);
CREATE TABLE IF NOT EXISTS spaces (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
  solo_operator INTEGER NOT NULL DEFAULT 0, registered_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS memberships (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), space_id TEXT NOT NULL REFERENCES spaces(id),
  status TEXT NOT NULL, joined_at TEXT NOT NULL, expires_at TEXT, revoked_at TEXT, revoked_by TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS memberships_active ON memberships(user_id, space_id) WHERE status = 'active';
CREATE TABLE IF NOT EXISTS roles (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, boundary TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
  permissions TEXT NOT NULL, grantable TEXT NOT NULL DEFAULT '[]', version INTEGER NOT NULL DEFAULT 1,
  based_on TEXT, created_by TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT);
CREATE TABLE IF NOT EXISTS role_bindings (
  id TEXT PRIMARY KEY, subject_type TEXT NOT NULL, subject_id TEXT NOT NULL, role_id TEXT NOT NULL,
  role_version INTEGER NOT NULL, scope_type TEXT NOT NULL, scope_id TEXT NOT NULL DEFAULT '',
  space_id TEXT, starts_at TEXT NOT NULL, ends_at TEXT, issuer_id TEXT, reason TEXT NOT NULL DEFAULT '',
  request_id TEXT, system INTEGER NOT NULL DEFAULT 0, revoked_at TEXT, revoked_by TEXT, revoked_reason TEXT);
CREATE INDEX IF NOT EXISTS bindings_subject ON role_bindings(subject_type, subject_id);
CREATE INDEX IF NOT EXISTS bindings_space ON role_bindings(space_id);
CREATE TABLE IF NOT EXISTS groups (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, boundary TEXT NOT NULL, space_id TEXT, description TEXT NOT NULL DEFAULT '',
  created_by TEXT, created_at TEXT NOT NULL, deleted_at TEXT);
CREATE TABLE IF NOT EXISTS group_members (
  group_id TEXT NOT NULL REFERENCES groups(id), user_id TEXT NOT NULL REFERENCES users(id), added_at TEXT NOT NULL,
  added_by TEXT, expires_at TEXT, PRIMARY KEY (group_id, user_id));
CREATE TABLE IF NOT EXISTS policy_denies (
  id TEXT PRIMARY KEY, subject_type TEXT NOT NULL, subject_id TEXT NOT NULL, permission TEXT NOT NULL,
  scope_type TEXT NOT NULL, scope_id TEXT NOT NULL DEFAULT '', starts_at TEXT NOT NULL, ends_at TEXT,
  issuer_id TEXT, reason TEXT NOT NULL DEFAULT '', revoked_at TEXT, revoked_by TEXT);
CREATE TABLE IF NOT EXISTS resource_policies (
  resource_type TEXT NOT NULL, resource_id TEXT NOT NULL, space_id TEXT NOT NULL,
  classification TEXT NOT NULL DEFAULT 'internal', restricted_to TEXT NOT NULL DEFAULT '[]',
  version INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL, updated_by TEXT,
  PRIMARY KEY (resource_type, resource_id));
CREATE TABLE IF NOT EXISTS access_requests (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), space_id TEXT, role_id TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, requested_at TEXT NOT NULL, requested_days INTEGER,
  decided_by TEXT, decided_at TEXT, decision_reason TEXT NOT NULL DEFAULT '', binding_id TEXT);
CREATE TABLE IF NOT EXISTS audit_events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE, at TEXT NOT NULL, actor_id TEXT,
  actor_type TEXT NOT NULL, on_behalf_of TEXT, session_ref TEXT, action TEXT NOT NULL, outcome TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT '', target_type TEXT, target_id TEXT, target_label TEXT, space_id TEXT,
  request_id TEXT, policy_version INTEGER NOT NULL, before TEXT, after TEXT, detail TEXT, address TEXT,
  prev_hash TEXT NOT NULL, hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rate_limits (
  key TEXT PRIMARY KEY, window_started_at TEXT NOT NULL, count INTEGER NOT NULL, blocked_until TEXT);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL, updated_by TEXT);
CREATE TABLE IF NOT EXISTS policy_versions (id INTEGER PRIMARY KEY CHECK (id = 1), version INTEGER NOT NULL, changed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS recovery_events (
  id TEXT PRIMARY KEY, at TEXT NOT NULL, user_id TEXT, kind TEXT NOT NULL, reason TEXT NOT NULL,
  host_user TEXT NOT NULL DEFAULT '', shown_at TEXT);
CREATE TABLE IF NOT EXISTS user_pictures (
  user_id TEXT PRIMARY KEY REFERENCES users(id), image BLOB NOT NULL, content_type TEXT NOT NULL, updated_at TEXT NOT NULL);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def stamp(moment: datetime) -> str:
    """One fixed-width form for every timestamp, so text comparison orders them correctly."""
    return moment.astimezone(timezone.utc).isoformat(timespec="microseconds")


def parse(text: str | None) -> datetime | None:
    return datetime.fromisoformat(text) if text else None


class IamStore:
    def __init__(self, path: str | Path | None = None, clock: Callable[[], datetime] | None = None) -> None:
        self.path = Path(path) if path else None
        self.clock = clock or utcnow
        self._lock = threading.RLock()
        self._depth = 0
        target = str(self.path) if self.path else ":memory:"
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(target, check_same_thread=False, isolation_level=None, timeout=10)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            if self.path:
                self._conn.execute("PRAGMA journal_mode=WAL")
                os.chmod(self.path, 0o600)
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA busy_timeout=10000")
            self._conn.executescript(SCHEMA)
            if self._conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0] == 0:
                self._conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            if self._conn.execute("SELECT COUNT(*) FROM policy_versions").fetchone()[0] == 0:
                self._conn.execute("INSERT INTO policy_versions (id, version, changed_at) VALUES (1, 1, ?)", (self.stamp(),))

    # -- time --------------------------------------------------------------------------------------------------
    def now(self) -> datetime:
        return self.clock()

    def stamp(self, moment: datetime | None = None) -> str:
        return stamp(moment or self.now())

    def later(self, **delta: float) -> str:
        return stamp(self.now() + timedelta(**delta))

    # -- access ------------------------------------------------------------------------------------------------
    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """One transaction, however deeply nested; the outermost commits, a failure anywhere rolls it all back."""
        with self._lock:
            if self._depth == 0:
                self._conn.execute("BEGIN IMMEDIATE")
            self._depth += 1
            try:
                yield self._conn
            except BaseException:
                if self._depth == 1:
                    self._conn.execute("ROLLBACK")
                raise
            else:
                if self._depth == 1:
                    self._conn.execute("COMMIT")
            finally:
                self._depth -= 1

    def run(self, sql: str, params: tuple | list = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, params)

    def one(self, sql: str, params: tuple | list = ()) -> dict | None:
        with self._lock:
            row = self._conn.execute(sql, params).fetchone()
        return dict(row) if row is not None else None

    def all(self, sql: str, params: tuple | list = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def insert(self, table: str, row: dict[str, Any]) -> None:
        keys = list(row)
        self.run(f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({', '.join('?' for _ in keys)})",
                 [row[k] for k in keys])

    def update(self, table: str, key: dict[str, Any], values: dict[str, Any]) -> int:
        sets = ", ".join(f"{k} = ?" for k in values)
        where = " AND ".join(f"{k} = ?" for k in key)
        return self.run(f"UPDATE {table} SET {sets} WHERE {where}", [*values.values(), *key.values()]).rowcount

    @staticmethod
    def new_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:20]}"

    # -- policy version and settings ---------------------------------------------------------------------------
    def policy_version(self) -> int:
        return int(self.one("SELECT version FROM policy_versions WHERE id = 1")["version"])

    def bump_policy_version(self) -> int:
        with self.transaction():
            version = self.policy_version() + 1
            self.run("UPDATE policy_versions SET version = ?, changed_at = ? WHERE id = 1", (version, self.stamp()))
        return version

    def setting(self, key: str, default: Any = None) -> Any:
        row = self.one("SELECT value FROM settings WHERE key = ?", (key,))
        return json.loads(row["value"]) if row else default

    def set_setting(self, key: str, value: Any, by: str | None = None) -> None:
        self.run("INSERT INTO settings (key, value, updated_at, updated_by) VALUES (?, ?, ?, ?) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at, "
                 "updated_by = excluded.updated_by", (key, json.dumps(value), self.stamp(), by))

    def close(self) -> None:
        with self._lock:
            self._conn.close()
