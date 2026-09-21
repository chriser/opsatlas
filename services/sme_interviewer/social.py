"""Conservative, CPU-only listener policy. Social acts never assert process facts.

Only complete, explicit conversational requests bypass the content reasoner.
Unrecognised/mixed utterances remain intact for that reasoner. Silence is a
valid action; elapsed silence alone is never evidence of distress.
"""

import re
from dataclasses import dataclass

PHRASES = {
    'wait': ('Of course. Take your time.', 'There is no rush.'),
    'reassure': ('No need to apologise. We have time.', 'That is all right. Take it at your own pace.'),
    'correction': ('Thanks for stopping me. What should I change?', 'Let me hear the correction.'),
    'quiet': ('Of course. I will leave you space to think.',),
    'encourage': ('Of course. I can offer a little encouragement.',),
    'thanks': ('You are welcome.',),
}
PATTERNS = {
    'wait': r'(?:please )?(?:give me (?:a second|a moment|a minute)|let me think|bear with me'
             r'|i need (?:a moment|a minute|some time)(?: to think)?|i am trying to remember)(?:[, ]+please)?',
    'reassure': r'(?:sorry[, ]+)?(?:i(?: am|\x27m) (?:rambling|taking so long|struggling to explain(?: this)?)'
                  r'|this is hard to explain)|sorry (?:for rambling|this is taking so long)',
    'correction': r'(?:no[, ]+)?(?:that(?: is|\x27s) not what i meant|you misunderstood me|i need to correct (?:that|something))',
    'quiet': r'(?:please )?(?:stop (?:the )?(?:encouragement|reassurances)|stay quiet while i think'
              r'|let me think in silence|do not fill (?:the )?pauses)(?:[, ]+please)?',
    'encourage': r'(?:please )?(?:you can encourage me|a little encouragement would help|turn encouragement back on)',
    'thanks': r'(?:thanks|thank you)(?: for (?:waiting|being patient))?',
}


def intent(text):
    text = ' '.join(text.casefold().replace('’', "'").split()).strip(' .!?')
    if len(text) > 180:
        return None
    for action, pattern in PATTERNS.items():
        if re.fullmatch(pattern, text):
            return action
    return None


@dataclass(frozen=True)
class Action:
    kind: str
    text: str
    generation: int
    expires: float


class Listener:
    def __init__(self, saved=None):
        saved = saved or {}
        self.quiet = bool(saved.get('quiet', False))
        self.counts = dict(saved.get('counts', {}))
        self.last_kind = None
        self.last_at = float('-inf')

    def snapshot(self):
        return {'quiet': self.quiet, 'counts': {k: min(int(v), 10000) for k, v in self.counts.items() if k in PHRASES}}

    def decide(self, text, generation, now):
        kind = intent(text)
        if kind is None:
            return None
        # Repeated requests for thinking time need no repeated spoken reply.
        silent = ((self.quiet and kind in ('wait', 'reassure', 'thanks')) or
                  (kind == self.last_kind and now - self.last_at < 30))
        options = PHRASES[kind]
        wording = '' if silent else options[self.counts.get(kind, 0) % len(options)]
        return Action(kind, wording, generation, now + 2)

    def committed(self, action, now):
        if action.kind == "quiet":
            self.quiet = True
        elif action.kind == "encourage":
            self.quiet = False
        self.last_kind, self.last_at = action.kind, now
        if action.text:
            self.counts[action.kind] = self.counts.get(action.kind, 0) + 1

    @staticmethod
    def valid(action, generation, now):
        return action.generation == generation and now <= action.expires
