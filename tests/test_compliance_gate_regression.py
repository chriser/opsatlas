"""Regression gates for compliance reasoning heuristics and safety gates."""

from __future__ import annotations

import json
from pathlib import Path

from assistant.eval.compliance_reasoning import (
    evaluate_compliance_reasoning,
    load_compliance_labels,
)

BASELINE_PATH = Path("tests/evaluation/compliance_regression_baseline.json")
REQUIRED_PROTECTED_LABELS = {
    "vat-contradiction-retention-delete-001",
    "vat-contradiction-rate-change-old-rate-003",
    "packaging-contradiction-supplier-purchased-007",
}


def _baseline() -> dict:
    return json.loads(BASELINE_PATH.read_text())


def test_regression_baseline_captures_v6_in_domain_protected_labels() -> None:
    baseline = _baseline()
    protected = baseline["protected_labels"]

    assert baseline["schema"] == "compliance-regression-baseline-v1"
    assert len(protected) >= 28
    assert {item["split"] for item in protected} == {"in_domain"}
    assert REQUIRED_PROTECTED_LABELS.issubset({item["id"] for item in protected})


def test_fake_harness_preserves_v6_protected_labels_and_no_false_supported() -> None:
    labels = load_compliance_labels()
    baseline = _baseline()
    protected_ids = {item["id"] for item in baseline["protected_labels"]}

    report = evaluate_compliance_reasoning(labels, depth="deep", runs=1, fake_generator=True)
    rows_by_id = {row["id"]: row for row in report["rows"]}
    flipped = [
        f"{label_id}: expected {rows_by_id[label_id]['expected']} got {rows_by_id[label_id]['actual']}"
        for label_id in sorted(protected_ids)
        if rows_by_id[label_id]["actual"] != rows_by_id[label_id]["expected"]
    ]
    false_supported = [
        row["id"]
        for row in report["rows"]
        if row["actual"] == "supported" and not row["llm_called"]
    ]

    assert flipped == []
    assert false_supported == []
    assert report["split_metrics"]["in_domain"]["per_class"]["contradiction"]["recall"] == 1.0
