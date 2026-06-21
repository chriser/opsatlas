"""Knowledge-intelligence checks over the source register."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..ingestion.store import SectionStore
from ..retrieval.embedder import Embedder, EmbeddingCache
from ..retrieval.service import _cosine
from ..sources.register import SourceRegister

DUPLICATE_SIMILARITY = 0.92
OUTDATED_DAYS = 180


class KnowledgeIntelligence:
    def __init__(
        self,
        register: SourceRegister,
        section_store: SectionStore,
        embedder: Embedder | None = None,
        cache: EmbeddingCache | None = None,
    ) -> None:
        self.register = register
        self.section_store = section_store
        self.embedder = embedder
        self.cache = cache

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
                for i in range(len(secs)):
                    for j in range(i + 1, len(secs)):
                        if secs[i][0].id == secs[j][0].id:
                            continue
                        if _cosine(vecs[i], vecs[j]) >= DUPLICATE_SIMILARITY:
                            a, b = secs[i], secs[j]
                            issues["consistency"].append(
                                _issue("duplicate", a[0],
                                       f"Section '{a[1].heading}' closely matches '{b[1].heading}' in '{b[0].title}'.")
                            )

        total = sum(len(v) for v in issues.values())
        return {
            "total_issues": total,
            "categories": {k: len(v) for k, v in issues.items()},
            "issues": issues,
        }


def _issue(check: str, source, detail: str) -> dict:
    return {"check": check, "source_id": source.id, "source_title": source.title, "detail": detail}
