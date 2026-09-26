"""Governed editing of any source: drafts, submission, approval and publishing, versions, comments, activity (CM E1).

Edits never change what answers, Tibi or search use until the Human approves them. A draft is kept here. Submitting
it asks for approval. Approving publishes it as the source's next version: the text is written, re-ingested and
approved through the audited ontology action. If ingestion fails, the previous text is restored.

A workspace can add hooks:
- ``prepare(source, text) -> (bytes, context)`` shapes what is written and may refuse; the sales workspace keeps a
  record's document in its canonical form;
- ``published(source, text, context) -> dict`` runs after publishing; the sales workspace updates the record;
- ``describe(source) -> dict`` adds details, such as the evidence a record cites;
- ``suggestions(source_id) -> list`` returns governance suggestions for the document;
- ``suggestion_notes() -> {source id: [line]}`` summarises open suggestions per document, one line each, for pages
  that list sources;
- ``decide(source, approve) -> None`` approves or rejects a document's published version; the sales workspace
  routes a record through its own review so the record is enabled or excluded consistently.
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ..governance.scope import PHASE_WORDS, PHASES
from ..ingestion.service import extract_text, ingest_source
from . import text as texts
from .store import ContentStore, now

EDITABLE = {".md", ".txt"}
IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 400_000


class ContentError(ValueError):
    """A request that conflicts with the document's current state (HTTP 409)."""


class NotFound(KeyError):
    """No such source, version or comment (HTTP 404)."""


@dataclass(frozen=True)
class Operator:
    name: str
    role: str

    @classmethod
    def from_env(cls) -> Operator:
        return cls(os.environ.get("KP_OPERATOR_NAME", "Operator").strip() or "Operator",
                   os.environ.get("KP_OPERATOR_ROLE", "Platform operator").strip() or "Platform operator")


def sha(text: str | bytes) -> str:
    return hashlib.sha256(text.encode() if isinstance(text, str) else text).hexdigest()


class ContentService:
    def __init__(self, register, section_store, actions=None, operator: Operator | None = None) -> None:
        self.register, self.section_store, self.actions = register, section_store, actions
        self.store = ContentStore(register.base_dir)
        self.operator = operator or Operator.from_env()
        self.hooks: dict = {"prepare": None, "published": None, "describe": None, "suggestions": None,
                            "suggestion_notes": None, "decide": None}

    # ---- reading ------------------------------------------------------------------------

    def _source(self, source_id: str):
        source = self.register.get(source_id)
        if source is None:
            raise NotFound("No such source")
        return source

    @staticmethod
    def editable(source) -> bool:
        return Path(source.filename).suffix.lower() in EDITABLE

    def published_text(self, source) -> str:
        content = self.register.read_content(source.id)
        return content.decode("utf-8", "replace") if self.editable(source) else extract_text(source.filename, content)

    def _ensure_history(self, source, text: str) -> None:
        """The first time a document is opened, its current text becomes its first version."""
        if not self.store.versions(source.id):
            self.store.add_version(source.id, text, sha(text), "imported", "OpsAtlas", "System",
                                   f"Version {source.version} as it was when content management started", source.version)

    def document(self, source_id: str) -> dict:
        source = self._source(source_id)
        published = self.published_text(source)
        self._ensure_history(source, published)
        state = self.store.document(source_id) or {"status": "published"}
        draft = None
        if state.get("draft_text") is not None:
            draft = {"text": state["draft_text"], "sha": state["draft_sha"], "base_sha": state["base_sha"],
                     "updated_at": state["draft_updated_at"], "author": state["draft_author"],
                     "stale": state["base_sha"] != sha(published), "stats": texts.stats(state["draft_text"])}
        comments = self.store.comments(source_id)
        activity = self.store.activity(source_id, limit=1)
        info = {k: getattr(source, k, None) for k in (
            "id", "title", "filename", "source_type", "sensitivity", "version", "processing_state", "approval_status",
            "section_count", "created_at", "content_sha256", "effective_from", "effective_to", "phases", "applies_to",
            "supersedes")}
        return {
            "source": {**info, "editable": self.editable(source), "format": Path(source.filename).suffix.lower().lstrip(".")},
            "published": {"text": published, "sha": sha(published), "stats": texts.stats(published)},
            "draft": draft,
            "status": state.get("status") or "published",
            "submitted": {"at": state["submitted_at"], "by": state["submitted_by"], "note": state["submitted_note"]}
            if state.get("status") == "submitted" else None,
            "comments": {"open": sum(1 for c in comments if c["status"] == "open"),
                         "resolved": sum(1 for c in comments if c["status"] == "resolved")},
            "versions": len(self.store.versions(source_id)),
            "last_activity": activity[0] if activity else None,
            "operator": {"name": self.operator.name, "role": self.operator.role},
            **(self.hooks["describe"](source) if self.hooks["describe"] else {}),
        }

    def summary(self) -> dict:
        """Documents with a draft or awaiting approval, for the pages that list sources."""
        return {row["source_id"]: row for row in self.store.documents()}

    def suggestion_notes(self) -> dict:
        """Open governance suggestions per document, one line each."""
        return self.hooks["suggestion_notes"]() if self.hooks["suggestion_notes"] else {}

    def decide(self, source_id: str, expected_sha: str, approve: bool) -> dict:
        """Approve or reject the published version the Human has just read, without editing it."""
        source = self._source(source_id)
        if sha(self.published_text(source)) != expected_sha:
            raise ContentError("The document changed since you opened it; reload it and review it again")
        state = "approved" if approve else "rejected"
        if source.approval_status == state:
            raise ContentError(f"The document is already {state}")
        if self.hooks["decide"]:
            self.hooks["decide"](source, approve)
        elif approve:
            self._approve(source_id)
        else:
            self._reject(source_id)
        self.store.log(source_id, self.operator.name, "approved" if approve else "rejected",
                       f"Version {source.version}" + ("" if approve else ": not used for answers"))
        return self.document(source_id)

    # ---- drafts and workflow ------------------------------------------------------------------

    def save_draft(self, source_id: str, text: str, base_sha: str | None = None) -> dict:
        source = self._source(source_id)
        if not self.editable(source):
            raise ContentError(f"{Path(source.filename).suffix.upper().lstrip('.')} documents are read-only here; "
                               "replace the file on Knowledge Sources to change one")
        if len(text) > MAX_TEXT_CHARS:
            raise ContentError("The document is too long to save")
        published = self.published_text(source)
        current = sha(published)
        state = self.store.document(source_id) or {}
        base = state.get("base_sha") or base_sha or current
        if text == published:
            # Back to the published text: no draft remains.
            if state.get("draft_text") is not None:
                self.store.clear_draft(source_id)
                self.store.log(source_id, self.operator.name, "draft discarded", "The draft matched the published text again")
            return self.document(source_id)
        status = "draft"
        if state.get("status") == "submitted" and state.get("draft_text") != text:
            self.store.log(source_id, self.operator.name, "returned to draft", "Edited after submission")
        elif state.get("status") == "submitted":
            status = "submitted"
        self.store.save_document(source_id, status=status, draft_text=text, draft_sha=sha(text), base_sha=base,
                                 draft_updated_at=now(), draft_author=self.operator.name,
                                 **({} if status == "submitted" else {"submitted_at": None, "submitted_by": None, "submitted_note": None}))
        self.store.log(source_id, self.operator.name, "edited", "Draft saved", coalesce=True)
        return self.document(source_id)

    def discard_draft(self, source_id: str) -> dict:
        self._source(source_id)
        state = self.store.document(source_id) or {}
        if state.get("draft_text") is None:
            raise ContentError("There is no draft to discard")
        self.store.clear_draft(source_id)
        self.store.log(source_id, self.operator.name, "draft discarded")
        return self.document(source_id)

    def submit(self, source_id: str, note: str = "") -> dict:
        self._source(source_id)
        state = self.store.document(source_id) or {}
        if state.get("draft_text") is None:
            raise ContentError("Edit the document before submitting it")
        if state.get("status") == "submitted":
            raise ContentError("The draft is already waiting for approval")
        self.store.save_document(source_id, status="submitted", submitted_at=now(), submitted_by=self.operator.name,
                                 submitted_note=note.strip()[:1000] or None)
        self.store.log(source_id, self.operator.name, "submitted for approval", note.strip()[:300])
        return self.document(source_id)

    def return_to_draft(self, source_id: str, note: str = "") -> dict:
        self._source(source_id)
        state = self.store.document(source_id) or {}
        if state.get("status") != "submitted":
            raise ContentError("Only a submitted draft can be returned")
        self.store.save_document(source_id, status="draft", submitted_at=None, submitted_by=None, submitted_note=None)
        self.store.log(source_id, self.operator.name, "returned to draft", note.strip()[:300])
        return self.document(source_id)

    def publish(self, source_id: str, draft_sha: str, note: str = "") -> dict:
        """The Human's approval: the submitted draft becomes the source's next version."""
        with self.store.lock:
            source = self._source(source_id)
            state = self.store.document(source_id) or {}
            if state.get("status") != "submitted" or state.get("draft_text") is None:
                raise ContentError("Submit the draft for approval first")
            text = state["draft_text"]
            if sha(text) != draft_sha:
                raise ContentError("The draft changed since you reviewed it; review it again")
            published = self.published_text(source)
            if state.get("base_sha") and state["base_sha"] != sha(published):
                raise ContentError("The published document changed after this draft was started; compare the versions "
                                   "and restore before approving")
            if not text.strip():
                raise ContentError("An empty document cannot be published")
            self._ensure_history(source, published)
            content, context = (self.hooks["prepare"](source, text) if self.hooks["prepare"]
                                else ((text if text.endswith("\n") else text + "\n").encode(), None))
            before = {"content": self.register.read_content(source_id),
                      "fields": {k: getattr(source, k) for k in ("size_bytes", "content_sha256", "version", "approval_status",
                                                                 "processing_state", "section_count")}}
            self.register.write_content(source_id, content)
            self.register.update(source_id, size_bytes=len(content), content_sha256=sha(content), version=source.version + 1,
                                 approval_status="pending")
            try:
                ingest_source(self.register, self.section_store, source_id)
                self._approve(source_id)
            except Exception as exc:
                self._restore(source_id, before)
                raise ContentError(f"The new version could not be published, so the previous one stays live: {exc}") from exc
            updated = self.register.get(source_id)
            written = content.decode("utf-8", "replace")
            n = self.store.add_version(source_id, written, sha(written), "approved", self.operator.name, self.operator.role,
                                       note.strip()[:1000] or state.get("submitted_note"), updated.version)
            extra = self.hooks["published"](updated, written, context) if self.hooks["published"] else {}
            self.store.clear_draft(source_id)
            self.store.log(source_id, self.operator.name, "approved and published",
                           f"Version {updated.version}" + (f": {note.strip()[:300]}" if note.strip() else ""))
            return {"document": self.document(source_id), "version": n, "source_version": updated.version, **(extra or {})}

    def _approve(self, source_id: str) -> None:
        if self.actions is None:
            self.register.update(source_id, approval_status="approved")
            return
        from ..ontology.actions import ActionActor
        result = self.actions.execute("approve_source", {"source_id": source_id},
                                      ActionActor(type="operator", id=self.operator.name))
        if result.outcome != "ok":
            raise ContentError(result.message or "The approval action failed")

    def _reject(self, source_id: str) -> None:
        if self.actions is None:
            self.register.update(source_id, approval_status="rejected")
            return
        from ..ontology.actions import ActionActor
        result = self.actions.execute("reject_source", {"source_id": source_id}, ActionActor(type="operator", id=self.operator.name))
        if result.outcome != "ok":
            raise ContentError(result.message or "The rejection action failed")

    def _restore(self, source_id: str, before: dict) -> None:
        self.register.write_content(source_id, before["content"])
        self.register.update(source_id, **before["fields"])
        try:
            ingest_source(self.register, self.section_store, source_id)
        except Exception:  # the previous content was ingestible before; keep its recorded state regardless
            self.register.update(source_id, **before["fields"])

    # ---- versions ----------------------------------------------------------------------------

    def versions(self, source_id: str) -> list[dict]:
        source = self._source(source_id)
        self._ensure_history(source, self.published_text(source))
        rows = self.store.versions(source_id)
        current = sha(self.published_text(source))
        live = next((r for r in rows if r["sha"] == current), None)  # the newest version with the live text
        for row in rows:
            row["current"] = row is live
        return rows

    def version(self, source_id: str, n: int) -> dict:
        self._source(source_id)
        row = self.store.version(source_id, n)
        if row is None:
            raise NotFound("No such version")
        return {**row, "stats": texts.stats(row["text"])}

    def restore(self, source_id: str, n: int) -> dict:
        row = self.version(source_id, n)
        result = self.save_draft(source_id, row["text"])
        self.store.log(source_id, self.operator.name, "restored to draft", f"Version {n}")
        return result

    def _text_of(self, source_id: str, which: str) -> str:
        if which == "published":
            return self.published_text(self._source(source_id))
        if which == "draft":
            state = self.store.document(source_id) or {}
            if state.get("draft_text") is None:
                raise NotFound("There is no draft")
            return state["draft_text"]
        try:
            return self.version(source_id, int(which))["text"]
        except ValueError as exc:
            raise NotFound("Compare 'published', 'draft' or a version number") from exc

    def diff(self, source_id: str, base: str, target: str) -> dict:
        return texts.diff(self._text_of(source_id, base), self._text_of(source_id, target))

    # ---- comments ----------------------------------------------------------------------------

    def comments(self, source_id: str) -> list[dict]:
        source = self._source(source_id)
        state = self.store.document(source_id) or {}
        current = texts.plain(state["draft_text"] if state.get("draft_text") is not None else self.published_text(source))
        rows = self.store.comments(source_id)
        for row in rows:
            row["anchored"] = texts.find_anchor(current, row["quote"], row["prefix"], row["suffix"]) is not None
        return rows

    def add_comment(self, source_id: str, quote: str, text: str, prefix: str = "", suffix: str = "") -> dict:
        self._source(source_id)
        quote, text = " ".join(quote.split()), text.strip()
        if not quote:
            raise ContentError("Select the text the comment is about")
        if not text:
            raise ContentError("Write the comment first")
        comment_id = self.store.add_comment(source_id, quote[:2000], prefix[-200:], suffix[:200], text[:4000],
                                            self.operator.name, self.operator.role)
        self.store.log(source_id, self.operator.name, "commented", _clip(text))
        return self._comment(source_id, comment_id)

    def _comment(self, source_id: str, comment_id: str) -> dict:
        return next(c for c in self.comments(source_id) if c["id"] == comment_id)

    def _require_comment(self, comment_id: str) -> dict:
        row = self.store.comment(comment_id)
        if row is None:
            raise NotFound("No such comment")
        return row

    def reply(self, comment_id: str, text: str) -> dict:
        row = self._require_comment(comment_id)
        if not text.strip():
            raise ContentError("Write the reply first")
        self.store.add_reply(comment_id, text.strip()[:4000], self.operator.name, self.operator.role)
        self.store.log(row["source_id"], self.operator.name, "replied", _clip(text))
        return self._comment(row["source_id"], comment_id)

    def set_comment_status(self, comment_id: str, resolved: bool) -> dict:
        row = self._require_comment(comment_id)
        self.store.set_comment_status(comment_id, "resolved" if resolved else "open", self.operator.name)
        self.store.log(row["source_id"], self.operator.name, "resolved a comment" if resolved else "reopened a comment",
                       _clip(row["text"]))
        return self._comment(row["source_id"], comment_id)

    def delete_comment(self, comment_id: str) -> None:
        row = self._require_comment(comment_id)
        self.store.delete_comment(comment_id)
        self.store.log(row["source_id"], self.operator.name, "deleted a comment", _clip(row["text"]))

    # ---- details, activity, suggestions, images -----------------------------------------------

    def update_details(self, source_id: str, fields: dict) -> dict:
        source = self._source(source_id)
        described = self.hooks["describe"](source) if self.hooks["describe"] else {}
        changes: dict = {}
        if "title" in fields:
            title = " ".join(str(fields["title"] or "").split())
            if described.get("title_from_heading"):
                raise ContentError("This document's title is its first heading; edit the heading instead")
            if not title:
                raise ContentError("A document needs a title")
            changes["title"] = title[:300]
        for key in ("effective_from", "effective_to"):
            if key in fields:
                value = fields[key] or None
                if value is not None:
                    try:
                        date.fromisoformat(value)
                    except ValueError as exc:
                        raise ContentError(f"{key.replace('_', ' ').capitalize()} must be a date (YYYY-MM-DD)") from exc
                changes[key] = value
        if changes.get("effective_from") and changes.get("effective_to") and changes["effective_to"] < changes["effective_from"]:
            raise ContentError("The document cannot end before it starts")
        if "phases" in fields:
            phases = [p for p in (fields["phases"] or []) if p]
            unknown = [p for p in phases if p not in PHASES]
            if unknown:
                raise ContentError(f"Unknown phase: {', '.join(unknown)}")
            changes["phases"] = phases
        if "applies_to" in fields:
            changes["applies_to"] = [" ".join(str(a).split()) for a in (fields["applies_to"] or []) if str(a).strip()][:10]
        if not changes:
            raise ContentError("Nothing to change")
        self.register.update(source_id, **changes)
        words = lambda v: ", ".join(PHASE_WORDS.get(x, x) for x in v) if isinstance(v, list) else v  # noqa: E731
        self.store.log(source_id, self.operator.name, "changed details",
                       "; ".join(f"{k.replace('_', ' ')}: {words(v) if v not in (None, []) else 'none'}" for k, v in changes.items()))
        return self.document(source_id)

    def activity(self, source_id: str) -> list[dict]:
        self._source(source_id)
        return self.store.activity(source_id)

    def suggestions(self, source_id: str) -> list[dict]:
        self._source(source_id)
        return self.hooks["suggestions"](source_id) if self.hooks["suggestions"] else []

    def save_image(self, data: bytes, content_type: str) -> dict:
        extension = IMAGE_TYPES.get((content_type or "").split(";")[0].strip().lower())
        if extension is None:
            raise ContentError("Use a PNG, JPEG, GIF or WebP image")
        if not data or len(data) > MAX_IMAGE_BYTES:
            raise ContentError("Images must be under 5 MB")
        name = sha(data)[:32] + extension
        self.store.assets.mkdir(parents=True, exist_ok=True)
        path = self.store.assets / name
        if not path.exists():
            path.write_bytes(data)
        return {"name": name, "url": f"/api/content/assets/{name}"}

    def image(self, name: str) -> tuple[Path, str]:
        path = (self.store.assets / name).resolve()
        if not path.is_relative_to(self.store.assets.resolve()) or not path.is_file():
            raise NotFound("No such image")
        return path, mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def _clip(text: str, limit: int = 140) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
