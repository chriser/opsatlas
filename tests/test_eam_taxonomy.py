"""Enterprise Activity Model taxonomy tests."""

from __future__ import annotations

import json

import pytest

from assistant.eam.taxonomy import TaxonomyConfig, classify_domain, classify_lifecycle


def test_default_taxonomy_loads_sorted_retail_domains() -> None:
    taxonomy = TaxonomyConfig.load()

    assert taxonomy.version == "eam-taxonomy.v2"
    assert "APQC Retail Process Classification Framework and SCOR" in taxonomy.provenance
    assert [domain.id for domain in taxonomy.domains[:3]] == [
        "ordering",
        "receiving-returns-recalls",
        "grir-invoice-reconciliation",
    ]
    assert taxonomy.domains[-1].id == "forecasting-replenishment"
    assert [stage.id for stage in taxonomy.lifecycle_stages] == [
        "plan-govern",
        "configure",
        "source-replenish",
        "receive-control",
        "sell-operate",
        "reconcile-close",
        "assure-improve",
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

    configure = taxonomy.classify_lifecycle("Master data setup creates the article record and tax setup parameters.")
    source = taxonomy.classify_lifecycle("Supplier ordering and replenishment orders are generated from the schedule.")

    assert configure is not None
    assert configure.item_id == "configure"
    assert source is not None
    assert source.item_id == "source-replenish"


def test_lifecycle_classifier_maps_representative_value_chain_processes() -> None:
    taxonomy = TaxonomyConfig.load()

    invoice = taxonomy.classify_lifecycle("GRIR invoice matching and reconciliation happen before period close.")
    receipt = taxonomy.classify_lifecycle("Goods receipt and delivery return controls are recorded in inventory.")
    sales = taxonomy.classify_lifecycle("Pump sales flow through POS tills during forecourt business day operation.")

    assert invoice is not None
    assert invoice.item_id == "reconcile-close"
    assert receipt is not None
    assert receipt.item_id == "receive-control"
    assert sales is not None
    assert sales.item_id == "sell-operate"


def test_module_level_classifiers_can_use_supplied_taxonomy() -> None:
    taxonomy = TaxonomyConfig.load()

    domain = classify_domain("POS tax behaviour affects the sales channel.", taxonomy)
    lifecycle = classify_lifecycle("The annual audit reviews exceptions and corrective improvement actions.", taxonomy)

    assert domain is not None
    assert domain.item_id == "sales"
    assert lifecycle is not None
    assert lifecycle.item_id == "assure-improve"


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
