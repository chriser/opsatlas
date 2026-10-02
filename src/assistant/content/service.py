"""Governed editing of any source: drafts, submission, approval and publishing, versions, comments, activity (CM E1).

Edits never change what answers, Tibi or search use until the Human approves them. A draft is kept here. Submitting
it asks for approval. Approving publishes it as the source's next version: the text is written, re-ingested and
approved through the audited ontology action. If ingestion fails, the previous text is restored. No other route
changes a published text: the declared ``save_document`` action submits a draft here (REF S1).

A workspace can add hooks:
- ``prepare(source, text) -> (bytes, context)`` shapes what is written and may refuse; the sales workspace keeps a
  record's document in its canonical form;
- ``published(source, text, context) -> dict`` runs after publishing; the sales workspace updates the record;
- ``describe(source) -> dict`` adds details, such as the evidence a record cites;
- ``all_suggestions() -> {source id: [suggestion]}`` returns the open governance suggestions for every document
  (``suggestions(source_id)`` does it for one, without the record kept below). Each has a key that stays the same
  while the issue stays open, and an optional one-line ``note`` for pages that list sources;
- ``keep(source, suggestion, note)`` and ``unkeep(source, suggestion)`` stop and restart the workspace raising a
  suggestion the Human accepted as it is;
- ``settled_how(source, suggestion) -> {"actor", "role", "note"} | None`` explains a suggestion that went away
  without an edit to its document, for example an answer approved through Tibi;
- ``history(source, versions) -> [(suggestion, version)]`` names the suggestions earlier edits corrected, once, when
  the record of suggestions starts;
- ``decide(source, approve) -> None`` approves or rejects a document's published version; the sales workspace
  routes a record through its own review so the record is enabled or excluded consistently;
- ``retitle(source, title) -> str | None`` gives the document text a new title needs (a record's title is its first
  heading), or None when the title is only a label;
- ``default_library() -> {"groups": [(key, title, parent key)], "place": source -> key}`` groups a workspace's
  documents the first time the library is opened, and places documents added later.
"""

from __future__ import annotations

import hashlib
import mimetypes
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .. import settings
from ..governance.scope import PHASE_WORDS, PHASES
from ..iam.context import current_principal
from ..ingestion.service import extract_text, ingest_source
from . import text as texts
from .store import ContentStore, now

EDITABLE = {".md", ".txt"}
ASSET_REF = re.compile(r"/api/content/assets/([A-Za-z0-9._-]+)")
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
        return cls(settings.get("KP_OPERATOR_NAME").strip() or "Operator",
                   settings.get("KP_OPERATOR_ROLE").strip() or "Platform operator")


def sha(text: str | bytes) -> str:
    return hashlib.sha256(text.encode() if isinstance(text, str) else text).hexdigest()


class ContentService:
    def __init__(self, register, section_store, actions=None, operator: Operator | None = None, events=None) -> None:
        self.register, self.section_store, self.actions, self.events = register, section_store, actions, events
        self.store = ContentStore(register.base_dir)
        self._operator = operator or Operator.from_env()
        # Whether a person may publish a draft they wrote, in this space (REF S15). None: anyone may (a lone core, a
        # test). The app sets it: solo-operator mode on and the person holds governance.self_approve.
        self.self_approval = None
        if actions is not None:
            actions.register_handler("save_document", self._save_document_action)
        self.hooks: dict = {"prepare": None, "published": None, "describe": None, "suggestions": None,
                            "suggestion_notes": None, "decide": None, "retitle": None, "default_library": None,
                            "all_suggestions": None, "keep": None, "unkeep": None, "settled_how": None, "history": None}

    # ---- reading ------------------------------------------------------------------------

    @property
    def operator(self) -> Operator:
        """Who is acting: the signed-in person of this request (IAM F5), or the configured operator when no request
        is in flight (a start-up rebuild, a test)."""
        principal = current_principal()
        return Operator(principal.display_name, principal.role_label) if principal else self._operator

    @operator.setter
    def operator(self, value: Operator) -> None:
        self._operator = value

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
        return self.suggestion_overview()["notes"]

    # ---- governance suggestions: open, and settled (CM S21, CM S29) ------------------------------
    #
    # A suggestion is open while the governance checks raise it. When it goes away it is settled, and the document
    # keeps the record: "corrected" when an edit to the document removed it, "accepted" when the Human kept the
    # wording as it is, and "resolved" when it went away another way (an answer approved through Tibi, or a change
    # to the other document of a conflict).

    def _open_suggestions(self) -> dict:
        if not self.hooks["all_suggestions"]:
            return {}
        with self.store.lock:
            # A workspace's suggestions may cover documents kept in other spaces (KS S3): this service speaks, and keeps
            # suggestion history, only for the documents in its own register.
            current = {sid: items for sid, items in self.hooks["all_suggestions"]().items() if self.register.get(sid) is not None}
            self._reconcile(current)
        return current

    def _reconcile(self, current: dict) -> None:
        if self.store.meta("suggestions_tracked") is None:
            self._backfill()
            self.store.set_meta("suggestions_tracked", now())
        seen = self.store.seen()
        for (source_id, key), row in seen.items():
            if any(s["key"] == key for s in current.get(source_id, [])):
                continue
            self.store.unsee(source_id, key)
            source = self.register.get(source_id)
            if source is not None:
                self._settle_gone(source, row)
        for source_id, items in current.items():
            source = self.register.get(source_id)
            for suggestion in items:
                if source is not None and (source_id, suggestion["key"]) not in seen:
                    self.store.see(source_id, suggestion, source.content_sha256)

    def _settle_gone(self, source, row: dict) -> None:
        suggestion = row["data"]
        edits = [v for v in self.store.versions(source.id) if v["label"] != "imported" and v["at"] >= row["first_seen_at"]]
        if edits and row["content_sha"] != source.content_sha256:
            edit = min(edits, key=lambda v: v["n"])  # the first version published after the suggestion was raised
            self.store.settle(source.id, suggestion, "corrected", edit["source_version"], edit["author"], edit["role"], at=edit["at"])
            self.store.log(source.id, edit["author"], "corrected a suggestion", _clip(suggestion["text"]))
            return
        how = (self.hooks["settled_how"](source, suggestion) if self.hooks["settled_how"] else None) or {}
        self.store.settle(source.id, suggestion, "resolved", source.version, how.get("actor") or "OpsAtlas",
                          how.get("role") or "System", how.get("note") or "No longer raised by the governance checks")

    def _backfill(self) -> None:
        """Edits published before suggestions were recorded are credited with the suggestions they corrected."""
        if not self.hooks["history"]:
            return
        for source in self.register.list():
            entries = sorted(self.store.versions(source.id), key=lambda v: v["n"])
            if len(entries) < 2:
                continue
            versions = [self.store.version(source.id, v["n"]) for v in entries]
            for suggestion, v in self.hooks["history"](source, versions):
                self.store.settle(source.id, suggestion, "corrected", v["source_version"], v["author"], v["role"], at=v["at"])

    def suggestion_overview(self) -> dict:
        """Per document: open suggestions, one line each (answered ones wait for the Human in Governance), and a
        count and a line for each settled one."""
        notes = {}
        for source_id, items in self._open_suggestions().items():
            lines = [s.get("note") or s["text"] for s in items if not s.get("answer")]
            if lines:
                notes[source_id] = lines
        if not self.hooks["all_suggestions"] and self.hooks["suggestion_notes"]:
            notes = self.hooks["suggestion_notes"]()
        settled: dict = {}
        for row in self.store.settled():
            entry = settled.setdefault(row["source_id"], {"corrected": 0, "accepted": 0, "resolved": 0, "notes": []})
            entry[row["outcome"]] += 1
            entry["notes"].append(f"{_outcome_words(row)}: {row['data'].get('note') or row['data']['text']}")
        return {"notes": notes, "settled": settled}

    def suggestion_state(self, source_id: str) -> dict:
        return {"suggestions": self.suggestions(source_id), "settled": [
            {"id": r["id"], "key": r["key"], "outcome": r["outcome"], "label": r["data"].get("label"), "text": r["data"]["text"],
             "quote": r["data"].get("quote"), "version": r["version"], "actor": r["actor"], "role": r["role"], "at": r["at"],
             "note": r["note"], "words": _outcome_words(r)} for r in self.store.settled(source_id)]}

    def accept_suggestion(self, source_id: str, key: str, note: str = "") -> dict:
        """The Human keeps the wording as it is. The suggestion stops being raised for this document, Tibi included."""
        with self.store.lock:
            source = self._source(source_id)
            suggestion = next((s for s in self._open_suggestions().get(source_id, []) if s["key"] == key), None)
            if suggestion is None:
                raise NotFound("That suggestion is no longer open")
            if suggestion.get("other"):
                raise ContentError("A conflict or duplicate involves another record; settle it with Tibi or edit the passage")
            if not self.hooks["keep"]:
                raise ContentError("This workspace cannot keep a suggestion as it is")
            note = " ".join(str(note or "").split())[:500]
            self.hooks["keep"](source, suggestion, note)
            self.store.unsee(source_id, key)
            self.store.settle(source_id, suggestion, "accepted", source.version, self.operator.name, self.operator.role, note or None)
            self.store.log(source_id, self.operator.name, "accepted a suggestion as it is",
                           _clip(suggestion["text"] + (f" Reason: {note}" if note else "")))
        return self.suggestion_state(source_id)

    def reopen_suggestion(self, source_id: str, settled_id: str) -> dict:
        """Undo "accept as it is": the suggestion is raised again."""
        with self.store.lock:
            source = self._source(source_id)
            row = self.store.settled_row(settled_id)
            if row is None or row["source_id"] != source_id:
                raise NotFound("No such suggestion")
            if row["outcome"] != "accepted":
                raise ContentError("Only a suggestion accepted as it is can be reopened")
            if self.hooks["unkeep"]:
                self.hooks["unkeep"](source, row["data"])
            self.store.unsettle(settled_id)
            self.store.log(source_id, self.operator.name, "reopened a suggestion", _clip(row["data"]["text"]))
        return self.suggestion_state(source_id)

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
        principal = current_principal()
        self.store.save_document(source_id, status=status, draft_text=text, draft_sha=sha(text), base_sha=base,
                                 draft_updated_at=now(), draft_author=self.operator.name,
                                 draft_author_id=principal.id if principal else None,
                                 **({} if status == "submitted" else {"submitted_at": None, "submitted_by": None, "submitted_note": None}))
        self.store.log(source_id, self.operator.name, "edited", "Draft saved", coalesce=True)
        return self.document(source_id)

    def _save_document_action(self, context) -> dict:
        """The declared ``save_document`` action: the text becomes a draft submitted for approval. The published text,
        and so every answer, stays as it is until a person publishes the draft."""
        source_id, text = str(context.params["source_id"]), str(context.params["text"])
        with self.store.lock:
            if text == self.published_text(self._source(source_id)):
                raise ContentError("The text is the same as the published version")
            self.save_draft(source_id, text)
            if (self.store.document(source_id) or {}).get("status") != "submitted":
                self.submit(source_id, "Submitted through the save_document action")
            return {"response": self.document(source_id)}

    def forget(self, source_id: str, last_text: bytes = b"") -> dict:
        """A deleted source leaves nothing here (REF S4): its history goes, and so do the images it used that no other
        document's text or kept version uses."""
        with self.store.lock:
            texts_before = [last_text.decode("utf-8", "replace"), *self.store.version_texts(source_id)]
            draft = (self.store.document(source_id) or {}).get("draft_text")
            if draft:
                texts_before.append(draft)
            removed = self.store.forget_document(source_id)
            in_use = set()
            for other in self.register.list():
                try:
                    in_use |= set(ASSET_REF.findall(self.register.read_content(other.id).decode("utf-8", "replace")))
                except OSError:
                    continue
            for text in self.store.version_texts():
                in_use |= set(ASSET_REF.findall(text))
            images = 0
            for name in {n for text in texts_before for n in ASSET_REF.findall(text)} - in_use:
                path = self.store.assets / name
                if path.is_file():
                    path.unlink()
                    images += 1
            return {"rows": removed, "images": images}

    def _record_edited(self, source, text: str) -> None:
        if self.events is None:
            return
        self.events.record("source_edited", actor_type="operator", entity_type="source", entity_id=source.id,
                           source_id=source.id, metadata={"title": source.title, "section_count": source.section_count,
                                                          "size_bytes": len(text.encode("utf-8")),
                                                          "processing_state": source.processing_state,
                                                          "approval_status": source.approval_status})

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
            own = self._own_draft(state)
            self._ensure_history(source, published)
            content, context = (self.hooks["prepare"](source, text) if self.hooks["prepare"]
                                else ((text if text.endswith("\n") else text + "\n").encode(), None))
            updated = self._write_version(source, content, approve=True)
            written = content.decode("utf-8", "replace")
            n = self.store.add_version(source_id, written, sha(written), "approved", self.operator.name, self.operator.role,
                                       note.strip()[:1000] or state.get("submitted_note"), updated.version)
            extra = self.hooks["published"](updated, written, context, True) if self.hooks["published"] else {}
            self._record_edited(updated, written)
            self.store.clear_draft(source_id)
            self.store.log(source_id, self.operator.name, "approved and published",
                           f"Version {updated.version}" + (f": {note.strip()[:300]}" if note.strip() else "")
                           + ("; approved by its author under solo-operator mode" if own else ""))
            return {"document": self.document(source_id), "version": n, "source_version": updated.version,
                    "self_approved": own, **(extra or {})}

    def _own_draft(self, state: dict) -> bool:
        """True when the person publishing wrote the draft. Allowed only where self_approval says so (solo-operator
        mode and governance.self_approve); refused otherwise (REF S15)."""
        principal = current_principal()
        author = state.get("draft_author_id")
        if not principal or not author or author != principal.id:
            return False
        if self.self_approval is not None and not self.self_approval(principal.id):
            raise ContentError("You wrote this draft, so another approver must publish it. An administrator can turn on "
                               "solo-operator mode for this space on the Security & audit page.")
        return True

    def _write_version(self, source, content: bytes, approve: bool):
        """Write the source's next version and re-ingest it; with ``approve``, approve it through the audited action.
        Otherwise its approval stays as it was. If anything fails, the previous version is restored."""
        source_id = source.id
        before = {"content": self.register.read_content(source_id),
                  "fields": {k: getattr(source, k) for k in ("size_bytes", "content_sha256", "version", "approval_status",
                                                             "processing_state", "section_count")}}
        self.register.write_content(source_id, content)
        self.register.update(source_id, size_bytes=len(content), content_sha256=sha(content), version=source.version + 1,
                             approval_status="pending" if approve else source.approval_status)
        try:
            ingest_source(self.register, self.section_store, source_id)
            if approve:
                self._approve(source_id)
        except Exception as exc:
            self._restore(source_id, before)
            raise ContentError(f"The new version could not be published, so the previous one stays live: {exc}") from exc
        return self.register.get(source_id)

    def rename(self, source_id: str, title: str) -> dict:
        """A new title. Where the title is part of the document (a record's heading), this writes a new version and
        keeps the approval as it was: an approved record is re-approved, a pending one stays pending."""
        with self.store.lock:
            source = self._source(source_id)
            title = " ".join(str(title or "").split())[:300]
            if not title:
                raise ContentError("A document needs a title")
            if title == source.title:
                raise ContentError("That is already its title")
            old = source.title
            text = self.hooks["retitle"](source, title) if self.hooks["retitle"] else None
            if text is None:
                self.register.update(source_id, title=title)
                self.store.log(source_id, self.operator.name, "renamed", f"From “{old}” to “{title}”")
                return self.document(source_id)
            if (self.store.document(source_id) or {}).get("draft_text") is not None:
                raise ContentError("This document has a draft; rename it in the draft, or discard the draft first")
            self._ensure_history(source, self.published_text(source))
            content, context = (self.hooks["prepare"](source, text) if self.hooks["prepare"]
                                else ((text if text.endswith("\n") else text + "\n").encode(), None))
            approved = source.approval_status == "approved"
            updated = self._write_version(source, content, approve=approved)
            self.register.update(source_id, title=title)
            written = content.decode("utf-8", "replace")
            self.store.add_version(source_id, written, sha(written), "renamed", self.operator.name, self.operator.role,
                                   f"Renamed from “{old}” to “{title}”", updated.version)
            if self.hooks["published"]:
                self.hooks["published"](self.register.get(source_id), written, context, approved)
            self.store.log(source_id, self.operator.name, "renamed", f"From “{old}” to “{title}”; version {updated.version}")
            return self.document(source_id)

    # ---- the library: groups and where each document sits (CM S27) ----------------------------------

    def library(self) -> dict:
        self._seed_library()
        placements = self.store.placements()
        default = self.hooks["default_library"]() if self.hooks["default_library"] else None
        keys = _json(self.store.meta("library_keys")) or {}
        groups = {g["id"] for g in self.store.groups()}
        unplaced = [s for s in self.register.list() if s.id not in placements]
        if unplaced and default:
            known = {s.id for s in self.register.list()}
            for source in sorted(unplaced, key=default.get("rank") or (lambda s: s.title)):
                key = default["place"](source)
                if key.startswith("source:"):
                    parent = key if key.partition(":")[2] in known and key != f"source:{source.id}" else None
                else:
                    parent = f"group:{keys[key]}" if key in keys and keys[key] in groups else None
                self.store.place(source.id, parent)
        return {"groups": self.store.groups(), "placements": self.store.placements()}

    def _seed_library(self) -> None:
        """The first time, a workspace's own grouping is created; the Human reshapes it from then on."""
        if not self.hooks["default_library"] or self.store.meta("library_keys") is not None:
            return
        with self.store.lock:
            if self.store.meta("library_keys") is not None:
                return
            keys: dict = {}
            for key, title, parent in self.hooks["default_library"]()["groups"]:
                keys[key] = self.store.add_group(title, f"group:{keys[parent]}" if parent in keys else None)
            self.store.set_meta("library_keys", _dumps(keys))

    def _parent_of(self, node: str) -> str | None:
        kind, _, key = node.partition(":")
        if kind == "group":
            return next((g["parent"] for g in self.store.groups() if g["id"] == key), None)
        return (self.store.placements().get(key) or {}).get("parent")

    def _check_parent(self, node: str, parent: str | None) -> None:
        if parent is None:
            return
        kind, _, key = parent.partition(":")
        if kind == "group" and not any(g["id"] == key for g in self.store.groups()):
            raise ContentError("That group no longer exists")
        if kind == "source" and self.register.get(key) is None:
            raise ContentError("That document no longer exists")
        if kind not in ("group", "source"):
            raise ContentError("Choose a group or a document")
        seen, at = set(), parent
        while at is not None and at not in seen:
            if at == node:
                raise ContentError("Something cannot sit inside itself or inside what it contains")
            seen.add(at)
            at = self._parent_of(at)

    def set_parent(self, source_id: str, parent: str | None) -> dict:
        source = self._source(source_id)
        parent = parent or None
        self._check_parent(f"source:{source_id}", parent)
        self.store.place(source_id, parent)
        self.store.log(source_id, self.operator.name, "moved", f"Now in {self._describe_node(parent)}")
        return self.library() | {"source": source.id}

    def move(self, node: str, parent: str | None, before: str | None = None) -> dict:
        """Drag and drop (CM S30): put a document or a group under ``parent`` just before its sibling ``before``, or
        last when there is none, and number its new siblings in the order they are shown."""
        kind, _, key = str(node or "").partition(":")
        if kind == "source":
            self._source(key)
        elif kind != "group" or not any(g["id"] == key for g in self.store.groups()):
            raise NotFound("No such document or group")
        parent = parent or None
        self._check_parent(node, parent)
        previous = self._parent_of(node)
        current = self._children(parent)
        if before == node and node in current:  # dropped where it already is
            before = current[current.index(node) + 1] if current[-1] != node else None
        siblings = [k for k in current if k != node]
        if before is not None and before != node and before not in siblings:
            raise ContentError("The library changed while you were dragging; refresh and try again")
        at = siblings.index(before) if before in siblings else len(siblings)
        self.store.arrange(parent, [*siblings[:at], node, *siblings[at:]])
        if kind == "source" and previous != parent:
            self.store.log(key, self.operator.name, "moved", f"Now in {self._describe_node(parent)}")
        return self.library() | {"moved": node}

    def _children(self, parent: str | None) -> list[str]:
        """What sits directly under ``parent``, in the order the library shows it (position, then title). At the top
        level that includes anything whose parent no longer exists, as the library shows those there."""
        library = self.library()
        titles = {s.id: s.title for s in self.register.list()}
        nodes = {f"group:{g['id']}": (g["parent"], g["position"], g["title"]) for g in library["groups"]}
        nodes |= {f"source:{sid}": (at["parent"], at["position"], titles.get(sid, "")) for sid, at in library["placements"].items()
                  if sid in titles}
        shown = lambda p: p if p in nodes else None  # noqa: E731
        return sorted((k for k, (p, _, _) in nodes.items() if shown(p) == parent), key=lambda k: (nodes[k][1], nodes[k][2]))

    def create_group(self, title: str, parent: str | None = None) -> dict:
        title = " ".join(str(title or "").split())[:120]
        if not title:
            raise ContentError("Name the group")
        self._check_parent("group:new", parent or None)
        group_id = self.store.add_group(title, parent or None)
        return {"id": group_id, **self.library()}

    def update_group(self, group_id: str, fields: dict) -> dict:
        if not any(g["id"] == group_id for g in self.store.groups()):
            raise NotFound("No such group")
        changes = {}
        if "title" in fields:
            title = " ".join(str(fields["title"] or "").split())[:120]
            if not title:
                raise ContentError("Name the group")
            changes["title"] = title
        if "parent" in fields:
            parent = fields["parent"] or None
            self._check_parent(f"group:{group_id}", parent)
            changes["parent"] = parent
            changes["position"] = self.store.next_position(parent)
        if not changes:
            raise ContentError("Nothing to change")
        self.store.update_group(group_id, **changes)
        return self.library()

    def delete_group(self, group_id: str) -> dict:
        group = next((g for g in self.store.groups() if g["id"] == group_id), None)
        if group is None:
            raise NotFound("No such group")
        self.store.delete_group(group_id, group["parent"])
        return self.library()

    def _describe_node(self, node: str | None) -> str:
        if node is None:
            return "the top level"
        kind, _, key = node.partition(":")
        if kind == "group":
            return next((f"the group “{g['title']}”" for g in self.store.groups() if g["id"] == key), "a group")
        source = self.register.get(key)
        return f"“{source.title}”" if source else "a document"

    def _approve(self, source_id: str) -> None:
        if self.actions is None:
            self.register.update(source_id, approval_status="approved")
            return
        from ..ontology.actions import acting_person
        result = self.actions.execute("approve_source", {"source_id": source_id}, acting_person(self._operator.name))
        if result.outcome != "ok":
            raise ContentError(result.message or "The approval action failed")

    def _reject(self, source_id: str) -> None:
        if self.actions is None:
            self.register.update(source_id, approval_status="rejected")
            return
        from ..ontology.actions import acting_person
        result = self.actions.execute("reject_source", {"source_id": source_id}, acting_person(self._operator.name))
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
            if described.get("title_from_heading") or self.hooks["retitle"] and self.hooks["retitle"](source, title or "x"):
                raise ContentError("This document's title is its heading; rename it, which writes a new version")
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
        if self.hooks["all_suggestions"]:
            return self._open_suggestions().get(source_id, [])
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


def _outcome_words(row: dict) -> str:
    if row["outcome"] == "corrected":
        return f"Corrected in version {row['version']}" if row.get("version") else "Corrected"
    return {"accepted": "Accepted as it is", "resolved": "Resolved"}.get(row["outcome"], row["outcome"].capitalize())


def _clip(text: str, limit: int = 140) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _json(value: str | None):
    import json
    return json.loads(value) if value else None


def _dumps(value) -> str:
    import json
    return json.dumps(value)
