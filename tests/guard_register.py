"""Every guard proven (the Definition of Done of 3 October 2026, REF F10): the register of the checks that keep a
promise, how to switch each one off, and the tests that must then fail.

tests/test_guards_proven.py runs each guard's tests with ``OPSATLAS_DISABLE_GUARD=<name>`` (conftest.py applies the
switch before anything is imported) and requires at least one of them to fail. A guard whose tests still pass with it
off is not tested, whatever the coverage says. A new guard is added here with the tests that prove it.
"""
from __future__ import annotations

import importlib


def _off(module: str, name: str, replacement) -> None:
    target = importlib.import_module(module)
    setattr(target, name, replacement)


def _method_off(module: str, cls: str, name: str, replacement) -> None:
    setattr(getattr(importlib.import_module(module), cls), name, replacement)


GUARDS: dict[str, dict] = {
    "permission check (IAM)": {
        "off": lambda: _method_off("assistant.api.access", "Actor", "require", lambda self, *a, **k: None),
        "tests": ["tests/test_sales_iam.py::test_a_reader_of_one_organisation_gets_nothing_from_another_not_even_its_name"],
    },
    "restricted documents (REF S13)": {
        "off": lambda: _method_off("assistant.iam.visibility", "Visibility", "can_read", lambda self, source_id: True),
        "tests": ["tests/test_document_grants.py::test_a_restricted_document_is_invisible_to_a_reader_outside_its_audience"],
    },
    "derived views withheld (REF S13, S16)": {
        "off": lambda: _off("assistant.api.access", "derived_guard", lambda request: None),
        "tests": ["tests/test_leak_sweep.py::test_no_role_outside_the_audience_receives_a_marker"],
    },
    "revoked while prepared (REF S16)": {
        "off": lambda: _off("assistant.api.access", "still_allowed", lambda request, permission: None),
        "tests": ["tests/test_space_leaks.py::test_an_answer_is_withheld_when_access_is_revoked_while_it_is_prepared"],
    },
    "service principals (REF S12)": {
        "off": lambda: _method_off("services.opsatlas_sales.service_principals", "ServicePrincipals", "identify",
                                   lambda self, presented: next(iter(self.principals.values()))),
        "tests": ["tests/test_service_principals.py::test_a_credential_that_belongs_to_no_principal_reaches_nothing"],
    },
    "conversation ownership (REF S14)": {
        "off": lambda: _method_off("services.opsatlas_sales.tibi_owners", "TibiOwners", "may", lambda self, *a: True),
        "tests": ["tests/test_sales_tibi_proxy.py::test_a_conversation_belongs_to_whoever_started_it",
                  "tests/test_scenarios_owners.py"],
    },
    "evidence recheck at delivery (REF S19)": {
        "off": lambda: _method_off("assistant.evidence.contract", "EvidenceBundle", "recheck", lambda self, *a: True),
        "tests": ["tests/test_channel_conformance.py::test_delivery_rechecks_the_evidence"],
    },
    "governed statements (REF S22)": {
        "off": lambda: _method_off("assistant.space_statements", "SpaceStatements", "governed", lambda self, config: config),
        "tests": ["tests/test_space_statements.py::test_a_changed_sentence_is_pending_until_approved",
                  "tests/test_scenarios_statements.py"],
    },
    "one writer at a time across processes (REF F10)": {
        "off": lambda: _off("assistant.storage", "locked", __import__("contextlib").nullcontext),
        "tests": ["tests/redteam/test_redteam_space_statements.py::test_two_instances_on_one_folder_lose_a_version",
                  "tests/redteam/test_redteam_tibi_owners.py::test_two_instances_on_one_folder_lose_a_recording"],
    },
    "unknown conversations get no restricted guide document (REF S11, F10)": {
        "off": lambda: _off("services.opsatlas_sales.routes_sales_api", "open_to_anyone", lambda *a: True),
        "tests": ["tests/test_tibi_projection.py::test_a_conversation_opsatlas_does_not_know_never_gets_a_restricted_guide_document"],
    },
    "scope covers every evidence path (REF H3b)": {
        "off": lambda: _method_off("assistant.answer.scope", "ScopeFilter", "excludes_any", lambda self, records: False),
        "tests": ["tests/test_scope_every_path.py::test_with_scope_on_no_path_carries_a_source_not_in_force",
                  "tests/test_scenarios_scope.py"],
    },
    "scope reads sources as they are now (REF H3b)": {
        "off": lambda: _off("assistant.answer.service", "as_it_is_now", lambda scope, register: scope.allow),
        "tests": ["tests/redteam/test_scope_h3b_redteam.py::test_scope_edit_after_index_built_still_leaks_through_retrieval"],
    },
    "scope rechecked before the answer is given (REF H3b)": {
        "off": lambda: _method_off("assistant.answer.service", "AnswerService", "_scope_changed", lambda self, *a: False),
        "tests": ["tests/redteam/test_scope_h3b_redteam.py::test_supersede_approved_mid_answer_lets_replaced_source_answer"],
    },
    "scope filter (REF H3, candidate)": {
        "off": lambda: _method_off("assistant.answer.scope", "ScopeFilter", "allow", lambda self, record: True),
        "tests": ["tests/test_answer_candidates.py::test_scope_lets_only_sources_in_force_for_the_site_asked_answer",
                  "tests/test_scenarios_scope.py"],
    },
}


def switch_off(name: str) -> None:
    if name not in GUARDS:
        raise KeyError(f"No such guard in tests/guard_register.py: {name}")
    GUARDS[name]["off"]()
