"""Candidate pairs for governance: each statement's nearest statements (GOV S6).

Comparing every document with every other one grew with the square of the corpus (210 pairs took 35 hours)
and mostly compared statements about different processes. Here each governed statement is embedded once and
compared only with its k nearest statements: in other documents, and in other sections of its own document.
Measured on the 21-document corpus (docs/benchmark/governance): 2,345 candidates at k=3 and cosine >= 0.70,
seeing every planted cross-document conflict and duplicate the benchmark holds.

Two kinds of statement are never candidates: template text (a line repeated verbatim in three or more
documents, such as "Content has been anonymised for internal learning use") and statements from sources that
are cited evidence rather than governed knowledge (the caller names them).
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .statements import Statement, normalise

TEMPLATE_DOCUMENTS = 3


@dataclass(frozen=True)
class Candidate:
    a: Statement
    b: Statement
    cosine: float

    @property
    def same_document(self) -> bool:
        return self.a.source_id == self.b.source_id


class StatementIndex:
    def __init__(self, base_dir: str | Path, embedder, model: str) -> None:
        self.path = Path(base_dir) / 'governance' / 'statement-embeddings.json'
        self.embedder, self.model = embedder, model

    def _key(self, text: str) -> str:
        # Vectors from different embedding models never mix.
        return hashlib.sha256(f'{self.model}\u0000{text}'.encode()).hexdigest()

    def vectors(self, texts: list[str]) -> tuple[np.ndarray, int]:
        cache = json.loads(self.path.read_text()) if self.path.exists() else {}
        missing = list(dict.fromkeys(t for t in texts if self._key(t) not in cache))
        if missing:
            for text, vector in zip(missing, self.embedder.embed(missing)):
                norm = math.sqrt(sum(x * x for x in vector)) or 1.0
                cache[self._key(text)] = [x / norm for x in vector]
            live = {self._key(t) for t in texts}
            cache = {k: v for k, v in cache.items() if k in live}  # statements that no longer exist
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(cache))
        return np.array([cache[self._key(t)] for t in texts], dtype=np.float32), len(missing)

    @staticmethod
    def template(statements: list[Statement]) -> set[str]:
        documents = defaultdict(set)
        for s in statements:
            documents[normalise(s.text)].add(s.source_id)
        return {text for text, where in documents.items() if len(where) >= TEMPLATE_DOCUMENTS}

    def candidates(self, statements: list[Statement], k: int = 3, min_cosine: float = 0.70, k_same: int = 1,
                   exclude_sources: set[str] = frozenset(), group=None) -> tuple[list[Candidate], dict]:
        """The k nearest statements in other documents (as measured in the trial), plus the k_same nearest in
        other sections of the same document; a pair counts once, at or above ``min_cosine``. With ``group``
        (statement -> key), statements in different groups are never paired, for example conversation-style
        records and product records."""
        # Template lines are counted among governed statements only: a sentence two records copy from the evidence
        # they cite is a duplicate between those records, not template text.
        eligible = [s for s in statements if not s.derived and s.source_id not in exclude_sources]
        template = self.template(eligible)
        governed = [s for s in eligible if normalise(s.text) not in template]
        if len(governed) < 2:
            return [], {'governed': len(governed), 'template_lines': len(template), 'embedded': 0, 'same_document': 0}
        matrix, embedded = self.vectors([s.text for s in governed])
        sims = matrix @ matrix.T
        sources = np.array([s.source_id for s in governed])
        sections = np.array([f'{s.source_id}\u0000{s.heading.strip().lower()}' for s in governed])
        same_source = np.equal.outer(sources, sources)
        if group is not None:
            groups = np.array([group(s) for s in governed])
            sims = np.where(np.equal.outer(groups, groups), sims, -1.0)
        other_documents = np.where(same_source, -1.0, sims)
        # Same document, different section: a document contradicting itself (a section is not compared with itself).
        other_sections = np.where(same_source & ~np.equal.outer(sections, sections), sims, -1.0)
        pairs = {}
        for scores, count in ((other_documents, k), (other_sections, k_same)):
            if count <= 0:
                continue
            nearest = np.argsort(-scores, axis=1)[:, :count]
            for i in range(len(governed)):
                for j in (int(x) for x in nearest[i]):
                    if scores[i, j] >= min_cosine:
                        pairs[(min(i, j), max(i, j))] = float(scores[i, j])
        found = [Candidate(governed[i], governed[j], round(c, 4)) for (i, j), c in sorted(pairs.items())]
        return found, {'governed': len(governed), 'template_lines': len(template), 'embedded': embedded,
                       'same_document': sum(1 for c in found if c.same_document)}
