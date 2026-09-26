"""Content management in the sales workspace (CM S12, CM S21, CM S23).

A sales record's source is exactly ``document(title, text[, input hash])``, and the record is only used while that
holds. So editing a record's document goes through the record:
- the draft must start with the title as a heading;
- publishing writes the canonical document and updates the record's title, text and hash;
- publishing counts as the Human's review, and a record under a review block (a dispute, say) cannot be published.

When a document that records cite as evidence is published, those records follow the new evidence. Each gets a
governance note, and the publish reports them, so the Human can check they still match.

The governance agenda supplies suggestions: wording checks and conflicts or duplicates on this document's passages.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone

from assistant.content.service import ContentError

from .knowledge import document, sha
from .tibi_api import open_issue

TRAILER = re.compile(r"\n*Interview input SHA-256: [0-9a-f]{64}\s*$")
HEADING = re.compile(r"^#\s+(.+?)\s*#*\s*$")


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


def attach(content, knowledge, desk) -> None:
    def record_of(source_id, rows):
        return next((r for r in rows if r.get("source_id") == source_id), None)

    def prepare(source, text):
        rows = knowledge.records()
        row = record_of(source.id, rows)
        if row is None:
            return (text if text.endswith("\n") else text + "\n").encode(), {"record": None}
        if block := knowledge.review_block(row, rows):
            raise ContentError(block)
        title, body = parse_record(text)
        return document(title, body, row.get("input_hash")), {"record": row["id"]}

    def published(source, written, context):
        at = datetime.now(timezone.utc).isoformat()
        history = []
        with knowledge.lock:
            rows = knowledge.records()
            record = None
            if context and context.get("record"):
                record = next(r for r in rows if r["id"] == context["record"])
                record["title"], record["text"] = parse_record(written)
                record["sha256"] = sha(document(record["title"], record["text"], record.get("input_hash")))
                record["review"] = {"actor": "local operator", "scope": "internal rehearsal only", "at": at, "hash": record["sha256"]}
                record["approval"] = "approved"
                history.append({"id": record["id"], "decision": "edited and approved", **record["review"]})
            citing = []
            for row in rows:
                refs = [ref for ref in row.get("references", []) if ref.get("source_id") == source.id]
                if not refs or row is record:
                    continue
                for ref in refs:
                    ref["sha256"] = source.content_sha256
                row.setdefault("governance", []).append({
                    "evidence_edited": source.title, "at": at, "actor": "local operator",
                    "note": "The evidence this record cites was edited and approved; check the record still matches it."})
                citing.append({"id": row["id"], "title": row["title"]})
                history.append({"id": row["id"], "decision": "evidence updated", "evidence": source.id, "at": at})
            knowledge._save(rows)
            with (knowledge.register.base_dir / "sales-review-history.jsonl").open("a") as log:
                for entry in history:
                    log.write(json.dumps(entry) + "\n")
        if os.environ.get("SALES_GOVERNANCE_AUTO_REVIEW", "1") != "0":
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

    def suggestions(source_id):
        out = []
        for item in desk.agenda()["items"]:
            answer = (item.get("answer") or {}).get("status")
            if item.get("kind") == "statement":
                sides = item["statements"]
                mine = [s for s in sides if s["source_id"] == source_id]
                if not mine:
                    continue
                other = next((s for s in sides if s is not mine[0]), mine[0])
                conflict = item["relation"] == "conflict"
                out.append({"key": item["key"], "kind": item["relation"], "check": item["check"],
                            "label": "Possible conflict with another record" if conflict else "Says the same as another record",
                            "text": item.get("reason") or "", "quote": mine[0]["text"], "answer": answer,
                            "other": {"title": other["title"], "text": other["text"], "source_id": other["source_id"]}})
                continue
            if not any(ref.get("source_id") == source_id for ref in item.get("issues", [])):
                continue
            summary = open_issue(item)
            quote, fix = None, None
            if item.get("kind") == "acronym":
                quote = item["acronym"]
                known = item.get("known") or []
                if known:
                    fix = {"find": item["acronym"], "replace": f"{known[0]['expansion']} ({item['acronym']})",
                           "label": f"Spell it out as {known[0]['expansion']}"}
                elif mentions := item.get("mentions") or []:
                    # Not defined anywhere, but the sources do spell it out in passing ("subject matter experts").
                    phrase = mentions[0]["phrase"]
                    fix = {"find": item["acronym"], "replace": f"{phrase} ({item['acronym']})",
                           "label": f"Spell it out as {phrase}, as {mentions[0]['source_title']} does"}
            out.append({**summary, "quote": quote, "fix": fix})
        return out

    content.hooks.update(prepare=prepare, published=published, describe=describe, suggestions=suggestions)
