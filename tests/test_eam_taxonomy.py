"""Enterprise Activity Model taxonomy tests."""

from __future__ import annotations

import json

import pytest

from assistant.eam.taxonomy import TaxonomyConfig, classify_domain, classify_lifecycle


def test_default_taxonomy_loads_sorted_retail_domains() -> None:
    taxonomy = TaxonomyConfig.load()

    assert taxonomy.version == "eam-taxonomy.v1"
    assert [domain.id for domain in taxonomy.domains[:3]] == [
        "ordering",
        "receiving-returns-recalls",
        "grir-invoice-reconciliation",
    ]
    assert taxonomy.domains[-1].id == "forecasting-replenishment"
    assert [stage.id for stage in taxonomy.lifecycle_stages] == [
        "intake",
        "validation",
        "create",
        "integrate",
        "activate",
        "maintain",
    ]


def test_domain_classifier_returns_best_match_and_confidence() -> None:
    taxonomy = TaxonomyConfig.load()

    match = taxonomy.classify_domain(
        "Supplier schedule data feeds replenishment orders and ordering day cut-off logic."
    )

    assert match is not None
    assert match.item_id == "ordering"
    assert match.confidence > 0
    assert "ordering" in match.matched_keywords


def test_lifecycle_classifier_uses_phrase_and_token_keywords() -> None:
    taxonomy = TaxonomyConfig.load()

    validation = taxonomy.classify_lifecycle("Mandatory-field checks run before bulk processing.")
    integration = taxonomy.classify_lifecycle("The downstream interface maps article data into consumer systems.")

    assert validation is not None
    assert validation.item_id == "validation"
    assert integration is not None
    assert integration.item_id == "integrate"


def test_module_level_classifiers_can_use_supplied_taxonomy() -> None:
    taxonomy = TaxonomyConfig.load()

    domain = classify_domain("POS tax behaviour affects the sales channel.", taxonomy)
    lifecycle = classify_lifecycle("The record is released and available for use.", taxonomy)

    assert domain is not None
    assert domain.item_id == "sales"
    assert lifecycle is not None
    assert lifecycle.item_id == "activate"


def test_taxonomy_env_override_and_validation_errors(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "taxonomy.json"
    config_path.write_text(
        json.dumps(
            {
                "version": "custom",
                "domains": [
                    {"id": "alpha", "label": "Alpha", "order": 20, "keywords": ["alpha"]},
                    {"id": "beta", "label": "Beta", "order": 10, "keywords": ["beta"]},
                ],
                "lifecycle_stages": [
                    {"id": "start", "label": "Start", "order": 10, "keywords": ["start"]},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("KP_EAM_TAXONOMY", str(config_path))

    taxonomy = TaxonomyConfig.load()

    assert [domain.id for domain in taxonomy.domains] == ["beta", "alpha"]

    config_path.write_text(
        json.dumps(
            {
                "version": "broken",
                "domains": [
                    {"id": "alpha", "label": "Alpha", "order": 10, "keywords": ["alpha"]},
                    {"id": "alpha", "label": "Again", "order": 20, "keywords": ["again"]},
                ],
                "lifecycle_stages": [
                    {"id": "start", "label": "Start", "order": 10, "keywords": ["start"]},
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="domain ids must be unique"):
        TaxonomyConfig.load()
