"""Deterministic ontology entity reconciliation helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ReconciledEntityName:
    """Canonical name data for a named ontology entity."""

    normalized_name: str
    display_name: str
    aliases: list[str]


def reconcile_entity_name(object_type: str, raw_name: str) -> ReconciledEntityName | None:
    """Return a canonical entity name with aliases preserved.

    This is intentionally deterministic. It handles common operating-model
    alias patterns such as POS / point-of-sale and role labels with count
    suffixes, without asking an LLM to rewrite the ontology during rebuild.
    """

    display = _compact(raw_name)
    if not display:
        return None
    if object_type == "system":
        canonical = _canonical_system(display)
    elif object_type == "role":
        canonical = _canonical_role(display)
    else:
        canonical = display
    normalized = normalise_name(canonical)
    if not normalized:
        return None
    aliases = sorted({display, canonical}, key=str.lower)
    return ReconciledEntityName(normalized_name=normalized, display_name=canonical, aliases=aliases)


def normalise_name(value: str) -> str:
    """Normalise deduplicated role/system/control names across packs."""

    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _canonical_system(display: str) -> str:
    text = _clean_system_text(display)
    if _has_any(text, r"\bpos\b", r"point\s+of\s+sale", r"point-of-sale"):
        return "Point of Sale"
    if _has_any(text, r"operational\s+master\s+data\s+tool", r"\bmaster\s+data\s+tool\b"):
        return "Operational Master Data Tool"
    if _has_any(text, r"\bintegration\s+layer\b", r"\bintegration\s+route\b"):
        return "Integration Layer"
    if _has_any(text, r"replenish", r"replenishment"):
        return "Replenishment Platform"
    if _has_any(text, r"warehouse", r"\bdepot\b", r"logistics\s+platform"):
        return "Warehouse and Logistics Platform"
    if _has_any(text, r"\bfinance\b", r"accounting"):
        return "Finance Platform"
    if _has_any(text, r"business\s+intelligence", r"\bbi\b", r"reporting"):
        return "Business Intelligence and Reporting"
    if _has_any(text, r"planning", r"layout"):
        return "Planning and Layout System"
    if _has_any(text, r"article-list", r"article\s+list", r"list\s+engine", r"controlled\s+list"):
        return "Article List Engine"
    if _has_any(text, r"assortment", r"ranging", r"category", r"merchandise\s+hierarchy"):
        return "Ranging and Assortment Logic"
    if _has_any(text, r"promotion", r"discount"):
        return "Promotion and Discount Engine"
    if _has_any(text, r"forecourt", r"fuel", r"wet-stock", r"terminal\s+as\s+a\s+service", r"\btaas\b"):
        return "Payments and Forecourt Platform"
    return _title_case(_strip_qualifiers(display))


def _canonical_role(display: str) -> str:
    without_counts = _strip_parenthetical_counts(display)
    text = normalise_name(without_counts)
    text = re.sub(r"\baligned\b", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    patterns = {
        "Data Owner": (r"\bdata\s+owner\b",),
        "Process Owner": (r"\bprocess\s+owner\b",),
        "Finance Owner": (r"\bfinance\s+owner\b",),
        "Procurement Owner": (r"\bprocurement\s+owner\b",),
        "Logistics Owner": (r"\blogistics\s+owner\b",),
        "Commercial Owner": (r"\bcommercial\s+owner\b",),
        "Master Data Operator": (r"\bmaster\s+data\s+operator\b",),
        "Compliance Manager": (r"\bcompliance\s+manager\b",),
        "Buyer": (r"\bbuyer\b",),
    }
    for canonical, regexes in patterns.items():
        if _has_any(text, *regexes):
            return canonical
    return _compact(without_counts)


def _clean_system_text(value: str) -> str:
    text = normalise_name(_strip_qualifiers(value))
    text = re.sub(r"\bdownstream\b|\bupstream\b", "", text)
    text = re.sub(r"\bconsumer\b|\bsource\b|\benvironment\b|\bmodule\b|\bmodules\b", "", text)
    text = re.sub(r"\blive\s+article\s+screen\b|\bstaging\s+area\b", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _strip_qualifiers(value: str) -> str:
    text = value.replace("\u2013", "-").replace("\u2014", "-").replace("/", " / ")
    text = re.sub(r"\s+-\s+requires validation\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\brequires validation\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\banonymised\b|\banonymized\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bconceptual dependency\b", "", text, flags=re.IGNORECASE)
    return _compact(text)


def _strip_parenthetical_counts(value: str) -> str:
    return re.sub(r"\(\s*\d+\s*\)", "", value)


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip(" -/\t\n")


def _title_case(value: str) -> str:
    words = normalise_name(value).split()
    if not words:
        return ""
    small_words = {"and", "or", "of", "to", "the", "a", "an"}
    return " ".join(word if word in small_words else word.capitalize() for word in words)


def _has_any(text: str, *patterns: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)
