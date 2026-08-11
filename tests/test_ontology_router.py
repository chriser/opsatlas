"""Ontology answer router tests."""

from __future__ import annotations

from assistant.ontology import OntologyQueryService, OntologyStore
from assistant.ontology.router import build_structured_answer_plan


def test_aggregate_supplier_readiness_answer_preserves_contract_and_mapping_terms(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db")
    store.upsert_object(
        "process",
        "supplier-readiness",
        {
            "name": "Supplier Readiness",
            "domain": "supplier",
            "key_facts": [
                (
                    "System dependency: Downstream price and assortment processes. "
                    "Purpose: Use the supplier only after setup is complete. "
                    "Details: Supplier readiness and contract availability."
                ),
                (
                    "Process step: Trading support / master data owner performs Complete contract links "
                    "and readiness controls. The supplier is linked to the mandatory operational contracts "
                    "and any remaining setup controls are completed before activation."
                ),
                (
                    "Business rule: A supplier should not be treated as active and usable until mandatory "
                    "contracts, mapping and readiness controls are in place."
                ),
                (
                    "Business rule: A commercial contract, service contract and payment contract are all "
                    "required before the supplier can be used correctly in downstream processes."
                ),
            ],
        },
    )

    plan = build_structured_answer_plan(
        "List supplier readiness elements that should be complete before downstream use.",
        OntologyQueryService(store),
    )

    assert plan is not None
    assert plan.intent == "aggregate_facts"
    assert "commercial contract" in plan.answer
    assert "service contract" in plan.answer
    assert "payment contract" in plan.answer
    assert "mapping controls" in plan.answer


def test_aggregate_article_list_criteria_answer_preserves_hierarchy_nodes(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db")
    store.upsert_object(
        "process",
        "article-list-criteria",
        {
            "name": "Article Lists, Criteria Logic and Controlled List Usage",
            "domain": "article",
            "key_facts": [
                "Business rule: Automatic article lists are driven by criteria and refreshed regularly by the system.",
                (
                    "Learning record: authorised user / criteria combination: automatic lists can combine "
                    "multiple criteria such as hierarchy, manufacturer and attributes."
                ),
                (
                    "Business rule: Automatic list criteria can include manufacturer, attributes, hierarchy nodes "
                    "and other supported fields, and can be combined logically."
                ),
            ],
        },
    )

    plan = build_structured_answer_plan(
        "List examples of automatic article-list criteria.",
        OntologyQueryService(store),
    )

    assert plan is not None
    assert plan.intent == "aggregate_facts"
    assert "manufacturer" in plan.answer
    assert "attributes" in plan.answer
    assert "hierarchy nodes" in plan.answer


def test_relationship_readiness_controls_answer_uses_control_terms_not_owner(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db")
    store.upsert_object(
        "process",
        "supplier-readiness",
        {
            "name": "Supplier Readiness",
            "domain": "supplier",
            "key_facts": [
                (
                    "Role responsibility: Trading support assistant / master data operator - Creates the supplier "
                    "record in the operational master data tool and may manage status and readiness steps."
                ),
                (
                    "Business rule: A supplier should not be treated as active and usable until mandatory contracts, "
                    "mapping and readiness controls are in place."
                ),
            ],
        },
    )

    plan = build_structured_answer_plan(
        "Which readiness controls matter even if a supplier record is active?",
        OntologyQueryService(store),
    )

    assert plan is not None
    assert plan.intent == "aggregate_facts"
    assert "contracts mapping and readiness controls must be complete" in plan.answer
    assert "relevant owner" not in plan.answer


def test_relationship_sellability_answer_preserves_site_pricing_and_assortment_terms(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db")
    store.upsert_object(
        "process",
        "article-sellability",
        {
            "name": "Article Integration, Tax Handling, Product Change and Article Lists",
            "domain": "article",
            "key_facts": [
                (
                    "Business rule: Site sellability depends on later price and assortment associations, "
                    "not merely on article existence."
                ),
                (
                    "Q&A fact: Does article activation mean the item is immediately sellable in store? No. "
                    "Site sellability still depends on pricing and assortment-related setup."
                ),
            ],
        },
    )

    plan = build_structured_answer_plan(
        "Which downstream setup makes active articles become sellable at a site?",
        OntologyQueryService(store),
    )

    assert plan is not None
    assert "site sellability depends on pricing and assortment associations" in plan.answer


def test_relationship_bulk_upload_validation_answer_preserves_check_terms(tmp_path) -> None:
    store = OntologyStore(tmp_path / "ontology.db")
    store.upsert_object(
        "process",
        "article-upload",
        {
            "name": "End-to-End Article Setup and Bulk Upload Process",
            "domain": "article",
            "key_facts": [
                (
                    "Process step: Operational tool and master data operator performs Run staging validation checks. "
                    "The staging area performs mandatory-field, format and referential checks. Errors must be "
                    "corrected before processing."
                ),
            ],
        },
    )

    plan = build_structured_answer_plan(
        "Which validation checks should run before bulk article upload processing?",
        OntologyQueryService(store),
    )

    assert plan is not None
    assert "format mandatory-field and referential checks run before processing" in plan.answer
