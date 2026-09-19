"""Compatibility entry point for the current conversational development scenarios.

The v2 fixed-detail probe and its evidence remain in commit c2b7f4b. Its question-key
repetition assertions do not apply to deeper follow-ups on the same topic.
"""

import asyncio

from .evaluate_conversation import run

if __name__ == "__main__":
    asyncio.run(run())
