"""Explicit English voice controls, not inferred instructions from interview evidence."""

import re


def command(text):
    words = re.sub(r'[.!?,]+$', '', ' '.join(text.casefold().replace('’', "'").split())).strip()
    pause = r"(?:please )?(?:pause|stop listening)(?: (?:the |this )?(?:interview|conversation|session))?(?: (?:now|please))?"
    recap = (r"(?:(?:please |let us |let's |can we |could we )?)(?:review|see|hear|open)(?: (?:the|our))? recap"
             r"(?: (?:now|please))?")
    if re.fullmatch(pause, words):
        return 'pause'
    if re.fullmatch(recap, words):
        return 'recap'
    return 'none'
