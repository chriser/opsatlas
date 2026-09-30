# Permission matrix (generated: python -m assistant.iam catalogue --markdown)

Every registered permission against every built-in role. ⚠ marks a permission the role editor shows as sensitive; the scope column lists where the permission is valid (P platform, S space, C collection, R resource, O own).

| Permission | Scopes | Platform administrator | Identity administrator | Product owner | Sales user | Space owner | Space reader | Space contributor | Space approver | Analyst | Auditor | External guest |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `account.read_self` | O | ● |  |  |  |  |  |  |  |  |  |  |
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
| `iam.groups.update` | P/S | ● | ● |  |  | ● |  |  |  |  |  |  |
| `iam.groups.delete` | P/S | ● | ● |  |  | ● |  |  |  |  |  |  |
| `iam.groups.members.manage` | P/S | ● | ● |  |  | ● |  |  |  |  |  |  |
| `iam.access.explain` | P/S | ● | ● |  |  | ● |  |  |  |  | ● |  |
| `iam.access.review` | P/S | ● | ● |  |  | ● |  |  |  |  | ● |  |
| `iam.access.requests.create` | O | ● |  |  |  |  |  |  |  |  |  |  |
| `iam.access.requests.read_own` | O | ● |  |  |  |  |  |  |  |  |  |  |
| `iam.access.requests.cancel_own` | O | ● |  |  |  |  |  |  |  |  |  |  |
| `iam.access.requests.decide` | P/S | ● | ● |  |  | ● |  |  |  |  |  |  |
| `iam.access.deny.manage` ⚠ | P/S | ● | ● |  |  | ● |  |  |  |  |  |  |
| `iam.services.read` | P/S | ● | ● |  |  |  |  |  |  |  |  |  |
| `iam.services.create` | P/S | ● |  |  |  |  |  |  |  |  |  |  |
| `iam.services.update` | P/S | ● |  |  |  |  |  |  |  |  |  |  |
| `iam.services.credentials.rotate` ⚠ | P/S | ● |  |  |  |  |  |  |  |  |  |  |
| `iam.services.revoke` | P/S | ● |  |  |  |  |  |  |  |  |  |  |
| `platform.settings.read` | P | ● | ● |  |  |  |  |  |  |  |  |  |
| `platform.settings.manage` ⚠ | P | ● |  |  |  |  |  |  |  |  |  |  |
| `platform.services.read` | P | ● |  |  |  |  |  |  |  |  |  |  |
| `platform.services.restart` ⚠ | P | ● |  |  |  |  |  |  |  |  |  |  |
| `platform.models.manage` ⚠ | P | ● |  |  |  |  |  |  |  |  |  |  |
| `platform.integrations.manage` ⚠ | P | ● |  |  |  |  |  |  |  |  |  |  |
| `platform.secrets.rotate` ⚠ | P | ● |  |  |  |  |  |  |  |  |  |  |
| `platform.backup.manage` ⚠ | P | ● |  |  |  |  |  |  |  |  |  |  |
| `platform.restore.execute` ⚠ | P | ● |  |  |  |  |  |  |  |  |  |  |
| `platform.cross_space.read` ⚠ | P | ● |  |  |  |  |  |  |  |  |  |  |
| `platform.emergency.recover` ⚠ | P | ● |  |  |  |  |  |  |  |  |  |  |
| `spaces.create` | P | ● | ● |  |  |  |  |  |  |  |  |  |
| `spaces.read` | S | ● |  | ● | ● | ● | ● | ● | ● | ● | ● | ● |
| `spaces.update` | S | ● |  |  |  | ● |  |  |  |  |  |  |
| `spaces.archive` | S | ● |  |  |  | ● |  |  |  |  |  |  |
| `spaces.restore` | S | ● |  |  |  | ● |  |  |  |  |  |  |
| `spaces.delete` ⚠ | S | ● |  |  |  |  |  |  |  |  |  |  |
| `spaces.export` ⚠ | S | ● |  |  |  | ● |  |  |  |  |  |  |
| `spaces.members.read` | S | ● |  |  |  | ● |  |  |  |  |  |  |
| `spaces.members.invite` | S | ● |  |  |  | ● |  |  |  |  |  |  |
| `spaces.members.manage` | S | ● |  |  |  | ● |  |  |  |  |  |  |
| `spaces.policy.manage` ⚠ | S | ● |  |  |  | ● |  |  |  |  |  |  |
| `resources.permissions.read` | S/C/R | ● |  |  |  | ● |  |  |  |  |  |  |
| `resources.permissions.manage` ⚠ | S/C/R | ● |  |  |  | ● |  |  |  |  |  |  |
| `resources.classification.manage` | S/C/R | ● |  |  |  | ● |  |  |  |  |  |  |
| `resources.ownership.transfer` | S/C/R | ● |  |  |  | ● |  |  |  |  |  |  |
| `collections.read` | S/C | ● |  | ● | ● | ● | ● | ● | ● | ● |  | ● |
| `collections.create` | S/C | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `collections.update` | S/C | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `collections.move` | S/C | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `collections.delete` | S/C | ● |  |  |  | ● |  |  |  |  |  |  |
| `sources.register` | S/C/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `sources.upload` | S/C/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `sources.metadata.update` | S/C/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `sources.ingest` | S/C/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `sources.reindex` | S/C/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `sources.archive` | S/C/R | ● |  |  |  | ● |  |  |  |  |  |  |
| `sources.restore` | S/C/R | ● |  |  |  | ● |  |  |  |  |  |  |
| `sources.delete` ⚠ | S/C/R | ● |  |  |  | ● |  |  |  |  |  |  |
| `documents.read` | S/C/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  | ● |
| `documents.draft.read` | S/C/R | ● |  | ● |  | ● |  | ● | ● |  |  |  |
| `documents.create` | S/C/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `documents.edit` | S/C/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `documents.submit` | S/C/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `documents.withdraw` | S/C/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `documents.approve` | S/C/R | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `documents.reject` | S/C/R | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `documents.publish` | S/C/R | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `documents.versions.read` | S/C/R | ● |  | ● |  | ● |  | ● | ● |  |  |  |
| `documents.versions.restore` | S/C/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `documents.download` | S/C/R | ● |  | ● |  | ● |  |  |  |  |  |  |
| `documents.transfer` ⚠ | S/C/R | ● |  |  |  | ● |  |  |  |  |  |  |
| `comments.read` | S/C/R/O | ● |  | ● | ● | ● | ● | ● | ● | ● |  | ● |
| `comments.create` | S/C/R/O | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `comments.update_own` | O | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `comments.delete_own` | O | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `comments.moderate` | S/C/R/O | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `assets.upload` | R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `assets.read` | R | ● |  | ● | ● | ● | ● | ● | ● | ● |  | ● |
| `assets.delete` | R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `knowledge.search` | S/C/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  | ● |
| `knowledge.ask` | S/C/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  | ● |
| `knowledge.citations.read` | S/C/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  | ● |
| `knowledge.retrieval_trace.read` ⚠ | S/C/R | ● |  |  |  |  |  |  |  |  |  |  |
| `governance.read` | S/R | ● |  | ● |  | ● |  |  | ● |  | ● |  |
| `governance.scan.run` | S/R | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `governance.reviews.run` | S/R | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `governance.reviews.cancel` | S/R | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `governance.findings.resolve` | S/R | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `governance.exceptions.accept` | S/R | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `governance.self_approve` ⚠ | S/R | ● |  |  |  |  |  |  |  |  |  |  |
| `external_sources.read` | S/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `external_sources.register` | S/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `external_sources.refresh` | S/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `external_sources.delete` | S/R | ● |  |  |  | ● |  |  |  |  |  |  |
| `regulatory.read` | S/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `regulatory.reviews.run` | S/R | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `regulatory.decisions.approve` | S/R | ● |  | ● |  | ● |  |  | ● |  |  |  |
| `processes.read` | S/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `processes.diagrams.generate` | S/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `processes.capture.create` | S/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `processes.edit` | S/R | ● |  | ● |  | ● |  | ● |  |  |  |  |
| `processes.export` | S/R | ● |  |  |  | ● |  |  |  | ● |  |  |
| `processes.stress.run` | S/R | ● |  |  |  | ● |  |  |  |  |  |  |
| `eam.read` | S/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `eam.export` | S/R | ● |  |  |  | ● |  |  |  | ● |  |  |
| `ontology.read` | S/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `ontology.query` | S/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `ontology.edit` | S/R | ● |  | ● |  | ● |  |  |  |  |  |  |
| `ontology.rebuild` | S/R | ● |  | ● |  | ● |  |  |  |  |  |  |
| `ontology.export` | S/R | ● |  |  |  | ● |  |  |  |  |  |  |
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
| `analytics.value.manage` | S/R | ● |  |  |  | ● |  |  |  | ● |  |  |
| `tibi.use` | S/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `tibi.voice.use` | S/R | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `tibi.rehearsal.use` | S/R | ● |  | ● | ● |  |  |  |  |  |  |  |
| `tibi.knowledge.read` | S/R | ● |  | ● |  |  |  |  |  |  |  |  |
| `tibi.knowledge.edit` | S/R | ● |  | ● |  |  |  |  |  |  |  |  |
| `tibi.knowledge.approve` | S/R | ● |  | ● |  |  |  |  |  |  |  |  |
| `tibi.spoken.edit` | S/R | ● |  | ● |  |  |  |  |  |  |  |  |
| `tibi.spoken.approve` | S/R | ● |  | ● |  |  |  |  |  |  |  |  |
| `tibi.persona.manage` ⚠ | P | ● |  |  |  |  |  |  |  |  |  |  |
| `avatar.use` | S | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `avatar.session.create` | S | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `conversations.read_own` | O | ● |  | ● | ● | ● | ● | ● | ● | ● |  | ● |
| `conversations.delete_own` | O | ● |  | ● | ● | ● | ● | ● | ● | ● |  | ● |
| `conversations.read_all` ⚠ | S | ● |  |  |  |  |  |  |  |  |  |  |
| `conversations.review` | S | ● |  |  |  | ● |  |  |  |  |  |  |
| `conversations.export` ⚠ | S | ● |  |  |  |  |  |  |  |  |  |  |
| `conversations.delete_all` ⚠ | S | ● |  |  |  |  |  |  |  |  |  |  |
| `jobs.read_own` | O | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `jobs.cancel_own` | O | ● |  | ● | ● | ● | ● | ● | ● | ● |  |  |
| `jobs.read_all` | S | ● |  |  |  | ● |  |  |  |  |  |  |
| `jobs.cancel_all` | S | ● |  |  |  | ● |  |  |  |  |  |  |
| `exports.create` | S/R/O | ● |  |  |  | ● |  |  |  | ● |  |  |
| `exports.download` | S/R/O | ● |  |  |  | ● |  |  |  | ● |  |  |
| `exports.revoke` | S/R/O | ● |  |  |  | ● |  |  |  |  |  |  |
| `audit.read` | P/S | ● | ● |  |  | ● |  |  |  |  | ● |  |
| `audit.export` ⚠ | P/S | ● |  |  |  |  |  |  |  |  |  |  |
| `diagnostics.read` | P/S | ● |  |  |  | ● |  |  |  |  |  |  |
| `diagnostics.traces.read` ⚠ | P/S | ● |  |  |  |  |  |  |  |  |  |  |
| `diagnostics.simulator.run` | P/S | ● |  |  |  | ● |  |  |  |  |  |  |
