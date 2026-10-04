"""Tibi's turns in the Product Guide's usage analytics (REF S20).

The scorecard, gaps and forecasts read the core usage log, which only written answers fill; Tibi, the busiest channel,
writes its own conversation log. Each turn that heard something is read from that log as a usage entry, never copied
into the usage log, so nothing is counted twice and the conversation log stays the one record of what was said.

How a turn is read, from the values Tibi's engine writes (services/sme_interviewer/tibi.py ``_result``):
- a product or rehearsal question with ``grounding`` ``no_approved_evidence`` was declined for want of approved
  evidence: refused, and a knowledge-gap candidate like a refused written question;
- ``approved_spoken`` and ``grounded_synthesis`` answered from records: grounded;
- ``approved_fallback`` answered with a record's approved wording because nothing generated passed its checks:
  answered, but unverified, so it is a weak-evidence candidate;
- conversation, general, clarify, workspace and self turns, interview answers (no route, or ``governance``), a turn
  refused because the evidence changed, ``evidence_unavailable`` and failed turns cannot show a knowledge gap.
"""
from __future__ import annotations

from datetime import datetime

from assistant.analytics.log import UsageEntry

from . import conversations
from .spaces import PRODUCT

QUESTION_ROUTES = ('product', 'rehearsal')  # the routes on which a knowledge gap can show
GROUNDED = ('approved_spoken', 'grounded_synthesis')
NO_EVIDENCE = 'no_approved_evidence'


def channel(turn: dict) -> str:
    if turn.get('mode') == 'digital_sme':
        return 'digital_sme'
    return 'typed' if turn.get('typed') else 'voice'


def entry(turn: dict, owner: str | None = None) -> UsageEntry | None:
    """One turn as a usage entry; None for a turn that heard nothing, or whose time cannot be read."""
    question, timestamp = str(turn.get('heard') or '').strip(), _iso(turn.get('at'))
    if not question or timestamp is None:
        return None
    route, grounding, outcome = turn.get('route'), turn.get('grounding'), turn.get('outcome') or 'completed'
    records = [r for r in turn.get('records') or [] if r]
    on_question = route in QUESTION_ROUTES and outcome != 'failed'
    declined = on_question and grounding == NO_EVIDENCE
    refused = declined or outcome in ('refused', 'failed') or grounding in ('evidence_unavailable', 'evidence_changed')
    if grounding in GROUNDED and records:
        confidence = 'grounded'
    elif grounding == 'approved_fallback':
        confidence = 'unverified'
    else:
        confidence = 'none'
    return UsageEntry(
        id=f"tibi:{turn.get('session')}:{turn.get('turn')}", timestamp=timestamp, question=question,
        mode=str(turn.get('mode') or 'chat'), answer_path='tibi', refused=refused, actor_id=owner, space=PRODUCT,
        confidence=confidence, citation_count=len(records), channel=channel(turn),
        gap_eligible=on_question and (declined or grounding in GROUNDED or grounding == 'approved_fallback'),
    )


def entries(root, owners=None, days: int = 365) -> list[UsageEntry]:
    """Every turn of the last ``days`` that heard something, with who started its conversation where known."""
    known = owners.all() if owners is not None else {}
    rows = (entry(t, known.get(str(t.get('session')))) for t in conversations.turns(root, days))
    return [row for row in rows if row is not None]


def _iso(value) -> str | None:
    """Tibi writes ``2026-10-03T09:30:00+0100``; the analytics expect ISO-8601 with a colon in the offset. None for a
    time that cannot be read, so the turn is left out rather than breaking the time series."""
    text = str(value or '')
    for parse in (lambda t: datetime.strptime(t, '%Y-%m-%dT%H:%M:%S%z'), datetime.fromisoformat):
        try:
            return parse(text).isoformat()
        except ValueError:
            continue
    return None
