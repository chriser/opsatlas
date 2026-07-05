"""RAG-vs-OAG benchmark harness.

The fake service in this module exists only to test scoring arithmetic. Real
benchmark runs use the production AnswerService from the local app stack.
"""

from __future__ import annotations

import json
import re
import statistics
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from assistant.answer.prompt import REFUSAL
from assistant.answer.service import AnswerResult, Citation, RoutingMode

DEFAULT_LABELS_PATH = Path("tests/evaluation/rag_vs_oag_questions.json")
DEFAULT_OUTPUT_DIR = Path("docs/benchmark/oag")
DEFAULT_CONFIGS: tuple[RoutingMode, ...] = ("rag_only", "oag_first", "oag_only")

Category = Literal["structured_entity", "structured_relationship", "aggregate", "narrative", "out_of_scope", "mixed"]
ExpectedPath = Literal["oag", "rag", "either"]

_REFUSAL_RE = re.compile(
    r"\b(refuse|cannot|can't|not available|not in (the )?(approved )?(knowledge base|corpus|packs)|"
    r"no .* (available|present|provided)|do not invent|insufficient evidence)\b",
    re.IGNORECASE,
)


class ExpectedFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    aliases: list[str] = Field(default_factory=list)

    @field_validator("text")
    @classmethod
    def text_must_be_present(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("expected fact text must be present.")
        return stripped


class RagVsOagQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    category: Category
    question: str
    expected_path: ExpectedPath
    expected_answer_facts: list[ExpectedFact]
    notes: str


class RagVsOagDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version: str
    created_at: str
    source_corpus: str
    questions: list[RagVsOagQuestion]


def load_rag_vs_oag_dataset(path: str | Path = DEFAULT_LABELS_PATH) -> RagVsOagDataset:
    return RagVsOagDataset.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def evaluate_rag_vs_oag(
    dataset: RagVsOagDataset,
    *,
    configs: tuple[RoutingMode, ...] = DEFAULT_CONFIGS,
    runs: int = 3,
    fake_generator: bool = False,
    limit: int = 0,
) -> dict[str, Any]:
    if runs < 1:
        raise ValueError("runs must be at least 1.")
    if not configs:
        raise ValueError("At least one benchmark config must be supplied.")

    questions = dataset.questions[: limit or None]
    service = _FakeRagVsOagAnswerService(questions) if fake_generator else _production_answer_service()
    model_info = {"backend": "scripted", "llm": "fake-rag-vs-oag", "embed": "none"}
    if not fake_generator:
        model_info = getattr(service, "model_info", None) or {}

    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    for run_number in range(1, runs + 1):
        for config in configs:
            for label in questions:
                row_started = time.perf_counter()
                result = service.answer(label.question, routing_mode=config)
                latency_seconds = time.perf_counter() - row_started
                score = score_rag_vs_oag_answer(label, result)
                rows.append(
                    {
                        "run": run_number,
                        "config": config,
                        "id": label.id,
                        "category": label.category,
                        "question": label.question,
                        "expected_path": label.expected_path,
                        "answer_path": result.answer_path,
                        "mode": result.mode,
                        "refused": result.refused,
                        "confidence": result.confidence,
                        "grounding": result.grounding,
                        "facts_hit": score["facts_hit"],
                        "facts_missed": score["facts_missed"],
                        "fact_details": score["fact_details"],
                        "passed": score["passed"],
                        "expected_path_hit": score["expected_path_hit"],
                        "citation_types": [citation.citation_type for citation in result.citations],
                        "citation_count": len(result.citations),
                        "latency_seconds": round(latency_seconds, 3),
                        "answer": result.answer,
                    }
                )

    return _build_report(
        rows,
        dataset=dataset,
        configs=configs,
        runs=runs,
        fake_generator=fake_generator,
        model_info=model_info,
        total_seconds=time.perf_counter() - started,
    )


def score_rag_vs_oag_answer(label: RagVsOagQuestion, result: AnswerResult) -> dict[str, Any]:
    text = _normalise_text(result.answer)
    fact_details = []
    for fact in label.expected_answer_facts:
        candidates = [fact.text, *fact.aliases]
        hit = any(_normalise_text(candidate) in text for candidate in candidates if candidate.strip())
        fact_details.append({"text": fact.text, "hit": hit})

    facts_hit = [item["text"] for item in fact_details if item["hit"]]
    facts_missed = [item["text"] for item in fact_details if not item["hit"]]
    if label.category == "out_of_scope":
        fact_passed = result.refused or bool(_REFUSAL_RE.search(result.answer)) or not facts_missed
    else:
        fact_passed = not result.refused and not facts_missed
    expected_path_hit = _path_matches(label.expected_path, result.answer_path)
    return {
        "facts_hit": facts_hit,
        "facts_missed": facts_missed,
        "fact_details": fact_details,
        "passed": fact_passed,
        "expected_path_hit": expected_path_hit,
    }


def format_rag_vs_oag_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"# RAG vs OAG Benchmark - {summary['best_config']} best config",
        "",
        f"Generated: {summary['generated_at']}",
        f"Dataset: {summary['dataset_version']} ({summary['question_count']} questions)",
        f"Runs: {summary['runs']}",
        f"Fake generator: {summary['fake_generator']}",
        f"Model: {_model_label(summary['model_info'])}",
        f"Total runtime: {report['latency']['total_seconds']:.1f}s",
        "",
        "## Overall By Configuration",
        "",
        "| Config | Passed | Accuracy | Path hit | Stable | Mean latency | P95 latency |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for config, metrics in report["by_config"].items():
        lines.append(
            f"| {config} | {metrics['passed']}/{metrics['total']} | {metrics['accuracy']:.0%} | "
            f"{metrics['path_accuracy']:.0%} | {metrics['stable_count']}/{metrics['question_count']} | "
            f"{metrics['mean_latency_seconds']:.2f}s | {metrics['p95_latency_seconds']:.2f}s |"
        )

    lines.extend(
        [
            "",
            "## Per-Category Accuracy",
            "",
            "| Config | Category | Passed | Accuracy | Path hit |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for config, categories in report["by_category"].items():
        for category, metrics in categories.items():
            lines.append(
                f"| {config} | {category} | {metrics['passed']}/{metrics['total']} | "
                f"{metrics['accuracy']:.0%} | {metrics['path_accuracy']:.0%} |"
            )

    lines.extend(["", "## Path Usage Matrix", "", "| Config | oag | rag | rag+ontology | Other |"])
    lines.append("|---|---:|---:|---:|---:|")
    for config, paths in report["path_usage"].items():
        lines.append(
            f"| {config} | {paths.get('oag', 0)} | {paths.get('rag', 0)} | "
            f"{paths.get('rag+ontology', 0)} | {paths.get('other', 0)} |"
        )

    lines.extend(["", "## Citation Types", "", "| Config | document | ontology_object | process_registry | none |"])
    lines.append("|---|---:|---:|---:|---:|")
    for config, citations in report["citation_type_usage"].items():
        lines.append(
            f"| {config} | {citations.get('document', 0)} | {citations.get('ontology_object', 0)} | "
            f"{citations.get('process_registry', 0)} | {citations.get('none', 0)} |"
        )

    target = report["interpretation_targets"]
    lines.extend(
        [
            "",
            "## Interpretation Targets",
            "",
            f"- Structured relationship lift: {target['structured_relationship_lift']:+.0%}",
            f"- Aggregate lift: {target['aggregate_lift']:+.0%}",
            f"- Narrative loss versus RAG-only: {target['narrative_loss']:+.0%}",
            f"- Out-of-scope preserved by OAG-first: {target['out_of_scope_preserved']:.0%}",
            "",
            "## Failed Rows",
            "",
            "| Config | Run | ID | Category | Path | Missed facts |",
            "|---|---:|---|---|---|---|",
        ]
    )
    failed = [row for row in report["rows"] if not row["passed"]]
    for row in failed[:30]:
        missed = "; ".join(row["facts_missed"]) or "n/a"
        lines.append(
            f"| {row['config']} | {row['run']} | {row['id']} | {row['category']} | "
            f"{row['answer_path']} | {missed[:180]} |"
        )
    if not failed:
        lines.append("| n/a | 0 | n/a | n/a | n/a | No failed rows. |")
    elif len(failed) > 30:
        lines.append(f"| ... | ... | ... | ... | ... | {len(failed) - 30} more failed rows omitted. |")

    lines.extend(
        [
            "",
            "## Reviewer Notes",
            "",
            "- Fake-generator runs validate benchmark arithmetic only and are not model-quality evidence.",
            "- Real runs should use `--runs 3` so stability can be inspected before architectural decisions are made.",
            "- OAG-only is intentionally expected to degrade on narrative questions; it is a boundary probe, not the target user mode.",
        ]
    )
    return "\n".join(lines)


def write_rag_vs_oag_scorecard(report: dict[str, Any], output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stamp = report["summary"]["generated_at"].replace(":", "-")
    config_slug = "-".join(report["summary"]["configs"])
    base = output / f"rag-vs-oag-{config_slug}-{stamp}"
    json_path = base.with_suffix(".json")
    md_path = base.with_suffix(".md")
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(format_rag_vs_oag_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


class _FakeRagVsOagAnswerService:
    def __init__(self, labels: list[RagVsOagQuestion]) -> None:
        self.labels_by_question = {label.question: label for label in labels}
        self.model_info = {"backend": "scripted", "llm": "fake-rag-vs-oag", "embed": "none"}

    def answer(self, question: str, top_k: int = 5, *, routing_mode: RoutingMode = "oag_first", **kwargs) -> AnswerResult:
        del top_k, kwargs
        label = self.labels_by_question[question]
        if label.category == "out_of_scope":
            answer_path = "oag" if routing_mode == "oag_only" else "rag"
            return AnswerResult(answer=REFUSAL, citations=[], mode="fake", answer_path=answer_path, refused=True)
        if routing_mode == "oag_only" and label.category == "narrative":
            return AnswerResult(answer=REFUSAL, citations=[], mode="oag-only", answer_path="oag", refused=True)

        facts = [fact.text for fact in label.expected_answer_facts]
        if routing_mode == "rag_only" and label.category in {"structured_entity", "structured_relationship", "aggregate"}:
            facts = facts[: max(len(facts) - 1, 0)]
        if routing_mode == "oag_only" and label.category == "mixed":
            facts = facts[:1]
        answer = " ".join(facts) or "The available evidence does not provide that fact."
        citations = _fake_citations(label, routing_mode)
        return AnswerResult(
            answer=f"{answer} [1]",
            citations=citations,
            mode="fake",
            answer_path=_fake_answer_path(label, routing_mode),
            refused=False,
            confidence="grounded",
        )


def _fake_citations(label: RagVsOagQuestion, routing_mode: RoutingMode) -> list[Citation]:
    if routing_mode == "rag_only":
        citation_type = "document"
    elif routing_mode == "oag_only" or label.expected_path == "oag":
        citation_type = "ontology_object"
    elif label.category == "mixed" and routing_mode == "oag_first":
        return [
            Citation(source_id="fake-doc", source_title="Fake document", heading="fake", ordinal=1),
            Citation(
                source_id="fake-oag",
                source_title="Fake ontology object",
                heading="fake",
                ordinal=0,
                citation_type="ontology_object",
            ),
        ]
    else:
        citation_type = "document"
    return [Citation(source_id="fake", source_title="Fake evidence", heading="fake", ordinal=1, citation_type=citation_type)]


def _fake_answer_path(label: RagVsOagQuestion, routing_mode: RoutingMode) -> str:
    if routing_mode == "rag_only":
        return "rag"
    if routing_mode == "oag_only":
        return "oag"
    if label.category == "mixed":
        return "rag+ontology"
    if label.expected_path == "oag":
        return "oag"
    return "rag"


def _production_answer_service():
    from assistant.api.app import app

    return app.state.answer


def _build_report(
    rows: list[dict[str, Any]],
    *,
    dataset: RagVsOagDataset,
    configs: tuple[RoutingMode, ...],
    runs: int,
    fake_generator: bool,
    model_info: dict[str, Any],
    total_seconds: float,
) -> dict[str, Any]:
    by_config = {config: _metrics([row for row in rows if row["config"] == config]) for config in configs}
    by_category = {
        config: {
            category: _metrics([row for row in rows if row["config"] == config and row["category"] == category])
            for category in sorted({row["category"] for row in rows})
        }
        for config in configs
    }
    best_config = max(by_config, key=lambda config: (by_config[config]["accuracy"], by_config[config]["path_accuracy"]))
    latency_values = [float(row["latency_seconds"]) for row in rows]
    report = {
        "summary": {
            "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "dataset_version": dataset.dataset_version,
            "source_corpus": dataset.source_corpus,
            "question_count": len(dataset.questions),
            "runs": runs,
            "configs": list(configs),
            "fake_generator": fake_generator,
            "model_info": model_info,
            "best_config": best_config,
        },
        "latency": {
            "total_seconds": round(total_seconds, 3),
            "mean_seconds": round(statistics.mean(latency_values), 3) if latency_values else 0.0,
            "p95_seconds": round(_percentile(latency_values, 0.95), 3),
        },
        "by_config": by_config,
        "by_category": by_category,
        "path_usage": _path_usage(rows, configs),
        "citation_type_usage": _citation_type_usage(rows, configs),
        "stability": _stability(rows, configs),
        "interpretation_targets": _interpretation_targets(by_category),
        "rows": rows,
    }
    return report


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    passed = sum(1 for row in rows if row["passed"])
    path_hits = sum(1 for row in rows if row["expected_path_hit"])
    latencies = [float(row["latency_seconds"]) for row in rows]
    question_count = len({row["id"] for row in rows})
    stable_count = sum(1 for signatures in _signatures_by_question(rows).values() if len(signatures) == 1)
    return {
        "total": total,
        "passed": passed,
        "accuracy": passed / total if total else 0.0,
        "path_hits": path_hits,
        "path_accuracy": path_hits / total if total else 0.0,
        "question_count": question_count,
        "stable_count": stable_count,
        "mean_latency_seconds": statistics.mean(latencies) if latencies else 0.0,
        "p95_latency_seconds": _percentile(latencies, 0.95),
    }


def _signatures_by_question(rows: list[dict[str, Any]]) -> dict[str, set[tuple[Any, ...]]]:
    signatures: dict[str, set[tuple[Any, ...]]] = defaultdict(set)
    for row in rows:
        signatures[row["id"]].add(
            (
                row["passed"],
                row["answer_path"],
                tuple(row["facts_missed"]),
                row["refused"],
            )
        )
    return signatures


def _path_usage(rows: list[dict[str, Any]], configs: tuple[RoutingMode, ...]) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = {}
    for config in configs:
        counter: Counter[str] = Counter()
        for row in rows:
            if row["config"] != config:
                continue
            path = row["answer_path"]
            counter[path if path in {"oag", "rag", "rag+ontology"} else "other"] += 1
        matrix[config] = dict(counter)
    return matrix


def _citation_type_usage(rows: list[dict[str, Any]], configs: tuple[RoutingMode, ...]) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = {}
    for config in configs:
        counter: Counter[str] = Counter()
        for row in rows:
            if row["config"] != config:
                continue
            if not row["citation_types"]:
                counter["none"] += 1
            else:
                counter.update(row["citation_types"])
        matrix[config] = dict(counter)
    return matrix


def _stability(rows: list[dict[str, Any]], configs: tuple[RoutingMode, ...]) -> dict[str, Any]:
    by_config = {}
    for config in configs:
        config_rows = [row for row in rows if row["config"] == config]
        signatures = _signatures_by_question(config_rows)
        unstable = [question_id for question_id, values in signatures.items() if len(values) > 1]
        by_config[config] = {
            "question_count": len(signatures),
            "unstable_count": len(unstable),
            "unstable_ids": unstable,
        }
    return by_config


def _interpretation_targets(by_category: dict[str, dict[str, dict[str, Any]]]) -> dict[str, float]:
    def accuracy(config: str, category: str) -> float:
        return float(by_category.get(config, {}).get(category, {}).get("accuracy", 0.0))

    return {
        "structured_relationship_lift": accuracy("oag_first", "structured_relationship")
        - accuracy("rag_only", "structured_relationship"),
        "aggregate_lift": accuracy("oag_first", "aggregate") - accuracy("rag_only", "aggregate"),
        "narrative_loss": accuracy("oag_first", "narrative") - accuracy("rag_only", "narrative"),
        "out_of_scope_preserved": accuracy("oag_first", "out_of_scope"),
    }


def _path_matches(expected: ExpectedPath, actual: str) -> bool:
    if expected == "either":
        return True
    if expected == "rag":
        return actual in {"rag", "rag+ontology"}
    return actual == "oag"


def _normalise_text(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * percentile))))
    return float(ordered[index])


def _model_label(info: dict[str, Any]) -> str:
    return " · ".join(str(value) for value in (info.get("backend"), info.get("llm"), info.get("embed")) if value)
