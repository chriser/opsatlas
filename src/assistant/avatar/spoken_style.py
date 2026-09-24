"""Shared natural-delivery guidance; content and citation rules stay with callers."""
NATURAL_DELIVERY_RULES = '''Lead with the useful answer in everyday spoken language.
Speak about the subject, not about the retrieval process. Avoid routine openers such as
"the records confirm", "the evidence states", "I can confirm", or "according to the records".
Keep relevant uncertainty, conditions and limitations explicit. Never turn an unknown into a promise.
Mention sources when asked about them or when attribution is necessary; otherwise use the separate citations.
Use short, connected sentences and explain unfamiliar terms. Respond to the question actually asked.'''


def natural_evidence_wording(text):
    """Soften attribution only; preserve the following claim or uncertainty."""
    import re

    text = re.sub(r'\b(?:the (?:approved |available )?records|the evidence) (?:explicitly )?'
                  r'(?:do not|does not) establish\b', "I don't yet have confirmed details on", text, flags=re.I)
    text = re.sub(r'\b(?:the (?:approved |available )?records|the evidence) (?:explicitly )?'
                  r'(?:confirm|confirms|state|states|show|shows)(?: that)?\s+', '', text, flags=re.I)
    return re.sub(r'(^|[.!?]\s+)([a-z])', lambda m: m[1]+m[2].upper(), text)
