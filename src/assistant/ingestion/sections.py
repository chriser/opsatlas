"""Section builder: split source text into meaningful, ordered sections.

Splits on Markdown-style headings where present, otherwise on blank-line
paragraph boundaries, preserving the nearest heading as context. Deterministic
and model-free.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*\S)\s*$")
# Soft cap so very long blocks are split into retrievable chunks.
_MAX_CHARS = 1200


class Section(BaseModel):
    source_id: str
    ordinal: int
    heading: str
    text: str
    char_count: int


def _split_long(block: str) -> list[str]:
    block = block.strip()
    if len(block) <= _MAX_CHARS:
        return [block] if block else []
    # Split on paragraph breaks, packing into <= _MAX_CHARS chunks.
    paras = [p.strip() for p in re.split(r"\n\s*\n", block) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paras:
        if current and len(current) + len(para) + 2 > _MAX_CHARS:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks


def build_sections(source_id: str, text: str) -> list[Section]:
    """Build ordered sections from raw document text."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    blocks: list[tuple[str, list[str]]] = []  # (heading, body lines)
    heading = "Introduction"
    body: list[str] = []

    def flush() -> None:
        if any(line.strip() for line in body):
            blocks.append((heading, body.copy()))

    for line in lines:
        match = _HEADING.match(line)
        if match:
            flush()
            heading = match.group(2).strip()
            body = []
        else:
            body.append(line)
    flush()

    sections: list[Section] = []
    ordinal = 0
    for head, body_lines in blocks:
        body_text = "\n".join(body_lines).strip()
        for chunk in _split_long(body_text) or ([body_text] if body_text else []):
            chunk = chunk.strip()
            if not chunk:
                continue
            sections.append(
                Section(
                    source_id=source_id,
                    ordinal=ordinal,
                    heading=head,
                    text=chunk,
                    char_count=len(chunk),
                )
            )
            ordinal += 1
    return sections
