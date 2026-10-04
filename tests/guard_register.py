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


def _staging_writes_the_live_files():
    """A publish that writes its new text and passages straight over the live ones (as before REF S23)."""
    register = importlib.import_module("assistant.sources.register").SourceRegister
    store = importlib.import_module("assistant.ingestion.store").SectionStore
    register.stage_content = lambda self, source_id, content: self.write_content(source_id, content)
    store.stage_for_source = lambda self, source_id, sections, sha: self.replace_for_source(source_id, sections, sha=sha)


def _no_move_on_read():
    importlib.import_module("assistant.sources.register").SourceRegister.MOVE_ON_READ = False
    importlib.import_module("assistant.ingestion.store").SectionStore.MOVE_ON_READ = False


def _reader_moves_unchecked():
    """A reader's move that checks the staged text once, outside the lock, and renames it (as before S7)."""
    register = importlib.import_module("assistant.sources.register").SourceRegister
    hashlib = importlib.import_module("hashlib")

    def promote(self, source_id, sha, blocking=True):
        staged = self._staged_path(source_id)
        if not staged.exists() or hashlib.sha256(staged.read_bytes()).hexdigest() != sha:
            return False
        self.promote_content(source_id)
        return True
    register.promote_if_committed = promote


def _readers_wait():
    """Readers that wait for the workspace's lock instead of only trying it (as the content list did in round 7)."""
    from contextlib import contextmanager
    storage = importlib.import_module("assistant.storage")

    @contextmanager
    def waits(path):
        if path is None:
            yield True
            return
        with storage.locked(path):
            yield True
    for module in ("assistant.content.service", "assistant.sources.register", "assistant.ingestion.store"):
        setattr(importlib.import_module(module), "if_free", waits)


def _side_effects_fail_the_action():
    """Side effects whose failure fails the action, after its handler has taken the decision (as before round 11)."""
    engine = importlib.import_module("assistant.ontology.actions").ActionsEngine

    def run(self, context):
        payload = {"handler": self._handlers[context.action.api_name](context) or {}}
        for name in context.action.side_effects:
            self._side_effects[name](context, payload["handler"])
        return payload
    engine._run_handler_and_side_effects = run


def _draft_decisions_unnamed():
    """Publishing or returning a submitted draft without checking which draft the reviewer read."""
    service = importlib.import_module("assistant.content.service")

    def submitted(self, source_id, draft_sha, refused):
        state = self.store.document(source_id) or {}
        if state.get("status") != "submitted" or state.get("draft_text") is None:
            raise service.ContentError(refused)
        return state
    service.ContentService._submitted = submitted


def _stores_unchecked():
    """Governed stores that write whoever asks, lock or not (as before the door)."""
    _off("assistant.storage", "require", lambda *args, **kwargs: None)
    _off("assistant.content.store", "holds", lambda path: True)


def _a_lock_per_space():
    """Each space's door and stores on its own lock, not the workspace's one lock."""
    def govern(core, lock):
        own = core.state.register.index_file
        core.state.write_lock = own
        for store in (core.state.register, core.state.section_store, core.state.content.store):
            store.governed_by = own
    _off("services.opsatlas_sales.app", "govern", govern)


def _every_entry_committed():
    """Version entries written as committed from the start (as before S6 was refined)."""
    store = importlib.import_module("assistant.content.store").ContentStore
    real = store.add_version
    store.add_version = lambda self, *a, committed=True, **k: real(self, *a, committed=True, **k)


def _no_staged_reads():
    importlib.import_module("assistant.sources.register").SourceRegister.READ_STAGED = False
    importlib.import_module("assistant.ingestion.store").SectionStore.READ_STAGED = False


def _citations_named_as_now():
    """Citations stamped with the version live when the answer ends, whatever record they read."""
    service = importlib.import_module("assistant.answer.service").AnswerService
    real = service._stamp
    service._stamp = lambda self, citations: real(self, [c.model_copy(update={"read_n": None}) for c in citations])


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
        "tests": ["tests/redteam/test_s23_round3_redteam.py::"
                  "test_s23_round3_governance_statements_cache_previous_text_under_committed_version",
                  "tests/redteam/test_scope_h3b_round6_redteam.py::"
                  "test_scope_h3b_round6_failed_publish_text_read_midway_reaches_answer_scope_on",
                  "tests/redteam/test_scope_h3b_round6_redteam.py::"
                  "test_scope_h3b_round6_failed_publish_text_read_midway_reaches_answer_scope_off",
                  "tests/redteam/test_scope_h3b_round5_redteam.py::"
                  "test_scope_h3b_round5_new_version_landing_after_reading_reaches_this_answer",
                  "tests/test_scenarios_publish.py"],
    },
    "readers take only their record's text (REF S23)": {
        "off": lambda: _text_whatever_the_fingerprint(),
        "tests": ["tests/test_publish_order.py::test_a_reader_holding_the_previous_record_gets_none_of_the_new_text",
                  "tests/test_publish_order.py::test_the_live_version_stands_until_the_record_is_written",
                  "tests/redteam/test_scope_h3b_round6_redteam.py::"
                  "test_scope_h3b_round6_rebuild_racing_failed_publish_keeps_unapproved_facts",
                  "tests/test_scenarios_publish.py"],
    },
    "a publish stages before it touches anything live (REF S23)": {
        "off": lambda: _off("assistant.content.service", "stage_sections", lambda source_id, filename, content: []),
        "tests": ["tests/test_publish_order.py::test_a_text_that_cannot_be_split_fails_before_anything_live_is_touched"],
    },
    "nothing live changes before a publish's record is written (REF S23)": {
        "off": lambda: _staging_writes_the_live_files(),
        "tests": ["tests/test_publish_order.py::test_a_failed_swap_leaves_the_live_version_whole",
                  "tests/redteam/test_s23_round1_redteam.py::test_s23_round1_crash_between_writes_leaves_live_version_unreadable",
                  "tests/redteam/test_s23_round1_redteam.py::test_s23_round1_content_view_during_swap_shows_unapproved_text"],
    },
    "a committed version is moved into place by its readers (REF S23)": {
        "off": lambda: _no_move_on_read(),
        "tests": ["tests/test_publish_order.py::test_a_search_while_a_committed_version_cannot_be_moved_does_not_lose_the_document",
                  "tests/test_scenarios_publish.py"],
    },
    "the steps after a publish are tried again (REF S23)": {
        "off": lambda: setattr(importlib.import_module("assistant.content.service").ContentService, "FOLLOW_UP_ATTEMPTS", 1),
        "tests": ["tests/test_publish_order.py::test_a_rebuild_failing_after_the_swap_still_publishes",
                  "tests/redteam/test_s23_round1_redteam.py::test_s23_round1_failed_process_refresh_after_swap_is_never_retried"],
    },
    "the search index keeps no snapshot that missed a source (REF S23)": {
        "off": lambda: _index_keeps_every_snapshot(),
        "tests": ["tests/test_publish_order.py::test_a_search_while_a_committed_version_cannot_be_moved_does_not_lose_the_document"],
    },
    "citations name the version written on the record they read (REF S23)": {
        "off": lambda: _citations_named_as_now(),
        "tests": ["tests/redteam/test_s23_round1_redteam.py::test_s23_round1_receipt_names_the_version_the_answer_read",
                  "tests/redteam/test_s23_round2_redteam.py::test_s23_round2_stale_reader_poisons_version_cache_after_restore",
                  "tests/redteam/test_s23_round2_redteam.py::"
                  "test_s23_round2_replaced_file_receipt_names_text_the_answer_did_not_read"],
    },
    "every write settles a committed version first (REF S23)": {
        "off": lambda: _off("assistant.sources.settle", "settle", lambda register, section_store, source_id: None),
        "tests": ["tests/redteam/test_s23_round2_redteam.py::test_s23_round2_failed_publish_after_crash_destroys_live_passages",
                  "tests/redteam/test_s23_round2_redteam.py::test_s23_round2_move_after_crash_loses_the_committed_text"],
    },
    "the approval event is written once (REF S23)": {
        "off": lambda: setattr(importlib.import_module("assistant.content.service").ContentService, "EVENT_ATTEMPTS", 2),
        "tests": ["tests/redteam/test_s23_round2_redteam.py::test_s23_round2_approval_event_written_twice_when_ack_is_lost"],
    },
    "a reader's move checks again under the space lock (REF S23, S7)": {
        "off": lambda: _reader_moves_unchecked(),
        "tests": ["tests/redteam/test_s23_round3_redteam.py::test_s23_round3_reader_move_puts_writers_uncommitted_staged_text_live"],
    },
    "a commit is recognised by its version entry (REF S23)": {
        "off": lambda: setattr(importlib.import_module("assistant.content.service").ContentService, "_committed",
                               staticmethod(lambda landed, n: landed is not None)),
        "tests": ["tests/redteam/test_s23_round3_redteam.py::test_s23_round3_same_text_publish_with_failed_commit_reports_success"],
    },
    "uncommitted version entries name nothing (REF S23)": {
        "off": lambda: _every_entry_committed(),
        "tests": ["tests/redteam/test_s23_round3_redteam.py::"
                  "test_s23_round3_versions_view_sees_uncommitted_version_and_its_number_is_reused",
                  "tests/redteam/test_s23_round3_redteam.py::test_s23_round3_history_entry_lands_but_reports_failure"],
    },
    "a request that may change something takes the workspace's lock at the door (REF S23, S7)": {
        "off": lambda: _method_off("assistant.storage", "WriteDoor", "opens_for", lambda self, scope: None),
        "tests": ["tests/test_workspace_door.py::test_writes_take_turns",
                  "tests/test_workspace_door.py::test_a_request_that_may_change_something_holds_the_lock_and_a_read_does_not",
                  "tests/test_workspace_door.py::test_a_space_request_writes_through_the_door_and_a_direct_write_is_refused"],
    },
    "a governed store refuses a write without the workspace's lock (REF S23, S7)": {
        "off": lambda: _stores_unchecked(),
        "tests": ["tests/test_workspace_door.py::test_every_governed_write_refuses_without_the_lock"],
    },
    "a reader never waits for the workspace's lock (REF S23, S7)": {
        "off": lambda: _readers_wait(),
        "tests": ["tests/test_workspace_door.py::test_a_reader_never_waits_while_a_writer_holds_the_lock",
                  "tests/redteam/test_s23_round7_redteam.py::test_s23_round7_reading_the_content_list_waits_for_the_workspace_lock"],
    },
    "start-up holds the workspace's lock (REF S23, S7)": {
        "off": lambda: _off("services.opsatlas_sales.app", "locked", lambda path: __import__("contextlib").nullcontext()),
        "tests": ["tests/test_workspace_door.py::test_the_workspace_builds_under_its_lock"],
    },
    "a step after the commit never fails a publish (REF S23, S5)": {
        "off": lambda: _method_off("assistant.content.service", "ContentService", "_after_commit",
                                   lambda self, source_id, failed, step: step()),
        "tests": ["tests/test_publish_order.py::test_a_step_failing_after_the_commit_never_fails_the_publish"],
    },
    "a rename changes the title and nothing else (REF S23, S8)": {
        "off": lambda: _off("assistant.content.service", "_after_heading", lambda text: ""),
        "tests": ["tests/test_workspace_door.py::test_a_rename_that_would_change_the_text_is_refused"],
    },
    "imports keep to the module boundaries (REF S59)": {
        "off": lambda: _off("boundary_rules", "import_violations", lambda edges, rule, allowed=None: []),
        "tests": ["tests/test_boundaries.py::test_a_core_module_importing_the_sales_layer_is_caught",
                  "tests/test_boundaries.py::test_a_new_package_cycle_is_caught"],
    },
    "no module uses another module's private name (REF S59, the independent review's F1)": {
        "off": lambda: _off("boundary_rules", "private_violations", lambda found, allowed=None: []),
        "tests": ["tests/test_boundaries.py::"
                  "test_a_private_name_taken_from_another_module_is_caught_and_a_gone_one_must_leave_the_list"],
    },
    "each store is named only by its owner (REF S59)": {
        "off": lambda: _off("boundary_rules", "store_violations", lambda mentions, owners=None, also=None: []),
        "tests": ["tests/test_boundaries.py::test_store_ownership_catches_a_second_writer_an_undeclared_store_and_a_stale_allowance",
                  "tests/test_boundaries.py::test_a_store_named_with_a_folder_or_in_an_f_string_is_caught"],
    },
    "no file-level mark lets a private reach-in pass (REF S65, S59's N2)": {
        "off": lambda: _off("boundary_rules", "file_level_marks", lambda modules, sources=None: []),
        "tests": ["tests/test_boundaries.py::test_a_file_level_mark_for_the_private_member_check_is_caught"],
    },
    "an approval names the text it approves (REF S23, S8)": {
        "off": lambda: _method_off("assistant.sources.register", "SourceRegister", "names_text",
                                   lambda self, source_id, sha: None),
        "tests": ["tests/test_workspace_door.py::test_an_approval_names_the_text_it_approves",
                  "tests/test_workspace_door.py::test_an_approval_of_the_version_read_is_refused_once_another_is_written",
                  "tests/test_workspace_door.py::test_the_approve_action_names_the_text_too",
                  "tests/redteam/test_s23_round8_redteam.py::test_s23_round8_a_persons_rejection_through_the_actions_route_names_no_text",
                  "tests/redteam/test_s23_round9_replaced_file.py::test_s23_round9_governance_route_approves_replaced_file",
                  "tests/redteam/test_s23_round9_replaced_file.py::test_s23_round9_actions_route_approves_replaced_file"],
    },
    "a Sales decision changes nothing while a record is out of step (REF S23, S8)": {
        "off": lambda: _method_off("services.opsatlas_sales.knowledge", "Knowledge", "_in_step", lambda self, rows: None),
        "tests": ["tests/test_sales_statement_governance.py::"
                  "test_a_decision_on_several_records_changes_nothing_when_one_is_out_of_step"],
    },
    "an action's decision stands whatever its side effects do (REF S23, S5, S8)": {
        "off": lambda: _side_effects_fail_the_action(),
        "tests": ["tests/test_workspace_door.py::test_a_decision_stands_when_a_step_after_it_fails",
                  "tests/redteam/test_s23_round11_redteam.py::"
                  "test_s23_round11_dispute_refused_after_a_side_effect_fault_changes_nothing"],
    },
    "an action's decision stands whatever its audit write does (REF S57, the independent review's R2)": {
        "off": lambda: _method_off("assistant.ontology.actions", "ActionsEngine", "_record",
                                   lambda self, execution: self.action_log.append(execution) or ""),
        "tests": ["tests/redteam/test_s23_round12_redteam.py::test_s23_round12_content_approve_reported_failed_after_it_took_effect",
                  "tests/redteam/test_s23_round12_redteam.py::test_s23_round12_governance_approve_reported_failed_after_it_took_effect"],
    },
    "a failed records step is tried again (REF S23, S5)": {
        "off": lambda: _method_off("assistant.content.service", "ContentService", "retry_records",
                                   lambda self, source_id: True),
        "tests": ["tests/test_sales_records_in_step.py::test_a_failed_records_step_is_tried_again_and_a_dispute_waits_for_it"],
    },
    "an approval changes only through decide or a commit (REF S23, S8)": {
        "off": lambda: _method_off("assistant.sources.register", "SourceRegister", "update",
                                   lambda self, source_id, **fields: self._update(source_id, **fields)),
        "tests": ["tests/test_workspace_door.py::test_an_approval_cannot_be_written_around_decide"],
    },
    "a decision on a draft names the draft (REF S23, S8)": {
        "off": lambda: _draft_decisions_unnamed(),
        "tests": ["tests/test_workspace_door.py::test_a_return_names_the_draft_returned"],
    },
    "passages without a fingerprint are not served while a version is staged (REF S23)": {
        "off": lambda: setattr(importlib.import_module("assistant.ingestion.store").SectionStore, "UNKNOWN_IS_LIVE", True),
        "tests": ["tests/redteam/test_s23_round4_redteam.py::"
                  "test_s23_round4_unfingerprinted_passages_served_as_the_new_version_after_a_failed_move"],
    },
    "a failed publish action never counts as published (REF S23)": {
        "off": lambda: setattr(importlib.import_module("assistant.content.service").ContentService, "_published_despite",
                               staticmethod(lambda result, record, fields: record is not None
                                            and record.content_sha256 == fields["content_sha256"])),
        "tests": ["tests/redteam/test_s23_round4_redteam.py::test_s23_round4_failed_publish_of_the_same_text_reported_as_published"],
    },
    "no event failure fails a publish (REF S23)": {
        "off": lambda: _method_off("assistant.content.service", "ContentService", "_record_edited",
                                   lambda self, source, text: self._record_edited_event(source, text)),
        "tests": ["tests/redteam/test_s23_round3_redteam.py::test_s23_round3_event_store_down_fails_a_committed_publish"],
    },
    "a lost event is noted in the document's activity (REF S23)": {
        "off": lambda: _method_off("assistant.content.service", "ContentService", "_note_lost_event", lambda self, *a: None),
        "tests": ["tests/redteam/test_s23_round3_redteam.py::test_s23_round3_lost_approval_event_is_not_noted"],
    },
    "a citation from a record without a version names none (REF S23)": {
        "off": lambda: _off("assistant.answer.service", "unnumbered_version", lambda citation, version_of: version_of(citation.source_id)),
        "tests": ["tests/redteam/test_s23_round3_redteam.py::test_s23_round3_stamp_looks_up_current_version_for_unnumbered_record"],
    },
    "one lock per workspace (REF S23, S7)": {
        "off": lambda: _a_lock_per_space(),
        "tests": ["tests/test_workspace_door.py::test_writes_take_turns"],
    },
    "views read a record and its text together (REF S23)": {
        "off": lambda: setattr(importlib.import_module("assistant.sources.register").SourceRegister, "read_record_text",
                               lambda self, source_id: (self.get(source_id), self.read_content(source_id))),
        "tests": ["tests/redteam/test_s23_round5_redteam.py::test_s23_round5_document_view_pairs_old_record_with_new_text"],
    },
    "a publish is recognised by its entry whatever fails after it (REF S23)": {
        "off": lambda: setattr(importlib.import_module("assistant.content.service").ContentService, "_committed_by",
                               staticmethod(lambda slot, record: False)),
        "tests": ["tests/test_publish_order.py::test_a_publish_whose_action_fails_after_its_commit_is_published"],
    },
    "a committed version is read where it is staged while its writer moves it (REF S23)": {
        "off": lambda: _no_staged_reads(),
        "tests": ["tests/redteam/test_s23_round6_redteam.py::test_s23_round6_record_reader_during_commit_gets_the_previous_versions_text"],
    },
    "a version written without approval is not approved (REF S23)": {
        "off": lambda: setattr(importlib.import_module("assistant.content.service").ContentService, "_status_without_approval",
                               staticmethod(lambda source: None)),
        "tests": ["tests/test_publish_order.py::test_a_version_written_without_approval_keeps_the_status_its_writer_saw",
                  "tests/redteam/test_s23_round1_redteam.py::test_s23_round1_unapproved_version_inherits_concurrent_approval"],
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
