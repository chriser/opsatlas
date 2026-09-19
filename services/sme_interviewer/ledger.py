"""Independent SQLite session ledger with optimistic revisions and replayable events."""

import copy
import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from .dialogue import POLICY, QUESTIONS
from .evidence import digest

KINDS = {"reported_practice", "reported_policy", "proposal", "hypothetical", "uncertain"}


def now():
    return datetime.now(timezone.utc).isoformat()


class Conflict(Exception):
    pass


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()

    @contextmanager
    def connection(self):
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=5)
            self.path.chmod(0o600)
            connection.row_factory = sqlite3.Row
            try:
                connection.executescript("""
                    CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, revision INTEGER NOT NULL, data TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS events(session_id TEXT, seq INTEGER, type TEXT, at TEXT, payload TEXT,
                                                     PRIMARY KEY(session_id,seq));
                    CREATE TABLE IF NOT EXISTS requests(session_id TEXT, request_id TEXT, input_hash TEXT,
                                                       PRIMARY KEY(session_id,request_id));
                """)
                connection.execute("BEGIN IMMEDIATE")
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
            finally:
                connection.close()

    def _read(self, connection, identifier):
        row = connection.execute("SELECT data FROM sessions WHERE id=?", (identifier,)).fetchone()
        if not row:
            raise KeyError(identifier)
        return json.loads(row["data"])

    def get(self, identifier):
        with self.connection() as connection:
            return self._read(connection, identifier)

    def list(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT data FROM sessions ORDER BY rowid DESC LIMIT 50").fetchall()
            return [
                {key: value[key] for key in ("id", "title", "status", "revision", "created_at", "updated_at")}
                for value in (json.loads(row["data"]) for row in rows)
            ]

    def events(self, identifier):
        with self.connection() as connection:
            self._read(connection, identifier)
            rows = connection.execute("SELECT * FROM events WHERE session_id=? ORDER BY seq", (identifier,)).fetchall()
            return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]

    def _write(self, connection, session, event, payload):
        session["revision"] += 1
        session["updated_at"] = now()
        connection.execute(
            "INSERT INTO sessions VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,data=excluded.data",
            (session["id"], session["revision"], json.dumps(session)),
        )
        connection.execute(
            "INSERT INTO events VALUES(?,?,?,?,?)", (session["id"], session["revision"], event, session["updated_at"], json.dumps(payload))
        )
        return copy.deepcopy(session)

    @staticmethod
    def validate_scope(scope):
        if not isinstance(scope, dict) or scope.get("region") not in ("unknown", "UK", "other"):
            raise ValueError("Choose a region")
        if scope.get("variant") not in ("unknown", "standard", "emergency", "other"):
            raise ValueError("Choose a process variant")
        when = scope.get("date", "")
        if not isinstance(when, str) or len(when) > 10:
            raise ValueError("Use an ISO date or leave it unknown")
        if when:
            when = date.fromisoformat(when).isoformat()
        return {"region": scope["region"], "variant": scope["variant"], "date": when}

    def create(self, evidence, scope, request_id):
        scope = self.validate_scope(scope)
        if not isinstance(request_id, str):
            raise ValueError("A session request identifier is required")
        identifier = str(uuid.UUID(request_id))
        with self.connection() as connection:
            row = connection.execute("SELECT data FROM sessions WHERE id=?", (identifier,)).fetchone()
            if row:
                existing = json.loads(row["data"])
                if existing["creation_hash"] != digest({"scope": scope, "evidence": evidence}):
                    raise Conflict("Session identifier was already used with different settings")
                return existing
            if connection.execute("SELECT count(*) FROM sessions").fetchone()[0] >= 50:
                raise ValueError("This prototype is limited to 50 saved sessions")
            session = {
                "id": identifier,
                "revision": 0,
                "title": "Supplier activation",
                "policy": POLICY,
                "mode": "synthetic_fixture",
                "status": "active",
                "created_at": now(),
                "updated_at": now(),
                "scope": scope,
                "evidence": evidence,
                "segments": [],
                "questions": [],
                "analysis": None,
                "plan_state": "idle",
                "review": None,
                "gaps": [],
                "voice": "B",
                "creation_hash": digest({"scope": scope, "evidence": evidence}),
            }
            return self._write(
                connection,
                session,
                "session_created",
                {
                    "scope": scope,
                    "evidence_hash": evidence["hash"],
                    "storage": "Explicit synthetic session: transcript revisions/events saved locally; raw audio transient.",
                },
            )

    def _invalidate(self, session):
        if session["analysis"]:
            session["analysis"]["valid"] = False
        session["plan_state"] = "idle"
        # Prior questions remain historical, but no stale question is spoken as current.
        session["current_question"] = None
        session["review"] = None

    def mutate(self, identifier, expected, request_id, event, payload):
        if not isinstance(payload, dict):
            raise ValueError("Invalid session action")
        if not isinstance(request_id, str) or not 8 <= len(request_id) <= 80:
            raise ValueError("A request identifier is required")
        fingerprint = digest({"event": event, "payload": payload})
        with self.connection() as connection:
            session = self._read(connection, identifier)
            prior = connection.execute(
                "SELECT input_hash FROM requests WHERE session_id=? AND request_id=?", (identifier, request_id)
            ).fetchone()
            if prior:
                if prior["input_hash"] != fingerprint:
                    raise Conflict("Request identifier already used for different content")
                return session
            if type(expected) is not int or session["revision"] != expected:
                raise Conflict("This session changed. Reload it before applying your edit.")
            if event == "segment_saved":
                if session["status"] != "active":
                    raise Conflict("Resume the session before saving another contribution")
                text, kind, state = payload.get("text"), payload.get("kind"), payload.get("state")
                if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
                    raise ValueError("Enter 1–2000 characters")
                if not isinstance(kind, str) or kind not in KINDS or state not in ("provisional", "confirmed"):
                    raise ValueError("Choose the contribution kind and confirmation state")
                source = payload.get("source", "typed")
                if source not in ("typed", "microphone"):
                    raise ValueError("Unknown capture source")
                audio_sequence = payload.get("audio_sequence")
                if audio_sequence is not None and (not isinstance(audio_sequence, str) or len(audio_sequence) > 80):
                    raise ValueError("Invalid audio sequence reference")
                segment_id = payload.get("segment_id") or uuid.uuid4().hex
                if not isinstance(segment_id, str) or not 1 <= len(segment_id) <= 80:
                    raise ValueError("Invalid segment identifier")
                previous = next((s for s in session["segments"] if s["id"] == segment_id), None)
                if previous and payload.get("segment_revision") != previous["revision"]:
                    raise Conflict("This transcript segment changed")
                if not previous and len(session["segments"]) >= 30:
                    raise ValueError("This trial is limited to 30 contributions; finish the draft or start another session")
                revision = previous["revision"] + 1 if previous else 1
                segment = {
                    "id": segment_id,
                    "revision": revision,
                    "text": text.strip(),
                    "kind": kind,
                    "state": state,
                    "source": source,
                    "audio_sequence": audio_sequence,
                    "confirmed_at": now() if state == "confirmed" else None,
                    "question_key": previous["question_key"] if previous else (session.get("current_question") or {}).get("key"),
                    "supersedes": previous["revision"] if previous else None,
                }
                if previous:
                    session["segments"][session["segments"].index(previous)] = segment
                else:
                    session["segments"].append(segment)
                payload = {"previous": previous, "segment": segment}
                self._invalidate(session)
            elif event == "scope_changed":
                if session["status"] != "active":
                    raise Conflict("Resume before changing the scope")
                session["scope"] = self.validate_scope(payload)
                self._invalidate(session)
            elif event == "resumed":
                if session["status"] not in ("paused", "finished"):
                    raise Conflict("Only a paused session or a finished draft can resume")
                payload = {"previous_status": session["status"], "superseded_packet": session["review"]}
                session["status"] = "active"
                self._invalidate(session)
            elif event == "plan_requested":
                if session["status"] != "active" or session["plan_state"] == "planning":
                    raise Conflict("A plan is already pending, or this session is paused")
                if any(s["state"] == "provisional" for s in session["segments"]):
                    raise Conflict("Confirm or correct provisional wording before asking the next question")
                if len(session["questions"]) >= 60:
                    raise ValueError("This trial is limited to 60 questions; finish the draft or start another session")
                session["plan_state"] = "planning"
            else:
                raise ValueError("Unknown session action")
            result = self._write(connection, session, event, payload)
            connection.execute("INSERT INTO requests VALUES(?,?,?)", (identifier, request_id, fingerprint))
            return result

    def pause(self, identifier, reason="operator_pause"):
        with self.connection() as connection:
            session = self._read(connection, identifier)
            if session["status"] != "active":
                return session
            session["status"] = "paused"
            session["plan_state"] = "idle"
            session["current_question"] = None
            if reason in ("disconnect", "server_restart"):
                session["gaps"].append(
                    {"at": now(), "reason": reason, "note": "Only acknowledged text is saved; unsent audio/text may be missing."}
                )
            return self._write(connection, session, "paused", {"reason": reason})

    def recover(self):
        for session in self.list():
            if session["status"] == "active":
                self.pause(session["id"], "server_restart")

    def apply_plan(self, identifier, expected, plan):
        with self.connection() as connection:
            session = self._read(connection, identifier)
            if session["revision"] != expected or session["status"] != "active" or session["plan_state"] != "planning":
                return False
            if plan["question"] not in QUESTIONS:
                raise ValueError("Unknown question")
            question = {
                "id": uuid.uuid4().hex,
                "key": plan["question"],
                "text": QUESTIONS[plan["question"]][1],
                "at": now(),
                "input_revision": expected,
                "mode": plan["mode"],
            }
            session["questions"].append(question)
            session["current_question"] = question
            session["analysis"] = {**plan, "valid": True, "input_revision": expected}
            session["plan_state"] = "ready"
            self._write(connection, session, "plan_completed", {"question": question, "analysis": session["analysis"]})
            return True

    def finish(self, identifier, expected, evidence_current):
        with self.connection() as connection:
            session = self._read(connection, identifier)
            if session["status"] == "finished":
                return session
            if type(expected) is not int or session["revision"] != expected:
                raise Conflict("Session changed; reload before finishing the draft")
            if any(s["state"] != "confirmed" for s in session["segments"]):
                raise Conflict("Confirm provisional wording before finishing")
            if not session["segments"]:
                raise ValueError("Capture at least one contribution before finishing")
            from .review import packet

            session["review"] = packet(session, evidence_current)
            session["status"] = "finished"
            session["plan_state"] = "idle"
            session["current_question"] = None
            return self._write(connection, session, "draft_finished", {"packet": session["review"]})
