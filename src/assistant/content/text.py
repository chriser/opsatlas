"""Plain text, counts and readability of a Markdown document (CM S6, CM S22), and word-level differences (CM S16)."""

from __future__ import annotations

import difflib
import math
import re

WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’-]*")
TOKEN = re.compile(r"\s+|[^\s]+")


def plain(markdown: str) -> str:
    """What a reader sees: Markdown syntax removed, one block per line."""
    text = re.sub(r"```.*?```", " ", markdown, flags=re.S)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)  # images: their alt text
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links: their words
    text = re.sub(r"<[^>]+>", " ", text)
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if re.fullmatch(r"\|?[\s:|-]+\|?", line) and "-" in line:
            continue  # a table's separator row
        line = re.sub(r"^#{1,6}\s+", "", line)
        line = re.sub(r"^(?:[-*+]|\d+[.)])\s+", "", line)
        line = re.sub(r"^>\s?", "", line)
        line = line.strip("|").replace("|", " ")
        line = re.sub(r"[*_~`]+", "", line)
        lines.append(" ".join(line.split()))
    return "\n".join(line for line in lines if line)


def words(markdown: str) -> list[str]:
    return WORD.findall(plain(markdown))


def _syllables(word: str) -> int:
    word = re.sub(r"[^a-z]", "", word.lower())
    if not word:
        return 0
    groups = re.findall(r"[aeiouy]+", word)
    count = len(groups)
    if word.endswith("e") and not word.endswith(("le", "ee")) and count > 1:
        count -= 1
    return max(count, 1)


def _sentences(text: str) -> int:
    # A heading, list item or table row is its own sentence; within a line, full stops, question and exclamation marks.
    count = 0
    for line in text.splitlines():
        parts = [p for p in re.split(r"[.!?]+(?:\s+|$)", line) if WORD.search(p)]
        count += max(len(parts), 1 if WORD.search(line) else 0)
    return count


LABELS = ((90, "Very easy to read"), (80, "Easy to read"), (70, "Fairly easy to read"), (60, "Plain English"),
          (50, "Fairly difficult to read"), (30, "Difficult to read"), (-1000, "Very difficult to read"))


def stats(markdown: str) -> dict:
    """Word count, reading time and Flesch readability, computed locally."""
    text = plain(markdown)
    found = WORD.findall(text)
    n = len(found)
    if not n:
        return {"words": 0, "sentences": 0, "reading_minutes": 0, "flesch": None, "grade": None, "readability": None}
    sentences = max(_sentences(text), 1)
    syllables = sum(_syllables(w) for w in found)
    flesch = 206.835 - 1.015 * (n / sentences) - 84.6 * (syllables / n)
    grade = 0.39 * (n / sentences) + 11.8 * (syllables / n) - 15.59
    return {"words": n, "sentences": sentences, "reading_minutes": max(1, math.ceil(n / 200)),
            "flesch": round(flesch, 1), "grade": round(max(grade, 0), 1),
            "readability": next(label for floor, label in LABELS if flesch >= floor)}


def diff(before: str, after: str) -> dict:
    """Word-level changes from ``before`` to ``after``: [{op: equal|insert|delete, text}] and the words changed."""
    a, b = TOKEN.findall(before), TOKEN.findall(after)
    ops: list[dict] = []

    def add(op, tokens):
        if not tokens:
            return
        text = "".join(tokens)
        if ops and ops[-1]["op"] == op:
            ops[-1]["text"] += text
        else:
            ops.append({"op": op, "text": text})
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            add("equal", a[i1:i2])
        else:
            add("delete", a[i1:i2])
            add("insert", b[j1:j2])
    counted = lambda op: sum(len(WORD.findall(o["text"])) for o in ops if o["op"] == op)  # noqa: E731
    return {"ops": ops, "inserted_words": counted("insert"), "deleted_words": counted("delete")}


def find_anchor(text: str, quote: str, prefix: str = "", suffix: str = "") -> int | None:
    """Where a comment's quote is in ``text``: the occurrence whose surroundings best match, or None if it is gone.
    Whitespace is compared loosely, since a quote is taken from rendered text."""
    squash = lambda s: re.sub(r"\s+", " ", s)  # noqa: E731  (runs of whitespace; edges kept, they matter in context)
    haystack, needle = squash(text), squash(quote).strip()
    if not needle:
        return None
    best, best_score, start = None, -1, 0
    while (at := haystack.find(needle, start)) != -1:
        before, after = haystack[:at], haystack[at + len(needle):]
        score = _common_suffix(before, squash(prefix)) + _common_prefix(after, squash(suffix))
        if score > best_score:
            best, best_score = at, score
        start = at + 1
    return best


def _common_suffix(a: str, b: str) -> int:
    n = 0
    while n < min(len(a), len(b)) and a[-1 - n] == b[-1 - n]:
        n += 1
    return n


def _common_prefix(a: str, b: str) -> int:
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    return n
