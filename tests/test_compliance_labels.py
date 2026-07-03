"""Ground-truth label validation for compliance reasoning evaluation."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from assistant.eval.compliance_reasoning import (
    REQUIRED_CLASSIFICATIONS,
    ComplianceReasoningLabel,
)

ROOT = Path(__file__).resolve().parents[1]
LABELS_PATH = ROOT / "tests" / "evaluation" / "compliance_reasoning_labels.json"
FIXTURE_PATHS = [
    ROOT / "docs" / "data-and-governance" / "test-fixtures" / "synthetic-vat-conflict-learning-pack.md",
    ROOT / "docs" / "data-and-governance" / "test-fixtures" / "synthetic-packaging-waste-conflict-learning-pack.md",
]

REQUIRED_DOMAINS = {"vat", "packaging_waste"}


def _load_labels() -> list[ComplianceReasoningLabel]:
    raw_labels = json.loads(LABELS_PATH.read_text())
    assert isinstance(raw_labels, list)
    return [ComplianceReasoningLabel.model_validate(item) for item in raw_labels]


def test_compliance_reasoning_labels_have_required_coverage() -> None:
    labels = _load_labels()

    assert 30 <= len(labels) <= 50
    assert len({label.id for label in labels}) == len(labels)
    assert {label.domain for label in labels} == REQUIRED_DOMAINS

    coverage = Counter(label.expected_classification for label in labels)
    for classification in REQUIRED_CLASSIFICATIONS:
        assert coverage[classification] >= 5


def test_compliance_reasoning_fixtures_are_marked_as_test_only() -> None:
    for path in FIXTURE_PATHS:
        text = path.read_text().lower()

        assert "deliberately incorrect internal-source test fixture" in text
        assert "not policy, guidance or a training pack" in text
