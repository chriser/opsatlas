"""Query rewriting — turn a user question into a standalone search query.

Improves retrieval once the corpus is large enough to use retrieval mode. Uses
the model provider; falls back to the original question on any failure.
"""

from __future__ import annotations

from ..answer.generator import Generator

_REWRITE_PROMPT = (
    "Rewrite the user's question as a concise, standalone search query that captures "
    "the key entities and intent. Resolve vague references. Return ONLY the query, one line.\n\n"
    "Question: {q}\nQuery:"
)
_MAX_LEN = 200


class QueryRewriter:
    def __init__(self, generator: Generator) -> None:
        self.generator = generator

    def rewrite(self, question: str) -> str:
        try:
            out = self.generator.generate(_REWRITE_PROMPT.format(q=question)).strip()
        except Exception:
            return question
        out = out.splitlines()[0].strip() if out else ""
        # Fall back if the model returned nothing useful or rambled.
        if not out or len(out) > _MAX_LEN:
            return question
        return out
