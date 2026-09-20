"""Fictional development probes for local contribution/turn routing."""

import asyncio
import json

from services.sme_interviewer.turn_interpreter import interpret

cases = [
    (
        "agreement",
        "Was approval followed by activation?",
        "Yes, that sequence is correct.",
        "[reported_practice] The manager approved it and I activated it.",
    ),
    ("off_topic", "Who approved activation?", "Purple bananas play chess on the moon.", ""),
    ("unknown", "Which checks did Finance perform?", "I do not know.", ""),
    ("policy", "What does the policy require?", "The policy requires Finance approval before activation.", ""),
    ("pause", "Who approved activation?", "Please pause the interview.", ""),
    ("hesitation", "What happened next?", "Then the manager was about to", ""),
]


async def main():
    out = []
    for label, q, a, h in cases:
        result = await interpret(q, a, h)
        out.append({"case": label, "question": q, "answer": a, "result": result})
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
