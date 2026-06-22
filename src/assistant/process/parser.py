"""Deterministic parser: a structured learning pack -> a ProcessRecord.

Targets the pack section layout (roles table, systems table, key business rules,
JSON-style learning records, suggested tagging structure). No LLM, so it is fast and
unit-testable; sections it cannot find are simply left empty.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict

from .models import ProcessRecord, ProcessRule


def _section(text: str, keyword: str) -> str:
    """Body text under the first '## ' heading whose title contains keyword."""
    capturing = False
    buf: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if capturing:
                break
            capturing = keyword.lower() in line.lower()
            continue
        if capturing:
            buf.append(line)
    return "\n".join(buf)


def _table_first_col(section: str) -> list[str]:
    """First column of a pipe table, minus the header row and the |---| separator."""
    rows: list[str] = []
    for line in section.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        first = cells[0] if cells else ""
        if not first or set(first) <= set("-: "):  # blank or separator
            continue
        rows.append(first)
    return rows[1:]  # drop the header cell (e.g. "Role")


def _bullets(section: str) -> list[str]:
    return [s.strip()[2:].strip() for s in section.splitlines() if s.strip().startswith("- ")]


def _json_records(section: str) -> list[dict]:
    out: list[dict] = []
    for line in section.splitlines():
        s = line.strip()
        if s.startswith("{") and s.endswith("}"):
            try:
                out.append(json.loads(s))
            except json.JSONDecodeError:
                continue
    return out


def _tags(section: str) -> dict[str, list[str]]:
    tags: dict[str, list[str]] = defaultdict(list)
    for raw in _bullets(section):
        item = raw.strip("`").strip()
        if ":" in item:
            key, val = item.split(":", 1)
            tags[key.strip()].append(val.strip())
    return tags


def _name(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            heading = line[2:].strip()
            m = re.match(r"Anonymised Learning Pack \d+\s*[–\-]\s*(.*)", heading)
            return (m.group(1) if m else heading).strip()
    return fallback


def parse_process(source_id: str, source_title: str, text: str) -> ProcessRecord:
    tags = _tags(_section(text, "tagging structure"))
    rules = [
        ProcessRule(**{k: str(r.get(k, "")) for k in ("record_id", "topic", "role", "rule", "confidence")})
        for r in _json_records(_section(text, "JSON-style learning records"))
    ]
    return ProcessRecord(
        id=source_id,
        source_id=source_id,
        source_title=source_title,
        name=_name(text, source_title),
        domain=(tags.get("domain") or [""])[0],
        process=(tags.get("process") or [""])[0],
        capabilities=tags.get("capability", []),
        roles=_table_first_col(_section(text, "Roles and responsibilities")),
        systems=_table_first_col(_section(text, "Systems and data dependencies")),
        controls=tags.get("control", []),
        dependencies=tags.get("dependency", []),
        business_rules=_bullets(_section(text, "Key business rules")),
        rules=rules,
    )
