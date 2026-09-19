"""Deterministic unpublished draft; source wording never becomes approved knowledge."""

from .dialogue import DETAILS, QUESTIONS, SLOTS
from .evidence import digest


def escape_markdown(text):
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for character in "\\`*_{}[]()#!|":
        text = text.replace(character, "\\" + character)
    return text


def packet(session, evidence_current):
    segments = session["segments"]
    analysis = session.get("analysis") or {}
    observations = analysis.get("observations", []) if analysis.get("valid") else []
    coverage = sorted({entry["slot"] for entry in observations})
    details = {entry["detail"]: entry["assessment"] for entry in observations if entry.get("detail")}
    open_points = [QUESTIONS[key][1] for key in sorted(SLOTS - set(coverage))]
    if details:
        open_points = [("Left open: " if details.get(key) == "left_open" else "Still to explore: ") + value[1]
                       for key, value in DETAILS.items() if details.get(key) != "addressed"]
    claims = [
        {
            "id": "claim-" + s["id"],
            "source_segment": s["id"],
            "source_revision": s["revision"],
            "wording": s["text"],
            "kind": s["kind"],
            "status": "SME-confirmed wording; factual validation pending",
            "approval": "not_requested",
            "scope": session["scope"],
        }
        for s in segments
        if s["state"] == "confirmed"
    ]
    result = {
        "schema": 1,
        "session_id": session["id"],
        "session_revision": session["revision"],
        "mode": "synthetic_fixture",
        "title": session["title"],
        "scope": session["scope"],
        "claims": claims,
        "observations": observations,
        "evidence": session["evidence"],
        "evidence_current_at_export": evidence_current,
        "coverage": {key: "excerpt captured, unverified" if key in coverage else "not assessed" for key in sorted(SLOTS)},
        "open_points": open_points,
        "detail_assessments": details,
        "checks": {
            "wording": "participant-confirmed",
            "factual_validation": "pending",
            "conflict_adjudication": "not_run",
            "owner_approval": "not_requested",
            "publication": "disabled",
        },
        "gaps": session["gaps"],
        "notice": "Synthetic draft only. Not approved organisational knowledge. No publication occurred.",
    }
    if not evidence_current:
        result["open_points"].insert(0, "The evidence pack changed or is unavailable; comparison and review need revalidation.")
    result["hash"] = digest(result)
    return result


def markdown(result):
    lines = [
        "# Supplier activation — synthetic interview draft",
        "",
        result["notice"],
        "",
        "Packet hash: " + result["hash"],
        "",
        "## Scope",
        "",
        ", ".join(f"{key}: {value or 'unknown'}" for key, value in result["scope"].items()),
        "",
        "## Captured account — factual validation pending",
        "",
    ]
    for index, claim in enumerate(result["claims"], 1):
        lines += [
            f"### Contribution {index} ({claim['kind']})",
            "",
            f"Segment {escape_markdown(claim['source_segment'])} / revision {claim['source_revision']}",
            "",
        ]
        # Quoted plain text is escaped so supplied Markdown/HTML does not become
        # an active link, image, heading or embedded HTML when the export is viewed.
        text = escape_markdown(claim["wording"])
        lines += ["> " + line for line in text.splitlines()] + [""]
    lines += ["## Open points", ""] + ["- " + point for point in result["open_points"]]
    lines += [
        "",
        "## Review state",
        "",
        "No factual validation, owner approval or Atlas publication has occurred.",
        "The pinned comparator is synthetic training material, not a statement of organisational policy.",
        "",
    ]
    return "\n".join(lines)
