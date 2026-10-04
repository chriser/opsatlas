# Today's callers of OpsAtlas's document stores (REF S60's missing basis), 5 October 2026

An inventory, not a design. It maps every production caller of the document stores at **main `3e51749`**: what each call
does, how it reaches the store, which copy it acts on, who it names when it changes an approval, and what it does with
the errors. Every row comes from reading its call site.

**How it was made, and how to check it again.** All helpers are in `tests/redteam/`, read-only, hermetic (temporary
folders, sockets refused, no live service, no model):

| File | What it does |
|---|---|
| `probe_s60_callers_inventory.py` | AST sweep of `src/` and `services/`: every call of a store method name, every store-taking helper, every `getattr(app.state, …)` and `<x>.state.<store>` load. It finds candidates; it decides nothing |
| `s60_callers_rows.py` | The map as data: 415 rows, 52 wiring sites, 69 entry points, each written from reading the call site |
| `probe_s60_callers_render.py --check` | Checks that every row's line still holds its call (a token match), and that every candidate the sweep finds on a store-like receiver is covered by a row. `--counts`, `--tables`, `--tests` print the numbers and tables below |
| `probe_s60_callers_verify.py` | Lone-core checks of the claims reading alone could get wrong (the approval guard, the move's approval, the ontology and governance routes' statuses) |
| `probe_s60_callers_sales.py` | A hermetic Sales workspace: the cores' order, where each decision lands, Knowledge's reconfirmation, a document held by two spaces |

The earlier probes `probe_s60_users.py`, `probe_s60_measurements.py` (round 1), `probe_s60_r3_decisions.py` and
`probe_s60_r3_wiring.py` (round 3) were copied in and re-run: their claims about today's code hold (Knowledge's
reconfirmation calls the register's decide with no audit entry; through the engine a write without the lock is an
"error" outcome and still leaves an audit entry; the Sales family's cores carry the hooks and the workspace lock, a
lone core neither).

Kinds used below: **read**; **read+settle** (a read that may move a committed version into place: `read_content`,
`read_record_text`, `names_text`, `list_for_source(sha=…)`); **read+record** (a read that may also write bookkeeping when
the workspace's lock is free: first versions, suggestion history, the library's placing); **write**; **decision**
(changes, or re-checks, a document's approval); **settle** (an explicit `settle()` or `promote_if_committed`); **move**
(between spaces); **listener/hook**.

Short file names in the prose: `service.py` is `src/assistant/content/service.py`, `register.py`
`src/assistant/sources/register.py`, `store.py` `src/assistant/content/store.py`, `actions.py`
`src/assistant/ontology/actions.py`; `routes_content.py`, `routes_governance.py`, `routes_ontology.py`,
`routes_sources.py` are in `src/assistant/api/`; `content.py`, `knowledge.py`, `governance.py`, `spaces.py`,
`tibi_api.py`, `routes_sales_api.py`, `routes_spaces.py` are in `services/opsatlas_sales/`. The tables give full paths.

## 1. Summary

### Counts

- **415 call sites** in **34 modules**. 29 of them are the family wrappers' own delegation lines
  (`services/opsatlas_sales/spaces.py`, `FamilyRegister`/`FamilySections`/`FamilyActions`), so **386 caller sites**.
- Beside them: **52 wiring sites** (construction, exposure on an app's state, injection, governance) and **69 entry
  points** into store-holding helpers and services (process registry, ontology rebuild, intelligence, Knowledge, the
  desk). Tables in section 6.
- **42 caller modules** in all (32 under `src/`, 10 under `services/`), 34 of them with direct calls. Tibi's engine is
  apart (section 7): one module with direct calls, the frozen benchmark fixture, and three that call the Sales API.
  Cross-check with round 1's `probe_s60_users.py` (re-run): its 26 modules that import a store module and 33 that use
  one are all in the map, except the fixture (section 7); the map adds 6 it does not see (`routes_content.py`,
  `routes_ontology.py`, `routes_ask.py`, `routes_query.py`, `routes_avatar.py`, `analytics/explain.py`), which reach
  the stores through the content workflow, the actions engine or the answer and retrieval services.
- **Decisions:** 21 call sites of kind decision; **13 live decision paths** (section 2: nine end in
  `SourceRegister.decide`, two in a commit, two are moves), creation with an approval, and three fallbacks that
  production never wires.

**Per operation group** (415 rows):

| Group | Rows | Operations (call sites) |
|---|---|---|
| ContentStore | 108 (+5 raw `content.db`, +5 raw assets folder) | `log` 25, `document` 10, `groups` 8, `versions` 5, `meta` 5, `set_meta` 4, `settle` 4, `folders_of` 3, `clear_draft` 3, `save_document` 3, `placements` 3, two each of `comment`, `add_version`, `comments`, `activity`, `unsee`, `version`, `settled`, `version_texts`, `place`, `add_group`; one each of `documents`, `seen`, `see`, `settled_row`, `unsettle`, `forget_document`, `commit_version`, `arrange`, `next_position`, `update_group`, `delete_group`, `add_comment`, `add_reply`, `set_comment_status`, `delete_comment` |
| SourceRegister (raw) | 91 | `list` 32, `get` 26, `read_content` 12 (6 with `sha`), `update` 7, `read_record_text` 3, `decide` 2, `remove` 2, `add` 2, `names_text` 1, `promote_if_committed` 1, `stage_content` 1, `promote_content` 1, `discard_staged_content` 1; **`file_path` and `write_content`: no production caller** |
| Family view (calls on the wrappers, Knowledge's decide) | 44 | `FamilyRegister.get` 14, `.space_of` 7, `.list` 7, `.read_content` 5, `.decide` 2, `.read_record_text` 2, `.names_text` 1, `FamilySections.list_for_source` 1, `FamilyActions.execute` 3, `GovernedSources` delegation 1, the Sales hook's `Knowledge.decide` 1 |
| ContentService, called from outside it | 43 | 35 from `routes_content.py` (33 routes; `documents` makes three calls, `operator` among them), `forget` 2, `record_text` 2, `operator` 1 more (a Sales hook), `ensure_all_versions` 1, `retry_records` 1, `_approve`/`_reject` 1 |
| Listeners, hooks, action handlers and rules | 40 | 20 sites where the content workflow calls its hooks (13 names; the Sales workspace sets 12, `default_library` on the Product Guide only); 3 other hook calls (`self_approval`, the follow-up rebuilds, `on_out_of_step`); 2 attachments of the Sales hooks; 6 hook assignments (`refresh_processes`, `rebuild_facts`, `self_approval`, `version_of`, `on_add`, `on_out_of_step`); 5 action handlers; 4 validation rules |
| Family wrappers' own delegation | 29 | one line per wrapper method |
| SectionStore (raw) | 22 | `list_for_source` 11 (9 with `sha`), `remove_for_source` 3, `replace_for_source` 3, `promote_if_committed` 1, `fingerprint` 1, `stage_for_source` 1, `promote_for_source` 1, `discard_staged_for_source` 1; **`count_for_source`: no production caller** |
| Store-taking helpers | 17 | `register_upload` 7, `ingest_source` 6, `settle()` 3, `stamp_unfingerprinted` 1 |
| Actions engine (document actions) | 7 | `approve_source`, `reject_source`, `publish_version`, `capture_governance_snapshot`, and the two routes that run any action |
| Space moves | 4 | `apply_family_layout` 2, `move_document` 2 (layout `keep_approval=True`, Transfer `False`) |

**Per kind:**

| Kind | All 415 rows | 386 caller sites |
|---|---|---|
| read | 161 | 152 |
| write | 126 | 114 |
| read+settle | 42 | 38 |
| listener/hook | 40 | 40 |
| decision | 21 | 19 |
| move | 13 | 13 |
| settle | 7 | 5 |
| read+record | 5 | 5 |

### How each kind is reached (386 caller sites)

| Reached by | read | write | read+settle | read+record | decision | settle | move | listener/hook | Total |
|---|---|---|---|---|---|---|---|---|---|
| Attribute of `ContentService` (`self.register`, `self.section_store`, `self.store`, `self.actions`, `self.hooks`) | 66 | 68 | 6 | – | 5 | 1 | – | 23 | 169 |
| Injection (a router builder's or a helper's parameter) | 37 | 33 | 17 | 5 | 8 | 4 | 8 | 7 | 119 |
| Family view (`FamilyRegister`/`FamilySections`/`FamilyActions`, through Knowledge, the desk, the statement review, the Sales routes) | 32 | 8 | 9 | – | 5 | – | 4 | – | 58 |
| Attribute of another service (`AnswerService.retrieval`, `CorpusIndex`, `KnowledgeIntelligence`, attribute assignments) | 7 | – | 4 | – | – | – | – | 7 | 18 |
| `app.state`, literal | 4 | 2 | – | – | – | – | – | 1 | 7 |
| Attribute of the `ContentService` the Sales hooks are attached to | 1 | – | 2 | – | 1 | – | – | 1 | 5 |
| `app.state` through `getattr` | 4 | – | – | – | – | – | – | – | 4 |
| Local variable in `create_app` | 1 | 2 | – | – | – | – | – | – | 3 |
| `app.state` through a bound name | – | 1 | – | – | – | – | 1 | – | 2 |
| `SourceRegister.on_add` listener list | – | – | – | – | – | – | – | 1 | 1 |

Counting every place that reads a store off an app's state (rows and wiring): **22 literal loads** (the Sales
`app.py` 8, on 6 lines; `routes_sales_api.py` 6; `routes_spaces.py` 3; `tibi_api.py` 2; `routes_conversations.py` 2
on one line; core `app.py` 1), **2 bindings** (`source`/`target = cores[x].state` in Transfer) used at 5 attributes,
and **4 `getattr` calls** (`access.py` 3, `routes_sales_api.py` 1). Construction by imported class: 8 sites (wiring
table), plus the frozen fixture's two.

**Test usage** (summary numbers only; AST call sites in `tests/` on store-like receiver names, so approximate):
498 calls in 45 files. SourceRegister 315 (`get` 201, `read_content` 32, `list` 27, `update` 22, `write_content` 9,
`file_path` 7, `add` 6, `names_text` 5, `remove` 3, `decide` 2, `read_record_text` 1); SectionStore 50
(`list_for_source` 27, `replace_for_source` 19, `fingerprint` 4); ContentStore 36 (`document` 21, `versions` 8, others 7);
ContentService 97 (`save_draft` 20, `_write_version` 20, `submit` 18, `publish` 7, `current_version` 7, others 25);
`actions.execute("approve_source", …)` 2; `register_upload` 54, `ingest_source` 29, `move_document` 5,
`apply_family_layout` 1, `stamp_unfingerprinted` 1. Tests use `write_content` and `file_path`, which production never
calls.

### What the next design round should know first

1. **Approval is set outside `decide` and the commit in two ways** (verified). `SourceRegister.add` stores whatever
   approval its record carries. `SourceRegister.update` accepts an approval change whenever `content_sha256` is in the
   call, even the same text: the guard tests presence, not change (`register.py:213`). `move_document` uses both: the
   target's record is created with the origin's approval and then updated with every field (`spaces.py:390-391`).
2. **The family layout moves an approved document into another space approved**, with no decision and no audit entry
   there (`keep_approval=True`, `spaces.py:467`; verified). Transfer resets it to pending (verified).
3. **A document held by two family spaces is decided on the first holder's copy** (verified with a simulated
   crash-window duplicate). Approving it through the Sales Playbook's content route approved the Product Guide's copy
   (audit entry in the Product Guide); the playbook's copy stayed pending, and the playbook's activity says
   "approved". `move_document` adds in the target before it removes from the origin, so a crash leaves exactly this.
4. **The ontology route's generic execution answers HTTP 200 for a refused or failed action** (`routes_ontology.py:194`;
   verified: a stale `approve_source` is 200 with outcome "rejected"; `publish_version` is 200 with outcome "error",
   "Nothing staged to publish for this document").
5. **The governance route answers a refusal raised by the register inside the handler as a 500** with detail "409: …"
   (verified). `_set_status` raises `HTTPException(409)` inside the engine, which records it as an "error".
6. **The governance and ontology routes bypass the Sales decide hook.** Approving a record's document there enables the
   record for Tibi (catalog approval "approved", eligible) with no Knowledge review and no review-history line
   (verified on the ontology route; the governance route takes the same engine path).
7. **Knowledge's reconfirmation** (Tibi's review of a record whose document already has the decided status) calls the
   register's decide through the family register: no audit entry, no side effects (re-verified). Only Tibi's review
   route reaches it: the content route refuses an unchanged status first (`service.py:382-383`).
8. **Errors dropped or turned:** `Knowledge.decide` drops the action's message ("Atlas approval action failed; review
   remains pending"); `Knowledge._in_step` swallows every failure of `on_out_of_step`, a `KeyError` from
   `cores[None]` included; `Knowledge.decide` catches `ValueError` only, so `NotHolding` from the register is a 500.
9. **Partial outcomes with no rollback:** the desk withdraws records before `accept_issue`, and a failed `accept_issue`
   leaves the withdrawals in place and the answer pending; Transfer logs in the target after the move without a
   `try`; `ContentService.decide` logs after the decision without a `try`; a delete removes the register entry before
   the passages and the content history; the proposals route answers 500 after the claim is saved if the layout fails.
10. **Writes the stores' lock does not check:** the audit log (`ActionLog.append`), the raw SQLite of the space move
    (`_move_content` relies on `move_document`'s `require`; `prune_emptied` has no check of its own), image files
    (`save_image`, `forget`, the move), the review-history file. A reader (a GET) briefly takes the workspace lock
    when it settles or records.
11. **The actor's fallback differs by path:** the content workflow names the configured operator; Knowledge and the
    desk `service:workspace-key`; the governance and generic ontology routes `system`; agent proposals the agent run,
    approved by the person or `operator`; moves name no one.
12. **Dead wiring:** `answer_service.version_of = content_service.current_version` is never called; six
    `FamilyRegister` methods, five `FamilySections` methods, `FamilyActions.__getattr__` and
    `GovernedSources.__getattr__` have no production caller.

## 2. Every decision path, end to end

A decision changes, or re-checks, a document's approval. In production approval changes in four ways: the register's
`decide`; a commit (an `update` that names a text, written by `_swap`); a move's `add` and `update`; and the
creation of a record (`add`). Each path below runs from its entry point to the store, with the actor and the errors at
each hop. The engine hops are the same everywhere; they are written out once, in D1.

**Who acts** (`ontology/actions.py:44-53`): `acting_person(fallback)` names the signed-in person (stable id and display
name) when a request has one; otherwise `fallback` becomes the actor's id. Service calls (`x-sales-token`, Tibi) have
no person.

### D1. The content route, a document no record owns (a lone core, an organisation space, or a family space)

| Hop | Where | Actor | Errors |
|---|---|---|---|
| Entry | `POST /api/content/documents/{id}/approve` (`documents.approve` and `documents.publish`) or `/reject` (`documents.reject`); `source_guard` (404 if hidden); the door of the core the `X-OpsAtlas-Space` header picks takes the lock | the signed-in person | `AccessError` 401/403/404 |
| 1 | `routes_content.py:127/131` → `ContentService.decide(id, expected_sha, approve)` | – | `_guard`: `NotFound`→404, `ContentError`→409, anything else→500 |
| 2 | `service.py:370-392`: `_source` (`NotFound`); `record_text` (`ContentReplaced`→`ContentError`; `OSError`, `NotIngestableError`→500); SHA mismatch→`ContentError`; `retry_records` (failures ignored); unchanged status→`ContentError` "already approved"; then the hook, else `_approve`/`_reject`; then `store.log` (no `try`: a failure is a 500 after the decision) | activity: the person's name, else the configured operator | as listed |
| 2' | Family space: the Sales hook `content.py:253-258`, no record owns the document → `content._approve`/`_reject` on the attached core | – | `ContentError` propagates |
| 3 | `service.py:977-996` → `self.actions.execute("approve_source"/"reject_source", {source_id, sha: record's}, acting_person(self._operator.name))` (the attached core's engine) | the person, else the configured operator name | not ok→`ContentError(message or "The approval action failed")`→409 |
| 4 | `ActionsEngine.execute` (`actions.py:184-244`): parameters; `requires_human_approval` (blocks an agent without approver); rules `auth_required`, `source_exists` (`register.get`), `names_current_text` (`register.names_text`, may settle), `not_already_approved`/`_rejected`; handler; side effects `refresh_process_registry`, `rebuild_ontology`, `record_analytics_event`; audit `ActionLog.append` | recorded in `action_log.json` | failed rule→"rejected" (rule, message); handler exception→"error" (message `str(exc)`); side-effect failure→"ok" with a note; audit failure raises only for a non-ok outcome |
| 5 | Handler `routes_governance.py:138-144` → `_set_status` (`:326-338`): `register.get` None→`HTTPException(404)`; `register.decide`; `TextNotNamed`→`HTTPException(409)` | – | inside the engine both become "error", message "404: …"/"409: …" |
| 6 | `SourceRegister.decide` (`register.py:201-207`): `@writes` (`NotHolding` without the lock); `names_text`→`TextNotNamed(reason)`; `_update(approval_status=…)` | not passed to the store | `NotHolding`, `TextNotNamed` |

### D2. The content route, a record's document (a family space)

Hops 1-2 as D1. Then:

| Hop | Where | Actor | Errors |
|---|---|---|---|
| 3 | Sales hook `content.py:253-262` → `knowledge.decide(row id, row sha256, approve)` | – | `ValueError`→`ContentError` (409); anything else (`NotHolding`, `OSError`)→500 |
| 4 | `Knowledge.decide` (`knowledge.py:272-308`): `@writes` (workspace lock); unknown record, review block, changed document or evidence→`ValueError`; reads through the family register (first holder; plain reads, may settle). The status always differs here (D1 hop 2 refused an unchanged one), unless two spaces hold the document (section 5) → `FamilyActions.execute("approve_source"/"reject_source", {source_id, sha: expected}, acting_person("service:workspace-key"))`; then Knowledge's own review (`acting_name`, `acting_id`), `sales-records.json`, `sales-review-history.jsonl` | audit: the person, else `service:workspace-key` | not ok→`ValueError("Atlas approval action failed; review remains pending")` (the action's message dropped) |
| 5 | `FamilyActions.execute` (`spaces.py:308-310`): the engine of the first holder (product-guide, sales-playbook, system), else the Product Guide's | – | passes through |
| 6-8 | D1's hops 4-6 on that core | as above | as above |

### D3. Tibi's Knowledge review, including the reconfirmation

| Hop | Where | Actor | Errors |
|---|---|---|---|
| Entry | `POST /api/tibi/knowledge/{id}/review` (`tibi.knowledge.approve`); a workspace route: the Product Guide app; its door takes the workspace lock | the person | – |
| 1 | `tibi_api.py:130` → `conflict(knowledge.decide(…))` | – | `ValueError`/`TypeError`/`KeyError`→409; anything else→500 |
| 2a | Status differs: as D2 hops 4-8 (audited) | person, else `service:workspace-key` | as D2 |
| 2b | **Status already the decided one** (reconfirming after cited evidence changed): `self.register.decide(source.id, state, expected)` (`knowledge.py:298`) → `FamilyRegister.decide` (`spaces.py:253`) → the holder's `SourceRegister.decide`: the approval does not change, the text is checked again, the index is rewritten; **no engine, no audit entry, no side effects** (verified) | none passed; Knowledge's review names `acting_name()`/`acting_id()` | `TextNotNamed`→`ValueError("Source changed; review the current version")`→409; `NotHolding`→500 |

### D4. Tibi's Knowledge resolve (dispute or supersede)

`POST /api/tibi/knowledge/{id}/resolve` (`tibi.knowledge.approve`) → `tibi_api.py:134` `conflict(…)` →
`Knowledge.adjudicate` (`knowledge.py:366-395`, `@writes`): invalid input or changed claim→`ValueError`;
`_in_step(withdrawn)` (`FamilyRegister.names_text` per record; out of step→`on_out_of_step`, swallowed, then
`ValueError`); for each withdrawn record `_withdraw` (`:62-76`): holder gone or already rejected→no-op; else
`FamilyActions.execute("reject_source", {source_id, sha: record's}, acting_person("service:workspace-key"))`→ D1 hops
4-6 on the holder's core; not ok→`ValueError(message or "The withdrawal was refused…")`→409. A later withdrawal that
fails does not undo an earlier one (the records file is not saved). Actor: the person, else `service:workspace-key`.

### D5. Tibi's governance answer review (statement findings)

`POST /api/tibi/governance/answers/{id}/review` (`governance.findings.resolve`) → `tibi_api.py:183` `conflict(…)` →
`GovernanceDesk.review` (`governance.py:671-694`, `@writes`): changed or reviewed answer→`ValueError`; sources changed
since proposed→the answer is saved as stale, then `ValueError`; approve→`_close` (`:642-669`): a statement finding→
`Knowledge.settle` (`knowledge.py:397-438`, `@writes`): `_in_step`, then `_withdraw` per record withdrawn (as D4);
then per issue `FamilyActions.execute("accept_issue", …, acting_person("service:workspace-key"))` (its rule
`source_exists` reads the holder's register); not ok→`ValueError("Atlas could not record the resolution; the answer
remains pending")`→409, **after** the withdrawals and Knowledge's records were saved. Actor: the person, else
`service:workspace-key`.

### D6. The Sales proposals route (Tibi's engine, over HTTP)

Tibi's service `POST /api/contributions/propose` (`sales_preview.py:187-198`) → `POST /api/sales/proposals` with the
service credential (`sales.proposals.create`) → the Product Guide app; its door takes the workspace lock (not a pass) →
`routes_sales_api.py:240` → `Knowledge.propose` (`knowledge.py:310-364`, `@writes`): invalid claim→`ValueError`; an
old revision→`_in_step([old])`, `_withdraw(old)` (as D4; no person, so the actor is `service:workspace-key`); then
`register_upload` through `FamilyRegister.add` (always the Product Guide) and `ingest_source` (family), twice;
`ValueError`/`TypeError`/`KeyError` (also `UploadError`, `NotIngestableError`)→409. The old revision stays withdrawn
if a later step fails (by design: "fail closed"). Then `:243` `apply_family_layout` (D12b): uncaught→500 after the
claim is saved. Tibi's backend turns any status ≥400 into an `HTTPException` with the same status.

### D7. The governance routes

`POST /api/governance/sources/{id}/approve` (`documents.approve`) or `/reject` (`documents.reject`); `source_guard`;
the door → `_execute_operator_action` (`routes_governance.py:75-83`) → `actions.execute(…, acting_person())` on the
header's core (actor: the person, else `system`) → D1 hops 4-6. Mapping: ok→the handler's `response` (the record);
rule `source_exists`→404 "Source not found."; `names_current_text`, `not_already_approved`/`_rejected`→409 with the
message; other rejections→400; "error"→500 with the message (verified: a refusal raised by the register in the handler
arrives as 500, "409: The document changed since it was read; review the current version."). The fallback without an
engine (`:269`, `:278`, `_refresh_process_registry`) is not wired in production. Bypasses the Sales hook (finding 6).

### D8. The ontology route's generic action execution

`POST /api/ontology/actions/{api_name}` (`agent.actions.execute` and the action's own permission:
`documents.approve`, `documents.reject`, `documents.edit` …); the door → `routes_ontology.py:194`
`actions.execute(api_name, params, acting_person())` on the header's core (actor: the person, else `system`).
`KeyError` (unknown action)→404; **every outcome→HTTP 200** with the result in the body (verified). `approve_source`/
`reject_source`→D1 hops 4-6. `publish_version` always fails ("Nothing staged to publish for this document": only
`_write_version` stages). `save_document`→`_save_document_action`: a draft submitted for approval, no approval change.
Bypasses the Sales hook.

### D9. Approving an agent's proposal

`POST /api/ontology/proposals/{id}/approve` (`agent.proposals.approve` and the action's permission) →
`routes_ontology.py:130` `actions.execute(proposal.action, proposal.params, acting_person(agent_run=…,
approved_by="operator"))`: actor type agent, id the run, `approved_by` the person's id, else `operator` (verified), so
`requires_human_approval` passes. `KeyError`→404; "rejected"→400; "error"→500; then `mark_approved`. Same targets as
D8.

### D10. Publishing a draft (a commit that approves)

| Hop | Where | Actor | Errors |
|---|---|---|---|
| Entry | `POST /api/content/documents/{id}/publish` (`documents.publish`); the door of the header's core | the person | – |
| 1 | `routes_content.py:123` → `ContentService.publish` | – | `_guard` |
| 2 | `service.py:515-544`: `_source`; `_submitted` (the draft read, by SHA); base changed, empty→`ContentError`; `_own_draft` (`self_approval` hook: refused→`ContentError`); `_ensure_history`; hook `prepare` (Sales: review block, heading→`ContentError`); `_write_version(approve=True)` | version author: the person's name and role, else the configured operator | `ContentError`→409 |
| 3 | `_write_version` (`:561-605`): `retry_records`; `stage_sections` (`NotIngestableError`→`ContentError`); `actions.execute("publish_version", {source_id, sha}, acting_person(self._operator.name))` (exception→no result); committed (the record names this publish's entry)→done; else not ok→`ContentError("…could not be published…")` | audit: the person, else the configured operator name | 409 |
| 4 | Engine: rules `auth_required`, `source_exists`; handler `_publish_version_action` (`:632-643`): nothing staged→`ContentError`→"error" | – | – |
| 5 | `_swap` (`:645-687`): `settle()`; `get`; stage text, passages, version entry (uncommitted) (failure→discard, re-raise); **`register.update(id, content_sha256=new, approval_status="approved", version, history_n, history_sha, …)`**, the commit (failure→landed? kept : discard, re-raise); `commit_version`, move into place (failures swallowed) | – | – |
| After | `_after_publish` (process registry, facts map: two tries each; event once); `_records_step` (Sales `published`: records follow, review history, statement review started; failure logged and `records_pending` set); `_record_edited`; draft cleared and logged through `_after_commit` (failures logged) | – | never fail the publish |

The approval becomes "approved" whatever it was. The route checks `documents.publish`; the action's declared
permission (`documents.approve`) is checked only by the ontology routes.

### D11. Renaming a document whose title is its heading (a commit that keeps the approval)

`POST /api/content/documents/{id}/rename` (`sources.metadata.update`) → `ContentService.rename` (`service.py:787-821`):
hook `retitle` (Sales: records' documents; reads `record_text`) returns None→a label-only rename
(`register.update(title)`, a write). Otherwise: a draft exists, or the body would change→`ContentError`;
`_write_version(approve=approved, extra={"title"})`: **approved**→the `publish_version` action as D10 (stays approved);
**not approved**→`_swap` directly, committing with the current approval (pending or rejected) and **no audited
action**. A person holding only `sources.metadata.update` can thus commit a new approved version whose body is
unchanged.

### D12. Space moves: two paths, the family layout (from two entries) and Transfer

| Entry | Path | Approval in the target | Actor |
|---|---|---|---|
| a. Start-up job | `create_sales_app` (holds `locked(root/'workspace')`) → `_build` (`services/opsatlas_sales/app.py:135`) → `apply_family_layout` (`spaces.py:447-476`) → `move_document(keep_approval=True)` for each undecided family document whose record says it belongs elsewhere | **the origin's**: `dst.add` with it, then `dst.update(**fields)` (`spaces.py:390-391`); no decision, no audit entry (verified) | none recorded (default `local operator`, returned only) |
| b. After a proposal | D6 → `routes_sales_api.py:243` → `apply_family_layout` | the origin's | none recorded |
| c. Transfer | `POST /api/spaces/transfer` (`documents.transfer` in the origin, `sources.upload` in the target; a workspace route, the Product Guide's door) → `routes_spaces.py:114` `move_document(keep_approval=False)` | **pending** (verified) | `actor.display_name`, in the target's activity log only (the review-history line names no one) |

Errors: none caught. `KeyError` (no document), `ValueError` (target holds it), `NotHolding`, `ContentReplaced`,
SQLite errors→500, or a failed start-up.

### D13. Creation with an approval

`SourceRegister.add` stores the record's approval as given. `register_upload` always creates "pending"; D12 creates
with the origin's approval; the frozen fixture creates "approved" (section 7).

### D14. Fallbacks production never wires

Reached only when no actions engine is given: `ContentService._decide` (`service.py:970-975`, `TextNotNamed`→
`ContentError`); `Knowledge._withdraw`'s `register.decide` (`knowledge.py:76`); the governance routes' `_set_status`
fallback (`routes_governance.py:269`, `:278`). `create_app` always passes its engine; the Sales app always passes
`FamilyActions`.

**Not decisions** (they look close): `retry_records` and the Sales `published` hook change Knowledge's copy of a record,
never the register's approval; `save_document` only drafts; `publish_version` through the ontology routes always fails.

## 3. Every write path that is not a decision

**The lock.** One lock per workspace (a lock file). Taken by: the **door** (`storage.WriteDoor`) of the core serving a
request, for every method but GET, HEAD and OPTIONS, except the passes (`src/assistant/api/app.py:342-344`: sign-in, IAM, ask, query,
answers, avatar, `/api/sales/search`, `/api/sales/governance/verify`, Tibi's ticket and gateway, services, activity,
the diagram service); a **start-up job** (`create_sales_app`'s `locked(root/'workspace')`; `create_app`'s
`locked(app.state.write_lock)` around `ensure_all_versions` and `stamp_unfingerprinted`); or a **reader** with
`if_free` (non-blocking: takes it when free, gives up when held). Each Sales core's door points at the workspace lock
(`govern`, `services/opsatlas_sales/app.py:41-46`); a lone core uses its own `source_register.json.lock`. Checked by: `@writes` on the register's
and section store's writes, Knowledge's and the desk's writes; the content store's SQLite authoriser (a connection
opened without the lock is read-only, `store.py:152-169`) and `forget_document`'s explicit check; `move_document`'s
`require` for both registers. Background threads (the statement review, the internal-review worker) start with an
empty context (checked: a new thread does not inherit context variables), so they hold no lock and settle only
through `if_free`.

| Write path | Entry points | Store writes | Lock taken by | Checked where |
|---|---|---|---|---|
| Publish and commit (D10, D11) | content `publish`, `rename` | `stage_content`, `stage_for_source`, `add_version` (uncommitted), `update` (commit), `commit_version`, `promote_content`, `promote_for_source` | the door | `@writes`; authoriser. **Unchecked:** `ActionLog.append` (the audit), events, the review-history file |
| Staging and its discard | inside `_swap` | `stage_*`, `discard_staged_*` | the door | `@writes` |
| Settles by a writer | `_swap` (`service.py:653`), `_ingest` (`ingestion/service.py:109`), `move_document` (`spaces.py:378`) | `promote_if_committed` → `promote_content`/`promote_for_source` | the writer's (held, so `if_free` passes) | `@writes` |
| Settles by a reader | every read+settle row (`read_content`, `read_record_text`, `names_text`, `list_for_source(sha)`) | same | `if_free`: a GET takes the workspace lock for the move. When a writer holds it, the plain read and the passages read the committed staged copy; a text read naming a SHA raises `ContentReplaced` | `@writes` |
| Moves (D12) | Transfer, the layout | target `add`, `update`, `replace_for_source`; origin `remove_for_source`, `remove`; `_move_content` (raw SQLite on both `content.db`); images copied and deleted; `prune_emptied` (raw `DELETE FROM groups`); `spaces.json` `placed` | the door (Transfer, proposals) or the start-up job | `require` in `move_document` (both registers); `@writes` on the store calls. **Unchecked:** raw SQLite (relies on `require`), image files, `prune_emptied`, `spaces.json` |
| Removal and forget | `DELETE /api/sources/{id}` | `remove` (and its staged file), `remove_for_source`, `forget` → `forget_document` + `VACUUM`, unused images deleted | the door | `@writes`; authoriser; `VACUUM`'s explicit check. **Unchecked:** image files. No settle first; no rollback if a later step fails |
| Upload | `POST /api/sources/upload`, `/api/process/captures`; Knowledge's seeding (start-up) and proposals | `add` → `on_add` → `first_version` (`add_version`, `update(history_n, history_sha)`) | the door or the start-up job | `@writes`; authoriser |
| Ingest | `POST /api/sources/{id}/ingest`; Knowledge's seeding and proposals | `settle()`, `remove_for_source`/`replace_for_source`, `update(processing_state, section_count)` | the door or the job | `@writes` |
| First version, stamping | GET `document`, `versions` (read+record); `publish`, `rename`; `on_add`; start-up `ensure_all_versions`; start-up `stamp_unfingerprinted` | `add_version`, `update(history_*)`; `replace_for_source(sha)` | `if_free` (readers), the door, the job | authoriser; `@writes` |
| Activity log | 25 `ContentStore.log` sites in `ContentService`; Transfer's raw `target.content.store.log` | `activity` rows | the door; `if_free` inside `_reconcile` | authoriser |
| Library | GET `library` (`_place_new`, `_seed_library`: read+record); `set_parent`, `move`, groups; the move's placing; `prune_emptied` | `place`, `arrange`, groups, `meta` | `if_free`; the door; the move's lock | authoriser; raw SQLite unchecked |
| Comments | add, reply, resolve or reopen, delete | `comments`, `replies` | the door | authoriser |
| Drafts | save, discard, submit, return, restore; `save_document` action (ontology routes) | `documents` row | the door | authoriser |
| Suggestions | accept, reopen (also the desk's `keep`/`unkeep`); `_reconcile` from GET documents and suggestions | `suggestions_seen`, `suggestions_settled`, `meta` | the door; `if_free` | authoriser; the desk's `@writes` |
| Details, label-only rename | `PATCH …/details`, `rename` without a heading | `update(title, dates, phases, applies_to)` | the door | `@writes` (approval refused by `ApprovalOutsideDecide`) |
| Records step | after a commit (`_records_step`); `retry_records` from `decide`, `_write_version`, Knowledge's `on_out_of_step` | Knowledge's records (`@writes`), review history, `records_pending` meta | the caller's | Knowledge's `@writes`; authoriser |
| Images | `POST /api/content/assets` | a file in `content/assets` | the door | **unchecked** |
| Failed ingest | `_ingest` | `remove_for_source`, `update(processing_state="failed")` | the caller's | `@writes` |

## 4. Error handling per operation

**What each operation raises** (read from the code; types in brackets are their bases):

| Operation | Raises |
|---|---|
| `SourceRegister.list`, `get` | `JSONDecodeError` (damaged index), `OSError`, pydantic `ValidationError` (a malformed row) |
| `read_content(id)` | `FileNotFoundError` (no live file). A busy or failed settle is handled inside (the committed staged copy, else the live file) |
| `read_content(id, sha)` | `ContentReplaced` [`LookupError`] when the live file is not that text and it cannot be moved into place now: not committed, or a writer holds the lock (busy raises at once, `register.py:86-89`); `FileNotFoundError` (the live file is read before the check) |
| `read_record_text` | `FileNotFoundError`; `ContentReplaced` is handled; no record→`(None, b"")` |
| `names_text` | returns a reason; `ContentReplaced` and `OSError` become reasons; `JSONDecodeError` passes |
| `decide` | `NotHolding` [`RuntimeError`]; `TextNotNamed` [`ValueError`]: "No such source", "The document changed since it was read…", "The file was changed outside content management…", "The document's text cannot be read" |
| `update` | `NotHolding`; `ApprovalOutsideDecide` [`ValueError`] (approval changed without `content_sha256`); unknown id→`None` |
| `add` | `NotHolding`; a listener's error after the record is stored |
| `remove` | `NotHolding`; unknown id→`False` |
| `stage_content`, `promote_content`, `discard_staged_content`, `write_content` | `NotHolding`, `OSError` |
| `promote_if_committed` (both stores) | `LockBusy` [`OSError`] when another holds the lock; JSON errors |
| `SectionStore.list_for_source`, `fingerprint`, `count_for_source` | `JSONDecodeError` (damaged file), pydantic errors; `LockBusy` handled inside |
| `SectionStore` writes | `NotHolding`, `OSError` |
| `ContentStore` reads | `sqlite3.Error` |
| `ContentStore` writes | `NotHolding` (authoriser, `store.py:163-166`), `sqlite3.Error`; `forget_document` also `NotHolding` for `VACUUM` |
| `ContentService` methods | `NotFound` [`KeyError`], `ContentError` [`ValueError`]; and through: `NotHolding`, `OSError`, SQLite, JSON, `NotIngestableError` [`ValueError`, not `ContentError`] from `record_text` on a damaged PDF or Word file |
| `FamilyRegister`, `FamilySections` | the holder's (they pass through) |
| `ActionsEngine.execute`, `FamilyActions.execute` | `KeyError` (unknown action); otherwise a result: "rejected" (failed rule, message), "error" (`str(exc)`: an `HTTPException` reads "409: …"), "ok" (a side-effect failure is a note); raises if the audit write fails for a non-ok outcome |
| `move_document` | `NotHolding`, `KeyError` (no document), `ValueError` (target holds it), `ContentReplaced`, `OSError`, SQLite |
| `register_upload` | `UploadError` [`ValueError`]; `add`'s |
| `ingest_source` | `NotIngestableError` [`ValueError`]; the stores' |

**Each caller's handling, mapped to statuses** (the full table has every row):

| Caller | Handles | Status |
|---|---|---|
| `routes_content` (all but `documents`, `library`) | `_guard` | `NotFound`→404, `ContentError`→409, anything else→500 (so `NotHolding`, `OSError`, `NotIngestableError`, `ApprovalOutsideDecide` are 500) |
| `routes_content` `documents`, `library` | none | 500 |
| `routes_governance` approve, reject, accept | result mapping | rule `source_exists`→404; `names_current_text`, `not_already_*`→409; other "rejected"→400; "error"→500 (a register refusal in the handler included) |
| `routes_governance` `get_document`, `remediation` | `None` | 404; else 500 |
| `routes_ontology` `execute_action` | `KeyError` | 404; every outcome 200 |
| `routes_ontology` `approve_proposal` | `KeyError`, outcome | 404; "rejected"→400; "error"→500 |
| `routes_sources` upload, `routes_process` capture | `UploadError` | 400; else 500 |
| `routes_sources` delete | `get` None, `remove` False; `read_content` `OSError` swallowed | 404; later failures 500 after the entry is gone |
| `routes_ingestion` | `get` None; `NotIngestableError` | 404; 400; else 500 |
| `routes_regulatory` impact | `ValueError` | 404 |
| `routes_analytics` snapshot | outcome | not ok→500 |
| `ContentService._approve`/`_reject` | outcome | `ContentError(message or default)`→409 |
| `ContentService._write_version` | any exception from the engine | `ContentError` unless committed→409 |
| `ContentService` after the commit (`_after_commit`, `_records_step`, `_move_into_place`, `_discard_staged`, `commit_version`, events, rebuilds) | `Exception` | swallowed; logged in the activity where it can be |
| `ContentService.first_version` | `Exception` on the read | swallowed (no version named for now) |
| `ContentService.retry_records` | the hooks' `Exception` | returns False |
| `ContentService.forget`, `settle.stamp_unfingerprinted`, `spaces._assets_in_use` | `OSError` on a read | skipped |
| `ContentService.record_text` / `published_text` | `ContentReplaced` | `ContentError` / the plain read |
| Sales hook `decide` | `ValueError` | `ContentError`→409; else 500 |
| Sales hook `prepare` | `ContentError`, `OSError` from `record_text` | swallowed (previous text unknown); `NotIngestableError` passes (500) |
| `Knowledge.decide` | action not ok; `ValueError` from the family's decide | `ValueError("Atlas approval action failed…")` (message dropped); `ValueError("Source changed…")`; 409 at Tibi's route, 409 via `ContentError` at the content route; `NotHolding`→500 |
| `Knowledge._withdraw` | action not ok | `ValueError(message or default)`→409 |
| `Knowledge._in_step` | `on_out_of_step`'s `Exception` | swallowed; the refusal stands |
| `Knowledge.eligible` | `OSError` | False |
| `GovernanceDesk.text` | `ContentReplaced` | empty text |
| `GovernanceDesk._close` | `accept_issue` not ok | `ValueError`→409 (after withdrawals) |
| `ProcessRegistry.derive_from_sources` | `ContentReplaced` | source skipped; `FileNotFoundError` passes |
| `ontology.sync._extract_process_key_facts` | `FileNotFoundError`, `KeyError`, `ContentReplaced` | empty text |
| Tibi's routes (`tibi_api`) | `conflict()` | `ValueError`/`TypeError`/`KeyError`→409; else 500 |
| Sales API `propose`, `governance_propose`, `spoken_draft` | as listed | 409; else 500 (`propose`'s layout failure 500 after saving) |
| Sales API `source` | `None` | 404; strict UTF-8 decode→500 on invalid bytes |
| `routes_spaces.transfer` | none around `move_document`, the rebuilds, the log | 500 |
| `bulk_import.import_folder` | `UploadError`, `NotIngestableError`, `UnicodeDecodeError`, `OSError` | the row "failed" |
| The background statement review | `Exception` | state "failed" with the message |

No app registers a handler for `ValueError`, `KeyError` or `RuntimeError`: only `IamError` and `AccessError`
(`src/assistant/api/app.py:100-107`), so anything a route does not catch is a 500.

## 5. Routing

**How a request finds a core.** `SpaceRouter` (`spaces.py:551-572`, the outermost layer after the Sales middlewares)
sends an `/api/` request to the core the `X-OpsAtlas-Space` header (or `?space=`) names; no header, or the Product
Guide→the Product Guide app; an unknown space→404. The workspace routes (`/api/auth`, `/api/services`,
`/api/activity`, `/api/conversations`, `/api/sales`, `/api/tibi`, `/api/spaces`) always go to the Product Guide app,
whatever the header. Each core's routes hold that core's stores by closure, so "own space" below means the space the
header picked.

**The family view** routes each call to the first family register holding the document, in the order product-guide,
sales-playbook, system (verified), and to the Product Guide when none does; `add` always writes the Product Guide.
**Transfer** searches every core in `cores` order: product-guide, sales-playbook, system, then the organisation spaces
(verified order with one organisation space: `['product-guide', 'sales-playbook', 'system', 'acme']`).

| Routing | Caller sites | Who |
|---|---|---|
| Own space, picked by the header | 66 | every core route: sources, ingestion, content (35), governance, ontology, process, regulatory, analytics; `access.py`'s guards and visibility |
| Its core's own space, as wired | 215 | `ContentService` (170 rows), the retrieval and answer services, the core's start-up, the Sales hooks `prepare`, `retitle`, `settled_how` and `decide` for a document no record owns (the attached core) |
| Family: first holder | 47 | Knowledge (every read, `names_text`, `decide` and its fallbacks, withdrawals), the desk, the statement review's `findings`, `GovernedSources`, the Sales hook `describe` and `decide` for a record's document, `tibi_api.source`, the Sales API's `source`, `readable`, `contract` and agenda filter, `on_out_of_step` (`cores[space_of(id)]`), `apply_family_layout`'s `space_of`, Knowledge's ingests and their settles |
| Family: always the Product Guide | 6 | `FamilyRegister.add` (every Knowledge upload: cards, evidence, claims, interview accounts), `FamilyActions.__getattr__`, the layout's starting folders, the Product Guide's `folders_of` for an unknown conversation. Also every `base_dir` use: Knowledge's files, the review history, the desk's files, the statement review's results, Tibi's `confirm_fact`, Transfer's history line |
| All family spaces | 9 | `FamilyRegister.list` (Knowledge's cards, the desk's corpus scans and fingerprint, the statement review's revision and `run_statement_review`, `apply_family_layout`), `readable`'s per-space `folders_of` |
| All spaces | 2 | `list_spaces` (each space's count), Transfer's origin search |
| A named space | 21 | `change_space`; Transfer's target; `move_document`'s two pairs; the layout's per-space moves and prunes |
| As handed (helpers) | 20 | `settle`, `_ingest`, `register_upload`, `KnowledgeIntelligence`, `StatementStore.sync`, `run_statement_review`, `import_folder`: the own core from core routes, the family from Knowledge and the desk |

**Where the family view and a space's own core can disagree about which copy is meant:**

1. **A document held by two spaces.** `move_document` adds in the target before it removes from the origin
   (`spaces.py:390-403`), so a crash between them leaves two copies; nothing removes the second. Then:
   - the family view acts on the first holder's copy, the space's own routes on their own (**verified**: the
     playbook's content route approved the Product Guide's copy; the playbook's copy stayed pending; the playbook's
     activity says "approved");
   - `ContentService.decide`'s "already approved" check reads the own copy, Knowledge reads the first holder's: if
     they differ, the content route can end in the reconfirmation branch (D3b) on the other copy;
   - `on_out_of_step` retries the first holder's records step;
   - Transfer takes the first holder over all cores as the origin; moving to a space that holds the other copy raises
     `ValueError` (500);
   - `FamilyRegister.list` returns both copies (the desk and the statement review see the document twice);
   - `readable` applies the first holder's space's visibility.
2. **An unknown id.** The family view falls back to the Product Guide: `get`→None, `decide`→`TextNotNamed("No such
   source")`, `update`→None, `read_content`→`FileNotFoundError` from the Product Guide's folder, and `FamilyActions`
   runs the Product Guide's engine, whose `source_exists` refuses.
3. **New documents land in the Product Guide.** `FamilyRegister.add` writes the Product Guide; the layout moves them
   later (at start-up, or after a proposal). Between the two, the playbook's routes do not see a new claim. The layout
   decides each document once (`spaces.json` `placed`), so a later Transfer stands.
4. **The Sales hook decides on two different engines.** A document no record owns: the attached core's engine. A
   record's document: Knowledge, then the holder's engine. The same space normally; not with two copies.
5. **Writes made from a space land in the Product Guide's folder.** Every family core's hooks write Knowledge's records
   and the review history under the family register's `base_dir` (the Product Guide's).
6. **The governance and ontology routes act on the header's core and bypass the Sales hook**, so Knowledge's records
   do not follow a decision made there on a record's document (verified, finding 6).
7. **Organisation spaces are outside the family view.** Knowledge, the desk and `FamilyActions` never reach them;
   Transfer moves documents in and out of them (not documents a record cites).

## 6. The full table, grouped by caller module

415 call sites in 34 modules, `src/` first, each module's rows in line order. Generated from `tests/redteam/s60_callers_rows.py` by `probe_s60_callers_render.py --tables`, after `--check` confirmed every row against the code. Routing words: *own space* is the core the `X-OpsAtlas-Space` header picks; *its core's own space* is the core a service was built in; *family: first holder* is the first of product-guide, sales-playbook, system holding the document, else the Product Guide. Two tables follow the call sites: the wiring (construction, exposure, injection, governance) and the entry points into store-holding helpers and services (their store calls are rows here).

### `src/assistant/answer/service.py` (3)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 379 | `AnswerService._all_sections` | SourceRegister.list | read | attribute of AnswerService (self.retrieval.register) | its core's own space | – | none caught: propagates (500 at a route) |
| 383 | `AnswerService._all_sections` | SectionStore.list_for_source(sha) | read+settle | attribute of AnswerService (self.retrieval.section_store) | its core's own space | – | none caught: propagates (500 at a route) |
| 463 | `AnswerService.answer` | SourceRegister.list | read | attribute of AnswerService (self.retrieval.register) | its core's own space | – | none caught: propagates (500 at a route) |

### `src/assistant/api/access.py` (3)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 148 | `source_guard` | ContentStore.comment | read | getattr(request.app.state, 'content') → .store | the serving core | – | none caught (sqlite error→500); invisible→AccessError 404 |
| 177 | `derived_guard` | SourceRegister.list | read | getattr(request.app.state, 'register') | the serving core | – | none caught; hides any→AccessError 403 |
| 188 | `_visibility` | ContentStore.folders_of (reference, called by Visibility.can_read) | read | getattr(app.state, 'content') → .store | the core whose PrincipalMiddleware runs (scope['app']) | – | none caught: propagates (500 at a route) |

### `src/assistant/api/app.py` (9)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 209 | `create_app.health_details` | SourceRegister.list | read | local variable (builder closure) | its core's own space | – | none caught: propagates (500 at a route) |
| 221 | `create_app.<lambda> forget_content` | ContentService.forget | write | app.state.content (literal, read when called) | its core's own space | – | none caught here or in routes_sources (500 after the register entry is gone) |
| 321 | `create_app` | ContentService.self_approval ← IAM solo-operator check | listener/hook | attribute assignment on ContentService | its core's own space | – | called by _own_draft; False→ContentError (409) |
| 322 | `create_app` | ContentService.rebuild_facts ← rebuild_ontology_store | listener/hook | attribute assignment on ContentService | its core's own space | – | called by _after_publish: tried twice, then left (swallowed) |
| 323 | `create_app` | ContentService.refresh_processes ← process_registry.build_from_sources | listener/hook | attribute assignment on ContentService | its core's own space | – | called by _after_publish: tried twice, then left (swallowed) |
| 327 | `create_app` | ContentService.current_version (as AnswerService.version_of) | listener/hook | attribute assignment on AnswerService | its core's own space | – | never called: unnumbered_version() ignores it (answer/service.py:120-123) |
| 328 | `create_app` | SourceRegister.on_add ← ContentService.first_version | listener/hook | listener list on SourceRegister | its core's own space | – | runs inside add() after the record is stored; its own errors mostly swallowed (first_version) |
| 330 | `create_app` | ContentService.ensure_all_versions | write | local variable (builder) | its core's own space | – | none caught: start-up fails; under locked(app.state.write_lock) |
| 331 | `create_app` | stamp_unfingerprinted (settle.py) | write | local variable (builder) | its core's own space | – | none caught: start-up fails; under locked(app.state.write_lock) |

### `src/assistant/api/routes_analytics.py` (1)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 204 | `capture_governance_snapshot` | ActionsEngine.execute(capture_governance_snapshot) → KnowledgeIntelligence.run | read | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | acting_person(): the signed-in person, else 'system' | not ok→500 |

### `src/assistant/api/routes_content.py` (35)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 94 | `build_content_router.documents` | ContentService.suggestion_overview | read+record | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | unguarded: anything→500 |
| 97 | `build_content_router.documents` | ContentService.summary | read | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | unguarded: anything→500 |
| 99 | `build_content_router.documents` | ContentService.operator | read | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | unguarded |
| 103 | `build_content_router.document` | ContentService.document | read+record | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 107 | `build_content_router.save_draft` | ContentService.save_draft | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 111 | `build_content_router.discard_draft` | ContentService.discard_draft | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 115 | `build_content_router.submit` | ContentService.submit | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 119 | `build_content_router.return_to_draft` | ContentService.return_to_draft | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 123 | `build_content_router.publish` | ContentService.publish | decision | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | acting_person(content._operator.name): the signed-in person, else the configured operator name (KP_OPERATOR_NAME: 'Operator', or the Sales profile's default) | _guard: NotFound→404, ContentError→409, anything else→500 |
| 127 | `build_content_router.approve` | ContentService.decide | decision | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | acting_person(content._operator.name): the signed-in person, else the configured operator name (KP_OPERATOR_NAME: 'Operator', or the Sales profile's default) | _guard: NotFound→404, ContentError→409, anything else→500 |
| 131 | `build_content_router.reject` | ContentService.decide | decision | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | acting_person(content._operator.name): the signed-in person, else the configured operator name (KP_OPERATOR_NAME: 'Operator', or the Sales profile's default) | _guard: NotFound→404, ContentError→409, anything else→500 |
| 135 | `build_content_router.versions` | ContentService.versions | read+record | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 139 | `build_content_router.version` | ContentService.version | read | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 143 | `build_content_router.restore` | ContentService.restore | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 147 | `build_content_router.diff` | ContentService.diff | read+settle | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 151 | `build_content_router.comments` | ContentService.comments | read+settle | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 155 | `build_content_router.add_comment` | ContentService.add_comment | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 159 | `build_content_router.reply` | ContentService.reply | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 163 | `build_content_router.resolve` | ContentService.set_comment_status | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 167 | `build_content_router.reopen` | ContentService.set_comment_status | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 171 | `build_content_router.delete_comment` | ContentService.delete_comment | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 176 | `build_content_router.activity` | ContentService.activity | read | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 180 | `build_content_router.suggestions` | ContentService.suggestion_state | read+record | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 184 | `build_content_router.accept_suggestion` | ContentService.accept_suggestion | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 188 | `build_content_router.reopen_suggestion` | ContentService.reopen_suggestion | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 192 | `build_content_router.details` | ContentService.update_details | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 196 | `build_content_router.rename` | ContentService.rename | decision | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | acting_person(content._operator.name): the signed-in person, else the configured operator name (KP_OPERATOR_NAME: 'Operator', or the Sales profile's default) | _guard: NotFound→404, ContentError→409, anything else→500 (a decision only when the title is the heading: a new version committed, approval kept) |
| 200 | `build_content_router.set_parent` | ContentService.set_parent | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 204 | `build_content_router.library` | ContentService.library | read+record | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | unguarded: anything→500 |
| 209 | `build_content_router.move` | ContentService.move | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 (the library tree, not a space move) |
| 213 | `build_content_router.create_group` | ContentService.create_group | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 217 | `build_content_router.update_group` | ContentService.update_group | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 221 | `build_content_router.delete_group` | ContentService.delete_group | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 226 | `build_content_router.upload_image` | ContentService.save_image | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |
| 238 | `build_content_assets_router.image` | ContentService.image | read | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | _guard: NotFound→404, ContentError→409, anything else→500 |

### `src/assistant/api/routes_governance.py` (16)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 65 | `_register_governance_actions` | rule source_exists (reads SourceRegister.get) | listener/hook | injection (router builder's parameter) | its core's own space | – | a failed rule is a 'rejected' outcome |
| 66 | `_register_governance_actions` | rule names_current_text (reads SourceRegister.names_text) | listener/hook | injection (router builder's parameter) | its core's own space | – | a failed rule is a 'rejected' outcome |
| 67 | `_register_governance_actions` | rule not_already_approved (reads SourceRegister.get) | listener/hook | injection (router builder's parameter) | its core's own space | – | a failed rule is a 'rejected' outcome |
| 68 | `_register_governance_actions` | rule not_already_rejected (reads SourceRegister.get) | listener/hook | injection (router builder's parameter) | its core's own space | – | a failed rule is a 'rejected' outcome |
| 71 | `_register_governance_actions` | handler approve_source → _set_status | listener/hook | injection (router builder's parameter) | its core's own space | – | handler exceptions become an 'error' outcome (actions.py:215-217) |
| 72 | `_register_governance_actions` | handler reject_source → _set_status | listener/hook | injection (router builder's parameter) | its core's own space | – | handler exceptions become an 'error' outcome |
| 73 | `_register_governance_actions` | handler accept_issue (AcceptedStore; not a document store) | listener/hook | injection (router builder's parameter) | its core's own space | – | handler exceptions become an 'error' outcome |
| 78 | `_execute_operator_action` | ActionsEngine.execute(approve_source \| reject_source \| accept_issue) | decision | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | acting_person(): the signed-in person, else 'system' | _raise_action_http_error: rule source_exists→404; names_current_text/not_already_*→409 (detail = message); other 'rejected'→400; 'error'→500 (a refusal raised inside the handler arrives as '409: …' with status 500) |
| 95 | `_validate_source_exists` | SourceRegister.get | read | injection (router builder's parameter) | its core's own space | – | none caught (→ engine 'error') |
| 102 | `_validate_names_current_text` | SourceRegister.names_text | read+settle | injection (router builder's parameter) | its core's own space | – | none caught; names_text itself turns ContentReplaced/OSError into a reason |
| 108 | `_validate_not_already_approved` | SourceRegister.get | read | injection (router builder's parameter) | its core's own space | – | none caught (→ engine 'error') |
| 114 | `_validate_not_already_rejected` | SourceRegister.get | read | injection (router builder's parameter) | its core's own space | – | none caught (→ engine 'error') |
| 249 | `get_document` | SourceRegister.read_record_text | read+settle | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | None→404; others propagate (500) |
| 258 | `remediation` | SourceRegister.read_record_text | read+settle | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | None→404; others propagate (500) |
| 330 | `_set_status` | SourceRegister.get | read | injection (function parameter) | its core's own space | – | None→HTTPException 404 (inside the engine: an 'error' outcome, message '404: Source not found.') |
| 333 | `_set_status` | SourceRegister.decide | decision | injection (function parameter) | its core's own space | the engine's actor (not passed to the register) | TextNotNamed→HTTPException 409 (inside the engine: an 'error' outcome, message '409: …'); NotHolding propagates |

### `src/assistant/api/routes_ingestion.py` (4)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 25 | `ingest` | SourceRegister.get | read | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | None→404 |
| 28 | `ingest` | ingest_source (settle, passages, record) | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | NotIngestableError→400; anything else (NotHolding, OSError, JSON)→500 |
| 49 | `list_sections` | SourceRegister.get | read | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | None→404 |
| 53 | `list_sections` | SectionStore.list_for_source(sha) | read+settle | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |

### `src/assistant/api/routes_ontology.py` (2)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 130 | `approve_proposal` | ActionsEngine.execute(the proposal's action: any, incl. approve_source/reject_source/save_document/publish_version) | decision | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | acting_person(agent_run=run id, approved_by='operator'): type agent, approved_by the signed-in person's id, else 'operator' | KeyError→404; 'rejected'→400; 'error'→500 (detail = message) |
| 194 | `execute_action` | ActionsEngine.execute(any action named in the path) | decision | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | acting_person(): the signed-in person, else 'system' | KeyError (unknown action)→404; every outcome, 'rejected' and 'error' included, answers HTTP 200 with the result |

### `src/assistant/api/routes_process.py` (1)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 166 | `save_capture` | register_upload → SourceRegister.add (+ on_add) | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | UploadError→400; anything else→500 |

### `src/assistant/api/routes_sources.py` (7)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 28 | `list_sources` | SourceRegister.list | read | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| 37 | `upload_source` | register_upload → SourceRegister.add (+ on_add) | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | UploadError→400; anything else→500 |
| 60 | `remove_source` | SourceRegister.get | read | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | None→404 |
| 64 | `remove_source` | SourceRegister.read_content | read+settle | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | OSError→b'' (swallowed: the text is only for finding unused images) |
| 69 | `remove_source` | SourceRegister.remove | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | False→404; NotHolding→500 |
| 74 | `remove_source` | SectionStore.remove_for_source | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught (500 after the record is gone) |
| 76 | `remove_source` | ContentService.forget (via app.py:221) | write | injection (router builder's parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught (500 after the record is gone) |

### `src/assistant/content/service.py` (170)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 109 | `ContentService.__init__` | handler save_document → _save_document_action | listener/hook | attribute of ContentService (self.actions, the core's engine) | its core's own space | – | handler exceptions become an 'error' outcome |
| 110 | `ContentService.__init__` | handler publish_version → _publish_version_action | listener/hook | attribute of ContentService (self.actions, the core's engine) | its core's own space | – | handler exceptions become an 'error' outcome |
| 130 | `ContentService._source` | SourceRegister.get | read | attribute of ContentService (self.register) | its core's own space | – | None→NotFound (404) |
| 141 | `ContentService._live` | SourceRegister.read_record_text | read+settle | attribute of ContentService (self.register) | its core's own space | – | no record→NotFound; OSError propagates |
| 152 | `ContentService.record_text` | SourceRegister.read_content(sha) | read+settle | attribute of ContentService (self.register) | its core's own space | – | ContentReplaced→ContentError (409); OSError and NotIngestableError propagate |
| 163 | `ContentService.published_text` | SourceRegister.read_content(sha) | read+settle | attribute of ContentService (self.register) | its core's own space | – | ContentReplaced→falls back to the plain read below |
| 165 | `ContentService.published_text` | SourceRegister.read_content | read+settle | attribute of ContentService (self.register) | its core's own space | – | OSError propagates |
| 183 | `ContentService.first_version` | SourceRegister.get | read | attribute of ContentService (self.register) | its core's own space | – | none caught; runs only under if_free (lock free or held) |
| 187 | `ContentService.first_version` | SourceRegister.read_content(sha) | read+settle | attribute of ContentService (self.register) | its core's own space | – | any Exception→return (no version named) |
| 191 | `ContentService.first_version` | ContentStore.versions | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 192 | `ContentService.first_version` | ContentStore.add_version | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates (author 'OpsAtlas', role 'System') |
| 194 | `ContentService.first_version` | SourceRegister.update | write | attribute of ContentService (self.register) | its core's own space | – | propagates |
| 200 | `ContentService.ensure_all_versions` | SourceRegister.list | read | attribute of ContentService (self.register) | its core's own space | – | propagates |
| 209 | `ContentService.current_version` | SourceRegister.get | read | attribute of ContentService (self.register) | its core's own space | – | propagates |
| 217 | `ContentService.document` | ContentStore.document | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 223 | `ContentService.document` | ContentStore.comments | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 224 | `ContentService.document` | ContentStore.activity | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 238 | `ContentService.document` | ContentStore.versions | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 241 | `ContentService.document` | hook describe | listener/hook | attribute of ContentService (self.hooks, set by the Sales workspace) | its core's own space | – | propagates |
| 246 | `ContentService.summary` | ContentStore.documents | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 266 | `ContentService._open_suggestions` | hook all_suggestions | listener/hook | attribute of ContentService (self.hooks, set by the Sales workspace) | its core's own space | – | propagates |
| 266 | `ContentService._open_suggestions` | SourceRegister.get | read | attribute of ContentService (self.register) | its core's own space | – | propagates |
| 274 | `ContentService._reconcile` | ContentStore.meta | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates; under if_free |
| 276 | `ContentService._reconcile` | ContentStore.set_meta | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates; under if_free |
| 277 | `ContentService._reconcile` | ContentStore.seen | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 281 | `ContentService._reconcile` | ContentStore.unsee | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates; under if_free |
| 282 | `ContentService._reconcile` | SourceRegister.get | read | attribute of ContentService (self.register) | its core's own space | – | propagates |
| 286 | `ContentService._reconcile` | SourceRegister.get | read | attribute of ContentService (self.register) | its core's own space | – | propagates |
| 289 | `ContentService._reconcile` | ContentStore.see | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates; under if_free |
| 293 | `ContentService._settle_gone` | ContentStore.versions | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 296 | `ContentService._settle_gone` | ContentStore.settle | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 297 | `ContentService._settle_gone` | ContentStore.log | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 299 | `ContentService._settle_gone` | hook settled_how | listener/hook | attribute of ContentService (self.hooks, set by the Sales workspace) | its core's own space | – | propagates |
| 300 | `ContentService._settle_gone` | ContentStore.settle | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 307 | `ContentService._backfill` | SourceRegister.list | read | attribute of ContentService (self.register) | its core's own space | – | propagates |
| 308 | `ContentService._backfill` | ContentStore.versions | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 311 | `ContentService._backfill` | ContentStore.version | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 312 | `ContentService._backfill` | hook history | listener/hook | attribute of ContentService (self.hooks, set by the Sales workspace) | its core's own space | – | propagates |
| 313 | `ContentService._backfill` | ContentStore.settle | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 324 | `ContentService.suggestion_overview` | hook suggestion_notes (unset in production) | listener/hook | attribute of ContentService (self.hooks, set by the Sales workspace) | its core's own space | – | propagates |
| 326 | `ContentService.suggestion_overview` | ContentStore.settled | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 336 | `ContentService.suggestion_state` | ContentStore.settled | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 349 | `ContentService.accept_suggestion` | hook keep (GovernanceDesk.keep) | listener/hook | attribute of ContentService (self.hooks, set by the Sales workspace) | its core's own space | – | propagates |
| 350 | `ContentService.accept_suggestion` | ContentStore.unsee | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 351 | `ContentService.accept_suggestion` | ContentStore.settle | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 352 | `ContentService.accept_suggestion` | ContentStore.log | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 359 | `ContentService.reopen_suggestion` | ContentStore.settled_row | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | None→NotFound |
| 365 | `ContentService.reopen_suggestion` | hook unkeep (GovernanceDesk.unkeep) | listener/hook | attribute of ContentService (self.hooks, set by the Sales workspace) | its core's own space | – | propagates |
| 366 | `ContentService.reopen_suggestion` | ContentStore.unsettle | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 367 | `ContentService.reopen_suggestion` | ContentStore.log | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 385 | `ContentService.decide` | hook decide (Sales) | listener/hook | attribute of ContentService (self.hooks, set by the Sales workspace) | its core's own space | – | propagates (the Sales hook raises ContentError) |
| 390 | `ContentService.decide` | ContentStore.log | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | none caught: a failure here is a 500 after the decision took effect |
| 405 | `ContentService.save_draft` | ContentStore.document | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 410 | `ContentService.save_draft` | ContentStore.clear_draft | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 411 | `ContentService.save_draft` | ContentStore.log | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 415 | `ContentService.save_draft` | ContentStore.log | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 419 | `ContentService.save_draft` | ContentStore.save_document | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 423 | `ContentService.save_draft` | ContentStore.log | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 433 | `ContentService._save_document_action` | ContentStore.document | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates (→ engine 'error') |
| 440 | `ContentService.forget` | ContentStore.version_texts | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 441 | `ContentService.forget` | ContentStore.document | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 444 | `ContentService.forget` | ContentStore.forget_document | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates (NotHolding for the VACUUM without the lock) |
| 446 | `ContentService.forget` | SourceRegister.list | read | attribute of ContentService (self.register) | its core's own space | – | propagates |
| 448 | `ContentService.forget` | SourceRegister.read_content | read+settle | attribute of ContentService (self.register) | its core's own space | – | OSError→skipped |
| 451 | `ContentService.forget` | ContentStore.version_texts | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 457 | `ContentService.forget` | assets folder (raw file delete under ContentStore.assets) | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates; no lock check |
| 479 | `ContentService.discard_draft` | ContentStore.document | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 482 | `ContentService.discard_draft` | ContentStore.clear_draft | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 483 | `ContentService.discard_draft` | ContentStore.log | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 488 | `ContentService.submit` | ContentStore.document | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 493 | `ContentService.submit` | ContentStore.save_document | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 495 | `ContentService.submit` | ContentStore.log | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 501 | `ContentService._submitted` | ContentStore.document | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 511 | `ContentService.return_to_draft` | ContentStore.save_document | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 512 | `ContentService.return_to_draft` | ContentStore.log | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 528 | `ContentService.publish` | hook prepare (Sales) | listener/hook | attribute of ContentService (self.hooks, set by the Sales workspace) | its core's own space | – | propagates (ContentError→409) |
| 535 | `ContentService.publish` | hook published (Sales), via _records_step | listener/hook | attribute of ContentService (self.hooks, set by the Sales workspace) | its core's own space | – | swallowed by _after_commit: logged, records_pending set |
| 538 | `ContentService.publish` | ContentStore.clear_draft (via _after_commit) | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | swallowed: logged in the activity |
| 539 | `ContentService.publish` | ContentStore.log (via _after_commit) | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | swallowed: logged in the activity |
| 553 | `ContentService._own_draft` | hook self_approval | listener/hook | attribute of ContentService (self.self_approval) | its core's own space | – | False→ContentError (409) |
| 593 | `ContentService._write_version` | ActionsEngine.execute(publish_version) | decision | attribute of ContentService (self.actions, the core's engine) | its core's own space | acting_person(content._operator.name): the signed-in person, else the configured operator name (KP_OPERATOR_NAME: 'Operator', or the Sales profile's default) | Exception→result None; then committed→the record, else ContentError ('could not be published') |
| 599 | `ContentService._write_version` | SourceRegister.get | read | attribute of ContentService (self.register) | its core's own space | – | propagates |
| 653 | `ContentService._swap` | settle() | settle | attribute of ContentService (self.register, self.section_store) | its core's own space | – | propagates (→ engine 'error') |
| 654 | `ContentService._swap` | SourceRegister.get | read | attribute of ContentService (self.register) | its core's own space | – | None→ContentError |
| 662 | `ContentService._swap` | SourceRegister.stage_content | write | attribute of ContentService (self.register) | its core's own space | – | Exception→_discard_staged, re-raised |
| 663 | `ContentService._swap` | SectionStore.stage_for_source | write | attribute of ContentService (self.section_store) | its core's own space | – | Exception→_discard_staged, re-raised |
| 665 | `ContentService._swap` | ContentStore.add_version (uncommitted) | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | Exception→_discard_staged, re-raised |
| 672 | `ContentService._swap` | SourceRegister.update (the commit: content_sha256 + approval_status) | decision | attribute of ContentService (self.register) | its core's own space | the publish_version action's actor (OPERATOR) when approved; no action for a rename of an unapproved document | Exception→landed? kept : _discard_staged + re-raise; None→ContentError |
| 674 | `ContentService._swap` | SourceRegister.get | read | attribute of ContentService (self.register) | its core's own space | – | propagates |
| 683 | `ContentService._swap` | ContentStore.commit_version | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | swallowed |
| 691 | `ContentService._move_into_place` | SourceRegister.promote_content | write | attribute of ContentService (self.register) | its core's own space | – | swallowed (a reader settles it later) |
| 692 | `ContentService._move_into_place` | SectionStore.promote_for_source | write | attribute of ContentService (self.section_store) | its core's own space | – | swallowed (a reader settles it later) |
| 697 | `ContentService._discard_staged` | SourceRegister.discard_staged_content (bound method) | write | attribute of ContentService (self.register) | its core's own space | – | swallowed |
| 697 | `ContentService._discard_staged` | SectionStore.discard_staged_for_source (bound method) | write | attribute of ContentService (self.section_store) | its core's own space | – | swallowed |
| 708 | `ContentService._after_publish` | hooks refresh_processes, rebuild_facts | listener/hook | attributes of ContentService | its core's own space | – | each tried twice, then swallowed |
| 743 | `ContentService._records_step` | ContentStore.set_meta | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | swallowed |
| 753 | `ContentService.retry_records` | ContentStore.meta | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 755 | `ContentService.retry_records` | SourceRegister.get | read | attribute of ContentService (self.register) | its core's own space | – | propagates |
| 759 | `ContentService.retry_records` | hook prepare (Sales) | listener/hook | attribute of ContentService (self.hooks, set by the Sales workspace) | its core's own space | – | Exception→return False |
| 760 | `ContentService.retry_records` | hook published (Sales) | listener/hook | attribute of ContentService (self.hooks, set by the Sales workspace) | its core's own space | – | Exception→return False |
| 763 | `ContentService.retry_records` | ContentStore.log | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 765 | `ContentService.retry_records` | ContentStore.set_meta | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 775 | `ContentService._after_commit` | ContentStore.log | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | swallowed |
| 783 | `ContentService._note_lost_event` | ContentStore.log | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | swallowed |
| 797 | `ContentService.rename` | hook retitle (Sales) | listener/hook | attribute of ContentService (self.hooks, set by the Sales workspace) | its core's own space | – | propagates |
| 799 | `ContentService.rename` | SourceRegister.update | write | attribute of ContentService (self.register) | its core's own space | – | propagates |
| 800 | `ContentService.rename` | ContentStore.log | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 802 | `ContentService.rename` | ContentStore.document | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 805 | `ContentService.rename` | hook prepare (Sales) | listener/hook | attribute of ContentService (self.hooks, set by the Sales workspace) | its core's own space | – | propagates |
| 818 | `ContentService.rename` | hook published (Sales), via _records_step | listener/hook | attribute of ContentService (self.hooks, set by the Sales workspace) | its core's own space | – | swallowed by _after_commit |
| 818 | `ContentService.rename` | SourceRegister.get | read | attribute of ContentService (self.register) | its core's own space | – | swallowed by _after_commit |
| 819 | `ContentService.rename` | ContentStore.log (via _after_commit) | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | swallowed |
| 831 | `ContentService.library` | ContentStore.groups | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 831 | `ContentService.library` | ContentStore.placements | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 835 | `ContentService._place_new` | ContentStore.placements | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates; under if_free |
| 836 | `ContentService._place_new` | hook default_library (Sales, Product Guide only) | listener/hook | attribute of ContentService (self.hooks, set by the Sales workspace) | its core's own space | – | propagates |
| 837 | `ContentService._place_new` | ContentStore.meta | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 838 | `ContentService._place_new` | ContentStore.groups | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 839 | `ContentService._place_new` | SourceRegister.list | read | attribute of ContentService (self.register) | its core's own space | – | propagates |
| 841 | `ContentService._place_new` | SourceRegister.list | read | attribute of ContentService (self.register) | its core's own space | – | propagates |
| 848 | `ContentService._place_new` | ContentStore.place | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates; under if_free |
| 852 | `ContentService._seed_library` | ContentStore.meta | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 855 | `ContentService._seed_library` | ContentStore.meta | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 858 | `ContentService._seed_library` | hook default_library (Sales) | listener/hook | attribute of ContentService (self.hooks, set by the Sales workspace) | its core's own space | – | propagates |
| 859 | `ContentService._seed_library` | ContentStore.add_group | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 860 | `ContentService._seed_library` | ContentStore.set_meta | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 865 | `ContentService._parent_of` | ContentStore.groups | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 866 | `ContentService._parent_of` | ContentStore.placements | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 872 | `ContentService._check_parent` | ContentStore.groups | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | absent→ContentError |
| 874 | `ContentService._check_parent` | SourceRegister.get | read | attribute of ContentService (self.register) | its core's own space | – | absent→ContentError |
| 889 | `ContentService.set_parent` | ContentStore.place | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 890 | `ContentService.set_parent` | ContentStore.log | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 899 | `ContentService.move` | ContentStore.groups | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | absent→NotFound |
| 911 | `ContentService.move` | ContentStore.arrange | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 913 | `ContentService.move` | ContentStore.log | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 920 | `ContentService._children` | SourceRegister.list | read | attribute of ContentService (self.register) | its core's own space | – | propagates |
| 932 | `ContentService.create_group` | ContentStore.add_group | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 936 | `ContentService.update_group` | ContentStore.groups | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | absent→NotFound |
| 948 | `ContentService.update_group` | ContentStore.next_position | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 951 | `ContentService.update_group` | ContentStore.update_group | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 955 | `ContentService.delete_group` | ContentStore.groups | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | absent→NotFound |
| 958 | `ContentService.delete_group` | ContentStore.delete_group | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 966 | `ContentService._describe_node` | ContentStore.groups | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 967 | `ContentService._describe_node` | SourceRegister.get | read | attribute of ContentService (self.register) | its core's own space | – | propagates |
| 973 | `ContentService._decide` | SourceRegister.decide | decision | attribute of ContentService (self.register) | its core's own space | none (no engine) | TextNotNamed→ContentError; only when no engine is wired (not in production) |
| 983 | `ContentService._approve` | ActionsEngine.execute(approve_source) | decision | attribute of ContentService (self.actions, the core's engine) | its core's own space | acting_person(content._operator.name): the signed-in person, else the configured operator name (KP_OPERATOR_NAME: 'Operator', or the Sales profile's default) | not ok→ContentError(message or 'The approval action failed') (409 at the content routes) |
| 993 | `ContentService._reject` | ActionsEngine.execute(reject_source) | decision | attribute of ContentService (self.actions, the core's engine) | its core's own space | acting_person(content._operator.name): the signed-in person, else the configured operator name (KP_OPERATOR_NAME: 'Operator', or the Sales profile's default) | not ok→ContentError(message or 'The rejection action failed') (409 at the content routes) |
| 1005 | `ContentService.versions` | ContentStore.versions | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 1013 | `ContentService.version` | ContentStore.version | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | absent→NotFound |
| 1021 | `ContentService.restore` | ContentStore.log | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 1028 | `ContentService._text_of` | ContentStore.document | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | no draft→NotFound |
| 1044 | `ContentService.comments` | ContentStore.document | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 1046 | `ContentService.comments` | ContentStore.comments | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 1058 | `ContentService.add_comment` | ContentStore.add_comment | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 1060 | `ContentService.add_comment` | ContentStore.log | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 1067 | `ContentService._require_comment` | ContentStore.comment | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | absent→NotFound |
| 1076 | `ContentService.reply` | ContentStore.add_reply | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 1077 | `ContentService.reply` | ContentStore.log | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 1082 | `ContentService.set_comment_status` | ContentStore.set_comment_status | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 1083 | `ContentService.set_comment_status` | ContentStore.log | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 1089 | `ContentService.delete_comment` | ContentStore.delete_comment | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 1090 | `ContentService.delete_comment` | ContentStore.log | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 1101 | `ContentService._update_details` | hook describe (Sales) | listener/hook | attribute of ContentService (self.hooks, set by the Sales workspace) | its core's own space | – | propagates |
| 1105 | `ContentService._update_details` | hook retitle (Sales) | listener/hook | attribute of ContentService (self.hooks, set by the Sales workspace) | its core's own space | – | propagates (Sales retitle: ContentError/OSError) |
| 1144 | `ContentService._update_details` | SourceRegister.update | write | attribute of ContentService (self.register) | its core's own space | – | propagates |
| 1146 | `ContentService._update_details` | ContentStore.log | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 1152 | `ContentService.activity` | ContentStore.activity | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates |
| 1158 | `ContentService.suggestions` | hook suggestions (unused while all_suggestions is set) | listener/hook | attribute of ContentService (self.hooks, set by the Sales workspace) | its core's own space | – | propagates |
| 1170 | `ContentService.save_image` | assets folder (raw file write under ContentStore.assets) | write | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | propagates; no lock check |
| 1174 | `ContentService.image` | assets folder (raw file read) | read | attribute of ContentService (self.store, the ContentStore) | its core's own space | – | outside or missing→NotFound |

### `src/assistant/governance/intelligence.py` (3)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 49 | `KnowledgeIntelligence.run` | SourceRegister.list (or GovernedSources.list) | read | attribute of KnowledgeIntelligence | the stores it is handed (own core from core routes; the family from Knowledge) | – | none caught: propagates (500 at a route) |
| 73 | `KnowledgeIntelligence.run` | SectionStore.list_for_source(sha) | read+settle | attribute of KnowledgeIntelligence | the stores it is handed (own core from core routes; the family from Knowledge) | – | none caught: propagates (500 at a route) |
| 138 | `KnowledgeIntelligence.run` | SectionStore.list_for_source(sha) | read+settle | attribute of KnowledgeIntelligence | the stores it is handed (own core from core routes; the family from Knowledge) | – | none caught: propagates (500 at a route) |

### `src/assistant/governance/reanalysis.py` (4)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 105 | `build_reanalysis_report` | SourceRegister.list | read | injection (function parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| 106 | `build_reanalysis_report` | SourceRegister.list | read | injection (function parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| 142 | `latest_reanalysis_status` | SourceRegister.list | read | injection (function parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| 170 | `_source_fingerprints` | SourceRegister.list | read | injection (function parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |

### `src/assistant/governance/review_jobs.py` (2)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 84 | `InternalReviewStore.create` | SourceRegister.list | read | injection (function parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| 271 | `internal_review_cache_key` | SourceRegister.list | read | injection (function parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |

### `src/assistant/governance/statement_review.py` (1)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 50 | `run_statement_review` | SourceRegister.list | read | injection (function parameter) | the stores it is handed (the family, from the Sales statement review) | – | none caught: the background thread records 'failed' |

### `src/assistant/governance/statements.py` (2)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 121 | `StatementStore.sync` | SourceRegister.list | read | injection (function parameter) | the stores it is handed (the family) | – | none caught: the background thread records 'failed' |
| 129 | `StatementStore.sync` | SectionStore.list_for_source(sha) | read+settle | injection (function parameter) | the stores it is handed (the family) | – | none caught: the background thread records 'failed' |

### `src/assistant/ingestion/service.py` (7)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 109 | `_ingest` | settle() | settle | injection (function parameter) | the stores it is handed (own core from core routes; the family from Knowledge) | – | propagates |
| 110 | `_ingest` | SourceRegister.get | read | injection (function parameter) | the stores it is handed (own core from core routes; the family from Knowledge) | – | None→NotIngestableError |
| 114 | `_ingest` | SourceRegister.read_content | read+settle | injection (function parameter) | the stores it is handed (own core from core routes; the family from Knowledge) | – | propagates (FileNotFoundError) |
| 118 | `_ingest` | SectionStore.remove_for_source | write | injection (function parameter) | the stores it is handed (own core from core routes; the family from Knowledge) | – | propagates; then NotIngestableError |
| 119 | `_ingest` | SourceRegister.update | write | injection (function parameter) | the stores it is handed (own core from core routes; the family from Knowledge) | – | propagates; then NotIngestableError |
| 126 | `_ingest` | SectionStore.replace_for_source | write | injection (function parameter) | the stores it is handed (own core from core routes; the family from Knowledge) | – | propagates |
| 128 | `_ingest` | SourceRegister.update | write | injection (function parameter) | the stores it is handed (own core from core routes; the family from Knowledge) | – | propagates; None→AssertionError |

### `src/assistant/ontology/sync.py` (3)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 42 | `_sync_sources` | SourceRegister.list | read | injection (function parameter) | its core's own space | – | none caught: propagates (500 at a route) |
| 240 | `_extract_process_key_facts` | SourceRegister.get | read | injection (function parameter) | its core's own space | – | FileNotFoundError/KeyError/ContentReplaced→empty text (swallowed) |
| 241 | `_extract_process_key_facts` | SourceRegister.read_content(sha) | read+settle | injection (function parameter) | its core's own space | – | FileNotFoundError/KeyError/ContentReplaced→empty text (swallowed) |

### `src/assistant/process/registry.py` (2)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 40 | `ProcessRegistry.derive_from_sources` | SourceRegister.list | read | injection (function parameter) | its core's own space | – | none caught: propagates (500 at a route) |
| 44 | `ProcessRegistry.derive_from_sources` | SourceRegister.read_content(sha) | read+settle | injection (function parameter) | its core's own space | – | ContentReplaced→source skipped; FileNotFoundError propagates |

### `src/assistant/regulatory/discovery.py` (2)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 65 | `discover_regulatory_candidates` | SourceRegister.list | read | injection (function parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| 67 | `discover_regulatory_candidates` | SectionStore.list_for_source(sha) | read+settle | injection (function parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |

### `src/assistant/regulatory/impact.py` (2)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 110 | `_affected_sources` | SourceRegister.list | read | injection (function parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| 112 | `_affected_sources` | SectionStore.list_for_source(sha) | read+settle | injection (function parameter) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |

### `src/assistant/retrieval/index.py` (5)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 83 | `CorpusIndex.fingerprint` | SourceRegister.list | read | attribute of CorpusIndex | its core's own space | – | none caught: propagates (500 at a route) (only when no records are passed) |
| 88 | `CorpusIndex.current` | SourceRegister.list | read | attribute of CorpusIndex | its core's own space | – | none caught: propagates (500 at a route) |
| 112 | `CorpusIndex._build` | SectionStore.list_for_source(sha) | read+settle | attribute of CorpusIndex | its core's own space | – | none caught: propagates (500 at a route) |
| 124 | `CorpusIndex.all_texts` | SourceRegister.list | read | attribute of CorpusIndex | its core's own space | – | OSError swallowed by its caller (retrieval/service.py:86-89); a JSON error passes |
| 124 | `CorpusIndex.all_texts` | SectionStore.list_for_source (no sha) | read | attribute of CorpusIndex | its core's own space | – | OSError swallowed by its caller (retrieval/service.py:86-89); a JSON error passes |

### `src/assistant/sources/bulk_import.py` (3)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 60 | `import_folder` | SourceRegister.list | read | injection (function parameter) | the register its script builds (ungoverned) | – | none caught |
| 96 | `import_folder` | register_upload → SourceRegister.add | write | injection (function parameter) | the register its script builds (ungoverned) | – | UploadError/NotIngestableError/UnicodeDecodeError/OSError→row 'failed' |
| 98 | `import_folder` | ingest_source | write | injection (function parameter) | the register its script builds (ungoverned) | – | UploadError/NotIngestableError/UnicodeDecodeError/OSError→row 'failed' |

### `src/assistant/sources/service.py` (1)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 48 | `register_upload` | SourceRegister.add (+ on_add listeners) | write | injection (function parameter) | the stores it is handed (own core from core routes; the family from Knowledge); FamilyRegister.add always writes the Product Guide | – | UploadError raised before it; add's errors propagate |

### `src/assistant/sources/settle.py` (8)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 9 | `settle` | SourceRegister.get | read | injection (function parameter) | the stores it is handed (own core from core routes; the family from Knowledge) | – | none caught: propagates (500 at a route) |
| 12 | `settle` | SourceRegister.promote_if_committed | settle | injection (function parameter) | the stores it is handed (own core from core routes; the family from Knowledge) | – | LockBusy only when not holding (callers hold the lock); propagates |
| 14 | `settle` | SectionStore.promote_if_committed | settle | injection (function parameter) | the stores it is handed (own core from core routes; the family from Knowledge) | – | propagates |
| 22 | `stamp_unfingerprinted` | SourceRegister.list | read | injection (function parameter) | its core's own space | – | none caught: propagates (500 at a route) |
| 23 | `stamp_unfingerprinted` | SectionStore.fingerprint | read | injection (function parameter) | its core's own space | – | none caught: propagates (500 at a route) |
| 25 | `stamp_unfingerprinted` | SectionStore.list_for_source (no sha) | read | injection (function parameter) | its core's own space | – | none caught: propagates (500 at a route) |
| 29 | `stamp_unfingerprinted` | SourceRegister.read_content | read+settle | injection (function parameter) | its core's own space | – | OSError→source skipped |
| 33 | `stamp_unfingerprinted` | SectionStore.replace_for_source | write | injection (function parameter) | its core's own space | – | none caught: propagates (500 at a route) |

### `services/opsatlas_sales/app.py` (5)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 135 | `_build` | apply_family_layout | move | family view (local FamilyRegister/FamilySections) | family: each document to the space its record says, from its first holder | none recorded (move_document's default 'local operator', returned only) | none caught: start-up fails; under locked(root/'workspace') |
| 150 | `_build` | Knowledge.on_out_of_step ← ContentService.retry_records | listener/hook | attribute assignment on Knowledge | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | swallowed by Knowledge._in_step (knowledge.py:56-59) |
| 150 | `_build.<lambda>` | FamilyRegister.space_of | read | family view | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | no holder→cores[None] KeyError, swallowed by _in_step |
| 150 | `_build.<lambda>` | ContentService.retry_records | write | app.state literal (cores[…].state.content) | the first holder's core | – | swallowed by _in_step |
| 154 | `_build` | ContentService.hooks ← the Sales hooks (content.attach) | listener/hook | app.state literal (cores[space].state.content) | each family space's own core | – | none caught: start-up fails |

### `services/opsatlas_sales/content.py` (7)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 90 | `attach.prepare` | ContentService.record_text | read+settle | attribute of the attached core (content) | the attached core's own space | – | ContentError/OSError→previous None (swallowed); NotIngestableError propagates |
| 152 | `attach.describe` | FamilyRegister.get | read | family view (Knowledge.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| 233 | `attach.settled_how` | ContentService.operator | read | attribute of the attached core (content) | the attached core's own space | – | none caught: propagates (500 at a route) |
| 257 | `attach.decide` | ContentService._approve / _reject (→ the attached core's engine) | decision | attribute of the attached core (content) | the attached core's own space | acting_person(content._operator.name): the signed-in person, else the configured operator name (KP_OPERATOR_NAME: 'Operator', or the Sales profile's default) | ContentError propagates (409 at the content routes) |
| 260 | `attach.decide` | Knowledge.decide (→ FamilyActions / FamilyRegister.decide) | decision | family view (Knowledge) | family: first holder (product-guide, sales-playbook, system), else Product Guide | acting_person('service:workspace-key'): the signed-in person, else 'service:workspace-key' | ValueError→ContentError (409); anything else (NotHolding) propagates (500) |
| 270 | `attach.retitle` | ContentService.record_text | read+settle | attribute of the attached core (content) | the attached core's own space | – | none caught: ContentError→409, OSError→500 at the route |
| 293 | `attach` | ContentService.hooks ← prepare, published, describe, suggestions, all_suggestions, keep, unkeep, settled_how, history, decide, retitle, default_library | listener/hook | attribute of the attached core (content) | the attached core | – | none |

### `services/opsatlas_sales/governance.py` (13)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 186 | `GovernedSources.list` | FamilyRegister.list | read | family view (GovernedSources.register) | all three family spaces | – | none caught: propagates (500 at a route) |
| 189 | `GovernedSources.__getattr__` | FamilyRegister.* (delegation) | read | family view (GovernedSources.register) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through; nothing reaches it today (KnowledgeIntelligence calls only list) |
| 212 | `GovernanceDesk.text` | FamilyRegister.get | read | family view (GovernanceDesk.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| 218 | `GovernanceDesk.text` | FamilyRegister.read_content(sha) | read+settle | family view (GovernanceDesk.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | ContentReplaced→'' (not remembered); FileNotFoundError propagates |
| 226 | `GovernanceDesk.corpus_definitions` | FamilyRegister.list | read | family view (GovernanceDesk.register = FamilyRegister) | all three family spaces | – | none caught: propagates (500 at a route) |
| 238 | `GovernanceDesk.corpus_mentions` | FamilyRegister.list | read | family view (GovernanceDesk.register = FamilyRegister) | all three family spaces | – | none caught: propagates (500 at a route) |
| 253 | `GovernanceDesk.fingerprint` | FamilyRegister.list | read | family view (GovernanceDesk.register = FamilyRegister) | all three family spaces | – | none caught: propagates (500 at a route) |
| 456 | `GovernanceDesk.section_text` | FamilyRegister.get | read | family view (GovernanceDesk.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| 457 | `GovernanceDesk.section_text` | FamilySections.list_for_source(sha) | read+settle | family view (GovernanceDesk.sections = FamilySections) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| 471 | `GovernanceDesk.relation` | FamilyRegister.get | read | family view (GovernanceDesk.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| 622 | `GovernanceDesk._versions` | FamilyRegister.get | read | family view (GovernanceDesk.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| 635 | `GovernanceDesk._changed_since_proposed` | FamilyRegister.get | read | family view (GovernanceDesk.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| 665 | `GovernanceDesk._close` | FamilyActions.execute(accept_issue) (its rule source_exists reads the holder's register) | read | family view (GovernanceDesk.actions = FamilyActions) | family: first holder (product-guide, sales-playbook, system), else Product Guide | acting_person('service:workspace-key'): the signed-in person, else 'service:workspace-key' | not ok→ValueError('Atlas could not record the resolution…') (409 at Tibi's route) |

### `services/opsatlas_sales/knowledge.py` (27)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 54 | `Knowledge._in_step` | FamilyRegister.names_text | read+settle | family view (Knowledge.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | a reason→ValueError ('out of step'), after on_out_of_step |
| 57 | `Knowledge._in_step` | hook on_out_of_step (→ retry_records on the holder's core) | listener/hook | attribute of Knowledge | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | any Exception swallowed; the refusal stands |
| 66 | `Knowledge._withdraw` | FamilyRegister.get | read | family view (Knowledge.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | None or already rejected→no-op |
| 71 | `Knowledge._withdraw` | FamilyActions.execute(reject_source) | decision | family view (Knowledge.actions = FamilyActions) | family: first holder (product-guide, sales-playbook, system), else Product Guide | acting_person('service:workspace-key'): the signed-in person, else 'service:workspace-key' | not ok→ValueError(message or 'The withdrawal was refused…') |
| 76 | `Knowledge._withdraw` | FamilyRegister.decide | decision | family view (Knowledge.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | none (no engine) | none caught; only when no actions are wired (not in production) |
| 160 | `Knowledge._card` | FamilyRegister.list | read | family view (Knowledge.register = FamilyRegister) | all three family spaces | – | none caught: propagates (500 at a route) |
| 163 | `Knowledge._card` | register_upload → FamilyRegister.add | write | family view (Knowledge.register = FamilyRegister) | family: always the Product Guide (home) | – | none caught (start-up fails) |
| 165 | `Knowledge._card` | ingest_source (family stores) | write | family view (Knowledge.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught (start-up fails) |
| 168 | `Knowledge._card` | register_upload → FamilyRegister.add | write | family view (Knowledge.register = FamilyRegister) | family: always the Product Guide (home) | – | none caught (start-up fails) |
| 169 | `Knowledge._card` | ingest_source (family stores) | write | family view (Knowledge.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught (start-up fails) |
| 200 | `Knowledge.evidence_changed` | FamilyRegister.get | read | family view (Knowledge.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| 249 | `Knowledge._eligible` | FamilyRegister.get | read | family view (Knowledge.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | eligible() turns OSError into False |
| 252 | `Knowledge._eligible` | FamilyRegister.read_content | read+settle | family view (Knowledge.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | eligible() turns OSError into False |
| 255 | `Knowledge._eligible` | FamilyRegister.get | read | family view (Knowledge.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | eligible() turns OSError into False |
| 258 | `Knowledge._eligible` | FamilyRegister.read_content | read+settle | family view (Knowledge.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | eligible() turns OSError into False |
| 264 | `Knowledge.catalog` | FamilyRegister.space_of | read | family view (Knowledge.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| 282 | `Knowledge.decide` | FamilyRegister.get | read | family view (Knowledge.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | None→ValueError('Source changed…') |
| 283 | `Knowledge.decide` | FamilyRegister.read_content | read+settle | family view (Knowledge.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | mismatch→ValueError('Source changed…'); OSError propagates |
| 286 | `Knowledge.decide` | FamilyRegister.get | read | family view (Knowledge.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | None→ValueError('Supporting evidence changed…') |
| 287 | `Knowledge.decide` | FamilyRegister.read_content | read+settle | family view (Knowledge.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | mismatch→ValueError; OSError propagates |
| 292 | `Knowledge.decide` | FamilyActions.execute(approve_source \| reject_source) | decision | family view (Knowledge.actions = FamilyActions) | family: first holder (product-guide, sales-playbook, system), else Product Guide | acting_person('service:workspace-key'): the signed-in person, else 'service:workspace-key' | not ok→ValueError('Atlas approval action failed; review remains pending') (the action's message dropped) |
| 298 | `Knowledge.decide` | FamilyRegister.decide | decision | family view (Knowledge.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | none recorded (no audited action; Knowledge's own review names acting_name()) | ValueError (TextNotNamed)→ValueError('Source changed; review the current version'); NotHolding propagates |
| 343 | `Knowledge.propose` | register_upload → FamilyRegister.add | write | family view (Knowledge.register = FamilyRegister) | family: always the Product Guide (home) | – | propagates (→409 for ValueError at the Sales route) |
| 344 | `Knowledge.propose` | ingest_source (family stores) | write | family view (Knowledge.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | propagates (NotIngestableError is a ValueError→409) |
| 353 | `Knowledge.propose` | register_upload → FamilyRegister.add | write | family view (Knowledge.register = FamilyRegister) | family: always the Product Guide (home) | – | propagates |
| 354 | `Knowledge.propose` | ingest_source (family stores) | write | family view (Knowledge.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | propagates |
| 441 | `Knowledge.native_approval` | FamilyRegister.get | read | family view (Knowledge.register = FamilyRegister) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |

### `services/opsatlas_sales/routes_sales_api.py` (8)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 91 | `readable` | ContentStore.folders_of (reference) | read | getattr(app.state, 'content') + app.state.content literal | the Product Guide's content store | – | none caught: propagates (500 at a route) |
| 92 | `readable.<lambda>` | FamilyRegister.space_of | read | app.state.family_register (literal, bound to 'family') | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| 97 | `readable` | ContentStore.folders_of (reference) | read | app.state literal (app.state.cores[s].state.content) | each family space the conversation's owner may read | – | none caught: propagates (500 at a route) |
| 103 | `readable.keep` | FamilyRegister.space_of | read | app.state.family_register (bound) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| 128 | `contract` | FamilyRegister.space_of | read | app.state.family_register (bound) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| 189 | `governance_agenda.visible_source` | FamilyRegister.space_of | read | app.state.family_register (bound) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| 232 | `source` | FamilyRegister.read_record_text | read+settle | app.state.family_register (literal) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | None→404; strict utf-8 decode: UnicodeDecodeError→500 |
| 243 | `propose` | apply_family_layout | move | family view (injected) | family: each undecided document to its record's space | none recorded (move_document's default 'local operator', returned only) | none caught: 500 after the claim is saved |

### `services/opsatlas_sales/routes_spaces.py` (5)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 48 | `list_spaces` | SourceRegister.list | read | app.state literal (cores[id].state.register) | each space the caller may see | – | none caught: propagates (500 at a route) |
| 91 | `change_space` | SourceRegister.list | read | app.state literal (cores[id].state.register) | the named space | – | none caught: propagates (500 at a route) |
| 98 | `transfer` | SourceRegister.get | read | app.state literal (core.state.register) | all active spaces, in cores order: the first holder is the origin | – | none caught: propagates (500 at a route) |
| 114 | `transfer` | move_document(keep_approval=False) | move | app.state through bound names (source/target = cores[x].state) | origin: first holder; target: named in the body | actor.display_name (returned and logged only) | none caught: KeyError/ValueError/NotHolding→500 |
| 118 | `transfer` | ContentStore.log | write | app.state through a bound name (target.content.store) | the target space | – | none caught: 500 after the move |

### `services/opsatlas_sales/spaces.py` (51)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 210 | `FamilyRegister.space_of` | SourceRegister.get (each family register, in order) | read | attribute of FamilyRegister (self.registers) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| 217 | `FamilyRegister.list` | SourceRegister.list (each family register) | read | attribute of FamilyRegister (self.registers) | all three family spaces | – | none caught: propagates (500 at a route) |
| 220 | `FamilyRegister.get` | SourceRegister.get (the holder's) | read | attribute of FamilyRegister (self._for) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through |
| 223 | `FamilyRegister.file_path` | SourceRegister.file_path (the holder's) | read | attribute of FamilyRegister (self._for) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through; no production caller |
| 226 | `FamilyRegister.read_content` | SourceRegister.read_content (the holder's) | read+settle | attribute of FamilyRegister (self._for) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through |
| 229 | `FamilyRegister.read_record_text` | SourceRegister.read_record_text (the holder's) | read+settle | attribute of FamilyRegister (self._for) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through |
| 232 | `FamilyRegister.write_content` | SourceRegister.write_content (the holder's) | write | attribute of FamilyRegister (self._for) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through; no production caller |
| 235 | `FamilyRegister.stage_content` | SourceRegister.stage_content (the holder's) | write | attribute of FamilyRegister (self._for) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through; no production caller |
| 238 | `FamilyRegister.promote_content` | SourceRegister.promote_content (the holder's) | write | attribute of FamilyRegister (self._for) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through; no production caller |
| 241 | `FamilyRegister.promote_if_committed` | SourceRegister.promote_if_committed (the holder's) | settle | attribute of FamilyRegister (self._for) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through |
| 244 | `FamilyRegister.discard_staged_content` | SourceRegister.discard_staged_content (the holder's) | write | attribute of FamilyRegister (self._for) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through; no production caller |
| 247 | `FamilyRegister.update` | SourceRegister.update (the holder's) | write | attribute of FamilyRegister (self._for) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through |
| 250 | `FamilyRegister.names_text` | SourceRegister.names_text (the holder's) | read+settle | attribute of FamilyRegister (self._for) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through |
| 253 | `FamilyRegister.decide` | SourceRegister.decide (the holder's) | decision | attribute of FamilyRegister (self._for) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through |
| 256 | `FamilyRegister.add` | SourceRegister.add (the home register) | write | attribute of FamilyRegister (self.registers[home]) | family: always the Product Guide (home) | – | passes through |
| 259 | `FamilyRegister.remove` | SourceRegister.remove (the holder's) | write | attribute of FamilyRegister (self._for) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through; no production caller |
| 271 | `FamilySections._for` | FamilyRegister.space_of | read | attribute of FamilySections | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through |
| 274 | `FamilySections.replace_for_source` | SectionStore.replace_for_source (the holder's) | write | attribute of FamilySections (self._for) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through |
| 277 | `FamilySections.list_for_source` | SectionStore.list_for_source (the holder's) | read+settle | attribute of FamilySections (self._for) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through |
| 280 | `FamilySections.fingerprint` | SectionStore.fingerprint (the holder's) | read | attribute of FamilySections (self._for) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through; no production caller |
| 283 | `FamilySections.stage_for_source` | SectionStore.stage_for_source (the holder's) | write | attribute of FamilySections (self._for) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through; no production caller |
| 286 | `FamilySections.promote_for_source` | SectionStore.promote_for_source (the holder's) | write | attribute of FamilySections (self._for) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through; no production caller |
| 289 | `FamilySections.promote_if_committed` | SectionStore.promote_if_committed (the holder's) | settle | attribute of FamilySections (self._for) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through |
| 292 | `FamilySections.discard_staged_for_source` | SectionStore.discard_staged_for_source (the holder's) | write | attribute of FamilySections (self._for) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through; no production caller |
| 295 | `FamilySections.count_for_source` | SectionStore.count_for_source (the holder's) | read | attribute of FamilySections (self._for) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through; no production caller |
| 298 | `FamilySections.remove_for_source` | SectionStore.remove_for_source (the holder's) | write | attribute of FamilySections (self._for) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through |
| 309 | `FamilyActions.execute` | FamilyRegister.space_of | read | attribute of FamilyActions | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | passes through |
| 310 | `FamilyActions.execute` | ActionsEngine.execute (the holder's engine) | decision | attribute of FamilyActions (self.engines) | family: first holder (product-guide, sales-playbook, system), else Product Guide | the caller's | passes through |
| 313 | `FamilyActions.__getattr__` | ActionsEngine.* (the Product Guide's) | read | attribute of FamilyActions | family: always the Product Guide (home) | – | passes through; no production caller (Knowledge and the desk call only execute) |
| 328 | `_move_content` | content.db of both spaces (raw sqlite: copy and delete rows, place in the target library) | move | injection (function parameter) | the two spaces move_document is given | – | propagates; no store, no authoriser: the lock is checked by move_document's require |
| 378 | `move_document` | settle() | settle | injection (function parameter) | the origin space | – | propagates |
| 379 | `move_document` | SourceRegister.get | read | injection (function parameter) | the origin space | – | None→KeyError |
| 382 | `move_document` | SourceRegister.get | read | injection (function parameter) | the target space | – | held→ValueError |
| 385 | `move_document` | SourceRegister.read_content(sha) | read+settle | injection (function parameter) | the origin space | – | ContentReplaced propagates |
| 390 | `move_document` | SourceRegister.add (the record as moved, with its approval) | move | injection (function parameter) | the target space | – | propagates |
| 391 | `move_document` | SourceRegister.update (every field, content_sha256 and approval_status included) | move | injection (function parameter) | the target space | – | propagates |
| 392 | `move_document` | SectionStore.list_for_source(sha) | read+settle | injection (function parameter) | the origin space | – | propagates |
| 392 | `move_document` | SectionStore.replace_for_source | move | injection (function parameter) | the target space | – | propagates |
| 401 | `move_document` | assets folder (raw copy) | move | injection (function parameter) | origin → target | – | propagates; no lock check |
| 402 | `move_document` | SectionStore.remove_for_source | move | injection (function parameter) | the origin space | – | propagates |
| 403 | `move_document` | SourceRegister.remove | move | injection (function parameter) | the origin space | – | propagates |
| 406 | `move_document` | assets folder (raw delete) | move | injection (function parameter) | the origin space | – | propagates; no lock check |
| 413 | `_assets_in_use` | SourceRegister.list | read | injection (function parameter) | the origin space | – | none caught: propagates (500 at a route) |
| 415 | `_assets_in_use` | SourceRegister.read_content | read+settle | injection (function parameter) | the origin space | – | OSError→skipped |
| 420 | `_assets_in_use` | content.db (raw sqlite read of versions) | read | injection (function parameter) | the origin space | – | propagates |
| 456 | `apply_family_layout` | FamilyRegister.list | read | family view (parameter) | all three family spaces | – | none caught: propagates (500 at a route) |
| 461 | `apply_family_layout` | FamilyRegister.space_of | read | family view (parameter) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| 464 | `apply_family_layout` | content.db (raw sqlite read of the library) | read | family view (register.registers[have]) | the holder's space | – | none caught: propagates (500 at a route) |
| 467 | `apply_family_layout` | move_document(keep_approval=True) | move | family view (register.registers[x], sections.stores[x]) | from the first holder to the space its record names | none recorded ('local operator' default) | none caught |
| 472 | `apply_family_layout` | content.db (raw sqlite read of meta) | read | family view (register.base_dir = the Product Guide's) | family: always the Product Guide (home) | – | none caught: propagates (500 at a route) |
| 474 | `apply_family_layout` | content.db (raw sqlite DELETE of emptied groups) | move | family view (register.registers[space]) | each space a move emptied | – | propagates; no authoriser and no lock check of its own |

### `services/opsatlas_sales/statement_governance.py` (2)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 135 | `SalesStatementReview.revision` | FamilyRegister.list | read | family view (SalesStatementReview.register) | all three family spaces | – | none caught: propagates (500 at a route) |
| 199 | `SalesStatementReview.findings` | FamilyRegister.get | read | family view (SalesStatementReview.register) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |

### `services/opsatlas_sales/tibi_api.py` (1)

| Line | Function | Operation | Kind | Reached by | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| 138 | `build_router.source` | FamilyRegister.read_record_text | read+settle | app.state.family_register (literal) | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | None→404; decode with 'replace'; others→500 |

### Wiring (52)

| Module | Line | Function | What | Reached by |
|---|---|---|---|---|
| `src/assistant/api/access.py` | 146 | `source_guard` | the serving core's ContentService (for its store) | getattr(app.state, …) |
| `src/assistant/api/access.py` | 176 | `derived_guard` | the serving core's register | getattr(app.state, …) |
| `src/assistant/api/access.py` | 187 | `_visibility` | the request's core's ContentService (for folders_of) | getattr(app.state, …) |
| `src/assistant/api/app.py` | 123 | `create_app` | SourceRegister constructed (when none is injected) | imported class |
| `src/assistant/api/app.py` | 124 | `create_app` | the door's lock: the core's own index file | app.state |
| `src/assistant/api/app.py` | 132 | `create_app` | SectionStore constructed | imported class |
| `src/assistant/api/app.py` | 136 | `create_app` | RetrievalService(registry, section_store) → CorpusIndex | injection |
| `src/assistant/api/app.py` | 187 | `create_app` | register exposed | app.state |
| `src/assistant/api/app.py` | 188 | `create_app` | section store exposed | app.state |
| `src/assistant/api/app.py` | 199 | `create_app` | engine exposed (read by the Sales app for FamilyActions) | app.state |
| `src/assistant/api/app.py` | 217 | `create_app` | routes_sources(register, section_store, forget_content) | injection |
| `src/assistant/api/app.py` | 222 | `create_app` | routes_ingestion(register, section_store) | injection |
| `src/assistant/api/app.py` | 243 | `create_app` | KnowledgeIntelligence(registry, section_store) | injection |
| `src/assistant/api/app.py` | 270 | `create_app` | routes_governance(register, section_store, actions) | injection |
| `src/assistant/api/app.py` | 291 | `create_app` | routes_regulatory(register, section_store) | injection |
| `src/assistant/api/app.py` | 295 | `create_app` | routes_process(register) | injection |
| `src/assistant/api/app.py` | 297 | `create_app` | routes_analytics(register, actions) | injection |
| `src/assistant/api/app.py` | 305 | `create_app` | ContentService constructed: builds its ContentStore, registers save_document and publish_version | imported class |
| `src/assistant/api/app.py` | 309 | `create_app` | register, section store and content store governed by the core's lock | attribute |
| `src/assistant/api/app.py` | 324 | `create_app` | content workflow exposed | app.state |
| `src/assistant/api/app.py` | 332 | `create_app` | routes_content(content) | injection |
| `src/assistant/api/app.py` | 333 | `create_app` | routes_content assets(content) | injection |
| `src/assistant/content/service.py` | 101 | `ContentService.__init__` | ContentStore constructed beside the register | imported class |
| `src/assistant/retrieval/service.py` | 47 | `RetrievalService.__init__` | the core's register kept as an attribute (AnswerService reads self.retrieval.register) | attribute |
| `src/assistant/retrieval/service.py` | 48 | `RetrievalService.__init__` | the core's section store kept as an attribute | attribute |
| `src/assistant/retrieval/service.py` | 54 | `RetrievalService.__init__` | CorpusIndex over the core's stores | injection |
| `services/opsatlas_sales/app.py` | 44 | `govern` | a space core's door points at the workspace lock | app.state |
| `services/opsatlas_sales/app.py` | 45 | `govern` | its register, section store and content store governed by the workspace lock | app.state literal |
| `services/opsatlas_sales/app.py` | 92 | `_build` | the Product Guide's core (its own SourceRegister on root/core) | imported class (in create_app) |
| `services/opsatlas_sales/app.py` | 106 | `_build.build_core` | each other space's core on its partition | imported class |
| `services/opsatlas_sales/app.py` | 124 | `_build` | the family register | app.state literal |
| `services/opsatlas_sales/app.py` | 125 | `_build` | the family sections | app.state literal |
| `services/opsatlas_sales/app.py` | 126 | `_build` | the family actions | app.state literal |
| `services/opsatlas_sales/app.py` | 127 | `_build` | family register exposed | app.state |
| `services/opsatlas_sales/app.py` | 128 | `_build` | Knowledge over the family | family view |
| `services/opsatlas_sales/app.py` | 129 | `_build` | Knowledge's writes governed | attribute |
| `services/opsatlas_sales/app.py` | 146 | `_build` | the desk over the family | family view |
| `services/opsatlas_sales/app.py` | 147 | `_build` | the desk's writes governed | attribute |
| `services/opsatlas_sales/app.py` | 224 | `_build` | routes_spaces(cores, knowledge, register=family) | injection |
| `services/opsatlas_sales/app.py` | 232 | `_build` | routes_sales_api(knowledge, desk, register, sections) | injection |
| `services/opsatlas_sales/governance.py` | 198 | `GovernanceDesk.__init__` | KnowledgeIntelligence over the family, without cited evidence | family view |
| `services/opsatlas_sales/governance.py` | 201 | `GovernanceDesk.__init__` | statement review over the family | family view |
| `services/opsatlas_sales/knowledge.py` | 40 | `Knowledge.__init__` | a SectionStore when none is given (not in production) | imported class |
| `services/opsatlas_sales/routes_conversations.py` | 85 | `raise_turn_action` | core.state.register for its base_dir (a path), core.state.actions for create_improvement_action: no document store touched | app.state literal |
| `services/opsatlas_sales/routes_sales_api.py` | 86 | `readable` | the family register bound to 'family' | app.state literal |
| `services/opsatlas_sales/routes_sales_api.py` | 125 | `contract` | the family register bound to 'family' | app.state literal |
| `services/opsatlas_sales/routes_sales_api.py` | 186 | `governance_agenda` | the family register bound to 'family' | app.state literal |
| `services/opsatlas_sales/routes_spaces.py` | 112 | `transfer` | the origin core's state bound to a name | app.state (bound name) |
| `services/opsatlas_sales/routes_spaces.py` | 113 | `transfer` | the target core's state bound to a name | app.state (bound name) |
| `services/opsatlas_sales/spaces.py` | 324 | `_move_content` | a ContentStore built only to create the target's tables | imported class |
| `services/opsatlas_sales/spaces.py` | 377 | `move_document` | the workspace lock checked for both registers (NotHolding propagates); the raw content move relies on it | lock check |
| `services/opsatlas_sales/tibi_api.py` | 160 | `confirm_fact` | app.state.register for its base_dir (the review history file) | app.state literal |

### Entry points into store-holding helpers and services (69)

| Module | Line | Function | Calls | Effect on the stores | Routing | Actor | Errors |
|---|---|---|---|---|---|---|---|
| `src/assistant/analytics/explain.py` | 41 | `build_computation_traces` | ProcessRegistry.derive_from_sources (the analytics routes' explain context) | read+settle | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| `src/assistant/analytics/export.py` | 296 | `_process_complexity_rows` | ProcessRegistry.derive_from_sources (the analytics routes' export context) | read+settle | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| `src/assistant/answer/service.py` | 397 | `AnswerService._process_records` | ProcessRegistry.derive_from_sources over one reading | read+settle | its core's own space | – | none caught: propagates (500 at a route) |
| `src/assistant/answer/service.py` | 399 | `AnswerService._process_records` | ProcessRegistry.build_from_sources (writes process_registry.json from an ask, which passes the door) | read+settle | its core's own space | – | none caught: propagates (500 at a route) |
| `src/assistant/api/app.py` | 150 | `create_app` | ProcessRegistry.build_from_sources | read+settle (start-up, before the stores are governed) | its core's own space | – | none caught: start-up fails |
| `src/assistant/api/app.py` | 155 | `create_app.rebuild_ontology_store` | rebuild_ontology (the core's register) | read+settle | its core's own space | – | propagates to its caller |
| `src/assistant/api/app.py` | 157 | `create_app` | rebuild_ontology → _sync_sources, _extract_process_key_facts, derive_from_sources | read+settle (start-up) | its core's own space | – | none caught |
| `src/assistant/api/app.py` | 160 | `create_app` | rebuild_ontology (action rebuild_ontology's side effect) | read+settle | its core's own space | – | side-effect failure recorded, outcome stays ok |
| `src/assistant/api/app.py` | 264 | `create_app.refresh_process_registry_side_effect` | ProcessRegistry.build_from_sources (approve/reject's side effect) | read+settle | its core's own space | – | side-effect failure recorded, outcome stays ok |
| `src/assistant/api/app.py` | 268 | `create_app` | rebuild_ontology (approve/reject's side effect) | read+settle | its core's own space | – | side-effect failure recorded, outcome stays ok |
| `src/assistant/api/routes_analytics.py` | 278 | `process_complexity` | ProcessRegistry.derive_from_sources | read+settle | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| `src/assistant/api/routes_analytics.py` | 382 | `_build_report_markdown` | ProcessRegistry.derive_from_sources | read+settle | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| `src/assistant/api/routes_ask.py` | 27 | `ask` | AnswerService.answer → register.list, CorpusIndex (list_for_source(sha)), _process_records (build_from_sources) | read+settle (the route passes the door: no lock held) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | the route's own handling (not store-specific) |
| `src/assistant/api/routes_avatar.py` | 137 | `avatar answer` | AnswerService.answer | read+settle (passes the door) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | the route's own handling (not store-specific) |
| `src/assistant/api/routes_governance.py` | 139 | `_approve_source_action` | _set_status → SourceRegister.decide | decision | its core's own space | the engine's actor | inside the engine: exceptions→'error' outcome |
| `src/assistant/api/routes_governance.py` | 143 | `_reject_source_action` | _set_status → SourceRegister.decide | decision | its core's own space | the engine's actor | inside the engine: exceptions→'error' outcome |
| `src/assistant/api/routes_governance.py` | 170 | `overview` | KnowledgeIntelligence.run | read+settle | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| `src/assistant/api/routes_governance.py` | 186 | `internal_review` | InternalReviewStore.create, cache key; worker thread runs intelligence.run | read+settle (background worker) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | worker records its own failure |
| `src/assistant/api/routes_governance.py` | 210 | `reanalysis_latest` | latest_reanalysis_status | read | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| `src/assistant/api/routes_governance.py` | 216 | `reanalysis` | build_reanalysis_report (intelligence, regulatory discovery) | read+settle | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| `src/assistant/api/routes_governance.py` | 269 | `approve` | _set_status → SourceRegister.decide (fallback without an engine: not in production) | decision | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | none | HTTPException 404/409 as raised |
| `src/assistant/api/routes_governance.py` | 278 | `reject` | _set_status → SourceRegister.decide (fallback without an engine: not in production) | decision | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | none | HTTPException 404/409 as raised |
| `src/assistant/api/routes_governance.py` | 286 | `_refresh_process_registry` | ProcessRegistry.build_from_sources (fallback only) | read+settle | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| `src/assistant/api/routes_process.py` | 70 | `list_processes` | ProcessRegistry.derive_from_sources | read+settle | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| `src/assistant/api/routes_process.py` | 81 | `list_process_maps` | ProcessRegistry.derive_from_sources | read+settle | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| `src/assistant/api/routes_process.py` | 86 | `coverage_map` | ProcessRegistry.derive_from_sources | read+settle | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| `src/assistant/api/routes_process.py` | 91 | `gap_overlap` | ProcessRegistry.derive_from_sources | read+settle | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| `src/assistant/api/routes_process.py` | 100 | `resolve_diagram` | ProcessRegistry.derive_from_sources | read+settle | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| `src/assistant/api/routes_process.py` | 172 | `_record_for` | ProcessRegistry.derive_from_sources | read+settle | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| `src/assistant/api/routes_query.py` | 23 | `query` | RetrievalService.search → CorpusIndex.current | read+settle (passes the door) | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| `src/assistant/api/routes_regulatory.py` | 37 | `candidates` | discover_regulatory_candidates | read+settle | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught: propagates (500 at a route) |
| `src/assistant/api/routes_regulatory.py` | 50 | `impact_simulation` | simulate_regulatory_impact → _affected_sources | read+settle | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | ValueError→404 |
| `src/assistant/api/routes_sources.py` | 90 | `remove_source` | rebuild_ontology | read+settle | own space (the core the X-OpsAtlas-Space header picks; Product Guide when absent) | – | none caught (500 after the deletion) |
| `src/assistant/ontology/sync.py` | 70 | `_sync_processes` | ProcessRegistry.derive_from_sources | read+settle | its core's own space | – | none caught: propagates (500 at a route) |
| `src/assistant/retrieval/service.py` | 87 | `RetrievalService.search` | CorpusIndex.all_texts | read | its core's own space | – | OSError swallowed (a cache that cannot be rewritten is pruned at the next change) |
| `src/assistant/sources/bulk_import.py` | 121 | `import_folder` | ProcessRegistry.build_from_sources | read+settle | the script's register | – | none caught (its script fails) |
| `services/opsatlas_sales/app.py` | 131 | `_build` | Knowledge.seed → _card (register_upload, ingest_source) | write (start-up job) | family: always the Product Guide (home) (uploads), then the family | – | none caught |
| `services/opsatlas_sales/app.py` | 132 | `_build` | Knowledge.seed_conversation → _card | write (start-up job) | family: always the Product Guide (home) | – | none caught |
| `services/opsatlas_sales/app.py` | 143 | `_build` | Knowledge.catalog | read+settle | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught |
| `services/opsatlas_sales/content.py` | 159 | `attach.describe` | Knowledge.native_approval | read | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| `services/opsatlas_sales/content.py` | 160 | `attach.describe` | Knowledge.eligible | read+settle | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | OSError→False |
| `services/opsatlas_sales/content.py` | 217 | `attach.suggestions` | GovernanceDesk.agenda | read+settle | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| `services/opsatlas_sales/content.py` | 220 | `attach.all_suggestions` | GovernanceDesk.agenda | read+settle | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| `services/opsatlas_sales/governance.py` | 353 | `GovernanceDesk.scan` | KnowledgeIntelligence.run over GovernedSources/FamilySections | read+settle | all three family spaces | – | first failure: retried without embeddings |
| `services/opsatlas_sales/governance.py` | 651 | `GovernanceDesk._close` | Knowledge.settle → _in_step, _withdraw | decision | family: first holder (product-guide, sales-playbook, system), else Product Guide | acting_person('service:workspace-key'): the signed-in person, else 'service:workspace-key' | propagates (ValueError→409 at Tibi's route) |
| `services/opsatlas_sales/routes_sales_api.py` | 157 | `catalog` | Knowledge.catalog | read+settle | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| `services/opsatlas_sales/routes_sales_api.py` | 166 | `digest` | Knowledge.catalog | read+settle | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| `services/opsatlas_sales/routes_sales_api.py` | 172 | `search` | Knowledge.catalog (the route passes the door) | read+settle | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| `services/opsatlas_sales/routes_sales_api.py` | 183 | `governance_agenda` | GovernanceDesk.agenda | read+settle | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| `services/opsatlas_sales/routes_sales_api.py` | 197 | `governance_verify` | GovernanceDesk.item (the route passes the door) | read+settle | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | None→409 |
| `services/opsatlas_sales/routes_sales_api.py` | 200 | `governance_verify` | GovernanceDesk.verify | read+settle | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| `services/opsatlas_sales/routes_sales_api.py` | 209 | `governance_propose` | GovernanceDesk.propose (reads _versions; writes the desk's answers) | read | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | ValueError/TypeError/KeyError→409, anything else→500 |
| `services/opsatlas_sales/routes_sales_api.py` | 215 | `product_ontology` | Knowledge.catalog | read+settle | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| `services/opsatlas_sales/routes_sales_api.py` | 220 | `spoken` | Knowledge.catalog | read+settle | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| `services/opsatlas_sales/routes_sales_api.py` | 226 | `spoken_draft` | Knowledge.add_spoken (catalog) | read+settle | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | ValueError→409 |
| `services/opsatlas_sales/routes_sales_api.py` | 240 | `propose` | Knowledge.propose → _in_step, _withdraw, register_upload, ingest_source | decision | family: first holder (product-guide, sales-playbook, system), else Product Guide | acting_person('service:workspace-key'): the signed-in person, else 'service:workspace-key' | ValueError/TypeError/KeyError→409, anything else→500 |
| `services/opsatlas_sales/routes_spaces.py` | 117 | `transfer` | rebuild_ontology (origin and target) | read+settle | the origin and target spaces | – | none caught (500 after the move) |
| `services/opsatlas_sales/spaces.py` | 394 | `move_document` | _move_content (raw sqlite on both content.db files) | move | origin → target | – | propagates |
| `services/opsatlas_sales/spaces.py` | 405 | `move_document` | _assets_in_use (origin register and content.db) | read+settle | the origin space | – | propagates |
| `services/opsatlas_sales/statement_governance.py` | 118 | `SalesStatementReview.run` | run_statement_review → StatementStore.sync | read+settle (background thread) | all three family spaces | – | the thread records 'failed' |
| `services/opsatlas_sales/tibi_api.py` | 125 | `records` | Knowledge.catalog | read+settle | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| `services/opsatlas_sales/tibi_api.py` | 130 | `review` | Knowledge.decide | decision | family: first holder (product-guide, sales-playbook, system), else Product Guide | acting_person('service:workspace-key'): the signed-in person, else 'service:workspace-key' | conflict(): ValueError/TypeError/KeyError→409, anything else→500 |
| `services/opsatlas_sales/tibi_api.py` | 134 | `resolve` | Knowledge.adjudicate → _in_step, _withdraw | decision | family: first holder (product-guide, sales-playbook, system), else Product Guide | acting_person('service:workspace-key'): the signed-in person, else 'service:workspace-key' | conflict(): ValueError/TypeError/KeyError→409, anything else→500 |
| `services/opsatlas_sales/tibi_api.py` | 149 | `review_spoken` | Knowledge.review_spoken (catalog) | read+settle | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | conflict(): ValueError/TypeError/KeyError→409, anything else→500 |
| `services/opsatlas_sales/tibi_api.py` | 153 | `product_ontology` | Knowledge.catalog | read+settle | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| `services/opsatlas_sales/tibi_api.py` | 173 | `governance_agenda` | GovernanceDesk.agenda | read+settle | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| `services/opsatlas_sales/tibi_api.py` | 183 | `governance_review` | GovernanceDesk.review → _close → Knowledge.settle, accept_issue | decision | family: first holder (product-guide, sales-playbook, system), else Product Guide | acting_person('service:workspace-key'): the signed-in person, else 'service:workspace-key' | conflict(): ValueError/TypeError/KeyError→409, anything else→500 |
| `services/opsatlas_sales/tibi_api.py` | 189 | `governance_statements` | GovernanceDesk.agenda | read+settle | family: first holder (product-guide, sales-playbook, system), else Product Guide | – | none caught: propagates (500 at a route) |
| `services/opsatlas_sales/tibi_api.py` | 196 | `governance_statements_run` | SalesStatementReview.start (background thread) | read+settle | all three family spaces | – | none caught: propagates (500 at a route) |

## 7. Tibi's engine (`services/sme_interviewer/`)

Tibi's engine never holds a document store in production. It reaches the documents only over HTTP, through the Sales
API, with its service credential (`x-sales-token`); no person is signed in on those calls, so every actor falls back
to `service:workspace-key`, and every call goes through the family view. Its own `store` objects (the interview
sessions, the conversation log, the ledger) are not document stores; the sweep's hits on them (`continuous.py`,
`interview.py`, `live.py`, `sales_preview.py`, `process_model.py`) were each read and set aside.

### The frozen benchmark fixture

`services/sme_interviewer/atlas_fixture.py` is a tool around the engine, outside its fingerprint (`engine.py:22-23`,
`TOOLS` lists `atlas_fixture`), unchanged since `e1067a1`. `concurrent_benchmark.py:50-60` starts it with uvicorn's
factory in a fresh `sme-atlas-benchmark-*` folder on port 8117; it refuses to run anywhere else (`:13-15`).

| Line | Call | Kind | Notes |
|---|---|---|---|
| 28 | `SourceRegister(directory / "data")` | wiring (imported class) | ungoverned when built (`governed_by` None) |
| 33 | `register.add(SourceRecord(…, processing_state="ingested", approval_status="approved", …), content)` | write: creation with an approval | an approved document with no decision (D13); before `create_app` governs the register; no `on_add` listener yet, so `ensure_all_versions` gives it its first version at start-up |
| 48 | `SectionStore(register.base_dir)` | wiring (imported class) | a second section store object on the same folder as `create_app`'s |
| 49 | `store.replace_for_source("synthetic-supplier", build_sections(…))` | write | passages with no fingerprint; `create_app`'s start-up `stamp_unfingerprinted` stamps them |
| 50 | `RetrievalService(register, store)` | wiring (injection) | retrieval keeps the fixture's own `store`, which `create_app` never governs (it governs its own `section_store`): this store's settles run under `if_free(None)`, with no lock |
| 57 | `create_app(register, AuthService("synthetic-benchmark"), retrieval, answer)` | wiring | a lone core over the fixture's register; the answer service is the fixture's `RagAnswer` |

What the fixture relies on (a duck-typed contract, frozen with it): `SourceRegister(path)`, `.add(record, content)`,
`.base_dir`; `SectionStore(path)`, `.replace_for_source(id, sections)` with `sha` optional; `RetrievalService(register,
section_store)`; `create_app(register, auth, retrieval, answer)` positionally; `SourceRecord`'s field names. Renaming
any of them breaks the benchmark without touching the engine's fingerprint.

### The engine's HTTP callers

| Engine module:line | Request | Sales route → what it does with the documents | Kind |
|---|---|---|---|
| `sales_preview.py:198` (from `/api/contributions/propose`, `:187`) | `POST /api/sales/proposals` | `Knowledge.propose`: withdraws an old revision (`reject_source` on its holder's engine), registers and ingests the claim and its interview account in the Product Guide, then the family layout moves them to the Sales Playbook, keeping their approval (pending, for a new claim) | decision (D6), write, move |
| `governance_interviewer.py:157` | `GET /api/sales/governance/agenda` | `GovernanceDesk.agenda`: the family's scan (reads, may settle) | read+settle |
| `governance_interviewer.py:208` | `POST /api/sales/governance/answers` | `GovernanceDesk.propose`: reads each source's version through the family register; writes the desk's answers file | read |
| `governance_interviewer.py:571` | `POST /api/sales/governance/verify` | `GovernanceDesk.verify`: reads the passages involved; the route passes the door (no lock) | read+settle |
| `tibi.py:361` | `GET /api/sales/knowledge`, `GET /api/sales/spoken` | `Knowledge.catalog` (every record's eligibility: family reads, plain `read_content`, may settle), spoken variants | read+settle |
| `tibi.py:369` | `POST /api/sales/search` | catalog and ranking; passes the door | read+settle |
| `tibi.py:377` | `GET /api/sales/digest` | catalog | read+settle |
| `tibi.py:1093`, `:1108` | `GET`, `POST /api/sales/spoken` | catalog; `Knowledge.add_spoken` writes a pending spoken variant (not a document store) | read+settle |

`x-tibi-conversation` narrows what a call may read (`routes_sales_api.readable`: the owner's family spaces, each
space's folder restrictions read from that core's content store), never where a call is routed. The engine never calls
Tibi's control-panel routes (`/api/tibi/…`), which need a person's sign-in. The replay, evaluation and benchmark tools
(`replay_latency.py`, `evaluate_*.py`, `benchmark*.py`) were not mapped beyond confirming they are tools.

**Test usage of the fixture:** none in `tests/` beyond the boundary rules' allow-list (`boundary_rules.py:171-187`).

## 8. What I could not determine, and why

1. **Live data.** Whether any document is held by two family spaces today, whether committed versions sit staged,
   which records are approved: the live workspace and `.runtime/` were off limits. The crash window in
   `move_document` (add in the target, then remove in the origin) can leave two copies; whether it has happened is
   unknown.
2. **Callers outside `src/` and `services/`.** Not mapped, only found by search: `scripts/import_packs.py` (calls
   `import_folder` with a register it builds itself: ungoverned, no lock, no content workflow, so no first-version
   listener until the next start-up), `scripts/data_reset.py` (deletes and restores the store files directly),
   `scripts/governance_statement_review.py`, `scripts/release_facts.py`, `scripts/export_process_maps.py`,
   `scripts/evaluate_grounding.py`, `scripts/evaluate_evidence.py`, `automation/evaluate.py` and
   `evaluation/evidence/audits/2026-09-27/content.py` (they construct stores or apps).
3. **The browser's choices.** Which page calls which route with which `X-OpsAtlas-Space` header is decided in
   `frontend/`, which I did not map; "own space, picked by the header" stops at the server.
4. **URLs built at run time.** The engine's HTTP callers were found by searching for `/api/` paths; a path composed
   elsewhere would be missed.
5. **Behaviour under contention.** The lock's behaviour for readers (`if_free`), the background threads holding no
   lock, and the settle paths are mapped by reading, plus one check that threads do not inherit context; no race was
   run.
6. **Third-party failures.** SQLite errors, pydantic validation of a malformed index row, and JSON errors from a damaged
   passages file are listed by reading; none was provoked.
7. **Whether the unguarded steps fail in practice.** `ContentService.decide`'s activity line, Transfer's activity line
   after the move, the proposals route's layout step, and a delete's later steps all answer 500 after a change was
   made; how often that happens is unknown.
8. **Test counts.** By AST, on receiver names (`register`, `section_store`, `content`, `content.store`, …): a call on a
   differently named receiver is missed and a same-named non-store could be counted. They are summary numbers, as
   asked; the production rows are not heuristic (each was read).
9. **Middleware order** was read from Starlette (`add_middleware` inserts at the front; the last added runs first) and
   confirmed in code, not by tracing a request; the Sales probe's results (each decision's audit entry in the expected
   space) are consistent with it.
