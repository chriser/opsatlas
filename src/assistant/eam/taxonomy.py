"""Editable Enterprise Activity Model taxonomy configuration."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_TAXONOMY_PATH = Path(__file__).resolve().parents[3] / "config" / "eam_taxonomy.json"


class TaxonomyEntry(BaseModel):
    """One domain or lifecycle axis entry."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    order: int
    keywords: list[str] = Field(default_factory=list)
    description: str = ""

    @model_validator(mode="after")
    def validate_entry(self) -> "TaxonomyEntry":
        if not self.id.strip():
            raise ValueError("Taxonomy entry id cannot be blank.")
        if not self.label.strip():
            raise ValueError(f"Taxonomy entry {self.id!r} label cannot be blank.")
        cleaned = [keyword.strip() for keyword in self.keywords if keyword and keyword.strip()]
        if not cleaned:
            raise ValueError(f"Taxonomy entry {self.id!r} must define at least one keyword.")
        self.keywords = cleaned
        return self


class TaxonomyMatch(BaseModel):
    """Deterministic taxonomy classification result."""

    model_config = ConfigDict(extra="forbid")

    item_id: str
    label: str
    confidence: float
    matched_keywords: list[str]


class TaxonomyConfig(BaseModel):
    """Editable EAM axis taxonomy."""

    model_config = ConfigDict(extra="forbid")

    version: str
    provenance: str = ""
    domains: list[TaxonomyEntry]
    lifecycle_stages: list[TaxonomyEntry]

    @model_validator(mode="after")
    def validate_config(self) -> "TaxonomyConfig":
        if not self.version.strip():
            raise ValueError("EAM taxonomy version cannot be blank.")
        self.domains = _validate_axis("domain", self.domains)
        self.lifecycle_stages = _validate_axis("lifecycle stage", self.lifecycle_stages)
        return self

    @classmethod
    def load(cls, path: str | Path | None = None) -> "TaxonomyConfig":
        """Load and validate the active taxonomy.

        `KP_EAM_TAXONOMY` can point at an alternate JSON file for local trials.
        """

        taxonomy_path = Path(path or os.environ.get("KP_EAM_TAXONOMY") or DEFAULT_TAXONOMY_PATH)
        try:
            payload = json.loads(taxonomy_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ValueError(f"EAM taxonomy config not found: {taxonomy_path}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"EAM taxonomy config is not valid JSON: {taxonomy_path}: {exc.msg}") from exc
        try:
            return cls.model_validate(payload)
        except ValueError as exc:
            raise ValueError(f"EAM taxonomy config is invalid: {taxonomy_path}: {exc}") from exc

    def classify_domain(self, text: str) -> TaxonomyMatch | None:
        """Classify text to the best configured EAM domain."""

        return _best_match(text, self.domains)

    def classify_lifecycle(self, text: str) -> TaxonomyMatch | None:
        """Classify text to the best configured EAM lifecycle stage."""

        return _best_match(text, self.lifecycle_stages)


def classify_domain(text: str, taxonomy: TaxonomyConfig | None = None) -> TaxonomyMatch | None:
    """Classify text to the best EAM domain using the active taxonomy."""

    return (taxonomy or TaxonomyConfig.load()).classify_domain(text)


def classify_lifecycle(text: str, taxonomy: TaxonomyConfig | None = None) -> TaxonomyMatch | None:
    """Classify text to the best EAM lifecycle stage using the active taxonomy."""

    return (taxonomy or TaxonomyConfig.load()).classify_lifecycle(text)


def _validate_axis(axis_name: str, entries: list[TaxonomyEntry]) -> list[TaxonomyEntry]:
    if not entries:
        raise ValueError(f"EAM taxonomy must define at least one {axis_name}.")

    ids = _duplicates(entry.id.strip().lower() for entry in entries)
    if ids:
        raise ValueError(f"EAM taxonomy {axis_name} ids must be unique: {', '.join(ids)}.")

    orders = _duplicates(str(entry.order) for entry in entries)
    if orders:
        raise ValueError(f"EAM taxonomy {axis_name} order values must be unique: {', '.join(orders)}.")

    return sorted(entries, key=lambda entry: (entry.order, entry.label.lower()))


def _best_match(text: str, entries: list[TaxonomyEntry]) -> TaxonomyMatch | None:
    normalised = _normalise(text)
    if not normalised:
        return None

    candidates: list[tuple[float, int, int, TaxonomyEntry, list[str]]] = []
    for entry in entries:
        matched = [keyword for keyword in entry.keywords if _keyword_matches(_normalise(keyword), normalised)]
        if not matched:
            continue
        weighted_score = sum(max(1, len(_normalise(keyword).split())) for keyword in matched)
        confidence = min(1.0, weighted_score / max(3, len(entry.keywords)))
        candidates.append((confidence, weighted_score, -entry.order, entry, matched))

    if not candidates:
        return None

    confidence, _, _, entry, matched = max(candidates, key=lambda row: (row[0], row[1], row[2]))
    return TaxonomyMatch(
        item_id=entry.id,
        label=entry.label,
        confidence=round(confidence, 2),
        matched_keywords=matched,
    )


def _keyword_matches(keyword: str, text: str) -> bool:
    if not keyword:
        return False
    if " " in keyword:
        return f" {keyword} " in f" {text} "
    return keyword in text.split()


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def _duplicates(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return sorted(dupes)
