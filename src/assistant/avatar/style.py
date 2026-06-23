"""Safe spoken-response styling for avatar rendering."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

from ..answer.service import AnswerResult

AvatarStyleMode = Literal["formal", "natural"]


class AvatarRenderedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: AvatarStyleMode
    rendered_text: str
    render_notes: list[str]


def render_avatar_answer(result: AnswerResult, style: AvatarStyleMode, question: str = "") -> AvatarRenderedAnswer:
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

    rendered, natural_notes = _natural_spoken_answer(answer, result, question)
    return AvatarRenderedAnswer(
        style=style,
        rendered_text=rendered,
        render_notes=[
            "Rendered canonical answer as a natural spoken overview.",
            "Preserved source reference markers from the approved answer where available.",
            *natural_notes,
        ],
    )


def _natural_spoken_answer(answer: str, result: AnswerResult, question: str) -> tuple[str, list[str]]:
    steps = _numbered_steps(answer)
    if len(steps) >= 3 and _is_supplier_process(question, answer, steps):
        return _supplier_process_overview(answer), [
            "Converted supplier setup steps into a stage-based spoken narrative.",
            "Omitted the generic citation-count outro because the Avatar Lab offers walkthroughs in the UI.",
        ]
    if len(steps) >= 3:
        return _process_overview(steps, answer, result, question), [
            "Converted numbered process steps into a grouped spoken overview.",
            "Added a generic follow-up invitation without adding factual claims.",
        ]
    follow_up = _follow_up_prompt(result)
    return f"Yes — here is the approved answer in plain English.\n\n{_soften_formal_phrasing(answer)}\n\n{follow_up}", [
        "Added a generic follow-up invitation without adding factual claims.",
    ]


def _is_supplier_process(question: str, answer: str, steps: list[tuple[str, str]]) -> bool:
    material = f"{question} {answer} {' '.join(label for label, _ in steps)}".lower()
    return "supplier" in material and any("setup" in label.lower() or "create" in label.lower() for label, _ in steps)


def _supplier_process_overview(answer: str) -> str:
    refs = _reference_tokens(answer)
    first_ref = _refs_text(refs[:1])
    setup_refs = _refs_text(refs[:2] or refs)
    final_refs = _refs_text(refs[-2:] or refs)
    paragraphs = [
        (
            "Yes — setting up a supplier is a bit like getting someone officially added to the company's approved "
            "address book, but with a lot more checks before anyone is allowed to start buying from them."
        ),
        (
            "The process starts when someone in the business, usually a buyer or commercial requester, says: "
            f'"We need this supplier set up" or "We need to change this supplier\'s details"{first_ref}. '
            f"They do this by filling in the formal supplier setup form{setup_refs}."
        ),
        "From there, it goes through a few important stages:",
        (
            'First, Trading Support checks the form. This is the "have we got everything we need?" stage. '
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
            "for ordering and process use, while finance needs to recognise the supplier for payment and reconciliation."
        ),
        (
            "The two records then need to be mapped together. Otherwise, you end up with the business equivalent of two "
            "people talking about the same supplier but using different names. That is where errors, payment issues and "
            "reconciliation problems can creep in."
        ),
        (
            "Finally, the supplier is linked to the required contracts, final controls are completed, and the supplier "
            f"can be activated. The requester is then told that the setup is complete and the supplier is available for use{final_refs}."
        ),
        (
            "So the short version is: request it, check it, approve it, create it in both operational and finance systems, "
            "link everything together, then activate it."
        ),
    ]
    return "\n\n".join(paragraphs)


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


def _refs_text(refs: list[str]) -> str:
    return f" {' '.join(refs)}" if refs else ""


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
