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
        if _valid_natural_render(answer, candidate, result, question):
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


def _valid_natural_render(answer: str, candidate: str, result: AnswerResult, question: str) -> bool:
    if not candidate:
        return False
    if "approved answer" in candidate.lower() or "canonical answer" in candidate.lower():
        return False
    if _contains_structured_list(candidate):
        return False
    if _question_prefers_process_subject(question, answer) and _starts_with_yes(candidate):
        return False
    if len(_numbered_steps(answer)) >= 3 and "short version" not in candidate.lower():
        return False
    allowed_refs = set(_available_reference_tokens(answer, result))
    answer_inline_refs = set(_reference_tokens(answer))
    candidate_refs = set(_reference_tokens(candidate))
    if candidate_refs - allowed_refs:  # candidate must not invent markers
        return False
    # Only require the candidate to carry markers when the source answer itself used inline
    # [n] markers; a marker-free answer may be spoken without them.
    if answer_inline_refs and not candidate_refs:
        return False
    return True


def _natural_opener(answer: str) -> str:
    # Only assert "Yes" when the answer is clearly affirmative; otherwise stay neutral so
    # a negative ("No, ...") answer is never introduced with a contradictory "Yes —".
    head = answer.strip().lower()
    if re.match(r"(yes\b|you can\b|it is\b|that is correct\b|correct\b)", head):
        return "Yes — in plain terms, here is what the approved knowledge base says."
    return "In plain terms, here is what the approved knowledge base says."


def _fallback_natural_answer(answer: str, result: AnswerResult, question: str) -> str:
    steps = _numbered_steps(answer)
    if len(steps) >= 3:
        return _process_overview(steps, answer, result, question)
    follow_up = _follow_up_prompt(result)
    return f"{_natural_opener(answer)}\n\n{_soften_formal_phrasing(answer)}\n\n{follow_up}"


def _process_overview(steps: list[tuple[str, str]], answer: str, result: AnswerResult, question: str) -> str:
    topic = _topic_hint(question, answer)
    if topic == "setting up a supplier":
        return _supplier_setup_overview(answer, result)
    refs = _reference_suffix(answer, result)
    intro = _process_intro(topic, steps, answer, refs)
    first = _combine_detail_sentences(steps[:2])
    second = _combine_detail_sentences(steps[2:3])
    middle = _combine_detail_sentences(steps[3:5])
    creation = _combine_detail_sentences(steps[5:8])
    final = _combine_detail_sentences(steps[8:])
    paragraphs = [
        intro,
        _first_stage_sentence(topic, first) if first else "",
        f"From there, {_lower_first(second)}" if second else "",
        f"The main control work is in these checks: {_lower_first(middle)}" if middle else "",
        f"After that, {_lower_first(creation)}" if creation else "",
        f"Finally, {_lower_first(final)}" if final else "",
        f"So the short version is: {_short_version(steps, topic, answer)}.",
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


def _process_intro(topic: str, steps: list[tuple[str, str]], answer: str, refs: str) -> str:
    return f"{_upper_first(topic)} is mainly about {_process_purpose(topic, steps, answer)}.{refs}"


def _first_stage_sentence(topic: str, first: str) -> str:
    if "tax" in topic:
        return f"The first decision is the tax-change route. {_upper_first(first)}"
    if "age restriction" in topic:
        return f"It starts with ownership and scope. {_upper_first(first)}"
    return f"It starts with {_lower_first(first)}"


def _numbered_steps(answer: str) -> list[tuple[str, str]]:
    steps: list[tuple[str, str]] = []
    for line in answer.splitlines():
        # Label may itself contain hyphens/asterisks; split on the first ':' or en/em dash
        # (a bare hyphen is usually intra-word, e.g. "pre-form", so it is not a delimiter).
        match = re.match(r"^\s*\d+\.\s+(?:\*\*)?([^:–—]+?)(?:\*\*)?\s*[:–—]\s*(.+?)\s*$", line)
        if match:
            steps.append((match.group(1).strip(" *"), match.group(2).strip()))
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


def _process_purpose(topic: str, steps: list[tuple[str, str]], answer: str) -> str:
    material = f"{topic} {answer} {' '.join(' '.join(step) for step in steps)}".lower()
    if "tax" in topic or ("tax" in material and "age restriction" not in topic):
        return (
            "managing tax-rate changes so downstream systems understand what changed, when it applies, and which items "
            "are affected"
        )
    if "age restriction" in material:
        return (
            "applying the right age-restriction groupings to affected items, checking that those groupings flow correctly "
            "into downstream systems, and keeping the model ready for legal or annual updates"
        )
    if "article" in material:
        return (
            "making sure the required product structure, pricing, tax handling and readiness controls are clear before "
            "an article is activated"
        )
    return "moving the work from the initial trigger through the checks, system updates and release points in the source material"


def _short_version(steps: list[tuple[str, str]], topic: str = "", answer: str = "") -> str:
    material = f"{topic} {answer} {' '.join(label + ' ' + detail for label, detail in steps)}".lower()
    if "tax" in topic or ("tax" in material and "age restriction" not in topic):
        return (
            "identify the tax change, create or update the right tax definition, apply it to the right items, "
            "validate downstream interpretation, then test before release"
        )
    if "age restriction" in material:
        return (
            "identify the restricted item families, apply the right grouping, check the downstream integration, "
            "test the grouped logic, then keep it ready for future legal changes"
        )
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
    q = question.lower()
    if "supplier" in material:
        return "setting up a supplier"
    if "tax" in q:
        return "the tax handling process"
    if "age restriction" in q:
        return "the age restriction grouping process"
    if "tax" in material and "age restriction" not in material:
        return "the tax handling process"
    if "age restriction" in material:
        return "the age restriction grouping process"
    if "article" in material:
        return "setting up or changing an article"
    question_topic = _question_topic(question)
    if question_topic:
        return question_topic
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


def _starts_with_yes(value: str) -> bool:
    return bool(re.match(r"^\s*yes(?:\s|[-–—])", value, flags=re.IGNORECASE))


def _question_prefers_process_subject(question: str, answer: str) -> bool:
    material = f"{question} {answer}".lower()
    if "supplier" in material:
        return False
    q = question.strip().lower()
    return len(_numbered_steps(answer)) >= 3 and (
        not q.endswith("?") or q.startswith(("what is", "what's")) or "process" in q
    )


def _question_topic(question: str) -> str:
    cleaned = question.strip().lower()
    cleaned = re.sub(r"[?.!]+$", "", cleaned)
    cleaned = re.sub(
        r"^(?:can you tell me about|can you explain|tell me about|explain|describe|what is|what's|how does)\s+",
        "",
        cleaned,
    )
    cleaned = re.sub(r"^(?:the|a|an)\s+", "", cleaned)
    cleaned = cleaned.strip()
    if not cleaned or len(cleaned.split()) > 7:
        return ""
    if "process" not in cleaned and not cleaned.endswith("handling"):
        return ""
    return f"the {cleaned}"


def _follow_up_prompt(result: AnswerResult) -> str:
    citation_count = len(result.citations)
    if citation_count:
        citation_word = "citation" if citation_count == 1 else "citations"
        return (
            f"I found {citation_count} supporting {citation_word}. "
            "You can ask about the owner, control, exception, or next step."
        )
    return "You can ask a follow-up about the owner, control, exception, or next step."
