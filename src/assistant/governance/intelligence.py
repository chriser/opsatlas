"""Knowledge-intelligence checks over the source register."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..answer.generator import Generator
from ..ingestion.store import SectionStore
from ..retrieval.embedder import Embedder, EmbeddingCache
from ..retrieval.service import _cosine
from ..sources.register import SourceRegister

DUPLICATE_SIMILARITY = 0.92
CONFLICT_MIN_SIMILARITY = 0.45  # related enough to be worth an LLM contradiction check
MAX_CONFLICT_CHECKS = 8  # bound LLM calls
OUTDATED_DAYS = 180

_CONFLICT_PROMPT = (
    "Two passages may come from DIFFERENT processes. Report a conflict ONLY if they make "
    "directly contradictory statements about the SAME specific fact (the same field, step, "
    "amount, date, or the same role's duty) such that both cannot be true at once.\n"
    "NOT a conflict, answer NONE: different processes or scopes, different roles, similar "
    "wording, or one passage simply omitting what the other says. When in doubt, answer NONE.\n"
    'Reply EXACTLY "NONE", or "CONFLICT: <one short sentence naming the contradicted fact>".'
    "\n\nPASSAGE A: {a}\n\nPASSAGE B: {b}"
)


class KnowledgeIntelligence:
    def __init__(
        self,
        register: SourceRegister,
        section_store: SectionStore,
        embedder: Embedder | None = None,
        cache: EmbeddingCache | None = None,
        generator: Generator | None = None,
        accepted=None,
    ) -> None:
        self.register = register
        self.section_store = section_store
        self.embedder = embedder
        self.cache = cache
        self.generator = generator
        self.accepted = accepted

    def run(self) -> dict:
        sources = self.register.list()
        issues: dict[str, list[dict]] = {"compliance": [], "consistency": [], "correctness": []}

        # Compliance — metadata / readiness.
        for s in sources:
            not_ingested_detail = _not_ingested_detail(s)
            if not_ingested_detail:
                issues["compliance"].append(_issue("not_ingested", s, not_ingested_detail))
            if s.title.strip().lower() == Path(s.filename).stem.lower():
                issues["compliance"].append(_issue("metadata_title", s, "No descriptive title set (defaults to the file name)."))

        # Correctness — outdated.
        cutoff = datetime.now(timezone.utc) - timedelta(days=OUTDATED_DAYS)
        for s in sources:
            try:
                created = datetime.fromisoformat(s.created_at)
            except ValueError:
                continue
            if created < cutoff:
                issues["correctness"].append(_issue("outdated", s, f"Registered over {OUTDATED_DAYS} days ago; review for currency."))

        # Consistency — near-duplicate sections across different sources.
        structural_count: dict[str, int] = {}  # per source: boilerplate sections suppressed
        if self.embedder is not None and self.cache is not None:
            secs = [(s, sec) for s in sources for sec in self.section_store.list_for_source(s.id)]
            if len(secs) >= 2:
                comparison_texts = [_duplicate_comparison_text(sec.text) for _, sec in secs]
                substantive = [_has_duplicate_substance(text) for text in comparison_texts]
                indexed_texts = [(idx, text) for idx, text in enumerate(comparison_texts) if substantive[idx]]
                vecs: list[list[float]] = [[] for _ in secs]
                if indexed_texts:
                    embedded = self.cache.get_or_embed(self.embedder, [text for _, text in indexed_texts])
                    for (idx, _), vector in zip(indexed_texts, embedded):
                        vecs[idx] = vector
                candidates = []  # (similarity, i, j) related but NOT duplicate -> conflict check
                dup_pairs = []  # (i, j) near-duplicate cross-source pairs
                dup_src: list[set[str]] = [set() for _ in secs]  # other source ids each section duplicates into
                structural_src: list[set[str]] = [set() for _ in secs]  # template/scaffold overlap across sources
                for i in range(len(secs)):
                    for j in range(i + 1, len(secs)):
                        if secs[i][0].id == secs[j][0].id:
                            continue
                        if not substantive[i] or not substantive[j]:
                            if _structural_lines_overlap(secs[i][1].text, secs[j][1].text):
                                structural_src[i].add(secs[j][0].id)
                                structural_src[j].add(secs[i][0].id)
                            continue
                        sim = _cosine(vecs[i], vecs[j])
                        if sim >= DUPLICATE_SIMILARITY:
                            dup_pairs.append((i, j))
                            dup_src[i].add(secs[j][0].id)
                            dup_src[j].add(secs[i][0].id)
                        elif sim >= CONFLICT_MIN_SIMILARITY:
                            candidates.append((sim, i, j))  # near-dups can't contradict; check the related band

                # A section recurring across 3+ documents (>=2 other sources) is boilerplate
                # — titles, disclaimers, template headings: structural, not actionable. We drop
                # those from the issue list and only count them per source (surfaced as a label).
                structural = [len(d) >= 2 or bool(structural_src[i]) for i, d in enumerate(dup_src)]
                for i, is_struct in enumerate(structural):
                    if is_struct:
                        sid = secs[i][0].id
                        structural_count[sid] = structural_count.get(sid, 0) + 1
                for i, j in dup_pairs:
                    if structural[i] or structural[j]:
                        continue  # suppressed structural boilerplate
                    a, b = secs[i], secs[j]
                    issue = _issue("duplicate", a[0],
                                   f"Section '{a[1].heading}' closely matches '{b[1].heading}' in '{b[0].title}'.")
                    issue["source_b_id"] = b[0].id
                    issue["source_b_title"] = b[0].title
                    issues["consistency"].append(issue)

                # Correctness — LLM-checked contradictions on the most related pairs.
                if self.generator is not None:
                    for _, i, j in sorted(candidates, reverse=True)[:MAX_CONFLICT_CHECKS]:
                        a, b = secs[i], secs[j]
                        verdict = self.generator.generate(
                            _CONFLICT_PROMPT.format(a=a[1].text, b=b[1].text)
                        ).strip()
                        if verdict.upper().startswith("CONFLICT"):
                            detail = verdict.split(":", 1)[1].strip() if ":" in verdict else "Conflicting statements."
                            issues["correctness"].append(
                                _issue("conflict", a[0],
                                       f"'{a[1].heading}' vs '{b[1].heading}' in '{b[0].title}': {detail}")
                            )

        # Text-quality checks (deterministic, per source) — one issue per check/source.
        for s in sources:
            sections = self.section_store.list_for_source(s.id)
            if not sections:
                continue
            text = "\n\n".join(sec.text for sec in sections)
            for category, check, fn in _TEXT_CHECKS:
                detail = fn(text)
                if detail:
                    issues[category].append(_issue(check, s, detail))

        # Drop operator-accepted issues from the active list; count them per source.
        accepted_count: dict[str, int] = {}
        if self.accepted is not None:
            for category, lst in issues.items():
                kept = []
                for it in lst:
                    if self.accepted.is_accepted(it["source_id"], it["check"], it["detail"]):
                        accepted_count[it["source_id"]] = accepted_count.get(it["source_id"], 0) + 1
                    else:
                        kept.append(it)
                issues[category] = kept

        total = sum(len(v) for v in issues.values())
        flat = [i for v in issues.values() for i in v]
        # Health is the worst severity present: any high -> red, else any issue -> amber,
        # none -> green. Gives an at-a-glance "do we have a problem?" signal.
        if not flat:
            health = "green"
        elif any(i["severity"] == "high" for i in flat):
            health = "red"
        else:
            health = "amber"
        # Per-source labels for the source table: active issues touching the source, plus
        # the boilerplate (structural) duplicates that were suppressed from the list.
        source_summary: dict[str, dict] = {}
        for s in sources:
            active = sum(1 for it in flat if it["source_id"] == s.id or it.get("source_b_id") == s.id)
            structural = structural_count.get(s.id, 0)
            accepted = accepted_count.get(s.id, 0)
            if active or structural or accepted:
                source_summary[s.id] = {"active": active, "structural": structural, "accepted": accepted}
        return {
            "total_issues": total,
            "health": health,
            "categories": {k: len(v) for k, v in issues.items()},
            "descriptions": CHECK_DESCRIPTIONS,
            "source_summary": source_summary,
            "issues": issues,
        }


# Severity reflects estimated impact on answer quality: contradictions and unusable
# sources corrupt answers (high); stale content is a medium risk; duplicates and weak
# metadata are mostly tidiness (low). Score drives ranking (higher = fix first).
SEVERITY = {
    "conflict": "high",
    "not_ingested": "high",
    "broken_link": "medium",
    "localisation": "medium",
    "outdated": "medium",
    "readability": "low",
    "undefined_acronym": "low",
    "content_style": "low",
    "duplicate": "low",
    "metadata_title": "low",
}
_SCORE = {"high": 3, "medium": 2, "low": 1}

# Plain-English description per check, surfaced in the UI.
CHECK_DESCRIPTIONS = {
    "not_ingested": "Source is not usable because ingestion has not completed or produced usable sections.",
    "metadata_title": "Descriptive title missing (defaults to the file name).",
    "undefined_acronym": "Acronyms used without a first-use definition or glossary entry.",
    "readability": "Long, dense sentences that are hard to read or skim.",
    "duplicate": "Sections that closely match another document and may be merged.",
    "localisation": "Mixed locale within a document (US/UK spelling or currency).",
    "content_style": "House-style deviations (placeholders or inconsistent terms).",
    "conflict": "Contradictions in fact across related documents.",
    "outdated": "Registered long ago; review for currency.",
    "broken_link": "Empty, placeholder or malformed link targets (structural check).",
}

_ACRONYM = re.compile(r"\b[A-Z]{2,6}\b")  # letters only — skips Q1/Q10 item numbering
_ACRONYM_STOP = {"VAT", "JSON", "ID", "IDS", "URL", "API", "PDF", "OK", "UK", "US", "EU", "CSV",
                 "XML", "HTML", "HTTP", "HTTPS", "FAQ", "CEO", "HR", "IT", "KPI", "SLA", "UI", "UX"}
_US_UK = [("organize", "organise"), ("color", "colour"), ("catalog", "catalogue"), ("center", "centre"),
          ("license", "licence"), ("behavior", "behaviour"), ("optimize", "optimise"), ("fulfill", "fulfil")]
_TERMS = [("email", "e-mail"), ("login", "log in"), ("website", "web site"), ("backend", "back end")]
_PLACEHOLDER = re.compile(r"\b(TODO|TBD|FIXME|XXX)\b|\?\?\?")
_LINK = re.compile(r"\[[^\]]*\]\(([^)]*)\)")
_ACRONYM_EXPANSION_STOPWORDS = {"a", "an", "and", "for", "in", "of", "or", "the", "to"}


def _check_undefined_acronym(text: str) -> str:
    defined = _defined_acronyms(text)
    undefined = sorted(set(_ACRONYM.findall(text)) - defined - _ACRONYM_STOP)
    return f"Acronyms used without a definition: {', '.join(undefined[:8])}." if undefined else ""


def _defined_acronyms(text: str) -> set[str]:
    defined = set(re.findall(r"\(([A-Z]{2,6})\)", text))  # e.g. "...Name (ABC)"
    for match in re.finditer(r"\b([A-Z]{2,6})\b\s*\(([^)]{3,160})\)", text):
        acronym, expansion = match.groups()
        if _expansion_matches_acronym(acronym, expansion):
            defined.add(acronym)
    return defined


def _expansion_matches_acronym(acronym: str, expansion: str) -> bool:
    words = re.findall(r"[A-Za-z]+", expansion)
    initials = "".join(
        word[0].upper()
        for word in words
        if word.lower() not in _ACRONYM_EXPANSION_STOPWORDS
    )
    return initials == acronym


def _check_readability(text: str) -> str:
    long_sentences = [s for s in _readability_sentences(text) if _readability_word_count(s) > 40]
    return f"{len(long_sentences)} long sentences (40+ words) may be hard to read." if len(long_sentences) >= 3 else ""


def _readability_sentences(text: str) -> list[str]:
    prose = _readability_prose(text)
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", prose) if sentence.strip()]


def _readability_prose(text: str) -> str:
    lines: list[str] = []
    in_fence = False
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
            lines.append("")
            continue
        if in_fence or _is_markdown_table_row(stripped):
            lines.append("")
            continue
        lines.append(line)
    return "\n".join(lines)


def _is_markdown_table_row(line: str) -> bool:
    return line.startswith("|") and line.count("|") >= 2


def _readability_word_count(sentence: str) -> int:
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", sentence))


def _duplicate_comparison_text(text: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    kept: list[str] = []
    in_fence = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if _is_fence_marker(stripped):
            in_fence = not in_fence
            continue
        if in_fence or _is_structural_markdown_line(stripped):
            continue
        if _is_markdown_table_row(stripped):
            if _is_table_separator(stripped) or _is_table_header(lines, index):
                continue
            kept.append(" ".join(cell.strip() for cell in stripped.strip("|").split("|") if cell.strip()))
            continue
        kept.append(stripped)
    return " ".join(" ".join(kept).split())


def _has_duplicate_substance(text: str) -> bool:
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", text)) >= 6


def _structural_lines_overlap(a: str, b: str) -> bool:
    return bool(_structural_lines(a) & _structural_lines(b))


def _structural_lines(text: str) -> set[str]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: set[str] = set()
    in_fence = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if _is_fence_marker(stripped):
            out.add(_normalise_line(stripped))
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if (
            _is_structural_markdown_line(stripped)
            or _is_table_separator(stripped)
            or _is_table_header(lines, index)
        ):
            normalised = _normalise_line(stripped)
            if normalised:
                out.add(normalised)
    return out


def _normalise_line(line: str) -> str:
    return " ".join(line.strip().lower().split())


def _is_fence_marker(line: str) -> bool:
    return line.startswith(("```", "~~~"))


def _is_structural_markdown_line(line: str) -> bool:
    return (
        not line
        or bool(re.match(r"^#{1,6}\s+\S", line))
        or bool(re.match(r"^[-*_]{3,}$", line))
        or bool(re.match(r"^\*\*[^*]{2,60}:\*\*", line))
    )


def _is_table_separator(line: str) -> bool:
    if not _is_markdown_table_row(line):
        return False
    cells = [cell.strip().replace(" ", "") for cell in line.strip("|").split("|")]
    return bool(cells) and all(re.match(r"^:?-{1,}:?$", cell) for cell in cells)


def _is_table_header(lines: list[str], index: int) -> bool:
    if not _is_markdown_table_row(lines[index].strip()):
        return False
    return index + 1 < len(lines) and _is_table_separator(lines[index + 1].strip())


def _check_localisation(text: str) -> str:
    hits = [f"{us}/{uk}" for us, uk in _US_UK if _contains_locale_token(text, us) and _contains_locale_token(text, uk)]
    if "$" in text and "£" in text:
        hits.append("$/£")
    return f"Mixed locale in one document: {', '.join(hits)}." if hits else ""


def _contains_locale_token(text: str, token: str) -> bool:
    return bool(re.search(rf"(?<![A-Za-z]){re.escape(token)}(?![A-Za-z])", text, flags=re.IGNORECASE))


def _check_content_style(text: str) -> str:
    smells = []
    placeholders = sorted({m.group(0) for m in _PLACEHOLDER.finditer(text)})
    if placeholders:
        smells.append("placeholders (" + ", ".join(placeholders) + ")")
    low = text.lower()
    mixed = [f"{a}/{b}" for a, b in _TERMS if a in low and b in low]
    if mixed:
        smells.append("inconsistent terms (" + ", ".join(mixed) + ")")
    return "House-style issues: " + "; ".join(smells) + "." if smells else ""


def _check_broken_link(text: str) -> str:
    bad = [h for h in _LINK.findall(text)
           if not h.strip() or h.strip() in {"#", "TODO"} or "example.com" in h
           or not h.strip().startswith(("http://", "https://", "/", "#", "mailto:"))]
    return f"{len(bad)} empty/placeholder/malformed link target(s) (structural check)." if bad else ""


# (category, check name, function) — appended per source in run().
_TEXT_CHECKS = [
    ("compliance", "undefined_acronym", _check_undefined_acronym),
    ("compliance", "readability", _check_readability),
    ("consistency", "localisation", _check_localisation),
    ("consistency", "content_style", _check_content_style),
    ("correctness", "broken_link", _check_broken_link),
]


def _not_ingested_detail(source) -> str:
    if source.processing_state == "ingested" and source.section_count > 0:
        return ""
    if source.processing_state == "registered":
        return "Source is registered but has not been ingested yet, so it cannot be used."
    if source.processing_state == "failed":
        return "Source ingestion failed or produced no usable sections. Fix the file content and ingest it again."
    if source.processing_state == "ingested":
        return "Source is marked ingested but has no usable sections. Re-ingest it after adding body content."
    return f"Source is in '{source.processing_state}' state and is not ready to use."


def _issue(check: str, source, detail: str) -> dict:
    severity = SEVERITY.get(check, "medium")
    return {
        "check": check,
        "severity": severity,
        "score": _SCORE[severity],
        "source_id": source.id,
        "source_title": source.title,
        "detail": detail,
    }
