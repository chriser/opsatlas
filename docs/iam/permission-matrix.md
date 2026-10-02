# Permission matrix (generated: python -m assistant.iam catalogue --markdown)

Every registered permission against every built-in role. ⚠ marks a permission the role editor shows as sensitive; the scope column lists where the permission is valid (P platform, S space, C collection, R resource, O own). (reserved) marks a permission registered ahead of the route that will check it: it guards nothing yet, a custom role cannot be given it, and the reason is in `src/assistant/iam/catalogue.py` (REF S5).

| Permission | Scopes | Platform administrator | Identity administrator | Product owner | Sales user | Space owner | Space reader | Space contributor | Space approver | Analyst | Auditor | External guest |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `account.read_self` (reserved) | O | ● |  |  |  |  |  |  |  |  |  |  |
| `account.update_self` | O | ● |  |  |  |  |  |  |  |  |  |  |
| `account.password.change` | O | ● |  |  |  |  |  |  |  |  |  |  |
| `account.sessions.read_self` | O | ● |  |  |  |  |  |  |  |  |  |  |
| `account.sessions.revoke_self` | O | ● |  |  |  |  |  |  |  |  |  |  |
| `iam.users.read` | P | ● | ● |  |  |  |  |  |  |  |  |  |
| `iam.users.invite` | P | ● | ● |  |  |  |  |  |  |  |  |  |
| `iam.users.update` | P | ● | ● |  |  |  |  |  |  |  |  |  |
| `iam.users.suspend` | P | ● | ● |  |  |  |  |  |  |  |  |  |
| `iam.users.reactivate` | P | ● | ● |  |  |  |  |  |  |  |  |  |
| `iam.users.recovery.initiate` ⚠ | P | ● | ● |  |  |  |  |  |  |  |  |  |
| `iam.users.deactivate` ⚠ | P | ● | ● |  |  |  |  |  |  |  |  |  |
| `iam.sessions.read` | P | ● | ● |  |  |  |  |  |  |  |  |  |
| `iam.sessions.revoke` | P | ● | ● |  |  |  |  |  |  |  |  |  |
| `iam.roles.read` | P/S | ● | ● |  |  | ● |  |  |  |  |  |  |
| `iam.roles.create` | P/S | ● | ● |  |  |  |  |  |  |  |  |  |
| `iam.roles.update` | P/S | ● | ● |  |  |  |  |  |  |  |  |  |
| `iam.roles.delete` | P/S | ● | ● |  |  |  |  |  |  |  |  |  |
| `iam.roles.assign` ⚠ | P/S | ● | ● |  |  | ● |  |  |  |  |  |  |
| `iam.groups.read` | P/S | ● | ● |  |  | ● |  |  |  |  |  |  |
| `iam.groups.create` | P/S | ● | ● |  |  | ● |  |  |  |  |  |  |
| `iam.groups.update` (reserved) | P/S | ● | ● |  |  | ● |  |  |  |  |  |  |
| `iam.groups.delete` | P/S | ● | ● |  |  | ● |  |  |  |  |  |  |
| `iam.groups.members.manage` | P/S | ● | ● |  |  | ● |  |  |  |  |  |  |
| `iam.access.explain` | P/S | ● | ● |  |  | ● |  |  |  |  | ● |  |
| `iam.access.review` (reserved) | P/S | ● | ● |  |  | ● |  |  |  |  | ● |  |
| `iam.access.requests.create` | O | ● |  |  |  |  |  |  |  |  |  |  |
| `iam.access.requests.read_own` (reserved) | O | ● |  |  |  |  |  |  |  |  |  |  |
| `iam.access.requests.cancel_own` | O | ● |  |  |  |  |  |  |  |  |  |  |
| `iam.access.requests.decide` | P/S | ● | ● |  |  | ● |  |  |  |  |  |  |
| `iam.access.deny.manage` ⚠ | P/S | ● | ● |  |  | ● |  |  |  |  |  |  |
| `iam.services.read` (reserved) | P/S | ● | ● |  |  |  |  |  |  |  |  |  |
| `iam.services.create` (reserved) | P/S | ● |  |  |  |  |  |  |  |  |  |  |
| `iam.services.update` (reserved) | P/S | ● |  |  |  |  |  |  |  |  |  |  |
| `iam.services.credentials.rotate` ⚠ (reserved) | P/S | ● |  |  |  |  |  |  |  |  |  |  |
| `iam.services.revoke` (reserved) | P/S | ● |  |  |  |  |  |  |  |  |  |  |
| `platform.settings.read` | P | ● | ● |  |  |  |  |  |  |  |  |  |
| `platform.settings.manage` ⚠ | P | ● |  |  |  |  |  |  |  |  |  |  |
| `platform.services.read` (reserved) | P | ● |  |  |  |  |  |  |  |  |  |  |
| `platform.services.restart` ⚠ | P | ● |  |  |  |  |  |  |  |  |  |  |
| `platform.models.manage` ⚠ (reserved) | P | ● |  |  |  |  |  |  |  |  |  |  |
| `platform.integrations.manage` ⚠ (reserved) | P | ● |  |  |  |  |  |  |  |  |  |  |
| `platform.secrets.rotate` ⚠ (reserved) | P | ● |  |  |  |  |  |  |  |  |  |  |
| `platform.backup.manage` ⚠ (reserved) | P | ● |  |  |  |  |  |  |  |  |  |  |
| `platform.restore.execute` ⚠ (reserved) | P | ● |  |  |  |  |  |  |  |  |  |  |
| `platform.cross_space.read` ⚠ (reserved) | P | ● |  |  |  |  |  |  |  |  |  |  |
| `platform.emergency.recover` ⚠ (reserved) | P | ● |  |  |  |  |  |  |  |  |  |  |
| `spaces.create` | P | ● | ● |  |  |  |  |  |  |  |  |  |
| `spaces.read` | S | ● |  | ● | ● | ● | ● | ● | ● | ● | ● | ● |
| `spaces.update` | S | ● |  |  |  | ● |  |  |  |  |  |  |
| `spaces.archive` | S | ● |  |  |  | ● |  |  |  |  |  |  |
| `spaces.restore` | S | ● |  |  |  | ● |  |  |  |  |  |  |
| `spaces.delete` ⚠ (reserved) | S | ● |  |  |  |  |  |  |  |  |  |  |
| `spaces.export` ⚠ (reserved) | S | ● |  |  |  | ● |  |  |  |  |  |  |
| `spaces.members.read` | S | ● |  |  |  | ● |  |  |  |  |  |  |
| `spaces.members.invite` | S | ● |  |  |  | ● |  |  |  |  |  |  |
| `spaces.members.manage` | S | ● |  |  |  | ● |  |  |  |  |  |  |
| `spaces.policy.manage` ⚠ (reserved) | S | ● |  |  |  | ● |  |  |  |  |  |  |
| `resources.permissions.read` (reserved) | S/C/R | ● |  |  |  | ● |  |  |  |  |  |  |
| `resources.permissions.manage` ⚠ (reserved) | S/C/R | ● |  |  |  | ● |  |  |  |  |  |  |
| `resources.classification.manage` (reserved) | S/C/R | ● |  |  |  | ● |  |  |  |  |  |  |
| `resources.ownership.transfer` (reserved) | S/C/R | ● |  |  |  | ● |  |  |  |  |  |  |
| `collections.read` | S/C | ● |  | ● | ● | ● | ● | ● | ● | ● |  | ● |
| `collections.create` | S/C | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `collections.update` | S/C | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `collections.move` | S/C | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `collections.delete` | S/C | ● |  |  |  | ● |  |  |  |  |  |  |
| `sources.register` (reserved) | S/C/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `sources.upload` | S/C/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `sources.metadata.update` | S/C/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `sources.ingest` | S/C/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `sources.reindex` (reserved) | S/C/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `sources.archive` (reserved) | S/C/R | ● |  |  |  | ● |  |  |  |  |  |  |
| `sources.restore` (reserved) | S/C/R | ● |  |  |  | ● |  |  |  |  |  |  |
| `sources.delete` ⚠ | S/C/R | ● |  |  |  | ● |  |  |  |  |  |  |
| `documents.read` | S/C/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  | ● |
| `documents.draft.read` | S/C/R | ● |  | ● |  | ● |  | ● | ● |  |  |  |
| `documents.create` (reserved) | S/C/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `documents.edit` | S/C/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `documents.submit` | S/C/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `documents.withdraw` (reserved) | S/C/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `documents.approve` | S/C/R | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `documents.reject` | S/C/R | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `documents.publish` | S/C/R | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `documents.versions.read` | S/C/R | ● |  | ● |  | ● |  | ● | ● |  |  |  |
| `documents.versions.restore` | S/C/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `documents.download` (reserved) | S/C/R | ● |  | ● |  | ● |  |  |  |  |  |  |
| `documents.transfer` ⚠ | S/C/R | ● |  |  |  | ● |  |  |  |  |  |  |
| `comments.read` | S/C/R/O | ● |  | ● | ● | ● | ● | ● | ● | ● |  | ● |
| `comments.create` | S/C/R/O | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `comments.update_own` (reserved) | O | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `comments.delete_own` (reserved) | O | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `comments.moderate` | S/C/R/O | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `assets.upload` | R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `assets.read` | R | ● |  | ● | ● | ● | ● | ● | ● | ● |  | ● |
| `assets.delete` (reserved) | R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `knowledge.search` | S/C/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  | ● |
| `knowledge.ask` | S/C/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  | ● |
| `knowledge.citations.read` (reserved) | S/C/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  | ● |
| `knowledge.retrieval_trace.read` ⚠ (reserved) | S/C/R | ● |  |  |  |  |  |  |  |  |  |  |
| `governance.read` | S/R | ● |  | ● |  | ● |  |  | ● |  | ● |  |
| `governance.scan.run` | S/R | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `governance.reviews.run` | S/R | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `governance.findings.resolve` | S/R | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `governance.exceptions.accept` | S/R | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `governance.self_approve` ⚠ | S/R | ● |  |  |  |  |  |  |  |  |  |  |
| `external_sources.read` | S/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `external_sources.register` (reserved) | S/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `external_sources.refresh` | S/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `external_sources.delete` | S/R | ● |  |  |  | ● |  |  |  |  |  |  |
| `regulatory.read` | S/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `regulatory.reviews.run` | S/R | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `regulatory.decisions.approve` | S/R | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `processes.read` | S/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `processes.diagrams.generate` | S/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `processes.capture.create` | S/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `processes.edit` (reserved) | S/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `processes.export` (reserved) | S/R | ● |  |  |  | ● |  |  |  | ● |  |  |
| `eam.read` | S/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `eam.export` (reserved) | S/R | ● |  |  |  | ● |  |  |  | ● |  |  |
| `ontology.read` | S/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `ontology.query` (reserved) | S/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `ontology.edit` (reserved) | S/R | ● |  | ● |  | ● |  |  |  |  |  |  |
| `ontology.rebuild` | S/R | ● |  | ● |  | ● |  |  |  |  |  |  |
| `ontology.export` (reserved) | S/R | ● |  |  |  | ● |  |  |  |  |  |  |
| `agent.run` | S/R | ● |  |  |  | ● |  |  |  |  |  |  |
| `agent.proposals.read` | S/R | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `agent.proposals.approve` | S/R | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `agent.proposals.reject` | S/R | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `agent.actions.execute` ⚠ | S/R | ● |  |  |  | ● |  |  |  |  |  |  |
| `analytics.read` | S/R | ● |  | ● | ● | ● | ● | ● | ● | ● | ● |  |
| `analytics.raw.read` ⚠ | S/R | ● |  |  |  |  |  |  |  |  |  |  |
| `analytics.export` | S/R | ● |  |  |  | ● |  |  |  | ● |  |  |
| `analytics.improvements.create` | S/R | ● |  |  |  | ● |  |  |  | ● |  |  |
| `analytics.improvements.manage` | S/R | ● |  |  |  | ● |  |  |  | ● |  |  |
| `tibi.use` | S/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `tibi.voice.use` | S/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `tibi.rehearsal.use` | S/R | ● |  | ● | ● |  |  |  |  |  |  |  |
| `tibi.knowledge.read` | S/R | ● |  | ● |  |  |  |  |  |  |  |  |
| `tibi.knowledge.edit` (reserved) | S/R | ● |  | ● |  |  |  |  |  |  |  |  |
| `tibi.knowledge.approve` | S/R | ● |  | ● |  |  |  |  |  |  |  |  |
| `tibi.spoken.edit` | S/R | ● |  | ● |  |  |  |  |  |  |  |  |
| `tibi.spoken.approve` | S/R | ● |  | ● |  |  |  |  |  |  |  |  |
| `tibi.persona.manage` ⚠ (reserved) | P | ● |  |  |  |  |  |  |  |  |  |  |
| `avatar.use` | S | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `avatar.session.create` | S | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `conversations.read_own` (reserved) | O | ● |  | ● | ● | ● | ● | ● | ● | ● |  | ● |
| `conversations.delete_own` (reserved) | O | ● |  | ● | ● | ● | ● | ● | ● | ● |  | ● |
| `conversations.read_all` ⚠ | S | ● |  |  |  |  |  |  |  |  |  |  |
| `conversations.review` | S | ● |  |  |  | ● |  |  |  |  |  |  |
| `conversations.export` ⚠ (reserved) | S | ● |  |  |  |  |  |  |  |  |  |  |
| `conversations.delete_all` ⚠ (reserved) | S | ● |  |  |  |  |  |  |  |  |  |  |
| `jobs.read_own` (reserved) | O | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `jobs.cancel_own` (reserved) | O | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `jobs.read_all` (reserved) | S | ● |  |  |  | ● |  |  |  |  |  |  |
| `jobs.cancel_all` (reserved) | S | ● |  |  |  | ● |  |  |  |  |  |  |
| `exports.create` (reserved) | S/R/O | ● |  |  |  | ● |  |  |  | ● |  |  |
| `exports.download` (reserved) | S/R/O | ● |  |  |  | ● |  |  |  | ● |  |  |
| `exports.revoke` (reserved) | S/R/O | ● |  |  |  | ● |  |  |  |  |  |  |
| `audit.read` | P/S | ● | ● |  |  | ● |  |  |  |  | ● |  |
| `audit.export` ⚠ (reserved) | P/S | ● |  |  |  |  |  |  |  |  |  |  |
| `diagnostics.read` | P/S | ● |  |  |  | ● |  |  |  |  |  |  |
| `diagnostics.traces.read` ⚠ | P/S | ● |  |  |  |  |  |  |  |  |  |  |
