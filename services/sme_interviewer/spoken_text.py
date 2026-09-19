"""Deterministic speech rendering; never rewrite captured/displayed transcripts.

Expand explicit sterling amounts using British English. Unsupported forms (such
as currency abbreviations, malformed grouping or more than two decimal places)
remain untouched rather than guessing their value.
"""

import re

POLICY_VERSION = "en-gb-sterling-v1"
_SMALL = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
)
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
_STERLING = re.compile(
    r"(?<![\w£.,+−-])(?P<sign>[+−-]?)£[ \t]*"
    r"(?P<amount>(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]{1,2})?)"
    r"(?!\w|[,.][0-9])"
)


def _words(value: int) -> str:
    if value < 20:
        return _SMALL[value]
    if value < 100:
        tens, rest = divmod(value, 10)
        return _TENS[tens] + ("-" + _SMALL[rest] if rest else "")
    if value < 1000:
        hundreds, rest = divmod(value, 100)
        return _SMALL[hundreds] + " hundred" + (" and " + _words(rest) if rest else "")
    for scale, name in ((1_000_000_000, "billion"), (1_000_000, "million"), (1000, "thousand")):
        if value >= scale:
            count, rest = divmod(value, scale)
            tail = (" and " if rest < 100 else " ") + _words(rest) if rest else ""
            return _words(count) + " " + name + tail
    raise ValueError("Unsupported amount")


def for_speech(text: str) -> str:
    def expand(match: re.Match) -> str:
        whole, _, fraction = match["amount"].replace(",", "").partition(".")
        if len(whole) > 12:
            return match[0]
        pounds = int(whole)
        pence = int(fraction.ljust(2, "0")) if fraction else 0
        parts = []
        if pounds or not pence:
            parts.append(_words(pounds) + (" pound" if pounds == 1 else " pounds"))
        if pence:
            parts.append(_words(pence) + (" penny" if pence == 1 else " pence"))
        sign = {"-": "minus ", "−": "minus ", "+": "plus ", "": ""}[match["sign"]]
        return sign + " and ".join(parts)

    return _STERLING.sub(expand, text)
