"""Explicit English voice controls, not inferred instructions from interview evidence."""

import re


def command(text):
    words = re.sub(r'[.!?,]+$', '', ' '.join(text.casefold().replace('’', "'").replace(",", " ").split())).strip()
    pause = r"(?:please )?(?:pause|stop listening)(?: (?:the |this )?(?:interview|conversation|session))?(?: (?:now|please))?"
    recap = (
        r"(?:(?:please |let us |let's |can we |could we |can i |could i |may i |"
        r"can you |could you |would you |i would like to |i'd like to )?)"
        r"(?:review|see|hear|open|get|have|do|show(?: me)?|give me|read(?: me)?)"
        r"(?: (?:the|our|a|my))? recap(?: (?:now|please|out loud|aloud))?"
        r"(?: please)?"
    )
    if re.fullmatch(pause, words):
        return 'pause'
    noun_request = r"(?:i'd like|i would like|i want)(?: (?:a|the|our))? recap(?: please)?"
    if (re.fullmatch(recap, words) or re.fullmatch(noun_request, words)
            or words in ('recap', 'recap please', 'please recap')):
        return 'recap'
    return 'none'
