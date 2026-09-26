"""Name activation for the sales rehearsal (REH S8, S9): is an utterance addressed to Tibi, and is it Tibi's own echo?

A distinctive name helps but does not make wake detection reliable, so the rules are deliberately narrow:

* the name counts when it is addressed to Tibi, at the start of an utterance or of a later sentence ("Tibi, what have I
  missed?", "Hey Tiberius, ...", "... forty branches. Tibi, what have I missed?") or after a comma at the end ("What
  have I missed, Tibi?"), never in passing ("I told Tibi about it", "Tibi's voice is good", "Tibi is our assistant");
* speech recognition does not always spell the name the same way, so the common mis-hearings count too
  (measured by services/sme_interviewer/evaluate_wake.py, which also counts near-misses such as "Toby" and "TV");
* the name alone ("Tibi?") makes the next utterance the request;
* while Tibi speaks and just after, what the microphone hears of Tibi's own reply is its echo, never a request and
  never meeting context.
"""
from __future__ import annotations

import re

# "Tibi" as speech recognition writes it; "Toby", "Tabby", "TV" and "Tiber" are deliberately not here. The spoken test
# (evaluate_wake.py, 26 September 2026) heard "Tiberius" as "Tibiarius" and "Tibi" as "Tb"; the name must still be
# addressed to Tibi, so "TB is ..." does not count.
NAME = (r"(?:t(?:i|ee|e)bb?(?:y|ie|i|ee)|tibi|tibbie|tib[a-z]{0,4}r[a-z]{0,3}us|teebee|tee\s*bee|t\.?\s?b\b\.?)")
# Greetings run into the name ("OkTibi", "OKTb"), and "Hey Tibi" was heard as "ATB": separated before matching.
FUSED = re.compile(r"^(\W*)(ok(?:ay)?|hey|hi)(?=t(?:i|ee)?b)", re.I)
HEY_TB = re.compile(r"^(\W*)a\s?tb\b", re.I)
LEAD = r"(?:hey|hi|hello|ok|okay|right|so|and|now|please|excuse me|sorry|oh)"
# After the name, what shows it is addressed: a pause mark, or a request ("Tibi what have I missed").
ASKING = (r"(?:what|how|can|could|would|will|give|help|explain|tell|say|show|please|do|does|why|when|where|which|who|"
          r"any|have|summari[sz]e|remind|repeat)")
VOCATIVE = re.compile(
    rf"^\W*(?:(?P<lead>(?:{LEAD}[\s,.!]+)+){NAME}(?!['’]s)\b[\s,.!?:;—–-]*(?P<led>.*)"
    rf"|{NAME}(?!['’]s)(?:\s*[,.!?:;—–-]+\s*|\s*$)(?P<marked>.*)"
    rf"|{NAME}\s+(?P<asked>{ASKING}\b.*))$", re.I | re.S)
# At the end only as a vocative, after a comma: "What have I missed, Tibi?" but not "I told Tibi".
END = re.compile(rf"^(?P<rest>.*?),\s*{NAME}\W*$", re.I | re.S)
SENTENCE = re.compile(r"(?<=[.!?])\s+")
WORD = re.compile(r"[a-z']+")


def _vocative(text: str):
    match = VOCATIVE.match(text)
    if not match:
        return None
    return next(g for g in (match.group('led'), match.group('marked'), match.group('asked')) if g is not None).strip()


def addressed(text: str) -> tuple[bool, str]:
    """(whether ``text`` is addressed to Tibi, the request without the name). The request may be empty: the name alone.

    The name must be addressed to Tibi: after "hey" or "OK", or followed by a pause mark or a request ("Tibi, what
    have I missed?", "Tibi what have I missed?"), at the start of the utterance or of a later sentence ("... forty
    branches. Tibi, what have I missed?"), or after a comma at the end ("What have I missed, Tibi?")."""
    text = HEY_TB.sub(r"\1hey tb", FUSED.sub(r"\1\2 ", (text or '').strip()))
    parts = SENTENCE.split(text)
    for n in range(len(parts)):
        request = _vocative(' '.join(parts[n:]))
        if request is not None:
            return True, request
    if (match := END.match(text)) and len(WORD.findall(match.group('rest').lower())) >= 2:
        return True, match.group('rest').strip().rstrip(',')
    return False, text


def echo_of(heard: str, reply: str, threshold: float = 0.6) -> bool:
    """Whether ``heard`` is mostly words from Tibi's own ``reply``, as a speakerphone lets the microphone hear it."""
    heard_words = WORD.findall((heard or '').lower())
    reply_words = set(WORD.findall((reply or '').lower()))
    if len(heard_words) < 3 or not reply_words:
        return False
    return sum(1 for w in heard_words if w in reply_words) / len(heard_words) >= threshold
