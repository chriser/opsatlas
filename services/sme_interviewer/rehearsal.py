"""Sales rehearsal (TIBI E3, REH F1): Tibi listens to the pitch as meeting context and helps only when asked.

The salesperson pitches; what they and the customer say is meeting context, heard but not answered. When they ask
(the Ask Tibi button, the T key, or, with name listening on, "Tibi, ..."), the request is one of:

* "What have I missed?"  → one or two points from the approved records the meeting has not covered yet;
* "Explain that more simply." → the last point, in plain words;
* "Help me answer that question." → the customer's last question, answered;
* "Give an example relevant to this customer." → an example for the customer's context;
* anything else → answered as a question, with the meeting as context.

Every reply goes through Tibi's evidence path: approved records only, each sentence checked and cited. It is brief
and ends without a question, so the floor returns to the salesperson. Meeting lines never become product claims or
proposals, and they are kept only for this rehearsal unless the Human chooses to keep a transcript.
"""
from __future__ import annotations

import re
from collections import deque

import httpx

from services.opsatlas_sales import claims

from .tibi import Route, Tibi, content_words

BRIEF = ('You help a salesperson in a live meeting with their customer. One or two short sentences, under 250 '
         'characters, then stop: no question. Records only. Say plainly what is planned rather than available.')
VOICES = {
    'missed': BRIEF + ' They asked what their pitch has missed. From the approved records, name the one or two most '
                      'useful points the meeting so far has not mentioned, as points they could add.',
    'simpler': BRIEF + ' Say the point in the question more simply, in plain words someone outside the field would use. '
                       'Add nothing the records do not say.',
    'answer': BRIEF + " Answer the customer's question (the question field) directly, for the customer to hear.",
    'example': BRIEF + ' Give one concrete example, from the approved records, of how OpsAtlas could help this customer. '
                       'Say it is an example, not a commitment.',
    'ask': BRIEF + " Answer the salesperson's question.",
}
INTENTS = (
    ('missed', re.compile(r"\b(?:what (?:have|did) I (?:missed|miss|left out|forgotten|forget)|anything I(?:'ve| have)? "
                          r"(?:missed|left out)|what else should I (?:mention|say|cover)|what did I miss)\b", re.I)),
    ('simpler', re.compile(r"\b(?:more simply|simpler|in plain (?:english|words)|simplif(?:y|ied)|layman'?s? terms|"
                           r"explain (?:that|it|this) (?:again|better|differently))\b", re.I)),
    ('answer', re.compile(r"\b(?:help me (?:to )?answer|answer (?:that|the|their|his|her) question|how (?:do|should|would|"
                          r"can) I answer|what(?:'s| is| would be) (?:a good|the|my) answer)\b", re.I)),
    ('example', re.compile(r"\b(?:(?:give|share|offer) (?:me |them |us )?an? (?:good |concrete |relevant )?example|an example "
                           r"(?:for|relevant|of|that)|use case for|for this customer)\b", re.I)),
)
CUSTOMER = re.compile(r"\b(?:we(?:'re| are)|our|my team|at our|we have|we run|we use)\b", re.I)


def intent_of(request: str) -> str:
    return next((name for name, pattern in INTENTS if pattern.search(request)), 'ask')


class RehearsalCoach(Tibi):
    # Said as it is (audit F12): the meeting is not kept without a transcript, but requests and replies are logged.
    opening = ("Rehearsal mode. I'm listening to the meeting and I'll help when you ask. The meeting itself isn't kept "
               "unless you keep a transcript; what you ask me and what I say are kept in the conversation log.")

    def __init__(self, history, credential, base_url='http://127.0.0.1:8780', customer=''):
        super().__init__(history, credential, base_url)
        self.meeting = deque(maxlen=80)
        self.customer = ' '.join(str(customer or '').split())[:200]
        self.lines_since_reply = 0

    # ---- the meeting --------------------------------------------------------------------------------------------

    def observe(self, text: str) -> None:
        """A line of the meeting: context for later requests, never answered and never knowledge."""
        text = ' '.join((text or '').split())
        if text:
            self.meeting.append(text)
            self.lines_since_reply += 1

    def commit(self, text, reply, route=None, clarify=None):
        super().commit(text, reply, route, clarify)
        self.lines_since_reply = 0

    def meeting_so_far(self, limit: int = 900) -> list[str]:
        """The recent meeting, newest last: enough to resolve "that question", and short, because every character
        is read before Tibi speaks (1,800 characters cost about 0.6 s on the local model)."""
        lines, total = [], 0
        for line in reversed(self.meeting):
            total += len(line)
            if total > limit and lines:
                break
            lines.insert(0, line)
        return lines

    def last_question(self) -> str | None:
        """The customer's most recent question in the meeting."""
        return next((line for line in reversed(self.meeting) if claims.question_form(claims.focus(line))), None)

    def last_point(self) -> str | None:
        """The point to explain more simply: Tibi's own last reply if it was the last word, else the last product point."""
        if self.history and self.history[-1]['role'] == 'assistant' and self.lines_since_reply == 0:
            return self.history[-1]['content']
        return next((line for line in reversed(self.meeting)
                     if claims.product_claim(line) or claims.PRODUCT_NAMES.search(line)), self.meeting[-1] if self.meeting else None)

    def customer_context(self) -> str:
        said = [line for line in self.meeting if CUSTOMER.search(line) or claims.adoption_question(line)][-3:]
        return '; '.join([*([self.customer] if self.customer else []), *said])

    # ---- requests -----------------------------------------------------------------------------------------------

    async def route(self, text):
        """A request to Tibi, shaped by what it asks for and what the meeting has said."""
        intent = intent_of(text)
        question, search = text, text
        if intent == 'answer':
            question = self.last_question() or text
            search = question
        elif intent == 'simpler':
            point = self.last_point()
            question, search = (f'Explain more simply: {point}', point) if point else (text, text)
        elif intent == 'missed':
            question = 'Which important points about OpsAtlas has the meeting so far not covered?'
            search = ' '.join(self.meeting_so_far(600)) or 'What is OpsAtlas?'
        elif intent == 'example':
            situation = self.customer_context()
            question = f'An example of how OpsAtlas could help this customer: {situation or "a prospective customer"}'
            # Searched by their situation, not the word "customer", which finds the commercial disclaimers.
            search = f'{situation} use cases' if situation else 'OpsAtlas use cases for operations teams'
        try:
            ranking = await self.evidence.search(search)
        except (httpx.HTTPError, ValueError, KeyError):
            ranking = None
        if intent == 'missed' and ranking is not None:
            ranking = self._uncovered(ranking)
        elif ranking is not None:
            ranking = self._widened(ranking)
        context = {'meeting_so_far': self.meeting_so_far(), **({'customer': self.customer_context()} if self.customer_context() else {})}
        return Route('rehearsal', [f'rehearsal: {intent}'], ranking, question=question, voice=VOICES[intent], context=context)

    @staticmethod
    def _widened(ranking: dict, keep: int = 3) -> dict:
        """The three closest records by meaning. A meeting's questions are indirect ("how do you make sure staff don't
        get out-of-date answers?" is about governance, which came fifth), so one record is too narrow; the
        sentence checks still hold every word to what these records say."""
        closeness = lambda r: r['similarity'] if r.get('similarity') is not None else r.get('score', 0)  # noqa: E731
        results = sorted(ranking.get('results', []), key=lambda r: -closeness(r))
        return {**ranking, 'results': [{**r, 'relevant': True} for r in results[:keep]] + results[keep:]}

    def _uncovered(self, ranking: dict) -> dict:
        """For "what have I missed?": the approved product records the meeting has said least about."""
        heard = content_words(' '.join(self.meeting))
        product = [r for r in self.evidence.records.values() if r.get('kind') != 'conversation']

        def weight(item):
            # Least covered first; among those, the curated records earlier in the set (what OpsAtlas is and does
            # before evaluations and road maps) and what is available today before what is planned.
            n, record = item
            words = content_words(record['title'] + ' ' + record['text'])
            return len(words & heard) / max(1, len(words)) + n * 0.015 + (0.2 if claims.qualifier_for([record]) else 0)
        chosen = [r for _, r in sorted(enumerate(product), key=weight)[:3]]
        return {**ranking, 'ontology': {}, 'results': [{'id': r['id'], 'relevant': True, 'similarity': 1.0, 'score': 1.0,
                                                        'lexical': 1.0} for r in chosen]}
