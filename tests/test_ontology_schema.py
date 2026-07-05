"""Ontology schema registry tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from assistant.ontology import SchemaRegistry


def test_seed_schema_loads_expected_object_and_link_types() -> None:
    registry = SchemaRegistry.load()

    assert set(registry.object_types) == {
        "source",
        "process",
        "role",
        "system",
        "control",
        "obligation",
        "internal_claim",
        "compliance_finding",
    }
    assert registry.require_object_type("process").primary_key == "process_id"
    assert registry.require_object_type("process").properties[0].name == "process_id"
    assert registry.require_link_type("process_uses_system").from_type == "process"
    assert registry.require_link_type("process_uses_system").to_type == "system"
    assert registry.require_action_type("rebuild_ontology").edit_kind == "custom"


def test_schema_rejects_unknown_base_types_with_clear_error() -> None:
    payload = {
        "object_types": [
            {
                "api_name": "bad_object",
                "display_name": "Bad Object",
                "primary_key": "id",
                "properties": [{"name": "id", "base_type": "uuid", "required": True}],
            }
        ],
        "link_types": [],
        "action_types": [],
    }

    with pytest.raises(ValidationError, match="base_type"):
        SchemaRegistry.from_dict(payload)


def test_schema_rejects_unknown_link_references() -> None:
    payload = {
        "object_types": [
            {
                "api_name": "source",
                "display_name": "Source",
                "primary_key": "source_id",
                "properties": [{"name": "source_id", "base_type": "string", "required": True}],
            }
        ],
        "link_types": [
            {
                "api_name": "source_mentions_process",
                "from_type": "source",
                "to_type": "process",
                "cardinality": "many_to_many",
            }
        ],
        "action_types": [],
    }

    with pytest.raises(ValidationError, match="unknown to_type 'process'"):
        SchemaRegistry.from_dict(payload)


def test_schema_rejects_action_object_parameters_with_unknown_object_type() -> None:
    payload = {
        "object_types": [
            {
                "api_name": "source",
                "display_name": "Source",
                "primary_key": "source_id",
                "properties": [{"name": "source_id", "base_type": "string", "required": True}],
            }
        ],
        "link_types": [],
        "action_types": [
            {
                "api_name": "approve_process",
                "display_name": "Approve Process",
                "parameters": [{"name": "process", "type": "object", "object_type": "process"}],
                "edit_kind": "custom",
            }
        ],
    }

    with pytest.raises(ValidationError, match="unknown object_type 'process'"):
        SchemaRegistry.from_dict(payload)


def test_describe_for_llm_snapshot() -> None:
    registry = SchemaRegistry.load()

    assert registry.describe_for_llm() == "\n".join([
        "Ontology schema ontology-schema.v1.",
        "Object types:",
        (
            "- source (Source); pk=source_id; props=source_id:string*, title:string*, filename:string, "
            "source_type:string, approval_status:string, content_sha256:string, version:integer."
        ),
        (
            "- process (Process); pk=process_id; props=process_id:string*, name:string*, domain:string, "
            "capabilities:string_list, business_rules:string_list."
        ),
        "- role (Role); pk=normalized_name; props=normalized_name:string*, name:string*.",
        "- system (System); pk=normalized_name; props=normalized_name:string*, name:string*.",
        "- control (Control); pk=normalized_name; props=normalized_name:string*, name:string*, control_type:string.",
        (
            "- obligation (External Obligation); pk=obligation_id; props=obligation_id:string*, modality:string*, "
            "actor:string, action:string*, condition:string, key_terms:string_list, source_section:string, source_title:string."
        ),
        (
            "- internal_claim (Internal Claim); pk=claim_id; props=claim_id:string*, modality:string*, actor:string, "
            "action:string*, condition:string, key_terms:string_list, source_section:string, source_title:string."
        ),
        (
            "- compliance_finding (Compliance Finding); pk=finding_id; props=finding_id:string*, review_id:string, "
            "classification:string*, severity:string, status:string, rationale:string, alignment_score:double."
        ),
        "Link types:",
        "- process_has_role: process -> role (many_to_many).",
        "- process_uses_system: process -> system (many_to_many).",
        "- process_enforced_by: process -> control (many_to_many).",
        "- process_derived_from: process -> source (many_to_many).",
        "- obligation_extracted_from: obligation -> source (many_to_many).",
        "- claim_extracted_from: internal_claim -> source (many_to_many).",
        "- finding_about_obligation: compliance_finding -> obligation (many_to_many).",
        "- finding_about_claim: compliance_finding -> internal_claim (many_to_many).",
        "- finding_affects_process: compliance_finding -> process (many_to_many).",
        "Action types:",
        "- rebuild_ontology (custom); params=none; approval=false.",
        "- approve_source (update); params=source_id:string*; approval=false.",
        "- reject_source (update); params=source_id:string*; approval=false.",
        "- accept_issue (custom); params=source_id:string*, check:string*, detail:string*; approval=false.",
        "- save_document (update); params=source_id:string*, text:string*; approval=false.",
        "- capture_governance_snapshot (custom); params=none; approval=false.",
    ])
