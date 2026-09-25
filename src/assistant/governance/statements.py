"""Governance statements: every bullet, table row and sentence of approved knowledge (GOV S5).

The document-pair Full Governance Review compared whole documents and only saw sentences with a modal verb
("must", "should"); it could never find a conflict in a plain statement of fact. Governance now works on
statements: each is extracted once, keeps a stable ID and its place in the source, and is re-extracted only
when its source changes.

A statement ID is a hash of its source, section heading and normalised text, so it survives re-ingestion and
sections moving; a changed sentence is a new statement. Statements in derived sections (a pack's Q&A pairs,
JSON-style learning records, open questions, the tagging structure, and the preamble before numbered sections)
restate the document: they are kept for reference but not governed.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

DERIVED_HEADINGS = ('realistic q&a pairs', 'json-style learning records', 'open questions and design decisions',
                    'suggested tagging structure')
NUMBERED = re.compile(r'^\d+\.\s')
SEPARATOR = re.compile(r'^\|?[\s:|-]+\|?$')
SENTENCE = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')
MIN_WORDS = 5


@dataclass(frozen=True)
class Statement:
    id: str
    source_id: str
    source_title: str
    source_version: int
    heading: str
    section: int
    offset: int
    kind: str       # bullet | row | sentence
    text: str
    derived: bool

    def payload(self) -> dict:
        """What a judge sees: the statement and where it comes from."""
        return {'document': self.source_title, 'section': self.heading, 'text': self.text}


def normalise(text: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'[*_`]', '', text)).strip().lower()


def statement_id(source_id: str, heading: str, text: str) -> str:
    return hashlib.sha256(f'{source_id}\u0000{heading.strip().lower()}\u0000{normalise(text)}'.encode()).hexdigest()[:16]


def units(text: str) -> list[tuple[int, str, str]]:
    """(offset, kind, text) for every bullet, table row and sentence of five or more words."""
    out = []
    lines = text.splitlines(keepends=True)
    position = 0
    for n, raw in enumerate(lines):
        start, line = position, raw.strip()
        position += len(raw)
        if not line or line.startswith('#') or SEPARATOR.fullmatch(line):
            continue
        if line.startswith('|'):
            following = lines[n + 1].strip() if n + 1 < len(lines) else ''
            if SEPARATOR.fullmatch(following) and '-' in following:
                continue  # a table's header row
            row = ' | '.join(c.strip() for c in line.strip('|').split('|'))
            if len(row.split()) >= MIN_WORDS:
                out.append((start + raw.index(line), 'row', row))
            continue
        body = re.sub(r'^[-*•]\s+|^\d+[.)]\s+', '', line)
        kind = 'bullet' if body != line else 'sentence'
        cursor = start + raw.index(line) + (len(line) - len(body))
        for sentence in SENTENCE.split(body):
            if len(sentence.split()) >= MIN_WORDS:
                out.append((cursor + body.index(sentence), kind, sentence.strip()))
    return out


def extract(source, sections) -> list[Statement]:
    """Statements of one source. With numbered headings, sections before the first one are its preamble."""
    numbered = [s.ordinal for s in sections if NUMBERED.match(s.heading)]
    first = min(numbered) if numbered else None
    out, seen = [], set()
    for section in sections:
        derived = (any(h in section.heading.lower() for h in DERIVED_HEADINGS)
                   or (first is not None and section.ordinal < first))
        for offset, kind, text in units(section.text):
            identifier = statement_id(source.id, section.heading, text)
            if identifier in seen:
                continue  # the same sentence twice under one heading is one statement
            seen.add(identifier)
            out.append(Statement(identifier, source.id, source.title, int(source.version), section.heading, section.ordinal,
                                 offset, kind, text, derived))
    return out


class StatementStore:
    """Statements of approved sources, re-extracted only for sources whose content or version changed."""

    def __init__(self, base_dir: str | Path) -> None:
        self.path = Path(base_dir) / 'governance' / 'statements.json'

    def _load(self) -> dict:
        return json.loads(self.path.read_text()) if self.path.exists() else {}

    def sync(self, register, section_store) -> tuple[list[Statement], dict]:
        stored = self._load()
        current, extracted = {}, []
        for source in register.list():
            if source.approval_status != 'approved':
                continue
            fingerprint = f'{source.content_sha256}:{source.version}'
            previous = stored.get(source.id)
            if previous and previous['fingerprint'] == fingerprint:
                current[source.id] = previous
                continue
            rows = extract(source, section_store.list_for_source(source.id))
            current[source.id] = {'fingerprint': fingerprint, 'statements': [asdict(s) for s in rows]}
            extracted.append(source.id)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(current))
        statements = [Statement(**row) for entry in current.values() for row in entry['statements']]
        return statements, {'sources': len(current), 'extracted': extracted, 'removed': sorted(set(stored) - set(current))}
