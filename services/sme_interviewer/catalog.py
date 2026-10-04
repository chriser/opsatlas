"""Versioned, synthetic speech audition; choices are not acceptance decisions."""

DEFAULT_VOICE = "B"

# Voice B is the Higgs voice. Every worker request names B (speech.py); the worker's engine (higgs or
# higgs_female) chooses the reference speaker, so these fields describe the default, male voice.
VOICES = {
    "B": {"engine": "higgs", "voice": "p254", "speed": 1.0, "name": "Higgs · British male reference", "quantisation": "bf16"},
}
PROMPTS = [
    {
        "id": "welcome",
        "label": "Welcome",
        "text": "Hello. We will work through one example together. You can pause, correct me, or leave a question open at any time.",
    },
    {
        "id": "story",
        "label": "An open question",
        "text": "Think of a recent supplier activation. What happened, from the first request through to the final approval?",
    },
    {
        "id": "reflect",
        "label": "Reflective listening",
        "text": "So the request arrived before the checks were complete, and your team held it back. Have I understood that correctly?",
    },
    {
        "id": "challenge",
        "label": "A gentle challenge",
        "text": (
            "There may be a difference worth exploring. The current guide names Finance as the approver. "
            "Does your example follow an emergency exception?"
        ),
    },
    {
        "id": "unknown",
        "label": "Leaving room for uncertainty",
        "text": "That is fine. We can leave this point open and identify the right person to ask. You do not need to guess.",
    },
    {
        "id": "numbers",
        "label": "Numbers and negation",
        "text": "The limit is fifteen thousand pounds, not fifty thousand. Approval is required before activation, not after it.",
    },
    {
        "id": "dates",
        "label": "Dates",
        "text": "This version takes effect on the third of October, twenty twenty-six. Was your example before or after that date?",
    },
    {
        "id": "acronyms",
        "label": "Acronyms",
        "text": "The SME reviews the ERP record. We will keep the VAT check separate from the final approval.",
    },
    {
        "id": "timeline",
        "label": "Checking the sequence",
        "text": "Let me check the order. First the request arrived, then you checked the evidence, and finally the owner approved it.",
    },
    {
        "id": "cues",
        "label": "Eliciting expertise",
        "text": "What did you notice at that point that told you this request needed a closer look?",
    },
    {
        "id": "alternatives",
        "label": "Alternatives",
        "text": "What other options did you consider, and what made this one appropriate in that situation?",
    },
    {
        "id": "hypothetical",
        "label": "A hypothetical",
        "text": "As a hypothetical example, if the usual approver were unavailable, what would you expect to happen?",
    },
    {
        "id": "correction",
        "label": "Accepting correction",
        "text": "Thank you for correcting the sequence. I will keep your revised account and revisit the conclusions that depended on it.",
    },
    {"id": "pause", "label": "A pause", "text": "Of course. Let us pause here. We can pick up from this point when you are ready."},
    {
        "id": "difference",
        "label": "Compatible variants",
        "text": (
            "These descriptions may both be valid under different conditions. Which region and process version does your example belong to?"
        ),
    },
    {
        "id": "review",
        "label": "Review completeness",
        "text": "I have captured the account. The wider evidence review is still pending, so I cannot call this point verified yet.",
    },
    {
        "id": "owner",
        "label": "Finding an owner",
        "text": "Who would be best placed to confirm this exception? I can include a follow-up question in the draft.",
    },
    {
        "id": "summary",
        "label": "Summary",
        "text": "We have a clear sequence, two exceptions and one unanswered ownership question. What would you change in that summary?",
    },
    {"id": "short", "label": "A short response", "text": "I understand. Please go on."},
    {
        "id": "close",
        "label": "Closing",
        "text": (
            "Thank you. You can review and correct the draft before an accountable owner decides what should become approved knowledge."
        ),
    },
    {"id": "think-1", "label": "Thinking cue one", "text": "Give me a moment. I am considering what you have just said."},
    {"id": "think-2", "label": "Thinking cue two", "text": "I am checking what we have already covered."},
    {"id": "think-3", "label": "Thinking cue three", "text": "I am finding the clearest next question."},
]
BY_PROMPT = {prompt["id"]: prompt for prompt in PROMPTS}
