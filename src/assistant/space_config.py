"""What a knowledge space says and recognises (ARCH H2): the router's cues, the guard lists and the refusal wording.

These used to be literals in the code, tuned to one document set. A space may now carry ``space-config.json`` in its
partition; anything it leaves out keeps the default below, which is exactly what the code used to say, so a space
without a file behaves as before. The Sales Product Guide, for instance, declines out-of-scope questions with a
redirect to the sales team rather than the plain refusal an organisation's space keeps.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FILE_NAME = "space-config.json"
DEFAULT_REFUSAL = "I do not have that information in the approved knowledge base."
DEFAULT_SCOPE = "I can only answer questions about the approved process knowledge."


class Expansion(BaseModel):
    """Vocabulary a question implies: when every ``when`` token is present (and, if given, any ``any_of``), ``add``."""
    model_config = ConfigDict(extra="forbid")
    when: list[str]
    any_of: list[str] = Field(default_factory=list)
    add: list[str]


class Classification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    narrative: list[str] = Field(
        default_factory=lambda: ["why", "how", "explain", "describe", "walk me through", "summari[sz]e"])
    structured: list[str] = Field(
        default_factory=lambda: ["who", "which", "what", "list", "show", "how many", "count"])


class Guardrails(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope_message: str = DEFAULT_SCOPE
    off_topic: list[str] = Field(default_factory=lambda: [
        "weather", "temperature", "football", "sport", "recipe", "cook", "tell me a joke", "horoscope", "bitcoin", "stock price",
        "who won"])


class Referral(BaseModel):
    """Topics the space hands to people, and the sentence that says so (ARCH H2b). An answer to a question on one of the
    topics ends with the sentence, whether or not the knowledge answers it; a refusal already speaks the space's own
    wording. No topics, the default, means no sentence is ever added."""
    model_config = ConfigDict(extra="forbid")
    topics: list[str] = Field(default_factory=list)
    sentence: str = ""

    @model_validator(mode="after")
    def _complete(self) -> Referral:
        if self.topics and not self.sentence.strip():
            raise ValueError("a referral with topics needs its sentence")
        try:
            re.compile(r"\b(" + "|".join(self.topics) + r")\b", re.IGNORECASE)
        except re.error as exc:
            raise ValueError(f"the referral topics do not compile: {exc}") from exc
        return self


class SpaceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refusal: str = DEFAULT_REFUSAL
    classification: Classification = Field(default_factory=Classification)
    unsupported_lookup: list[str] = Field(default_factory=lambda: [
        "named employee", "companies house", "next year", "future", "commercially select", "recommend a supplier"])
    role_lookup_prefix: str = r"^\s*who\s+(owns?|is responsible)\b"
    role_terms: list[str] = Field(default_factory=lambda: ["role", "roles", "owner", "owners", "owns", "responsible"])
    aggregate_pattern: str = r"^\s*(list|show)\b|\b(examples|which .+s|what .+s)\b"
    aggregate_fact_limit: int = 12
    expansions: list[Expansion] = Field(default_factory=lambda: [
        Expansion(when=["article", "downstream"], add=["assortment", "consumer", "finance", "mapping", "point", "price", "pricing", "range",
                                                        "ranging", "sale", "sellability", "setup", "system", "warehouse"]),
        Expansion(when=["packaging"], add=["architecture", "attribute", "complexity", "descriptive", "dedicated", "information", "item",
                                           "logistic", "movement", "operational", "planning", "proportionate", "regulatory", "reporting",
                                           "record", "separate", "shelf", "waste"]),
        Expansion(when=["attribute"], any_of=["approve", "approv", "owner", "use", "unmanaged"],
                  add=["accountable", "governance", "purpose", "purposeful"]),
        Expansion(when=["readiness", "downstream"], add=["active", "commercial", "complete", "contract", "control", "mandatory", "mapping",
                                                          "payment", "service", "status"]),
    ])
    stopwords: list[str] = Field(default_factory=lambda: [
        "and", "are", "before", "can", "does", "for", "from", "how", "into", "list", "must", "need", "needs", "not", "only", "or",
        "should", "that", "the", "them", "this", "what", "when", "where", "which", "who", "why", "with"])
    guardrails: Guardrails = Field(default_factory=Guardrails)
    referral: Referral = Field(default_factory=Referral)

    @field_validator("refusal")
    @classmethod
    def _refusal_says_something(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("the refusal wording cannot be empty")
        return value.strip()

    @field_validator("role_lookup_prefix", "aggregate_pattern")
    @classmethod
    def _compiles(cls, value: str) -> str:
        re.compile(value, re.IGNORECASE)
        return value

    def compiled(self) -> CompiledSpaceConfig:
        return CompiledSpaceConfig.of(self)

    @classmethod
    def load(cls, base_dir: str | Path) -> SpaceConfig:
        """The space's configuration: its file, merged over the defaults; the defaults when there is no file. A file
        that cannot be read or does not validate stops the start, because a space must not silently run on the
        wrong cues."""
        path = Path(base_dir) / FILE_NAME
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise ValueError(f"{path}: not valid JSON ({exc})") from exc
        if not isinstance(data, dict):
            raise ValueError(f"{path}: expected an object")
        return cls.model_validate(data)

    @classmethod
    def ensure(cls, base_dir: str | Path, config: SpaceConfig) -> Path:
        """Write ``config`` as the space's file when it has none (a space's defaults, set once, then the owner's)."""
        path = Path(base_dir) / FILE_NAME
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(config.model_dump(exclude_defaults=True), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path


def _alternation(terms: list[str]) -> re.Pattern:
    return re.compile(r"\b(" + "|".join(terms) + r")\b", re.IGNORECASE) if terms else re.compile(r"(?!x)x")


@dataclass(frozen=True)
class CompiledSpaceConfig:
    source: SpaceConfig
    narrative_re: re.Pattern
    structured_re: re.Pattern
    unsupported_re: re.Pattern
    role_lookup_prefix_re: re.Pattern
    role_terms_re: re.Pattern
    aggregate_re: re.Pattern
    aggregate_fact_limit: int
    expansions: tuple[tuple[frozenset[str], frozenset[str], frozenset[str]], ...]
    stopwords: frozenset[str]
    off_topic_re: re.Pattern
    scope_message: str
    refusal: str
    referral_re: re.Pattern
    referral_sentence: str

    @classmethod
    def of(cls, config: SpaceConfig) -> CompiledSpaceConfig:
        return cls(
            source=config,
            narrative_re=_alternation(config.classification.narrative),
            structured_re=_alternation(config.classification.structured),
            unsupported_re=_alternation(config.unsupported_lookup),
            role_lookup_prefix_re=re.compile(config.role_lookup_prefix, re.IGNORECASE),
            role_terms_re=_alternation(config.role_terms),
            aggregate_re=re.compile(config.aggregate_pattern, re.IGNORECASE),
            aggregate_fact_limit=config.aggregate_fact_limit,
            expansions=tuple((frozenset(e.when), frozenset(e.any_of), frozenset(e.add)) for e in config.expansions),
            stopwords=frozenset(config.stopwords),
            off_topic_re=_alternation(config.guardrails.off_topic),
            scope_message=config.guardrails.scope_message,
            refusal=config.refusal,
            referral_re=_alternation(config.referral.topics),
            referral_sentence=config.referral.sentence.strip(),
        )


DEFAULT = SpaceConfig()
DEFAULT_COMPILED = DEFAULT.compiled()
