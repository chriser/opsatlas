"""Knowledge-intelligence checks over the source register."""

from __future__ import annotations

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
    "Do the two passages below contradict each other on any fact (amounts, dates, "
    "eligibility, who/what is responsible, mandatory vs optional)?\n"
    'Reply EXACTLY "NONE" if they are consistent, or "CONFLICT: <one short sentence>" '
    "if they contradict.\n\nPASSAGE A: {a}\n\nPASSAGE B: {b}"
)


class KnowledgeIntelligence:
    def __init__(
        self,
        register: SourceRegister,
        section_store: SectionStore,
        embedder: Embedder | None = None,
        cache: EmbeddingCache | None = None,
        generator: Generator | None = None,
    ) -> None:
        self.register = register
        self.section_store = section_store
        self.embedder = embedder
        self.cache = cache
        self.generator = generator

    def run(self) -> dict:
        sources = self.register.list()
        issues: dict[str, list[dict]] = {"compliance": [], "consistency": [], "correctness": []}

        # Compliance — metadata / readiness.
        for s in sources:
            if s.section_count == 0:
                issues["compliance"].append(_issue("not_ingested", s, "Source is not ingested yet, so it cannot be used."))
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
        if self.embedder is not None and self.cache is not None:
            secs = [(s, sec) for s in sources for sec in self.section_store.list_for_source(s.id)]
            if len(secs) >= 2:
                vecs = self.cache.get_or_embed(self.embedder, [sec.text for _, sec in secs])
                candidates = []  # (similarity, i, j) cross-source, related but not duplicate
                for i in range(len(secs)):
                    for j in range(i + 1, len(secs)):
                        if secs[i][0].id == secs[j][0].id:
                            continue
                        sim = _cosine(vecs[i], vecs[j])
                        if sim >= DUPLICATE_SIMILARITY:
                            a, b = secs[i], secs[j]
                            issues["consistency"].append(
                                _issue("duplicate", a[0],
                                       f"Section '{a[1].heading}' closely matches '{b[1].heading}' in '{b[0].title}'.")
                            )
                        # Related pairs (incl. near-duplicates that may differ on a fact)
                        # are candidates for an LLM contradiction check.
                        if sim >= CONFLICT_MIN_SIMILARITY:
                            candidates.append((sim, i, j))

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

        total = sum(len(v) for v in issues.values())
        return {
            "total_issues": total,
            "categories": {k: len(v) for k, v in issues.items()},
            "issues": issues,
        }


def _issue(check: str, source, detail: str) -> dict:
    return {"check": check, "source_id": source.id, "source_title": source.title, "detail": detail}
