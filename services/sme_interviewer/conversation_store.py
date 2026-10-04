"""Provisional conversation observations; only recap confirmation can create draft claims."""

import copy
import uuid

from .dialogue import question_text
from .ledger import KINDS, Conflict, now


class ConversationStore:
    def __init__(self, ledger):
        self.ledger = ledger

    def update(self, identifier, expected, event, change):
        with self.ledger.connection() as connection:
            session = self.ledger._read(connection, identifier)
            if session["revision"] != expected or session["status"] != "active":
                raise Conflict("The conversation changed. Reopen it before continuing.")
            payload = change(session)
            return self.ledger._write(connection, session, event, payload)

    def begin(self, session, voice=None):
        def change(s):
            if s["segments"] and not s.get("conversation"):
                raise Conflict("Use the original interview page for this saved session.")
            s["conversation"] = True
            if voice:
                s["conversation_voice"] = voice
            return {"mode": "continuous", "confirmation": "at_recap", "raw_audio": "transient"}

        return self.update(session["id"], session["revision"], "conversation_started", change)

    def observe(self, session, text, turn):
        def change(s):
            if not text.strip() or len(text) > 6000 or len(s.get("hearing_attempts", [])) >= 120:
                raise ValueError("Please review the recap before adding more audio.")
            attempt = {"id": turn, "text": text, "state": "unassessed", "question_id": (s.get("current_question") or {}).get("id")}
            s.setdefault("hearing_attempts", []).append(attempt)
            return {"attempt": attempt}

        return self.update(session["id"], session["revision"], "conversation_observed", change)

    def heard(self, session, text, kind, turn):
        def change(s):
            if not text.strip() or len(text) > 6000 or kind not in KINDS:
                raise ValueError("Invalid provisional transcript")
            if any(segment["id"] == turn for segment in s["segments"]):
                raise Conflict("This audio turn is already included.")
            if len(s["segments"]) >= 60:
                raise ValueError("Please review the recap before continuing this long session.")
            segment = {
                "id": turn,
                "revision": 1,
                "text": text,
                "kind": kind,
                "state": "provisional",
                "source": "microphone",
                "audio_sequence": turn,
                "confirmed_at": None,
                "question_id": (s.get("current_question") or {}).get("id"),
                "question_key": (s.get("current_question") or {}).get("key"),
                "supersedes": None,
            }
            s["segments"].append(segment)
            for attempt in s.get("hearing_attempts", []):
                if attempt["id"] == turn:
                    attempt["state"] = "included"
            self.ledger._invalidate(s)
            return {"segment": segment, "meaning": "Unconfirmed wording, not a factual claim"}

        return self.update(session["id"], session["revision"], "conversation_heard", change)

    def question(self, session, plan, context):
        def change(s):
            if len(s["questions"]) >= 120:
                raise ValueError("Please move to the recap.")
            q = {
                "id": uuid.uuid4().hex,
                "key": plan["question"],
                "text": question_text(plan, context),
                "detail": plan.get("detail"),
                "generation": plan.get("generation"),
                "at": now(),
                "input_revision": session["revision"],
                "mode": "unconfirmed_conversation",
            }
            s["questions"].append(q)
            s["current_question"] = q
            s["plan_state"] = "ready"
            # Analysis on unconfirmed hearing must never become ledger coverage or draft claims.
            s["analysis"] = None
            return {"question": q, "basis": "unconfirmed transcript, for interviewing only"}

        return self.update(session["id"], session["revision"], "conversation_question", change)

    def audit_question(self, session, question_id, review):
        def change(s):
            question = next(q for q in s["questions"] if q["id"] == question_id)
            question["semantic_review"] = review
            if (s.get("current_question") or {}).get("id") == question_id:
                s["current_question"]["semantic_review"] = review
            return {"question_id": question_id, "review": review, "meaning": "Question quality, not factual approval"}
        return self.update(session["id"], session["revision"], "conversation_question_reviewed", change)

    def confirm_recap(self, session, rows):
        def change(s):
            if not isinstance(rows, list) or not rows or len(rows) != len(s["segments"]):
                raise ValueError("Review the entire recap before confirming.")
            by_id = {r.get("id"): r for r in rows if isinstance(r, dict)}
            if len(by_id) != len(s["segments"]) or set(by_id) != {v["id"] for v in s["segments"]}:
                raise ValueError("Recap contributions do not match this revision.")
            before = copy.deepcopy(s["segments"])
            for segment in s["segments"]:
                row = by_id[segment["id"]]
                if row.get("revision") != segment["revision"]:
                    raise Conflict("A recap contribution changed.")
                text, kind = row.get("text"), row.get("kind")
                if not isinstance(text, str) or not 1 <= len(text.strip()) <= 6000 or kind not in KINDS:
                    raise ValueError("Check the wording and contribution kind in every recap row.")
                segment.update(
                    text=text.strip(),
                    kind=kind,
                    state="confirmed",
                    confirmed_at=now(),
                    supersedes=segment["revision"],
                    revision=segment["revision"] + 1,
                )
            self.ledger._invalidate(s)
            return {"previous": before, "segments": copy.deepcopy(s["segments"]), "confirmed_revision": session["revision"]}

        return self.update(session["id"], session["revision"], "conversation_recap_confirmed", change)


def hearing_context(session, text=None, kind="reported_practice", turn="preview"):
    """Ephemeral question-planning view. Never write this view or its coverage to storage."""
    result = copy.deepcopy(session)
    for segment in result["segments"]:
        segment["state"] = "confirmed"  # Existing question validator requires eligible source wording.
    if text:
        result["segments"].append(
            {
                "id": turn,
                "revision": 1,
                "text": text,
                "kind": kind,
                "state": "confirmed",
                "question_id": (session.get("current_question") or {}).get("id"),
            }
        )
    result["analysis"] = None
    result["plan_state"] = "idle"
    result["hearing_only"] = True
    return result
