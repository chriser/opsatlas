"""Explainable process-complexity and key-person-risk indicators."""

from __future__ import annotations

from collections import Counter

from ..process.models import ProcessRecord

_RISK_TERMS = ("exception", "manual", "unclear", "unknown", "requires validation", "open decision", "fail", "reject")

_RUBRIC = {
    "complexity_score": (
        "0-100 capped indicator from registry counts: roles, systems, dependencies, "
        "controls, hand-offs, exception wording and business rules."
    ),
    "key_person_risk_score": (
        "0-100 capped indicator from rule ownership concentration, missing/unclear owners, "
        "exception wording and rule-to-role imbalance."
    ),
    "score_100": (
        "A score of 100 means the indicator reached the cap; compare the signals "
        "and indicators to distinguish capped processes."
    ),
    "bands": "Low is below 34, medium is 34-66, and high is 67-100.",
    "evidence_boundary": "These scores are diagnostic triage signals, not operational risk proof.",
}


def build_process_complexity(records: list[ProcessRecord]) -> dict:
    rows = [_score_process(record) for record in records]
    return {
        "process_count": len(rows),
        "average_complexity": round(sum(row["complexity_score"] for row in rows) / len(rows), 1) if rows else 0.0,
        "high_risk_count": sum(1 for row in rows if row["key_person_risk_band"] == "high"),
        "rubric": _RUBRIC,
        "processes": sorted(rows, key=lambda row: (-row["complexity_score"], -row["key_person_risk_score"], row["name"])),
    }


def _score_process(record: ProcessRecord) -> dict:
    rule_roles = [rule.role.strip().lower() for rule in record.rules if rule.role.strip()]
    role_counts = Counter(rule_roles)
    dominant_role, dominant_count = role_counts.most_common(1)[0] if role_counts else ("", 0)
    role_count = len(record.roles)
    system_count = len(record.systems)
    dependency_count = len(record.dependencies)
    handoff_count = max(0, len({role.lower() for role in record.roles}) - 1)
    exception_count = _exception_count(record)
    unclear_ownership = _unclear_ownership_count(record)
    rule_count = len(record.rules)
    dominant_share = dominant_count / rule_count if rule_count else 0.0

    complexity_score = min(
        100,
        role_count * 7
        + system_count * 9
        + dependency_count * 10
        + len(record.controls) * 5
        + handoff_count * 7
        + exception_count * 8
        + len(record.business_rules) * 3,
    )
    key_person_risk_score = min(
        100,
        round(
            dominant_share * 40
            + (25 if role_count <= 1 and rule_count else 0)
            + unclear_ownership * 18
            + (16 if dominant_share >= 0.7 and role_count > 1 else 0)
            + min(18, exception_count * 3)
            + max(0, rule_count - role_count) * 2
        ),
    )

    return {
        "id": record.id,
        "name": record.name,
        "source_title": record.source_title,
        "domain": record.domain,
        "process": record.process,
        "complexity_score": complexity_score,
        "complexity_band": _band(complexity_score),
        "key_person_risk_score": key_person_risk_score,
        "key_person_risk_band": _band(key_person_risk_score),
        "dominant_role": dominant_role.replace("_", " ") if dominant_role else "",
        "signals": {
            "roles": role_count,
            "systems": system_count,
            "dependencies": dependency_count,
            "controls": len(record.controls),
            "handoffs": handoff_count,
            "exception_terms": exception_count,
            "unclear_ownership": unclear_ownership,
            "rules": rule_count,
            "dominant_role_share": round(dominant_share, 2),
        },
        "indicators": _indicators(
            role_count=role_count,
            system_count=system_count,
            dependency_count=dependency_count,
            handoff_count=handoff_count,
            exception_count=exception_count,
            unclear_ownership=unclear_ownership,
            dominant_role=dominant_role,
            dominant_share=dominant_share,
        ),
        "explanation": _explanation(complexity_score, key_person_risk_score),
    }


def _exception_count(record: ProcessRecord) -> int:
    text = " ".join(record.business_rules + [rule.rule for rule in record.rules]).lower()
    return sum(text.count(term) for term in _RISK_TERMS)


def _unclear_ownership_count(record: ProcessRecord) -> int:
    missing_rule_roles = sum(1 for rule in record.rules if not rule.role.strip())
    unclear_text = sum(
        1
        for rule in record.rules
        if "owner" in rule.rule.lower() and any(term in rule.rule.lower() for term in ("unclear", "unknown", "validation"))
    )
    return missing_rule_roles + unclear_text + (1 if not record.roles and record.rules else 0)


def _indicators(
    *,
    role_count: int,
    system_count: int,
    dependency_count: int,
    handoff_count: int,
    exception_count: int,
    unclear_ownership: int,
    dominant_role: str,
    dominant_share: float,
) -> list[str]:
    indicators = []
    if handoff_count >= 3:
        indicators.append("Multiple role hand-offs")
    if system_count >= 3:
        indicators.append("Multiple systems involved")
    if dependency_count >= 2:
        indicators.append("Several dependencies")
    if exception_count:
        indicators.append("Exception or manual-work wording present")
    if unclear_ownership:
        indicators.append("Ownership needs clarification")
    if dominant_role and dominant_share >= 0.6 and role_count > 1:
        indicators.append(f"Rule ownership concentrated around {dominant_role.replace('_', ' ')}")
    if role_count <= 1 and dominant_role:
        indicators.append("Single-role process knowledge concentration")
    return indicators or ["No elevated indicator from registry fields"]


def _band(score: int | float) -> str:
    if score >= 67:
        return "high"
    if score >= 34:
        return "medium"
    return "low"


def _explanation(complexity_score: int, key_person_risk_score: int) -> str:
    notes = ["Indicator only: scores combine registry counts and wording signals, not operational risk proof."]
    if complexity_score >= 100:
        notes.append("Complexity reached the 100 cap, so use signals and indicators to compare it with other capped processes.")
    if key_person_risk_score >= 100:
        notes.append("Key-person risk reached the 100 cap, so review role concentration and ownership signals before drawing conclusions.")
    return " ".join(notes)
