# Identity and access management (IAM E1)

**Built:** overnight, 29–30 September 2026, on `claude/iam`. **Status:** the first release of personal sign-in and
authorisation for OpsAtlas Sales, ready to go live on the local deployment. **Scope:** the IAM development
specification prepared on 30 September 2026 (a Codex document kept outside the repository), reviewed section by
section below. **Not in this release:** any second factor. Sign-in is single-factor; no assurance level is claimed.

This guide is the review of that specification against what was built, the model as it works, the runbook for the
person operating it, and the honest list of what was left for later and why.

Companion files: [permission-matrix.md](permission-matrix.md) (every permission against every built-in role,
generated), [route-manifest.md](route-manifest.md) (every route and how it is guarded, generated).

## 1. What the specification asked for, and what happened to it

The specification is sound, and unusually careful about what it does *not* claim. Everything below was checked
against the code before the work started (its observations in section 2 were all true of `06f57ba`: one shared
password, tokens without expiry, `kp_token` in local storage, a space header as the only selector, images served
without a session, a shared `Operator` from the environment, the Tibi socket taking the sign-in token in its
hello, a public health route with counts and models). The work went in the specification's own dependency order:
IAM-01 to IAM-04 first, then the routes (IAM-05), the Tibi gateway (IAM-06) and the administration screens (IAM-07).

| Specification | Implemented | Deviation or gap |
|---|---|---|
| §3 identity, tenancy and resource model | A deployment-wide `iam.db`; users with opaque ids; memberships per space; one organisation space is one tenant; the Product Guide entitlement is an explicit built-in binding (`space_reader` in `product-guide`) made when an account is activated; Sales Playbook and System settings are not implied by anything | Resource policies (restricted audiences) are set, changed and lifted through IAM's restriction route, which the "Who can read" card uses for documents (REF S13), only from the space that holds the document or folder: the row follows its holder, another space is refused (404), an archived space holds nothing, and a deleted resource's restriction can be lifted by its own space (Bug #2202); classification is stored, not enforced |
| §3.3 platform administrator | Explicit bindings: the role at the platform and, transactionally, in every space (existing spaces at bootstrap, new spaces when registered). No `if admin` in the evaluator | The *All organisations* view is still the knowledge-spaces phase-3 item; the permission `platform.cross_space.read` exists for it |
| §3.4 isolation invariants | The space core evaluates every request at its own space; an unknown or inaccessible space answers 404 with no name; no fallback to the Product Guide except where a request names no space (documented) | Conversations, jobs and caches are not yet bound to a principal (see §5) |
| §4 authorisation semantics | The decision order as written: active principal → active space → exact permission from a current binding at the applicable scope → no explicit deny → ownership for *own* permissions → restricted audience. Platform bindings never grant space permissions, nor the reverse. Hidden denials answer 404, visible ones 403 | Inheritance below a space (collection and resource grants) is modelled (`scope_type` collection/resource) but the routes pass no resource references yet, so only space grants take effect |
| §4.3 delegated administration | Grant ceilings from the role seeds (a space owner gives the six space roles and another owner; an identity administrator everything but platform administrator); no self-grant; protected roles need a fresh password; the last active platform administrator and the last active space owner cannot be removed, suspended or demoted; group membership is checked against the actor's ceiling | Bulk changes are not offered |
| §4.4 workflow authority | Approving a document needs both `documents.approve` and `documents.publish` (the route requires both). Since REF S15 (2 October 2026) a draft records its author's stable id, and publishing one's own draft is refused unless the space is in solo-operator mode and the person holds `governance.self_approve`; each such approval is noted on the document's activity. Solo-operator mode is a per-space setting, changed with a fresh password and recorded: the spaces that existed on 2 October were switched on once (the Human's decision), and a space registered while only one person uses the installation starts on | Comments, Tibi Knowledge reviews and governance answers do not compare author and approver yet (their contributors are not yet people: REF S14) |
| §5 permission catalogue | 163 permissions in 31 namespaces (catalogue version 3), exact keys, valid scopes per action, generated frontend copy, generated matrix, no wildcards; an unregistered key is denied. Version 2 (30 September 2026) retired four with the parked features. Version 3 (2 October 2026, REF S5) marks 58 as *reserved*: registered ahead of the routes that will check them, they guard nothing yet, each names why and the backlog item that will use it, the built-in roles keep them, and a custom role cannot be given one. A test fails if a permission that is not reserved guards nothing | Reserved permissions come into use with their items (REF E1) |
| §6 built-in roles | All eleven human roles as seeds (version 2) with what each leaves out (the external guest reads a whole organisation until grants on named documents are enforced, REF S13); `signed_in_user` as the system baseline; custom roles from the catalogue, versioned on every edit | Services are principals, not roles: Tibi's voice service holds exactly its route permissions (REF S12, §5 item 2) |
| §7.1 account lifecycle | Bootstrap from the host with a one-time invitation; invitations with a concrete role, space, expiry and message; acceptance sets the password; suspend, reactivate, deactivate (offboarding revokes every grant, membership, invitation and session; attribution stays); administrator-initiated recovery; the host recovery procedure | Change of email: by an administrator only, recorded; no address verification (there is no mail channel). Team moves with an access preview: not built |
| §7.2 passwords | argon2id at m=64 MiB, t=3, p=1, parameters stored with the hash, rehash on login when they change; 15–128 code points, NFC, spaces and Unicode, no composition rules, no rotation; common, repeated, sequential and context passwords (name, login, product) refused; a dummy verification for unknown accounts | The breached-password list is a small bundled list, not a maintained corpus |
| §7.3 tokens | 256-bit secrets, only digests stored, one use under concurrency (the consuming update must change one row), 72 h invitations, 30 min resets, resending revokes the previous token, links built from the configured origin, consumed by POST, previewed by POST (never a query string) | No mail adapter: the administrator shows the link once and hands it over, and that display is recorded |
| §7.4 abuse protection | Five failures per account in 15 minutes then growing delays capped at 15 minutes, counted alike for unknown accounts; 100 per address; recovery links limited per account per hour; counters in the store, surviving restarts; a `Retry-After`; no permanent lockout | Forwarding headers are not trusted at all (loopback only) |
| §7.5 emergency recovery | `python -m assistant.iam recover --login … --reason …` on the host: a 30-minute one-use reset link, the account's sessions ended, a durable recovery event shown to administrators afterwards. The workspace key no longer signs anyone in | The key is now Tibi's own service-principal credential (`x-sales-token`, REF S12); it signs no one in |
| §8 sessions | Opaque server-side sessions, digest only; cookie `opsatlas_session` HttpOnly SameSite=Lax Path=/ (the `__Host-` name and Secure on an HTTPS profile); 12 h / 30 min ordinary, 8 h / 15 min for administrators, both settings; rotation at sign-in and password change; revocation on the next request; polls do not extend a session, a request within a minute of a click or key press does; an expiry warning with a deliberate "stay signed in" | The bearer token an API client receives at sign-in is the same secret the cookie carries; it is never returned to a browser |
| §8.2 CSRF and origin | A session-bound token in `X-CSRF-Token` on every cookie-borne change, a pre-authentication token at sign-in, the workspace's existing origin check | CSP and a sanitiser review were not part of this release |
| §9.1 AI evidence enforcement | Every retrieval route needs `knowledge.search` or `knowledge.ask` in the space whose core answers; a core only holds its own partition | Field-level projection of family records for non-owners, evidence lineage on answers and recheck at delivery: not built (§5) |
| §9.2 Tibi gateway | The HTTP gateway needs `tibi.use`; the socket hello carries a 30-second one-use ticket bound to the session and the conversation (`POST /api/tibi/ws-ticket`, `tibi.voice.use`); the socket closes within five seconds of the session ending | Per-message authorisation and a path allowlist inside the gateway are not built; Tibi's own session token still applies |
| §9.3 service principals, §9.4 jobs and exports | Built-in service principals with one service permission per route, listed on Security & Audit; conversations, interview contributions and review jobs owned by a person (REF S12, S14) | Service accounts made through the API, key rotation by API, deleting one's own conversation (needs a Tibi route), organisation exports (§5) |
| §10 requests, reviews, audit | Access requests decided by someone else, approvals as ordinary grants with an expiry; the audit with the required fields, redaction, log-injection sanitising, hash chaining and a verification command; a security overview (refusals, throttles, recovery events) | Access reviews with due dates: not built; the audit is local and not exported |
| §11 user experience | Sign-in, invitation and reset screens; My Account, with a picture (IAM F10: cropped in the browser to a square with rounded corners, kept in `iam.db` as a 256-pixel JPEG decoded and saved again by the server, shown to its owner only, in the sidebar under the logo; `GET/POST/DELETE /api/auth/me/picture`, `account.update_self`); People, Roles, Access (grants, groups, denies, requests, explain), Security & Audit; navigation follows capabilities; 401 clears state, 403 explains; keyboard-reachable forms with labels | The effective-access viewer explains one decision at a time; no permission-preview mode; pictures are not yet shown to other people (People, comments) |
| §12 architecture | `assistant.iam` with the modules named; `AuthorizationContext`; explicit allowlisted request bodies; a single-host SQLite store with WAL and one lock | Alembic was not adopted: the schema is created idempotently and versioned in `schema_version` |
| §13 API contract | The routes as listed, with `{detail, code, request_id}` on the new errors; the route manifest with a test that fails on an unclassified route, mount or socket | ETags and idempotency keys: not built |
| §14 migration | Bootstrap of one named administrator; historic actions keep their name snapshots; the key retired from sign-in; one cut-over (cookie sessions, policies and the new panel together); `kp_token` removed from local storage on load | Rehearsed on a throwaway workspace with headless Chrome, not on a copy of the live one |
| §16 acceptance | AT-01, 02, 03, 04, 05, 06, 07, 08 (a reader forging the space selector gets 404 without the name), 09, 10, 11, 12 (last owner and administrator), 13 (denies), 15 (images guarded, but by the document's space only), 18 (tickets), 21 (socket: foreign origin, replayed ticket, wrong conversation, old token all refused), 29 (chain), 31 (offboarding), 34 (navigation), 35 (manifest) covered by tests | 14, 16, 17, 19, 20, 22–28, 30, 32, 33, 36 not covered: they belong to the deferred items |

## 2. The model, as it works

- **Principal.** A person with an opaque id; email is the login (matched case-insensitively, kept as typed). States:
  invited → active ⇄ suspended → deactivated. A deactivated account keeps its name on everything it did.
- **Scope.** The platform, or one space. Every space core evaluates at its own space; the workspace app evaluates at
  the Product Guide; platform routes say so.
- **Grant.** A role bound to a person or a group at a scope, with an optional end. A space grant creates the
  membership. Entitlements that follow the account (`signed_in_user` at the platform, `space_reader` in the Product
  Guide) are system bindings: they end with the account, not by revocation.
- **Decision.** Allowed when the account is active, the space is active (an archived space allows only `spaces.restore`),
  a current grant at that scope carries the exact permission, no explicit deny matches, an *own* permission is used on
  the caller's own thing, and any restricted resource names the caller. Everything else is denied; a denial that
  would reveal a hidden space or resource answers 404.
- **Session.** A cookie the browser never reads, or a bearer secret an API client holds. Idle and absolute expiry are
  checked on every request against the clock; the credential epoch on the account ends every session when the
  password changes; a change of grants bumps the policy version recorded on each audit event.
- **Audit.** Identity and access events only, hash-chained, redacted, never document text. `python -m assistant.iam
  verify-audit` checks the chain; so does the Security page.

## 3. Runbook

**First set-up (once, on the host):**

```bash
.venv/bin/python -m assistant.iam bootstrap --root .runtime/opsatlas-sales --email chriser@ymail.com --name "Kris Pochopien"
```

It prints a one-time invitation link, valid 72 hours, and keeps nothing. Opening it asks for a name and a password of
at least 15 characters (a sentence works; not the product's name, not the login); then sign in with the email
address and that password. The account holds every platform permission and every space permission in every space,
present and future. Set-up is refused once an administrator is active.

**Everyday administration** is in the panel under *Identity & Access*: invite (the link is shown once), give and
revoke roles, groups, denies, requests, sessions, settings, solo-operator mode, the audit trail. A change that raises
someone's standing, deactivates an account or issues a recovery link asks for the password again (within the
fresh-password window, five minutes by default).

**Lost password:** an administrator issues a recovery link from *People* (shown once, 30 minutes). If no
administrator can sign in:

```bash
.venv/bin/python -m assistant.iam recover --root .runtime/opsatlas-sales --login chriser@ymail.com --reason "lost the password"
```

**Status and the chain:** `python -m assistant.iam status --root …` and `… verify-audit --root …`.

**Settings** (Security & Audit → Settings; the working defaults): idle 30 min, lifetime 12 h (administrators 15 min /
8 h), fresh-password window 5 min, five failed attempts per account per 15 min then delays capped at 15 min, 100 per
address, three recovery links per account per hour, invitations 72 h, resets 30 min, voice tickets 30 s, guest access
30 days, elevated access 7 days.

**Going live:** the code, the rebuilt panel and the bootstrap; then restart the core (the voice and diagram
services are untouched). The workspace key in `local-access.key` stays for the sidecars; it signs no one in.

**Development and tests:** `AuthService(password)` is the single-operator legacy mode (an in-memory store, one
administrator called operator, a login body of just the password) used by the test suite and the generic
development core. The secured mode is `AuthService.from_workspace(root)`; the Sales workspace only ever uses that.

## 4. Assurance statement

Single-factor sign-in. No second factor, no phishing resistance, no AAL claim. Not a claim of OWASP ASVS Level 2:
the requirements met are those listed in section 1; the exceptions are the gaps in the same table and section 5.
The audit chain detects alteration but does not withstand the host administrator, who controls the store. The
deployment is loopback HTTP; the HTTPS cookie profile exists (`__Host-`, Secure) and must be used on any network
listener. Real client data remains behind the gates already agreed for the knowledge spaces; nothing here changes
them.

## 5. Deferred, in the order they should come

1. **Author-versus-approver by stable id** (§4.4): done for publishing a document (REF S15, 2 October 2026); still to do for
   Tibi Knowledge reviews and governance answers, whose contributors become people with REF S14.
2. **Service principals** (§9.3): built in for Tibi's voice service (REF S12, 2 October 2026): its own credential,
   one service permission per route, every call recorded as Tibi acting for the conversation's owner. The diagram
   service needs none (it is called, never calls, holds nothing; OpsAtlas Classic shares it). Still to do: service
   accounts made through the API, key rotation by API, and a short-lived per-person token for Tibi in place of the
   conversation binding (the Human accepted the binding for now, 2 October 2026; REF S10).
3. **Conversations, jobs and exports bound to a principal** (§9.4, §5): done for the conversation log (read and export
   one's own), interview contributions, process-interview deletion and governance review jobs (REF S14). Still to do:
   deleting one's own conversation everywhere (needs a Tibi route, so a new engine version), cancelling a job, and
   exports as private jobs with a manifest (REF S31).
4. **Family projection** (§3.2, §9.1): done (REF S11): Tibi answers each person from the family spaces they may read,
   without documents restricted from them. Evidence lineage on answers and a recheck at delivery remain (REF S18).
5. **Collection and resource grants in the routes, restricted audiences in a screen** (§4.2), with the move preview.
6. **Access reviews** with due dates and the sole-owner escalation (§10.1); a mail adapter for invitations and resets
   (§7.3); an audit export to a separately controlled destination (§10.2).
7. **All organisations** mode for the administrator (§3.3), together with the knowledge-spaces phase 3.
8. OIDC/SAML, SCIM and passkeys stay out of scope, as the specification says.

## 6. Evidence

- Tests: `tests/test_iam_catalogue_roles.py`, `tests/test_iam_policy.py` (table-driven, controlled clock),
  `tests/test_iam_manifest.py`, `tests/test_iam_auth.py` (the HTTP lifecycle), `tests/test_sales_iam.py` (the secured
  workspace: key not a sign-in, space forgery, owner ceilings, tickets, audit), `tests/test_sales_tibi_proxy.py` (the
  socket), and the existing suite green under the new sessions.
- The panel was driven in headless Chrome on a throwaway workspace: invitation landing, account creation, sign-in,
  every IAM page, an invitation with its one-time link, the audit trail; no console errors.
