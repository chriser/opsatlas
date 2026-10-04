"""Content management in the sales workspace (CM S12, CM S21, CM S23).

A sales record's source is exactly ``document(title, text[, input hash])``, and the record is only used while that
holds. So editing a record's document goes through the record:
- the draft must start with the title as a heading;
- publishing writes the canonical document and updates the record's title, text and hash;
- publishing counts as the Human's review, and a record under a review block (a dispute, say) cannot be published.

When a document that records cite as evidence is published, those records follow the new evidence. Each gets a
governance note, and the publish reports them, so the Human can check they still match.

The governance agenda supplies suggestions: wording checks and conflicts or duplicates on this document's passages.
A suggestion the Human accepts as it is stops being raised for that document, Tibi included (CM S29); one an edit
removed is recorded as corrected by the platform.

Renaming a record rewrites its heading as a new version and keeps its approval: an approved record stays approved,
a pending one stays pending (CM S28). The library starts grouped by topic (CM S27); the Human reshapes it after that.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from assistant import settings
from assistant.content.service import ContentError
from assistant.content.text import plain
from assistant.governance.intelligence import undefined_acronyms
from assistant.iam.context import acting_id, acting_name

from .governance import STANDARD, GovernedSources, document_key
from .knowledge import document, sha
from .tibi_api import open_issue

TRAILER = re.compile(r"\n*Interview input SHA-256: [0-9a-f]{64}\s*$")

# The starting library: (key, title, parent key). Records are placed by their id, evidence by its title.
LIBRARY = [
    ("product", "Product knowledge", None),
    ("what", "What OpsAtlas is", "product"),
    ("how", "How it works", "product"),
    ("trust", "Governance and trust", "product"),
    ("deploy", "Deployment and roadmap", "product"),
    ("tibi", "Tibi", None),
]
# Conversation style, contributed claims and the evidence live in the System and Sales Playbook spaces (KS S3).
TOPICS = {
    "what": ("overview", "problem", "outputs", "stakeholders", "commercial"),
    "how": ("answers", "ontology", "activity-model", "process", "analytics", "evaluation", "architecture"),
    "trust": ("governance", "security", "data"),
    "deploy": ("deployment", "limitations", "next-steps", "real-deployment"),
    "tibi": ("tiberius",),
}
# A record that reads best under another record.
UNDER = {"governance-review": "governance"}
HEADING = re.compile(r"^#\s+(.+?)\s*#*\s*$")


def _words(markdown: str) -> list[str]:
    """A document's words in order, without its formatting: equal lists mean only the formatting changed."""
    return re.findall(r"[\w'’.,;:!?%£$€-]+", plain(markdown))


def parse_record(text: str) -> tuple[str, str]:
    """(title, text) of a record's document: its first heading, and everything after it."""
    lines = text.strip().splitlines()
    match = HEADING.match(lines[0]) if lines else None
    if not match:
        raise ContentError("A record's document starts with its title as a heading (# Title)")
    body = TRAILER.sub("", "\n".join(lines[1:])).strip()
    if not body:
        raise ContentError("Write the record's text under its title")
    return " ".join(match.group(1).split()), body


def attach(content, knowledge, desk, library=True) -> None:
    """The sales workspace's hooks on one space's content service. ``library``: that space starts with the sales
    workspace's folders (the Product Guide); the other family spaces keep the folders their documents arrive with."""
    def record_of(source_id, rows):
        return next((r for r in rows if r.get("source_id") == source_id), None)

    def prepare(source, text):
        rows = knowledge.records()
        row = record_of(source.id, rows)
        if row is None:
            # What the document said before, so publishing can tell a reworded document from a reformatted one.
            try:
                previous = knowledge.register.read_content(source.id).decode("utf-8", "replace")
            except OSError:
                previous = None
            return (text if text.endswith("\n") else text + "\n").encode(), {"record": None, "previous": previous}
        if block := knowledge.review_block(row, rows):
            raise ContentError(block)
        title, body = parse_record(text)
        return document(title, body, row.get("input_hash")), {"record": row["id"]}

    def published(source, written, context, approved=True):
        at = datetime.now(timezone.utc).isoformat()
        history = []
        with knowledge.lock:
            rows = knowledge.records()
            record = None
            if context and context.get("record"):
                record = next(r for r in rows if r["id"] == context["record"])
                record["title"], record["text"] = parse_record(written)
                record["sha256"] = sha(document(record["title"], record["text"], record.get("input_hash")))
                if approved:
                    record["review"] = {"actor": acting_name(), "actor_id": acting_id(), "scope": "internal rehearsal only",
                                        "at": at, "hash": record["sha256"], "evidence": knowledge.evidence_snapshot(record)}
                    record["approval"] = "approved"
                    history.append({"id": record["id"], "decision": "edited and approved", **record["review"]})
                else:
                    history.append({"id": record["id"], "decision": "renamed, approval unchanged", "at": at, "hash": record["sha256"]})
            citing = []
            # Audit F01: approving a document is not approving the records that cite it. A change to what it says
            # makes those records unavailable until the Human confirms each still holds; only a change of formatting
            # (the same words in the same order) carries their approval over.
            previous = (context or {}).get("previous")
            reformatted = previous is not None and _words(previous) == _words(written)
            for row in rows:
                refs = [ref for ref in row.get("references", []) if ref.get("source_id") == source.id]
                if not refs or row is record:
                    continue
                for ref in refs:
                    ref["sha256"] = source.content_sha256
                reviewed = (row.get("review") or {}).get("evidence")
                if reformatted and reviewed is not None and source.id in reviewed:
                    reviewed[source.id] = source.content_sha256
                    note = "The evidence this record cites was reformatted, with the same wording; its approval carries over."
                else:
                    note = "The evidence this record cites changed; the record is unavailable until you confirm it still holds."
                row.setdefault("governance", []).append({"evidence_edited": source.title, "at": at, "actor": acting_name(),
                                                         "actor_id": acting_id(), "reformatted": reformatted, "note": note})
                citing.append({"id": row["id"], "title": row["title"], "reconfirm": not reformatted})
                history.append({"id": row["id"], "decision": "evidence updated", "evidence": source.id, "at": at,
                                "reformatted": reformatted})
            knowledge._save(rows)
            with (knowledge.register.base_dir / "sales-review-history.jsonl").open("a") as log:
                for entry in history:
                    log.write(json.dumps(entry) + "\n")
        if settings.get("SALES_GOVERNANCE_AUTO_REVIEW") != "0":
            desk.statements.start()  # the changed statements are judged again; unchanged pairs come from the cache
        return {"record": record["id"] if record else None, "records_citing": citing}

    def describe(source):
        rows = knowledge.records()
        row = record_of(source.id, rows)
        cites = []
        for ref in (row or {}).get("references", []):
            parent = knowledge.register.get(ref["source_id"])
            cites.append({"source_id": ref["source_id"], "title": parent.title if parent else ref.get("path"), "path": ref.get("path")})
        cited_by = [{"id": r["id"], "title": r["title"], "source_id": r["source_id"]}
                    for r in rows if any(ref.get("source_id") == source.id for ref in r.get("references", []))]
        record = None
        if row is not None:
            record = {"id": row["id"], "title": row["title"], "status": row["status"], "kind": row.get("kind") or "product",
                      "contributor": (row.get("provenance") or {}).get("contributor"), "approval": knowledge.native_approval(row),
                      "eligible": knowledge.eligible(row), "review_block": knowledge.review_block(row, rows)}
        return {"record": record, "cites": cites, "cited_by": cited_by, "title_from_heading": row is not None}

    def cards(items):
        """{source id: [suggestion]}: each open agenda item as a suggestion on each document it concerns."""
        out = {}

        def add(source_id, card):
            mine = out.setdefault(source_id, [])
            if not any(c["key"] == card["key"] for c in mine):
                mine.append(card)

        for item in items:
            answer = (item.get("answer") or {}).get("status")
            if item.get("kind") == "statement":
                sides = item["statements"]
                conflict = item["relation"] == "conflict"
                for side in sides:
                    other = next((s for s in sides if s is not side), side)
                    add(side["source_id"], {
                        "key": item["key"], "issue_key": item["key"], "kind": item["relation"], "check": item["check"],
                        "label": "Possible conflict with another record" if conflict else "Says the same as another record",
                        "text": item.get("reason") or "", "quote": side["text"], "answer": answer,
                        "note": f"Possible conflict with “{other['title']}”" if conflict else f"Says the same as “{other['title']}”",
                        "other": {"title": other["title"], "text": other["text"], "source_id": other["source_id"]}})
                continue
            summary = open_issue(item)
            for ref in item.get("issues", []):
                source_id = ref.get("source_id")
                if not source_id:
                    continue
                if item.get("kind") == "standard":
                    # One suggestion per common acronym, so each can be spelled out or kept on its own.
                    for acronym in ref.get("standard") or [a for a in ref.get("acronyms", []) if a in item.get("acronyms", [])]:
                        meaning = (item.get("meanings") or {}).get(acronym) or STANDARD.get(acronym)
                        add(source_id, {**summary, "key": document_key(item, ref, acronym), "issue_key": item["key"],
                                        "text": f"{acronym} is a common acronym, used without being spelled out.",
                                        "hint": f"It usually stands for {meaning}." if meaning else None, "quote": acronym,
                                        "fix": {"find": acronym, "replace": f"{meaning} ({acronym})", "label": f"Spell it out as {meaning}"}
                                        if meaning else None, "acronyms": [acronym]})
                    continue
                card = {**summary, "key": document_key(item, ref), "issue_key": item["key"], "quote": None, "fix": None}
                if item.get("kind") == "acronym":
                    card.update(quote=item["acronym"], acronyms=[item["acronym"]])
                    known = item.get("known") or []
                    if known:
                        card["fix"] = {"find": item["acronym"], "replace": f"{known[0]['expansion']} ({item['acronym']})",
                                       "label": f"Spell it out as {known[0]['expansion']}"}
                    elif mentions := item.get("mentions") or []:
                        # Not defined anywhere, but the sources do spell it out in passing ("subject matter experts").
                        phrase = mentions[0]["phrase"]
                        card["fix"] = {"find": item["acronym"], "replace": f"{phrase} ({item['acronym']})",
                                       "label": f"Spell it out as {phrase}, as {mentions[0]['source_title']} does"}
                add(source_id, card)
        return out

    def suggestions(source_id):
        return cards(desk.agenda()["items"]).get(source_id, [])

    def all_suggestions():
        return cards(desk.agenda()["items"])

    def keep(source, suggestion, note):
        desk.keep(source.id, suggestion, note)

    def unkeep(source, suggestion):
        desk.unkeep(source.id, suggestion["key"])

    def settled_how(source, suggestion):
        """A suggestion that went away without an edit here: an answer the Human approved through Tibi, if any."""
        key = suggestion.get("issue_key") or suggestion["key"]
        answer = next((a for a in reversed(desk.answers()) if a.get("issue_key") == key and a.get("status") == "approved"), None)
        if answer:
            return {"actor": content.operator.name, "role": content.operator.role, "note": f"Settled with Tibi: {answer['answer']}"}
        return None

    def history(source, versions):
        """Acronyms each earlier edit spelled out, for the record of corrected suggestions. Cited evidence is not
        governed, so it has none."""
        if source.id in GovernedSources(knowledge.register, knowledge).evidence():
            return []
        found = []
        for before, after in zip(versions, versions[1:]):
            if after["label"] == "imported":
                continue
            for acronym in sorted(undefined_acronyms(before["text"]) - undefined_acronyms(after["text"])):
                standard = acronym in STANDARD
                found.append(({"key": ("standard:" if standard else "acronym:") + acronym, "kind": "standard" if standard else "acronym",
                               "check": "undefined_acronym", "label": "Acronym not spelled out", "quote": acronym, "acronyms": [acronym],
                               "text": f"{acronym} is a common acronym, used without being spelled out." if standard
                               else f"{acronym} is used without being spelled out."}, after))
        return found

    def decide(source, approve):
        rows = knowledge.records()
        row = record_of(source.id, rows)
        if row is None:
            content._approve(source.id, source.content_sha256) if approve else content._reject(source.id, source.content_sha256)
            return
        try:
            knowledge.decide(row["id"], row["sha256"], approve)  # the record's own review: enabled or excluded
        except ValueError as exc:
            raise ContentError(str(exc)) from exc

    def retitle(source, title):
        row = record_of(source.id, knowledge.records())
        return None if row is None else f"# {title}\n\n{row['text']}\n"

    def default_library():
        rows = knowledge.records()
        by_source = {r["source_id"]: r for r in rows}
        by_id = {r["id"]: r for r in rows}
        rank = {r["source_id"]: i for i, r in enumerate(rows)}

        def place(source):
            row = by_source.get(source.id)
            if row is None:
                return "paper" if source.title.startswith("DT603") else "notes"
            if row["id"] in UNDER and UNDER[row["id"]] in by_id:
                return f"source:{by_id[UNDER[row['id']]]['source_id']}"
            if row.get("kind") == "conversation":
                return "conversation"
            if row.get("provenance"):
                return "claims"
            return next((key for key, ids in TOPICS.items() if row["id"] in ids), "product")

        return {"groups": LIBRARY, "place": place,
                "rank": lambda source: (0, rank[source.id], "") if source.id in rank else (1, 0, source.title)}

    content.hooks.update(prepare=prepare, published=published, describe=describe, suggestions=suggestions,
                         all_suggestions=all_suggestions, keep=keep, unkeep=unkeep, settled_how=settled_how, history=history,
                         decide=decide, retitle=retitle, default_library=default_library if library else None)
