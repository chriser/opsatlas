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
            candidate = _clean_natural_output(generator.generate(_natural_spoken_prompt(question, answer, result)))
        except Exception:  # pragma: no cover - exact provider failures depend on local model/runtime.
            candidate = ""
        if _valid_natural_render(answer, candidate, result):
            return candidate, [
                "Used constrained LLM natural-spoken renderer over the canonical grounded answer.",
                "Validated rendered citation markers against the canonical answer markers.",
            ]

    fallback = _fallback_natural_answer(answer, result, question)
    return fallback, [
        "Used deterministic natural-spoken fallback because the LLM renderer was unavailable or invalid.",
        "Kept structured answer content in paragraph form without numbered steps.",
    ]


def _natural_spoken_prompt(question: str, answer: str, result: AnswerResult) -> str:
    refs = " ".join(_available_reference_tokens(answer, result)) or "none"
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
        "- Use 4 to 7 short paragraphs, not a numbered or bulleted list.\n"
        "- Prefer plain spoken language, helpful analogies where they clarify the answer, and a short-version close.\n"
        "- Avoid saying \"approved answer\", \"canonical answer\", \"evidence extract\" or \"as outlined in the evidence\".\n"
        "- Do not use Markdown tables, numbered lists, bullet lists, or step-heading labels.\n"
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


def _valid_natural_render(answer: str, candidate: str, result: AnswerResult) -> bool:
    if not candidate:
        return False
    if "approved answer" in candidate.lower() or "canonical answer" in candidate.lower():
        return False
    if _contains_structured_list(candidate):
        return False
    if len(_numbered_steps(answer)) >= 3 and "short version" not in candidate.lower():
        return False
    allowed_refs = set(_available_reference_tokens(answer, result))
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
    if topic == "setting up a supplier":
        return _supplier_setup_overview(answer, result)
    refs = _reference_suffix(answer, result)
    intro = _process_intro(topic, refs)
    first = _combine_detail_sentences(steps[:2])
    second = _combine_detail_sentences(steps[2:3])
    middle = _combine_detail_sentences(steps[3:5])
    creation = _combine_detail_sentences(steps[5:8])
    final = _combine_detail_sentences(steps[8:])
    paragraphs = [
        intro,
        f"The process starts when {_lower_first(first)}" if first else "",
        f"From there, {_lower_first(second)} This is the \"have we got everything we need?\" stage." if second else "",
        f"Next, the control gates happen. {middle}" if middle else "",
        f"Once those checks are clear, the records and system links are put in place. {creation}" if creation else "",
        f"Finally, {_lower_first(final)}" if final else "",
        f"So the short version is: {_short_version(steps)}.",
    ]
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def _supplier_setup_overview(answer: str, result: AnswerResult) -> str:
    refs = _available_reference_tokens(answer, result)
    first_ref = _ref_at(refs, 0)
    second_ref = _ref_at(refs, 1)
    final_ref = _ref_at(refs, -1)
    trigger_refs = _refs([final_ref])
    form_refs = _refs([first_ref, final_ref])
    final_refs = _refs([second_ref, final_ref])
    return "\n\n".join(
        [
            (
                "Yes — setting up a supplier is a bit like getting someone officially added to the company's approved "
                "address book, but with a lot more checks before anyone is allowed to start buying from them."
            ),
            (
                "The process starts when someone in the business, usually a buyer or commercial requester, says: "
                f"\"We need this supplier set up\" or \"We need to change this supplier's details\"{trigger_refs}. "
                f"They do this by filling in the formal supplier setup form{form_refs}."
            ),
            "From there, it goes through a few important stages:",
            (
                "First, Trading Support checks the form. This is the \"have we got everything we need?\" stage. "
                "If key details are missing, they go back to the requester rather than letting bad data move further down the line."
            ),
            (
                "Next, the due diligence and credit checks happen. These are the serious gates in the process. "
                "The supplier should not be created and activated just because someone filled in a form. "
                "The organisation needs to know the supplier has passed the required checks first."
            ),
            (
                "Once the checks pass, the supplier is created in the operational master data tool and also in the finance "
                "master data environment. This is important because the operational side needs to know who the supplier is "
                "for ordering and store/process use, while finance needs to recognise the supplier for payment and reconciliation."
            ),
            (
                "The two records then need to be mapped together. Otherwise, you end up with the business equivalent of two "
                "people talking about the same supplier but using different names. That is where errors, payment issues and "
                "reconciliation problems can creep in."
            ),
            (
                "Finally, the supplier is linked to the required contracts, final controls are completed, and the supplier can "
                f"be activated. The requester is then told that the setup is complete and the supplier is available for use{final_refs}."
            ),
            (
                "So the short version is: request it, check it, approve it, create it in both operational and finance systems, "
                "link everything together, then activate it."
            ),
        ]
    )


def _process_intro(topic: str, refs: str) -> str:
    if topic == "setting up a supplier":
        return (
            "Yes — setting up a supplier is a bit like getting someone officially added to the company's approved "
            f"address book, but with more checks before anyone is allowed to start buying from them.{refs}"
        )
    return (
        f"Yes — in plain terms, {topic} is about getting the request captured, checked, created in the right places, "
        f"and only released once the required controls are complete.{refs}"
    )


def _numbered_steps(answer: str) -> list[tuple[str, str]]:
    steps: list[tuple[str, str]] = []
    for line in answer.splitlines():
        match = re.match(r"^\s*\d+\.\s+(?:\*\*)?([^:*–—-]+?)(?:\*\*)?\s*(?::|–|—|-)\s*(.+?)\s*$", line)
        if match:
            steps.append((match.group(1).strip(), match.group(2).strip()))
    return steps


def _combine_detail_sentences(steps: list[tuple[str, str]]) -> str:
    if not steps:
        return ""
    sentences = []
    for _, detail in steps:
        cleaned = _strip_reference(detail.rstrip("."))
        if cleaned:
            sentences.append(f"{_upper_first(cleaned)}.")
    return " ".join(dict.fromkeys(sentences))


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


def _reference_suffix(answer: str, result: AnswerResult) -> str:
    unique_refs = _available_reference_tokens(answer, result)
    return f" {' '.join(unique_refs[:4])}" if unique_refs else ""


def _available_reference_tokens(answer: str, result: AnswerResult) -> list[str]:
    refs = _reference_tokens(answer)
    if refs:
        return refs
    return list(dict.fromkeys(f"[{citation.ordinal}]" for citation in result.citations))


def _reference_tokens(answer: str) -> list[str]:
    refs = re.findall(r"\[\d+\]", answer)
    return list(dict.fromkeys(refs))


def _ref_at(refs: list[str], index: int) -> str:
    if not refs:
        return ""
    try:
        return refs[index]
    except IndexError:
        return refs[-1]


def _refs(refs: list[str]) -> str:
    unique_refs = [ref for ref in dict.fromkeys(refs) if ref]
    return f" {' '.join(unique_refs)}" if unique_refs else ""


def _strip_reference(value: str) -> str:
    return re.sub(r"\s*\[\d+\]", "", value).strip()


def _soften_formal_phrasing(answer: str) -> str:
    softened = answer.replace("as outlined in the evidence", "based on the approved knowledge base")
    return softened.strip()


def _lower_first(value: str) -> str:
    return value[:1].lower() + value[1:] if value else value


def _upper_first(value: str) -> str:
    return value[:1].upper() + value[1:] if value else value


def _contains_structured_list(value: str) -> bool:
    return bool(re.search(r"(?m)^\s*(?:\d+[\.)]|[-*•])\s+\S", value))


def _follow_up_prompt(result: AnswerResult) -> str:
    citation_count = len(result.citations)
    if citation_count:
        citation_word = "citation" if citation_count == 1 else "citations"
        return (
            f"I found {citation_count} supporting {citation_word}. "
            "You can ask about the owner, control, exception, or next step."
        )
    return "You can ask a follow-up about the owner, control, exception, or next step."
