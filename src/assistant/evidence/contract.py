"""One evidence contract for both answer paths (REF S19).

OpsAtlas has two answer engines and keeps both: the core's answer service (Written Query, the Ask page) and Tibi's
engine over curated records (voice, the Digital SME, rehearsal), because voice needs its own model and latency. What
they share is this contract, so the guarantees are the same whichever engine speaks:

- the request: who is asking, which spaces they may use, the question, when, on which channel;
- the evidence: only authorised passages, records or facts, each with its source, space, the version and SHA-256 of
  what it rests on, and whether it passed the relevance threshold;
- the decision: answer when some evidence is relevant, refuse (with the space's refusal) when none is; the space's
  referral sentence travels with it, so every channel can point to the sales team the same way;
- delivery: before an answer is shown or spoken, the evidence is checked again (still readable, same versions).

The written path records its bundle in the answer's receipt (REF S18); Tibi's product contract (/api/sales/search)
returns it with the ranked records. tests/test_channel_conformance.py holds both to it.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class EvidenceRequest(BaseModel):
    person: str | None
    spaces: list[str]
    question_sha256: str
    asked_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    channel: Literal["written", "voice", "digital_sme", "typed", "service"]


class EvidenceItem(BaseModel):
    kind: Literal["passage", "record", "object"]
    source_id: str
    space: str | None
    title: str
    locator: str = ""  # where in the source: a heading and position, or a record id
    version: int | None = None
    sha256: str | None = None
    relevant: bool = True


class EvidenceBundle(BaseModel):
    request: EvidenceRequest
    items: list[EvidenceItem]
    trace_id: str = Field(default_factory=lambda: f"ev-{uuid.uuid4().hex[:16]}")
    refusal: str
    referral: str | None = None
    referral_topics: list[str] = []  # the topics an answer ends with the referral on
    statements: dict = {}  # the governed sentences above, by key: their version and hash (REF S22)

    @property
    def decision(self) -> Literal["answer", "refuse"]:
        return "answer" if any(item.relevant for item in self.items) else "refuse"

    def recheck(self, may_read: Callable[[EvidenceItem], bool], version_of: Callable[[EvidenceItem], str | None]) -> bool:
        """At delivery: every item still readable by the person and still the version it was when retrieved."""
        return all(may_read(item) and (item.sha256 is None or version_of(item) in (None, item.sha256)) for item in self.items)

    def summary(self) -> dict:
        return {"trace_id": self.trace_id, "decision": self.decision, "spaces": self.request.spaces,
                "relevant": sum(item.relevant for item in self.items), "considered": len(self.items),
                "refusal": self.refusal, "referral": self.referral, "referral_topics": self.referral_topics,
                "statements": self.statements}
