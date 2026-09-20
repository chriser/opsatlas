"""Local coverage assessment and reviewed conversational follow-ups, never tools."""

import asyncio
import copy
import re

import httpx

from .evidence import digest
from .planner_runtime import MODEL

POLICY = "synthetic-interview-v6"
QUESTIONS = {
    "story": (
        "A concrete example",
        "Think of a recent supplier activation. Walk me through what happened, from the first request to the outcome.",
    ),
    "sequence": (
        "Check the sequence",
        "Before we explore the details, is that sequence right or would you change anything?",
    ),
    "trigger": ("Trigger and inputs", "What started the request, and what information did you need before anyone could act?"),
    "owner": ("People and ownership", "Who took responsibility at each hand-off, and who made the final decision?"),
    "cues": ("Cues and decisions", "What did you notice that helped you decide whether this request was ready or needed a closer look?"),
    "systems": ("Systems and records", "Where did you record the checks and the decision, and what happened to the record afterwards?"),
    "controls": ("Checks and timing", "Which checks had to be complete before activation, and how did you know they had passed?"),
    "exceptions": ("Exceptions", "Was this the usual route or an exception? What conditions made that route appropriate?"),
    "scope": ("Scope and dates", "Which region and process version does this example belong to, and roughly when did it happen?"),
    "compare": (
        "Compare the guide",
        "The synthetic guide names Finance for the UK standard route. "
        "How does that scope and timing relate to your example? We can leave any difference unresolved.",
    ),
    "followup": ("An open point", "We can leave that point open. Which role or source would help us understand it later?"),
    "hypothetical": ("A hypothetical", "As a hypothetical, if the usual approver were unavailable, what would you expect to happen?"),
    "clarify": (
        "Clarify the account",
        "What remains uncertain in this account, or needs more precise wording before someone else reviews it?",
    ),
    "review": (
        "Review your account",
        "Please review the captured account and open points. What needs correcting before we finish this draft?",
    ),
}
SLOTS = {key for key in QUESTIONS if key in {"trigger", "owner", "cues", "systems", "controls", "exceptions", "scope"}}
UNCERTAIN = re.compile(r"\b(don.t know|do not know|not sure|uncertain|can.t remember|cannot remember|maybe|possibly)\b", re.I)


# Each detail is independently assessable. Covering ownership must not cause us
# to skip decision criteria, nor ask again who approved an already named decision.
DETAILS = {
    "outcome": ("controls", "What is the current outcome of this request?"),
    "request_start": ("trigger", "What set this request in motion?"),
    "required_inputs": ("trigger", "What information had to be supplied before work could start?"),
    "handoffs": ("owner", "How was responsibility passed between the people involved?"),
    "decision_owner": ("owner", "Who is responsible for activation decisions?"),
    "decision_criteria": ("cues", "What rule or reason guided the decision?"),
    "warning_signs": ("cues", "What would have made you stop and look more closely?"),
    "record_location": ("systems", "Was the decision recorded, and if so where?"),
    "record_changes": ("systems", "What changed in the supplier record, if anything?"),
    "required_checks": ("controls", "Which checks had to pass before activation?"),
    "check_evidence": ("controls", "What evidence shows the results of the checks?"),
    "usual_or_exception": ("exceptions", "Was this the usual route or an exception?"),
    "exception_conditions": ("exceptions", "What conditions would require a different route?"),
    "region": ("scope", "Which region did this example apply to?"),
    "process_date": ("scope", "When did this happen, and which process version applied?"),
}


def question_for_segment(session, segment):
    """Exact question identity for new records; key fallback for legacy sessions."""
    return next((q for q in reversed(session["questions"])
                 if (q.get("id") == segment["question_id"] if segment.get("question_id")
                     else q["key"] == segment.get("question_key"))), None)


def source_requested(session, segment):
    """A source prompt stays asked when the participant skips it without replying."""
    questions = session["questions"]
    answered = question_for_segment(session, segment)
    relevant = questions[questions.index(answered):] if answered else questions[-1:]
    return any(q.get("key") == "followup" or (q.get("generation") or {}).get("action") == "leave_open" for q in relevant)


def remaining_details(session):
    asked = {q["detail"] for q in session["questions"] if q.get("detail")}
    legacy = {q["key"] for q in session["questions"] if not q.get("detail")}
    return [key for key, (slot, _) in DETAILS.items() if key not in asked and slot not in legacy]


def final_segments(session):
    return [segment for segment in session["segments"] if segment["state"] == "confirmed"]


def allowed_questions(session, evidence_current=True):
    segments = final_segments(session)
    asked = {question["key"] for question in session["questions"]}
    if not segments:
        return ["story"]
    if "sequence" not in asked and not session.get("hearing_only"):
        return ["sequence"]
    allowed = list(dict.fromkeys(DETAILS[key][0] for key in remaining_details(session)))
    if (segments[-1]["kind"] == "uncertain" or UNCERTAIN.search(segments[-1]["text"])) and "followup" not in asked:
        return ["followup"]
    # A comparator is permitted only after the contributor explicitly states a
    # matching scope and confirms sequence. This proposes comparison, not conflict.
    scope = session["scope"]
    pack_scope = session["evidence"]["scope"]
    if (
        evidence_current
        and not session.get("hearing_only")
        and session["evidence"]["sources"]
        and "scope" in asked
        and "compare" not in asked
        and scope["region"] == pack_scope["region"]
        and scope["variant"] == pack_scope["variant"]
        and scope["date"]
        and scope["date"] >= pack_scope["effective_from"]
    ):
        allowed.append("compare")
    if not allowed and "hypothetical" not in asked:
        allowed.append("hypothetical")
    if not allowed and "clarify" not in asked:
        allowed.append("clarify")
    return allowed or ["review"]


def checked_plan(raw, session, allowed):
    if not isinstance(raw, dict) or raw.get("question") not in allowed:
        raise ValueError("Unapproved question")
    observations = []
    by_id = {segment["id"]: segment for segment in final_segments(session)}
    values = raw.get("observations", [])
    if not isinstance(values, list) or len(values) > len(DETAILS):
        raise ValueError("Invalid observations")
    for value in values:
        if not isinstance(value, dict) or value.get("slot") not in SLOTS:
            raise ValueError("Invalid slot")
        segment = by_id.get(value.get("segment_id"))
        quote = value.get("quote")
        if not segment or not isinstance(quote, str) or not 1 <= len(quote) <= 500 or quote not in segment["text"]:
            raise ValueError("An observation must quote a confirmed transcript exactly")
        observations.append(
            {
                "slot": value["slot"],
                "segment_id": segment["id"],
                "segment_revision": segment["revision"],
                "quote": quote,
                "start": segment["text"].index(quote),
                "end": segment["text"].index(quote) + len(quote),
                "kind": segment["kind"],
                "status": "unverified",
            }
        )
    return {"question": raw["question"], "observations": observations}


def spoken_excerpt(text):
    """Keep a short, verbatim excerpt without cutting off a spoken word/amount."""
    if len(text) <= 220:
        return text
    prefix = text[:220]
    boundaries = list(re.finditer(r"[.!?](?=\s|$)", prefix))
    if boundaries:
        return prefix[:boundaries[-1].end()].strip()
    cut = prefix.rfind(" ")
    return prefix[:cut].strip() if cut >= 3 else prefix


def checked_anchor(value, session):
    if not isinstance(value, dict):
        raise ValueError("Missing anchor")
    segment = next((s for s in final_segments(session) if s["id"] == value.get("segment_id")), None)
    quote = value.get("quote")
    if not segment or not isinstance(quote, str) or not 3 <= len(quote) <= 220 or quote not in segment["text"]:
        raise ValueError("Follow-up must reference current confirmed wording")
    return {"segment_id": segment["id"], "segment_revision": segment["revision"],
            "quote": quote, "kind": segment["kind"]}


def question_text(plan, session):
    """Check generated speech at persistence, or rebuild a guided/legacy question."""
    if plan.get("generation"):
        from .conversation import checked_spoken_question

        return checked_spoken_question(plan["generation"], session)
    key, detail = plan["question"], plan.get("detail")
    if detail and (detail not in DETAILS or DETAILS[detail][0] != key):
        raise ValueError("Invalid question detail")
    text = DETAILS[detail][1] if detail else QUESTIONS[key][1]
    if plan.get("anchor"):
        anchor = checked_anchor(plan["anchor"], session)
        if plan["anchor"].get("segment_revision") != anchor["segment_revision"]:
            raise ValueError("Superseded question anchor")
        labels = {"reported_practice": "In your account", "reported_policy": "In your description of policy",
                  "hypothetical": "In your hypothetical", "proposal": "In your proposal", "uncertain": "On the point you left open"}
        text = f'{labels[anchor["kind"]]}, you said: “{anchor["quote"]}” {text}'
    if len(text) > 600:
        raise ValueError("Question exceeds speech limit")
    return text


def checked_observations(values, session):
    by_id = {s["id"]: s for s in final_segments(session)}
    if not isinstance(values, list) or len(values) > len(DETAILS):
        raise ValueError("Invalid detail assessments")
    observations, seen = [], set()
    for value in values:
        if not isinstance(value, dict) or value.get("detail") not in DETAILS or value["detail"] in seen:
            raise ValueError("Invalid or duplicate detail")
        detail = value["detail"]
        seen.add(detail)
        assessment = value.get("assessment")
        if assessment == "missing":
            continue
        if assessment not in ("addressed", "left_open"):
            raise ValueError("Invalid assessment")
        checked = checked_plan({"question": "story", "observations": [
            {"slot": DETAILS[detail][0], "segment_id": value.get("segment_id"), "quote": value.get("quote")}
        ]}, session, ["story"])["observations"][0]
        source = by_id[checked["segment_id"]]
        # Unknowns are unresolved. Proposals/hypotheticals do not fill gaps in
        # reported practice. Exact quotes validate provenance, not semantics.
        if source["kind"] == "uncertain" or UNCERTAIN.search(checked["quote"]):
            assessment = "left_open"
        elif assessment == "left_open":
            raise ValueError("An open point must quote explicit uncertainty")
        if source["kind"] in ("hypothetical", "proposal"):
            assessment = "illustrative"
        observations.append({**checked, "detail": detail, "assessment": assessment})
    return observations


def checked_contextual_plan(raw, session, allowed):
    if not isinstance(raw, dict) or raw.get("target") not in [*remaining_details(session), *[k for k in allowed if k not in SLOTS]]:
        raise ValueError("Invalid follow-up target")
    observations = checked_observations(raw.get("observations"), session)
    covered = {o["detail"] for o in observations if o["assessment"] in ("addressed", "left_open")}
    candidates = [d for d in remaining_details(session) if d not in covered and DETAILS[d][0] in allowed]
    special = [k for k in allowed if k not in SLOTS]
    target = raw["target"]
    if target not in candidates + special:
        target = (candidates + special + ["review"])[0]
    detail = target if target in DETAILS else None
    key = DETAILS[detail][0] if detail else target
    anchor = checked_anchor(raw.get("anchor"), session)
    # When the model's target was rejected, avoid coupling its old anchor with
    # a different topic: use a checked, unanchored fallback question instead.
    result = {"question": key, "detail": detail, "observations": observations,
              "anchor": anchor if target == raw["target"] else None}
    result["text"] = question_text(result, session)
    return result


def source_sentences(context, session):
    """Verbatim, bounded sources; decimal points must not split monetary values."""
    sentences = {}
    for segment in context:
        question = question_for_segment(session, segment) or {}
        for match in re.finditer(r".+?(?:[.!?](?=\s|$)|\n|$)", segment["text"], re.S):
            remainder = match.group().strip()
            while remainder:
                cut = len(remainder) if len(remainder) <= 500 else (remainder.rfind(" ", 0, 501) or 500)
                if cut < 1:
                    cut = 500
                quote, remainder = remainder[:cut].strip(), remainder[cut:].strip()
                if quote:
                    sentences[str(len(sentences))] = {
                        "segment_id": segment["id"], "quote": quote, "kind": segment["kind"],
                        "answer_to_detail": question.get("detail"), "answer_to_topic": question.get("key"),
                        "answer_to_question": question.get("text"),
                    }
    return sentences


def explicit_absence_of_recording(sentences, session):
    """A narrow explicit negative answers both recording fields, without inference."""
    values = []
    for source in sentences.values():
        quote = source["quote"]
        if re.fullmatch(
            r"(?:I|we) (?:did not|didn't) (?:write|record|log) (?:this|it|anything) "
            r"(?:in|on) any (?:system|document)(?: or (?:system|document))?[.!]?",
            quote, re.I,
        ):
            for detail in ("record_location", "record_changes"):
                values.append({"detail": detail, "assessment": "addressed",
                               "segment_id": source["segment_id"], "quote": quote})
    # Later wording wins, while the ordinary kind/provenance checks still apply.
    unique = {v["detail"]: v for v in values}
    return checked_observations(list(unique.values()), session)


def explicit_process_facts(sentences, session):
    """Recognise a few high-confidence facts that must not be asked again.

    This deliberately covers only explicit reported events. The model still
    assesses broader meaning; these guards keep a missed extraction from
    reopening an outcome or decision owner stated in plain language.
    """
    values = []
    for source in sentences.values():
        if source["kind"] != "reported_practice":
            continue
        quote = source["quote"]
        indirect = re.search(
            r"\b(?:asked|wondered|unclear|unsure|do not know|don't know)\b[^.!?]{0,80}\b(?:if|whether)\b",
            quote,
            re.I,
        )
        contingent = re.search(r"\b(?:if|whether|would|could|might|should)\b[^.!?]{0,80}\b(?:activate|release|cancel)", quote, re.I)
        completed_outcome = re.search(
            r"\b(?:the\s+)?supplier\s+(?:was|has been|had been|got)\s+(?:not\s+|never\s+)?"
            r"(?:activated|released|cancelled|canceled)\b",
            quote,
            re.I,
        ) or re.search(
            r"\b(?:I|we|they|the company)\s+(?:activated|released|cancelled|canceled)\s+(?:the\s+)?supplier\b",
            quote,
            re.I,
        ) or re.search(
            r"\b(?:activated|released|cancelled|canceled)\s+(?:the\s+)?supplier\b",
            quote,
            re.I,
        )
        explicit_hold = re.search(
            r"\b(?:the\s+)?supplier\s+(?:was|remained|stayed)\s+(?:on\s+)?hold\b|"
            r"\b(?:I|we|they)\s+(?:kept|put|placed)\s+(?:the\s+)?supplier\s+on\s+hold\b",
            quote,
            re.I,
        )
        if not indirect and not contingent and (completed_outcome or explicit_hold):
            values.append({"detail": "outcome", "assessment": "addressed",
                           "segment_id": source["segment_id"], "quote": quote})
        if not indirect and re.search(
            r"\b(?:I|we)\s+(?:kept|put|placed)\s+(?:the\s+)?supplier\s+on\s+hold\b",
            quote,
            re.I,
        ):
            values.append({"detail": "decision_owner", "assessment": "addressed",
                           "segment_id": source["segment_id"], "quote": quote})

        active_decider = re.search(
            r"\b(?:the\s+)?(?:(?i:manager|owner|lead|director|supervisor|buyer|finance|operations|procurement)|"
            r"[A-Z][A-Za-z-]+(?:\s+[A-Z][A-Za-z-]+)?)\b[^.!?]{0,100}\b"
            r"(?:approved|authorised|authorized|decided)\b",
            quote,
        )
        passive_decider = re.search(
            r"\b(?:approved|authorised|authorized|decided)\b[^.!?]{0,40}\bby\s+"
            r"(?:the\s+)?(?:(?i:manager|owner|lead|director|supervisor|buyer|finance|operations|procurement)|"
            r"[A-Z][A-Za-z-]+(?:\s+[A-Z][A-Za-z-]+)?)\b",
            quote,
        )
        if not indirect and (active_decider or passive_decider):
            values.append({"detail": "decision_owner", "assessment": "addressed",
                           "segment_id": source["segment_id"], "quote": quote})

        named_outcome_owner = re.search(
            r"\b(?:the\s+)?(?:manager|owner|lead|director|supervisor|buyer|finance|operations|procurement|"
            r"[A-Z][A-Za-z-]+(?:\s+[A-Z][A-Za-z-]+)?)\b[^.!?]{0,80}\b"
            r"(?:activated|released|cancelled|canceled)\s+(?:the\s+)?supplier\b",
            quote,
            re.I,
        )
        if not indirect and named_outcome_owner:
            values.append({"detail": "decision_owner", "assessment": "addressed",
                           "segment_id": source["segment_id"], "quote": quote})

        if re.search(
            r"\b(?:check|checks|details|certificate|evidence)\b[^.!?]{0,60}"
            r"\b(?:green|passed|failed|matched|valid|invalid|expired)\b",
            quote,
            re.I,
        ):
            values.append({"detail": "check_evidence", "assessment": "addressed",
                           "segment_id": source["segment_id"], "quote": quote})
        if re.search(r"\b(?:expired|invalid|incorrect|wrong|mismatch|missing|blocked|blocking)\b", quote, re.I):
            values.append({"detail": "warning_signs", "assessment": "addressed",
                           "segment_id": source["segment_id"], "quote": quote})
        if re.search(r"\b(?:asked|requested)\b[^.!?]{0,100}\b(?:certificate|form|document|details|information|evidence)\b", quote, re.I):
            values.append({"detail": "required_inputs", "assessment": "addressed",
                           "segment_id": source["segment_id"], "quote": quote})
        if re.search(
            r"\b(?:approved|authorised|authorized|activated|released|cancelled|canceled|held|kept)\b"
            r"[^.!?]{0,80}\b(?:because|due to)\b",
            quote,
            re.I,
        ):
            values.append({"detail": "decision_criteria", "assessment": "addressed",
                           "segment_id": source["segment_id"], "quote": quote})
    unique = {value["detail"]: value for value in values}
    return checked_observations(list(unique.values()), session)


def answered_detail_facts(sentences, session, assessed_ids):
    """Use the question contract to update coverage without another inference pass."""
    segments = {segment["id"]: segment for segment in final_segments(session)}
    values = {}
    for source in sentences.values():
        if source["segment_id"] in assessed_ids:
            continue
        segment = segments[source["segment_id"]]
        question = question_for_segment(session, segment) or {}
        detail = question.get("detail")
        if detail not in DETAILS or (question.get("key") == "followup" and segment["kind"] == "uncertain"):
            continue
        values[detail] = {
            "detail": detail,
            "assessment": "left_open" if segment["kind"] == "uncertain" or UNCERTAIN.search(source["quote"]) else "addressed",
            "segment_id": source["segment_id"],
            "quote": source["quote"],
        }
    return checked_observations(list(values.values()), session)


def coverage_context(session, assessed_ids):
    """Immutable input snapshot for incremental assessment, never inferred facts."""
    return copy.deepcopy({"version": "coverage-v5", "scope": session["scope"], "segments": final_segments(session),
                          "questions": session["questions"], "assessed_ids": sorted(assessed_ids)})


def retained_coverage(session):
    """Keep assessments only while their complete input prefix is unchanged.

    A correction can change the meaning of later short answers, so any changed
    prefix invalidates all dependent coverage. Append-only contributions can be
    assessed incrementally; an empty new assessment cannot erase old coverage.
    """
    old = session.get("analysis") or {}
    context = old.get("coverage_context") or {}
    segments, questions = context.get("segments", []), context.get("questions", [])
    current = final_segments(session)
    if (context.get("version") != "coverage-v5" or context.get("scope") != session["scope"]
            or current[:len(segments)] != segments
            or session["questions"][:len(questions)] != questions):
        return [], set()
    values = old.get("observations", [])
    # Recheck even persisted observations against their present source revision.
    for value in values:
        source = next((s for s in current if s["id"] == value.get("segment_id")), None)
        if not source or source["revision"] != value.get("segment_revision"):
            return [], set()
    try:
        checked = checked_observations([
            {**v, "assessment": "addressed" if v.get("assessment") == "illustrative" else v.get("assessment")}
            for v in values], session)
    except (ValueError, KeyError, TypeError):
        return [], set()
    return checked, set(context.get("assessed_ids", []))


def merge_coverage(previous, current):
    values = {o["detail"]: o for o in previous}
    for observation in current:
        # Imagined accounts do not replace an established practice/policy account.
        prior = values.get(observation["detail"])
        if prior and prior["assessment"] != "illustrative" and observation["assessment"] == "illustrative":
            continue
        values[observation["detail"]] = observation
    return list(values.values())


class LocalPlanner:
    async def plan(self, session, evidence_current=True):
        allowed = allowed_questions(session, evidence_current)
        retained, assessed_ids = retained_coverage(session)
        result = {"question": allowed[0], "observations": retained,
                  "coverage_context": (session.get("analysis") or {}).get("coverage_context") if assessed_ids else None}
        mode, reason = "guided", None
        if allowed not in (["story"], ["sequence"]):
            context, size = [], 0
            for segment in reversed(final_segments(session)):
                if size + len(segment["text"]) > 12000:
                    break
                context.insert(0, segment)
                size += len(segment["text"])
            # Short source IDs make extraction cheaper and avoid quote-copy errors.
            # Source text stays verbatim; the model can select it but cannot edit it.
            sentences = source_sentences(context, session)
            new_sentences = {key: value for key, value in sentences.items()
                             if value["segment_id"] not in assessed_ids}
            observations = merge_coverage(retained, answered_detail_facts(new_sentences, session, assessed_ids))
            observations = merge_coverage(observations, explicit_process_facts(new_sentences, session))
            observations = merge_coverage(observations, explicit_absence_of_recording(new_sentences, session))
            result = {
                "question": "review",
                "observations": observations,
                "coverage_context": coverage_context(session, assessed_ids | {s["id"] for s in context}),
            }
            latest = final_segments(session)[-1]
            unknown = latest["kind"] == "uncertain" or bool(UNCERTAIN.search(latest["text"]))
            if unknown and not source_requested(session, latest):
                answered = question_for_segment(session, latest) or {}
                if answered.get("detail") in DETAILS:
                    source = next((value for value in reversed(list(new_sentences.values()))
                                   if value["segment_id"] == latest["id"]
                                   and (latest["kind"] == "uncertain" or UNCERTAIN.search(value["quote"]))), None)
                    if source:
                        open_point = checked_observations([{
                            "detail": answered["detail"], "assessment": "left_open",
                            "segment_id": latest["id"], "quote": source["quote"],
                        }], session)
                        result["observations"] = merge_coverage(result["observations"], open_point)
                result.update(
                    question="followup", detail=None, anchor=None, guide_reason="explicit_unknown",
                    coverage_context=coverage_context(session, assessed_ids | {latest["id"]}),
                )
                return self.finish(result, session, evidence_current, "guided", None)
            try:
                covered = {o["detail"] for o in observations if o["assessment"] != "illustrative"}
                if "compare" in allowed and not (set(remaining_details(session)) - covered):
                    result.update(question="compare", guide_reason="scoped_fixture_comparison")
                    return self.finish(result, session, evidence_current, "guided", None)
                from .conversation import compose_followup

                async with httpx.AsyncClient(base_url="http://127.0.0.1:11434", timeout=20, trust_env=False) as client:
                    generation = await compose_followup(client, MODEL, session, sentences, observations, DETAILS)
                focus = generation["focus"]
                key = DETAILS[focus][0] if focus in DETAILS else "review"
                result.update(question=key, detail=focus if focus in DETAILS else None, anchor=None, generation=generation)
                mode = "local_model"
            except asyncio.CancelledError:
                raise
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                reason = ("Contextual follow-up is pending because local planning was unavailable or failed validation. "
                          "Your wording is saved. Use Ask next question to retry, or review and finish the draft.")
                result = {"question": "review", "observations": result.get("observations", []),
                          "coverage_context": result.get("coverage_context")}
        return self.finish(result, session, evidence_current, mode, reason)

    @staticmethod
    def finish(result, session, evidence_current, mode, reason):
        key = result["question"]
        return {
            **result, "text": question_text(result, session), "label": QUESTIONS[key][0],
            "mode": mode, "reason": reason, "model": MODEL if mode == "local_model" else None,
            "policy": POLICY, "evidence_status": "current_fixture" if evidence_current else "stale_or_unavailable",
            "input_hash": digest(session),
            "context_limit": "At most 12000 characters per assessment; earlier unchanged source-backed coverage is retained.",
            "checks": ("Structure and current sources checked; local conversational review passed but remains fallible. "
                       "No factual validation." if result.get("generation") else
                       "Guided prompt; no generated question approved. Facts remain unverified."),
        }
