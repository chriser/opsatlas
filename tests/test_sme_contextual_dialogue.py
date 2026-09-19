"""Grounding, coverage and replay invariants for contextual follow-ups."""

import copy
import uuid

import pytest

from services.sme_interviewer.dialogue import (
    DETAILS,
    allowed_questions,
    checked_contextual_plan,
    question_for_segment,
    question_text,
    remaining_details,
    source_sentences,
    spoken_excerpt,
)
from services.sme_interviewer.evidence import FixtureEvidence
from services.sme_interviewer.ledger import Ledger


def account(text="Finance approved the form. I recorded the decision in the ERP.", kind="reported_practice"):
    return {
        "scope": {"region": "unknown", "variant": "unknown", "date": ""},
        "evidence": FixtureEvidence().snapshot(),
        "questions": [{"key": "story"}, {"key": "sequence"}],
        "segments": [{"id": "s1", "revision": 1, "text": text, "kind": kind, "state": "confirmed"}],
    }


def raw(target="required_checks", observations=None, quote="Finance approved the form."):
    return {"target": target, "anchor": {"segment_id": "s1", "quote": quote}, "observations": observations or []}


def observation(detail="decision_owner", quote="Finance approved the form.", assessment="addressed"):
    return {"detail": detail, "assessment": assessment, "segment_id": "s1", "quote": quote}


def checked(value, session):
    return checked_contextual_plan(value, session, allowed_questions(session))


def test_filled_detail_cannot_be_asked_even_if_model_selects_it():
    session = account()
    result = checked(raw("decision_owner", [observation()]), session)
    assert result["detail"] != "decision_owner"
    assert result["anchor"] is None  # Never attach an unrelated old anchor to fallback.
    assert result["observations"][0]["status"] == "unverified"


def test_followup_uses_exact_attributed_wording_and_a_specific_gap():
    session = account()
    result = checked(raw(observations=[observation()]), session)
    assert 'you said: “Finance approved the form.”' in result["text"]
    assert result["text"].endswith(DETAILS["required_checks"][1])
    assert result["anchor"]["segment_revision"] == 1
    assert len(result["text"]) <= 600


@pytest.mark.parametrize("change", ["invented", "provisional", "superseded", "invalid_target"])
def test_ungrounded_or_unapproved_questions_are_rejected(change):
    session, value = account(), raw()
    if change == "invented":
        value["anchor"]["quote"] = "Finance approved £50,000."
    elif change == "provisional":
        session["segments"][0]["state"] = "provisional"
    elif change == "superseded":
        session["segments"][0]["text"] = "Operations declined the request."
        session["segments"][0]["revision"] = 2
    else:
        value["target"] = "publish"
    with pytest.raises(ValueError):
        checked(value, session)


def test_open_point_cannot_be_reclassified_as_answered_or_pressed_again():
    session = account("I do not know who approved it.")
    session["questions"].append({"key": "followup"})
    result = checked(raw("decision_owner", [observation(quote=session["segments"][0]["text"])],
                         quote=session["segments"][0]["text"]), session)
    assert result["observations"][0]["assessment"] == "left_open"
    assert result["detail"] != "decision_owner"


@pytest.mark.parametrize("kind", ["hypothetical", "proposal"])
def test_imagined_claim_cannot_fill_actual_practice_gap(kind):
    session = account(kind=kind)
    result = checked(raw("decision_owner", [observation()]), session)
    assert result["observations"][0]["assessment"] == "illustrative"
    assert result["detail"] == "decision_owner"
    assert f"In your {kind}" in result["text"]


def test_open_classification_requires_explicit_unknown_and_duplicate_details_rejected():
    session = account()
    for observations in ([observation(assessment="left_open")], [observation(), observation()]):
        with pytest.raises(ValueError):
            checked(raw(observations=observations), session)


def test_previous_detail_suppressed_but_other_detail_in_same_topic_remains():
    session = account()
    session["questions"].append({"key": "owner", "detail": "decision_owner", "id": "q1"})
    assert "decision_owner" not in remaining_details(session)
    assert "handoffs" in remaining_details(session)
    assert "owner" in allowed_questions(session)
    session["questions"][-1].pop("detail")  # Old broad questions remain compatible.
    assert "handoffs" not in remaining_details(session)


def test_same_topic_replay_uses_question_identity_and_preserves_correction_link(tmp_path):
    store = Ledger(tmp_path / "ledger.sqlite")
    session = store.create(FixtureEvidence().snapshot(), account()["scope"], str(uuid.uuid4()))

    def mutate(event, payload):
        nonlocal session
        session = store.mutate(session["id"], session["revision"], f"request-{session['revision']}", event, payload)

    mutate("segment_saved", {"text": account()["segments"][0]["text"], "kind": "reported_practice", "state": "confirmed"})
    source_id = session["segments"][0]["id"]
    for detail in ("decision_owner", "handoffs"):
        mutate("plan_requested", {})
        plan = {"question": "owner", "detail": detail, "mode": "local_model", "observations": [],
                "text": "Ignored untrusted model text", "anchor": {"segment_id": source_id, "segment_revision": 1,
                                                                    "quote": "Finance approved the form."}}
        assert store.apply_plan(session["id"], session["revision"], plan)
        session = store.get(session["id"])
        assert "Ignored" not in session["current_question"]["text"]
        mutate("segment_saved", {"text": "The finance lead.", "kind": "reported_practice", "state": "confirmed"})
    first_answer = session["segments"][1]
    assert question_for_segment(session, first_answer)["detail"] == "decision_owner"
    mutate("segment_saved", {"text": "The deputy finance lead.", "kind": "reported_practice", "state": "provisional",
                             "segment_id": first_answer["id"], "segment_revision": 1})
    assert question_for_segment(session, session["segments"][1])["detail"] == "decision_owner"
    mutate("segment_discarded", {"segment_id": first_answer["id"]})
    assert session["current_question"]["detail"] == "decision_owner"


def test_current_revision_is_rechecked_when_persisting_question():
    session = account()
    plan = checked(raw(), session)
    corrected = copy.deepcopy(session)
    corrected["segments"][0]["revision"] = 2
    with pytest.raises(ValueError, match="Superseded"):
        question_text(plan, corrected)


def test_sentence_sources_preserve_decimal_amounts_long_answers_and_answer_context():
    text = "The fee was £15,000.50, not £50,000.00. Approval came first. " + "Long answer without punctuation " * 80
    session = account(text)
    session["questions"].append({"id": "q1", "key": "controls", "detail": "check_evidence"})
    session["segments"][0]["question_id"] = "q1"
    sources = source_sentences(session["segments"], session)
    assert sources["0"]["quote"] == "The fee was £15,000.50, not £50,000.00."
    assert all(3 <= len(s["quote"]) <= 500 and s["quote"] in text for s in sources.values())
    assert sources["0"]["answer_to_detail"] == "check_evidence"
    assert len(sources) > 3


def test_unknown_details_remain_explicit_in_export():
    from services.sme_interviewer.review import packet

    session = account("I do not know who approved it.")
    session.update(id="fixture", revision=1, title="Synthetic", gaps=[])
    session["analysis"] = {"valid": True, **checked(raw("followup", [observation(quote=session["segments"][0]["text"])],
                                                      quote=session["segments"][0]["text"]), session)}
    draft = packet(session, True)
    assert draft["detail_assessments"]["decision_owner"] == "left_open"
    assert "Left open: Who is responsible for activation decisions?" in draft["open_points"]
    assert draft["checks"]["factual_validation"] == "pending"


def test_spoken_anchor_ends_at_a_sentence_or_word_boundary():
    text = "Finance approved £15,000.50 before activation. " + "Additional details " * 30
    assert spoken_excerpt(text) == "Finance approved £15,000.50 before activation."
    words = "Detailed description without punctuation " * 20
    excerpt = spoken_excerpt(words)
    assert len(excerpt) <= 220 and words.startswith(excerpt)
    assert words[len(excerpt)] == " "
