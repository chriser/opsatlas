"""Safe spoken-response styling for avatar rendering."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from ..answer.service import AnswerResult

AvatarStyleMode = Literal["formal", "natural"]


class AvatarRenderedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: AvatarStyleMode
    rendered_text: str
    render_notes: list[str]


def render_avatar_answer(result: AnswerResult, style: AvatarStyleMode) -> AvatarRenderedAnswer:
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

    follow_up = _follow_up_prompt(result)
    rendered = f"Here is the approved answer in plain terms.\n\n{answer}\n\n{follow_up}"
    return AvatarRenderedAnswer(
        style=style,
        rendered_text=rendered,
        render_notes=[
            "Added spoken signposting before the approved answer.",
            "Added a generic follow-up invitation without adding factual claims.",
        ],
    )


def _follow_up_prompt(result: AnswerResult) -> str:
    citation_count = len(result.citations)
    if citation_count:
        citation_word = "citation" if citation_count == 1 else "citations"
        return (
            f"I found {citation_count} supporting {citation_word}. "
            "You can ask about the owner, control, exception, or next step."
        )
    return "You can ask a follow-up about the owner, control, exception, or next step."

