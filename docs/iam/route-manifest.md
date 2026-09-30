

| Method | Path | Kind | Permissions / note |
|---|---|---|---|
| POST | `/api/activity` | human | the caller records the events of their own page |
| GET | `/api/analytics/charts` | human | `analytics.read` |
| GET | `/api/analytics/explain` | human | `analytics.read` |
| GET | `/api/analytics/explain/{metric_id}` | human | `analytics.read` |
| GET | `/api/analytics/export` | human | `analytics.export`, `analytics.read` |
| GET | `/api/analytics/export/dictionary` | human | `analytics.export`, `analytics.read` |
| GET | `/api/analytics/export/reproducibility-pack` | human | `analytics.export`, `analytics.read` |
| GET | `/api/analytics/export/{dataset}` | human | `analytics.export`, `analytics.read` |
| GET | `/api/analytics/forecast/{series_id}` | human | `analytics.read` |
| GET | `/api/analytics/governance-history` | human | `analytics.read` |
| POST | `/api/analytics/governance-history/snapshot` | human | `analytics.improvements.manage` |
| GET | `/api/analytics/history` | human | `analytics.read` |
| GET | `/api/analytics/improvements` | human | `analytics.read` |
| POST | `/api/analytics/improvements` | human | `analytics.improvements.create` |
| GET | `/api/analytics/improvements/metrics` | human | `analytics.read` |
| POST | `/api/analytics/improvements/{action_id}/transition` | human | `analytics.improvements.manage` |
| GET | `/api/analytics/knowledge-gaps` | human | `analytics.raw.read`, `analytics.read` |
| GET | `/api/analytics/methods` | human | `analytics.read` |
| GET | `/api/analytics/oag-benchmark` | human | `analytics.read` |
| GET | `/api/analytics/oag-operations` | human | `analytics.read` |
| GET | `/api/analytics/ontology-stats` | human | `analytics.read` |
| GET | `/api/analytics/process-complexity` | human | `analytics.read` |
| GET | `/api/analytics/recurring-questions` | human | `analytics.raw.read`, `analytics.read` |
| GET | `/api/analytics/report.md` | human | `analytics.export`, `analytics.read` |
| GET | `/api/analytics/report.pdf` | human | `analytics.export`, `analytics.read` |
| GET | `/api/analytics/retrieval-health` | human | `analytics.read` |
| GET | `/api/analytics/scorecard` | human | `analytics.read` |
| GET | `/api/analytics/timeseries` | human | `analytics.read` |
| GET | `/api/analytics/timeseries/stats` | human | `analytics.read` |
| GET | `/api/analytics/validation-evidence` | human | `analytics.read` |
| POST | `/api/ask` | human | `knowledge.ask` |
| GET | `/api/auth/csrf` | public | pre-authentication CSRF token; no identity |
| POST | `/api/auth/invitations/accept` | public | one-use invitation link; the person chooses a password |
| POST | `/api/auth/invitations/preview` | public | what an invitation is for, without using it |
| POST | `/api/auth/login` | public | sign-in; throttled per account and per address |
| POST | `/api/auth/logout` | public | ends the session presented, if any; idempotent |
| POST | `/api/auth/logout-all` | human | `account.sessions.revoke_self` |
| GET | `/api/auth/me` | human | the caller's own account and capabilities |
| PATCH | `/api/auth/me` | human | `account.update_self` |
| POST | `/api/auth/password/change` | human | `account.password.change` |
| POST | `/api/auth/password/forgot` | public | the same answer for every address; nothing is sent without a mail channel |
| POST | `/api/auth/password/reset` | public | one-use reset link; all sessions end; sign in afresh |
| POST | `/api/auth/password/reset/preview` | public | what a reset link is for, without using it |
| POST | `/api/auth/reauthenticate` | human | verifies the caller's own password |
| GET | `/api/auth/sessions` | human | `account.sessions.read_self` |
| DELETE | `/api/auth/sessions/{session_id}` | human | `account.sessions.revoke_self` |
| GET | `/api/avatar/anam/config` | human | `avatar.use` |
| POST | `/api/avatar/anam/session-token` | human | `avatar.session.create`, `avatar.use` |
| POST | `/api/avatar/answer` | human | `avatar.use`, `knowledge.ask` |
| POST | `/api/content/assets` | human | `assets.upload` |
| GET | `/api/content/assets/{name}` | human | `assets.read` |
| DELETE | `/api/content/comments/{comment_id}` | human | `comments.moderate` |
| POST | `/api/content/comments/{comment_id}/reopen` | human | `comments.create` |
| POST | `/api/content/comments/{comment_id}/replies` | human | `comments.create` |
| POST | `/api/content/comments/{comment_id}/resolve` | human | `comments.create` |
| GET | `/api/content/documents` | human | `documents.read` |
| GET | `/api/content/documents/{source_id}` | human | `documents.read` |
| GET | `/api/content/documents/{source_id}/activity` | human | `documents.read` |
| POST | `/api/content/documents/{source_id}/approve` | human | `documents.approve`, `documents.publish` |
| GET | `/api/content/documents/{source_id}/comments` | human | `comments.read`, `documents.read` |
| POST | `/api/content/documents/{source_id}/comments` | human | `comments.create` |
| PATCH | `/api/content/documents/{source_id}/details` | human | `sources.metadata.update` |
| GET | `/api/content/documents/{source_id}/diff` | human | `documents.draft.read`, `documents.read` |
| DELETE | `/api/content/documents/{source_id}/draft` | human | `documents.edit` |
| PUT | `/api/content/documents/{source_id}/draft` | human | `documents.edit` |
| PUT | `/api/content/documents/{source_id}/parent` | human | `collections.move` |
| POST | `/api/content/documents/{source_id}/publish` | human | `documents.publish` |
| POST | `/api/content/documents/{source_id}/reject` | human | `documents.reject` |
| POST | `/api/content/documents/{source_id}/rename` | human | `sources.metadata.update` |
| POST | `/api/content/documents/{source_id}/return` | human | `documents.reject` |
| POST | `/api/content/documents/{source_id}/submit` | human | `documents.submit` |
| GET | `/api/content/documents/{source_id}/suggestions` | human | `documents.draft.read`, `documents.read` |
| POST | `/api/content/documents/{source_id}/suggestions/accept` | human | `documents.edit` |
| POST | `/api/content/documents/{source_id}/suggestions/settled/{settled_id}/reopen` | human | `documents.edit` |
| GET | `/api/content/documents/{source_id}/versions` | human | `documents.read`, `documents.versions.read` |
| GET | `/api/content/documents/{source_id}/versions/{n}` | human | `documents.read`, `documents.versions.read` |
| POST | `/api/content/documents/{source_id}/versions/{n}/restore` | human | `documents.versions.restore` |
| POST | `/api/content/groups` | human | `collections.create` |
| DELETE | `/api/content/groups/{group_id}` | human | `collections.delete` |
| PATCH | `/api/content/groups/{group_id}` | human | `collections.update` |
| GET | `/api/content/library` | human | `collections.read`, `documents.read` |
| POST | `/api/content/library/move` | human | `collections.move` |
| GET | `/api/conversations` | human | `conversations.read_all` |
| GET | `/api/conversations/flagged` | human | `conversations.read_all` |
| GET | `/api/conversations/{identifier}` | human | `conversations.read_all` |
| PUT | `/api/conversations/{identifier}/turns/{turn}/review` | human | `conversations.review` |
| GET | `/api/eam/model` | human | `eam.read` |
| GET | `/api/eam/svg` | human | `eam.read` |
| GET | `/api/eam/taxonomy` | human | `eam.read` |
| GET | `/api/external-sources` | human | `external_sources.read` |
| POST | `/api/external-sources/govuk/snapshot` | human | `external_sources.refresh` |
| GET | `/api/external-sources/snapshots` | human | `external_sources.read` |
| DELETE | `/api/external-sources/{source_id}` | human | `external_sources.delete` |
| GET | `/api/governance/intelligence` | human | `governance.read` |
| GET | `/api/governance/internal-review/latest` | human | `governance.read` |
| POST | `/api/governance/internal-review/reviews` | human | `governance.reviews.run` |
| GET | `/api/governance/internal-review/reviews/{job_id}` | human | `governance.read` |
| POST | `/api/governance/issues/accept` | human | `governance.exceptions.accept` |
| POST | `/api/governance/reanalysis` | human | `governance.scan.run` |
| GET | `/api/governance/reanalysis/latest` | human | `governance.read` |
| GET | `/api/governance/remediation/{a_id}/{b_id}` | human | `governance.read` |
| POST | `/api/governance/sources/{source_id}/approve` | human | `documents.approve` |
| GET | `/api/governance/sources/{source_id}/document` | human | `governance.read` |
| PUT | `/api/governance/sources/{source_id}/document` | human | `documents.edit` |
| POST | `/api/governance/sources/{source_id}/reject` | human | `documents.reject` |
| GET | `/api/health` | public | liveness only: no counts, no model details |
| GET | `/api/health/details` | human | `diagnostics.read` |
| GET | `/api/iam/access-requests` | human | own requests, or those the caller may decide |
| POST | `/api/iam/access-requests` | human | `iam.access.requests.create` |
| POST | `/api/iam/access-requests/{request_id}/cancel` | human | `iam.access.requests.cancel_own` |
| POST | `/api/iam/access-requests/{request_id}/decide` | human | iam.access.requests.decide at the request's scope; never one's own |
| POST | `/api/iam/access/explain` | human | iam.access.explain at the platform or in the space asked about |
| GET | `/api/iam/audit` | human | audit.read at the platform, or in the space filtered on |
| GET | `/api/iam/audit/verify` | human | `audit.read` |
| GET | `/api/iam/bindings` | human | iam.users.read at the platform, or spaces.members.read in the space asked for |
| POST | `/api/iam/bindings` | human | iam.roles.assign at the scope, within the caller's grant ceiling |
| DELETE | `/api/iam/bindings/{binding_id}` | human | iam.roles.assign at the grant's scope |
| GET | `/api/iam/capabilities/{user_id}` | human | `iam.users.read` |
| GET | `/api/iam/denies` | human | iam.access.deny.manage at the platform or in the space asked for |
| POST | `/api/iam/denies` | human | iam.access.deny.manage at the deny's scope |
| DELETE | `/api/iam/denies/{deny_id}` | human | iam.access.deny.manage at the deny's scope |
| GET | `/api/iam/grantable` | human | what the caller may give, at the platform or in a space |
| GET | `/api/iam/groups` | human | iam.groups.read at the platform or in the space asked for |
| POST | `/api/iam/groups` | human | iam.groups.create at the platform or in the space |
| DELETE | `/api/iam/groups/{group_id}` | human | iam.groups.delete at the group's boundary |
| POST | `/api/iam/groups/{group_id}/members` | human | iam.groups.members.manage; the group's roles must be within the caller's ceiling |
| DELETE | `/api/iam/groups/{group_id}/members/{user_id}` | human | iam.groups.members.manage at the group's boundary |
| GET | `/api/iam/permissions` | human | the registry is not secret: every signed-in person may read it |
| GET | `/api/iam/roles` | human | roles are readable by anyone who may give one; the list carries no secrets |
| POST | `/api/iam/roles` | human | `iam.roles.create` |
| DELETE | `/api/iam/roles/{role_id}` | human | `iam.roles.delete` |
| PATCH | `/api/iam/roles/{role_id}` | human | `iam.roles.update` |
| GET | `/api/iam/security/overview` | human | `audit.read` |
| GET | `/api/iam/sessions` | human | `iam.sessions.read` |
| DELETE | `/api/iam/sessions/{session_id}` | human | `iam.sessions.revoke` |
| GET | `/api/iam/settings` | human | `platform.settings.read` |
| PATCH | `/api/iam/settings` | human | `platform.settings.manage` |
| GET | `/api/iam/spaces/{space_id}/members` | human | spaces.members.read in that space, or iam.users.read |
| DELETE | `/api/iam/spaces/{space_id}/members/{user_id}` | human | spaces.members.manage in that space |
| POST | `/api/iam/spaces/{space_id}/solo-operator` | human | `platform.settings.manage` |
| GET | `/api/iam/users` | human | `iam.users.read` |
| POST | `/api/iam/users/invite` | human | iam.users.invite at the platform, or spaces.members.invite in the space |
| PATCH | `/api/iam/users/{user_id}` | human | `iam.users.update` |
| POST | `/api/iam/users/{user_id}/deactivate` | human | `iam.users.deactivate` |
| POST | `/api/iam/users/{user_id}/invitation/resend` | human | `iam.users.invite` |
| POST | `/api/iam/users/{user_id}/logout-all` | human | `iam.sessions.revoke` |
| POST | `/api/iam/users/{user_id}/reactivate` | human | `iam.users.reactivate` |
| POST | `/api/iam/users/{user_id}/recovery` | human | `iam.users.recovery.initiate` |
| GET | `/api/iam/users/{user_id}/sessions` | human | `iam.sessions.read` |
| POST | `/api/iam/users/{user_id}/suspend` | human | `iam.users.suspend` |
| GET | `/api/observability/traces` | human | `diagnostics.traces.read` |
| GET | `/api/ontology/actions` | human | `ontology.read` |
| GET | `/api/ontology/actions/log` | human | `ontology.read` |
| POST | `/api/ontology/actions/{api_name}` | human | `agent.actions.execute` |
| POST | `/api/ontology/agent/runs` | human | `agent.run` |
| GET | `/api/ontology/objects` | human | `ontology.read` |
| GET | `/api/ontology/objects/{object_id}` | human | `ontology.read` |
| GET | `/api/ontology/proposals` | human | `agent.proposals.read`, `ontology.read` |
| POST | `/api/ontology/proposals/{proposal_id}/approve` | human | `agent.proposals.approve` |
| POST | `/api/ontology/proposals/{proposal_id}/decline` | human | `agent.proposals.reject` |
| POST | `/api/ontology/rebuild` | human | `ontology.rebuild` |
| GET | `/api/ontology/schema` | human | `ontology.read` |
| GET | `/api/ontology/stats` | human | `ontology.read` |
| GET | `/api/ontology/traverse` | human | `ontology.read` |
| POST | `/api/process/captures` | human | `processes.capture.create` |
| GET | `/api/process/coverage-map` | human | `processes.read` |
| POST | `/api/process/diagrams/resolve` | human | `processes.diagrams.generate` |
| POST | `/api/process/diagrams/service/start` | human | `platform.services.restart` |
| GET | `/api/process/diagrams/service/status` | human | `processes.read` |
| GET | `/api/process/diagrams/{process_id}` | human | `processes.read` |
| GET | `/api/process/gap-overlap` | human | `processes.read` |
| POST | `/api/process/interview-map` | human | `processes.diagrams.generate` |
| GET | `/api/process/maps` | human | `processes.read` |
| GET | `/api/process/maps/{process_id}` | human | `processes.read` |
| GET | `/api/process/registry` | human | `processes.read` |
| GET | `/api/process/registry/{process_id}` | human | `processes.read` |
| POST | `/api/query` | human | `knowledge.search` |
| GET | `/api/regulatory/candidates` | human | `regulatory.read` |
| POST | `/api/regulatory/candidates/{candidate_id}/impact-simulation` | human | `regulatory.reviews.run` |
| POST | `/api/regulatory/candidates/{candidate_id}/review` | human | `regulatory.decisions.approve` |
| GET | `/api/sales/digest` | service | the workspace credential: Tibi's governance interviewer and the read-only product contract |
| GET | `/api/sales/governance/agenda` | service | the workspace credential: Tibi's governance interviewer and the read-only product contract |
| GET | `/api/sales/governance/answers` | service | the workspace credential: Tibi's governance interviewer and the read-only product contract |
| POST | `/api/sales/governance/answers` | service | the workspace credential: Tibi's governance interviewer and the read-only product contract |
| POST | `/api/sales/governance/answers/{identifier}/review` | service | the workspace credential: Tibi's governance interviewer and the read-only product contract |
| POST | `/api/sales/governance/verify` | service | the workspace credential: Tibi's governance interviewer and the read-only product contract |
| GET | `/api/sales/knowledge` | service | the workspace credential: Tibi's governance interviewer and the read-only product contract |
| POST | `/api/sales/knowledge/{identifier}/resolve` | service | the workspace credential: Tibi's governance interviewer and the read-only product contract |
| POST | `/api/sales/knowledge/{identifier}/review` | service | the workspace credential: Tibi's governance interviewer and the read-only product contract |
| GET | `/api/sales/ontology` | service | the workspace credential: Tibi's governance interviewer and the read-only product contract |
| POST | `/api/sales/proposals` | service | the workspace credential: Tibi's governance interviewer and the read-only product contract |
| POST | `/api/sales/search` | service | the workspace credential: Tibi's governance interviewer and the read-only product contract |
| GET | `/api/sales/source/{identifier}` | service | the workspace credential: Tibi's governance interviewer and the read-only product contract |
| GET | `/api/sales/spoken` | service | the workspace credential: Tibi's governance interviewer and the read-only product contract |
| POST | `/api/sales/spoken` | service | the workspace credential: Tibi's governance interviewer and the read-only product contract |
| POST | `/api/sales/spoken/{identifier}/review` | service | the workspace credential: Tibi's governance interviewer and the read-only product contract |
| POST | `/api/services/restart` | human | `platform.services.restart` |
| POST | `/api/services/start` | human | `platform.services.restart` |
| GET | `/api/sources` | human | `documents.read` |
| POST | `/api/sources/upload` | human | `sources.upload` |
| DELETE | `/api/sources/{source_id}` | human | `sources.delete` |
| POST | `/api/sources/{source_id}/ingest` | human | `sources.ingest` |
| GET | `/api/sources/{source_id}/sections` | human | `documents.draft.read` |
| GET | `/api/spaces` | human | the spaces the caller may read; archived ones for whoever may create spaces |
| POST | `/api/spaces` | human | `spaces.create` |
| POST | `/api/spaces/transfer` | human | documents.transfer in the origin and sources.upload in the target |
| PATCH | `/api/spaces/{space_id}` | human | spaces.update, spaces.archive or spaces.restore in that space |
| GET | `/api/tibi/governance/agenda` | human | `governance.read`, `tibi.use` |
| GET | `/api/tibi/governance/answers` | human | `governance.read`, `tibi.use` |
| POST | `/api/tibi/governance/answers/{identifier}/review` | human | `governance.findings.resolve` |
| GET | `/api/tibi/governance/statements` | human | `governance.read`, `tibi.use` |
| POST | `/api/tibi/governance/statements/run` | human | `governance.reviews.run` |
| GET | `/api/tibi/knowledge` | human | `tibi.knowledge.read`, `tibi.use` |
| POST | `/api/tibi/knowledge/{identifier}/resolve` | human | `tibi.knowledge.approve` |
| POST | `/api/tibi/knowledge/{identifier}/review` | human | `tibi.knowledge.approve` |
| GET | `/api/tibi/ontology` | human | `tibi.knowledge.read`, `tibi.use` |
| POST | `/api/tibi/ontology/{identifier}/confirm` | human | `tibi.knowledge.approve` |
| GET | `/api/tibi/sources/{identifier}` | human | `tibi.knowledge.read`, `tibi.use` |
| GET | `/api/tibi/spoken` | human | `tibi.knowledge.read`, `tibi.use` |
| POST | `/api/tibi/spoken/{identifier}/review` | human | `tibi.spoken.approve` |
| GET | `/api/tibi/status` | human | `tibi.use` |
| POST | `/api/tibi/ws-ticket` | human | `tibi.voice.use` |
| WEBSOCKET | `/services/tibi/api/conversation/{identifier}` | human | `tibi.voice.use` |
| DELETE | `/services/tibi/api/{path:path}` | human | `tibi.use` |
| GET | `/services/tibi/api/{path:path}` | human | `tibi.use` |
| POST | `/services/tibi/api/{path:path}` | human | `tibi.use` |
| PUT | `/services/tibi/api/{path:path}` | human | `tibi.use` |
| GET | `/{path:path}` | public | the control panel: its static files and page |
