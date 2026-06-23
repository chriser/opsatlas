"""Safe spoken-response styling for avatar rendering."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

from ..answer.generator import Generator
from ..answer.service import AnswerResult

AvatarStyleMode = Literal["formal", "natural"]


class AvatarRenderedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: AvatarStyleMode
    rendered_text: str
    render_notes: list[str]


def render_avatar_answer(
    result: AnswerResult,
    style: AvatarStyleMode,
    question: str = "",
    generator: Generator | None = None,
) -> AvatarRenderedAnswer:
    """Return text that may be sent to the avatar renderer.

    Formal mode keeps the canonical answer exact. Natural mode can add
    conversational signposting, but refusal and guardrail outputs stay exact.
    """
    answer = result.answer.strip()
    if style == "formal":
        return AvatarRenderedAnswer(
            style=style,
            rendered_text=answer,
            render_notes=["Canonical assistant answer used without style changes."],
        )

    if result.refused:
        return AvatarRenderedAnswer(
            style=style,
            rendered_text=answer,
            render_notes=["Refusal or compliance-boundary answer preserved exactly."],
        )

    rendered, natural_notes = _natural_spoken_answer(answer, result, question, generator)
    return AvatarRenderedAnswer(
        style=style,
        rendered_text=rendered,
        render_notes=[
            "Rendered canonical answer as a natural spoken overview.",
            "Preserved source reference markers from the approved answer where available.",
            *natural_notes,
        ],
    )


def _natural_spoken_answer(
    answer: str,
    result: AnswerResult,
    question: str,
    generator: Generator | None,
) -> tuple[str, list[str]]:
    if generator is not None:
        try:
            candidate = _clean_natural_output(generator.generate(_natural_spoken_prompt(question, answer)))
        except Exception:  # pragma: no cover - exact provider failures depend on local model/runtime.
            candidate = ""
        if _valid_natural_render(answer, candidate):
            return candidate, [
                "Used constrained LLM natural-spoken renderer over the canonical grounded answer.",
                "Validated rendered citation markers against the canonical answer markers.",
            ]

    fallback = _fallback_natural_answer(answer, result, question)
    return fallback, [
        "Used deterministic natural-spoken fallback because the LLM renderer was unavailable or invalid.",
        "Added a generic follow-up invitation without adding factual claims.",
    ]


def _natural_spoken_prompt(question: str, answer: str) -> str:
    refs = " ".join(_reference_tokens(answer)) or "none"
    return (
        "You are rewriting a grounded knowledge-base answer for a video Avatar to speak.\n"
        "Your job is style only. Do not answer from memory and do not add facts.\n\n"
        "Rules:\n"
        "- Use ONLY the canonical answer below.\n"
        "- Keep the same meaning, controls, owners, systems, conditions and limitations.\n"
        "- Preserve citation markers that appear in the canonical answer, such as [1] or [2].\n"
        "- Do not create new citation markers. Valid markers for this answer: "
        f"{refs}.\n"
        "- If the canonical answer is a list or process, turn it into friendly paragraphs with stages.\n"
        "- Prefer plain spoken language, helpful analogies where they clarify the answer, and a short-version close.\n"
        "- Avoid saying \"approved answer\", \"canonical answer\", \"evidence extract\" or \"as outlined in the evidence\".\n"
        "- Do not use Markdown tables. Avoid numbered lists unless the canonical answer is impossible to understand without them.\n"
        "- Return only the rewritten answer text.\n\n"
        f"USER QUESTION:\n{question.strip() or 'Not provided'}\n\n"
        f"CANONICAL GROUNDED ANSWER:\n{answer}\n\n"
        "NATURAL SPOKEN ANSWER:"
    )


def _clean_natural_output(value: str) -> str:
    text = value.strip()
    text = re.sub(r"^```(?:text|markdown)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = re.sub(r"^\s*(?:NATURAL SPOKEN ANSWER|ANSWER)\s*:\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def _valid_natural_render(answer: str, candidate: str) -> bool:
    if not candidate:
        return False
    if "approved answer" in candidate.lower() or "canonical answer" in candidate.lower():
        return False
    allowed_refs = set(_reference_tokens(answer))
    candidate_refs = set(_reference_tokens(candidate))
    if candidate_refs - allowed_refs:
        return False
    if allowed_refs and not candidate_refs:
        return False
    return True


def _fallback_natural_answer(answer: str, result: AnswerResult, question: str) -> str:
    steps = _numbered_steps(answer)
    if len(steps) >= 3:
        return _process_overview(steps, answer, result, question)
    follow_up = _follow_up_prompt(result)
    return f"Yes — in plain terms, here is what the approved knowledge base says.\n\n{_soften_formal_phrasing(answer)}\n\n{follow_up}"


def _process_overview(steps: list[tuple[str, str]], answer: str, result: AnswerResult, question: str) -> str:
    topic = _topic_hint(question, answer)
    refs = _reference_suffix(answer)
    intro = (
        f"Yes — in plain terms, {topic} is about getting the request captured, checked, created in the right places, "
        "and only released once the required controls are complete."
    )
    first = _step_detail_sentence(steps[0])
    second = _combine_step_sentences(steps[1:3])
    middle = _combine_step_sentences(steps[3:7])
    final = _combine_step_sentences(steps[7:])
    paragraphs = [
        intro,
        f"It starts when {_lower_first(first)}" if first else "",
        f"From there, {second}" if second else "",
        f"Once the request is ready to move forward, {middle}" if middle else "",
        f"Finally, {final}" if final else "",
        f"So the short version is: {_short_version(steps)}.{refs}",
        _follow_up_prompt(result),
    ]
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def _numbered_steps(answer: str) -> list[tuple[str, str]]:
    steps: list[tuple[str, str]] = []
    for line in answer.splitlines():
        match = re.match(r"^\s*\d+\.\s+(?:\*\*)?([^:*–—-]+?)(?:\*\*)?\s*(?::|–|—|-)\s*(.+?)\s*$", line)
        if match:
            steps.append((match.group(1).strip(), match.group(2).strip()))
    return steps


def _step_sentence(step: tuple[str, str]) -> str:
    label, detail = step
    cleaned = _strip_reference(detail.rstrip("."))
    if cleaned:
        return f"{_lower_first(label)}: {_lower_first(cleaned)}."
    return f"{_lower_first(label)}."


def _step_detail_sentence(step: tuple[str, str]) -> str:
    _, detail = step
    return _strip_reference(detail.rstrip("."))


def _combine_step_sentences(steps: list[tuple[str, str]]) -> str:
    if not steps:
        return ""
    sentences = [_step_sentence(step) for step in steps]
    if len(sentences) == 1:
        return sentences[0]
    return " ".join(sentences)


def _short_version(steps: list[tuple[str, str]]) -> str:
    labels = " ".join(label.lower() for label, _ in steps)
    parts: list[str] = []
    for keyword, phrase in [
        ("request", "request it"),
        ("review", "check it"),
        ("due diligence", "approve the checks"),
        ("credit", "approve the checks"),
        ("create", "create it in the right systems"),
        ("map", "link the records together"),
        ("contract", "complete the required links"),
        ("activate", "activate it"),
        ("confirm", "confirm completion"),
    ]:
        if keyword in labels and phrase not in parts:
            parts.append(phrase)
    return ", ".join(parts[:7]) or "capture it, check it, complete the controls, then release it"


def _topic_hint(question: str, answer: str) -> str:
    material = f"{question} {answer}".lower()
    if "supplier" in material:
        return "setting up a supplier"
    if "article" in material:
        return "setting up or changing an article"
    if "process" in material:
        return "this process"
    return "this"


def _reference_suffix(answer: str) -> str:
    unique_refs = _reference_tokens(answer)
    return f" {' '.join(unique_refs[:4])}" if unique_refs else ""


def _reference_tokens(answer: str) -> list[str]:
    refs = re.findall(r"\[\d+\]", answer)
    return list(dict.fromkeys(refs))


def _strip_reference(value: str) -> str:
    return re.sub(r"\s*\[\d+\]", "", value).strip()


def _soften_formal_phrasing(answer: str) -> str:
    softened = answer.replace("as outlined in the evidence", "based on the approved knowledge base")
    return softened.strip()


def _lower_first(value: str) -> str:
    return value[:1].lower() + value[1:] if value else value


def _follow_up_prompt(result: AnswerResult) -> str:
    citation_count = len(result.citations)
    if citation_count:
        citation_word = "citation" if citation_count == 1 else "citations"
        return (
            f"I found {citation_count} supporting {citation_word}. "
            "You can ask about the owner, control, exception, or next step."
        )
    return "You can ask a follow-up about the owner, control, exception, or next step."
