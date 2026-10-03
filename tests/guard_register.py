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


def _unreadable_as_absent(module: str):
    """A module's date reader with its fail-closed answer taken away: a date that cannot be read counts as no date."""
    scope = importlib.import_module("assistant.answer.scope")
    real = importlib.import_module(module).read_date
    return lambda value: None if real(value) is scope.UNREADABLE else real(value)


def _registry_from_the_live_register():
    """The process registry built from the register as it is when asked, not from the answer's reading."""
    service = importlib.import_module("assistant.answer.service").AnswerService
    real = service._process_records
    service._process_records = lambda self, reading=None: real(self, None)


def _passages_whatever_the_fingerprint():
    """The section store handing out a source's passages whatever text they were built from."""
    store = importlib.import_module("assistant.ingestion.store").SectionStore
    real = store.list_for_source
    store.list_for_source = lambda self, source_id, sha=None: real(self, source_id)


def _text_whatever_the_fingerprint():
    """The register handing out a source's text whatever record the reader holds."""
    register = importlib.import_module("assistant.sources.register").SourceRegister
    real = register.read_content
    register.read_content = lambda self, source_id, sha=None: real(self, source_id)


def _index_keeps_every_snapshot():
    """The search index keeping a snapshot even when it missed a source's passages."""
    index = importlib.import_module("assistant.retrieval.index").CorpusIndex
    real = index._build
    index._build = lambda self, records, fingerprint: (real(self, records, fingerprint)[0], True)


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
        "off": lambda: _method_off("assistant.answer.scope", "ScopeFilter", "closes_facts", lambda self, records: False),
        "tests": ["tests/test_scope_every_path.py::test_with_scope_on_no_path_carries_a_source_not_in_force",
                  "tests/test_scenarios_scope.py", "tests/test_scenarios_scope_answers.py"],
    },
    "scope reads sources as they are now (REF H3b)": {
        "off": lambda: _off("assistant.answer.service", "as_it_is_now", lambda scope, register: scope.allow),
        "tests": ["tests/redteam/test_scope_h3b_redteam.py::test_scope_edit_after_index_built_still_leaks_through_retrieval",
                  "tests/redteam/test_scope_h3b_round4_redteam.py::"
                  "test_a_source_approved_mid_answer_answers_beside_the_source_it_replaces",
                  "tests/test_scenarios_scope_answers.py"],
    },
    "the facts map holds to the answer's reading (REF H3b)": {
        "off": lambda: _method_off("assistant.answer.service", "AnswerService", "_facts_in_step", lambda self, approved: True),
        "tests": ["tests/redteam/test_scope_h3b_round4_redteam.py::"
                  "test_an_expired_process_approved_mid_answer_reaches_it_through_the_facts_map",
                  "tests/redteam/test_scope_h3b_round5_redteam.py::"
                  "test_scope_h3b_round5_out_of_step_facts_map_still_lets_process_registry_answer",
                  "tests/test_scenarios_scope_answers.py"],
    },
    "readers take only their record's passages (REF S23)": {
        "off": lambda: _passages_whatever_the_fingerprint(),
        "tests": ["tests/redteam/test_scope_h3b_round6_redteam.py::"
                  "test_scope_h3b_round6_failed_publish_text_read_midway_reaches_answer_scope_on",
                  "tests/redteam/test_scope_h3b_round6_redteam.py::"
                  "test_scope_h3b_round6_failed_publish_text_read_midway_reaches_answer_scope_off",
                  "tests/redteam/test_scope_h3b_round5_redteam.py::"
                  "test_scope_h3b_round5_new_version_landing_after_reading_reaches_this_answer",
                  "tests/test_scenarios_publish.py"],
    },
    "readers take only their record's text (REF S23)": {
        "off": lambda: _text_whatever_the_fingerprint(),
        "tests": ["tests/test_publish_order.py::test_the_live_version_stands_until_the_record_is_written",
                  "tests/redteam/test_scope_h3b_round6_redteam.py::"
                  "test_scope_h3b_round6_rebuild_racing_failed_publish_keeps_unapproved_facts",
                  "tests/test_scenarios_publish.py"],
    },
    "a publish stages before it touches anything live (REF S23)": {
        "off": lambda: _off("assistant.content.service", "stage_sections", lambda source_id, filename, content: []),
        "tests": ["tests/test_publish_order.py::test_a_text_that_cannot_be_split_fails_before_anything_live_is_touched"],
    },
    "a failed swap puts the live text and passages back (REF S23)": {
        "off": lambda: _method_off("assistant.content.service", "ContentService", "_put_back", lambda self, *a: None),
        "tests": ["tests/test_publish_order.py::test_a_failed_swap_leaves_the_live_version_whole",
                  "tests/test_scenarios_publish.py"],
    },
    "a rebuild failing after a publish is tried again (REF S23)": {
        "off": lambda: _method_off("assistant.content.service", "ContentService", "_rebuild_facts_after_publish", lambda self: None),
        "tests": ["tests/test_publish_order.py::test_a_rebuild_failing_after_the_swap_still_publishes"],
    },
    "the search index keeps no snapshot that missed a source (REF S23)": {
        "off": lambda: _index_keeps_every_snapshot(),
        "tests": ["tests/test_publish_order.py::test_a_search_during_a_failed_swap_does_not_lose_the_document"],
    },
    "the details editor applies one edit at a time (REF H3b)": {
        "off": lambda: _off("assistant.content.service", "locked", lambda path: __import__("contextlib").nullcontext()),
        "tests": ["tests/redteam/test_scope_h3b_round4_redteam.py::test_two_concurrent_edits_store_a_record_that_ends_before_it_starts"],
    },
    "plain site names only (REF H3b)": {
        "off": lambda: _off("assistant.content.service", "plain_site_name", lambda name: bool(name.strip())),
        "tests": ["tests/redteam/test_scope_h3b_round4_redteam.py::test_a_site_name_forges_an_until_label_on_a_source_with_no_end_date",
                  "tests/test_scenarios_details_editor.py"],
    },
    "an unreadable scope date keeps the source out (REF H3b)": {
        "off": lambda: _off("assistant.answer.scope", "read_date", _unreadable_as_absent("assistant.answer.scope")),
        "tests": ["tests/redteam/test_scope_h3b_today_redteam.py::test_unreadable_date_with_trailing_digits_is_read_as_a_date",
                  "tests/test_scenarios_scope.py"],
    },
    "the details editor refuses a date scope cannot read (REF H3b)": {
        "off": lambda: _off("assistant.content.service", "read_date", _unreadable_as_absent("assistant.content.service")),
        "tests": ["tests/redteam/test_scope_h3b_round3_redteam.py::test_scope_h3b_round3_editor_accepts_a_value_scope_cannot_read"],
    },
    "every passage says its scope (REF H3b)": {
        "off": lambda: _method_off("assistant.answer.scope", "ScopeFilter", "note", lambda self, record: ""),
        "tests": ["tests/redteam/test_scope_h3b_redteam.py::test_with_no_site_named_each_site_passage_says_its_site",
                  "tests/test_scenarios_scope_answers.py"],
    },
    "scope filter (REF H3, candidate)": {
        "off": lambda: _method_off("assistant.answer.scope", "ScopeFilter", "allow", lambda self, record: True),
        "tests": ["tests/test_answer_candidates.py::test_scope_judges_by_today_and_labels_what_comes_later",
                  "tests/test_scenarios_scope.py"],
    },
}


def switch_off(name: str) -> None:
    if name not in GUARDS:
        raise KeyError(f"No such guard in tests/guard_register.py: {name}")
    GUARDS[name]["off"]()
