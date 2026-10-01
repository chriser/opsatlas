# Documentation

Start here:

- [The README](../README.md): what OpsAtlas is, and how to install, run and test it.
- [Architecture status](../ARCHITECTURE_STATUS.md): the current module map, and what changed recently.
- [OpsAtlas Classic and OpsAtlas Sales](opsatlas-classic-and-sales.md): the two versions, with their folders, ports,
  data and sign-in.
- [The IAM guide](iam/README.md): accounts, roles, permissions, and the host's bootstrap and recovery commands.

| Folder | What it holds | Start with |
|---|---|---|
| [architecture/](architecture/) | Design records: RAG and OAG routing, the core modules, the Enterprise Activity Model, the diagram renderer, the DT603 industry context | [05-RAG-Framework.md](architecture/05-RAG-Framework.md), [07-Core-Modules.md](architecture/07-Core-Modules.md) |
| [audits/](audits/) | Reviews of the whole system and the responses to them, with their raw evidence | [the deep audit of 30 September 2026](audits/2026-09-30-deep-audit.md) |
| [benchmark/](benchmark/) | Measured results: RAG against OAG, the Sales hypotheses and checks (one dated record each), the governance judges, the EAM | [oag/README.md](benchmark/oag/README.md), `sales/` |
| [data-and-governance/](data-and-governance/) | How data is handled: anonymisation and synthetic-data rules, the learning packs, statement-level governance, external sources | [statement-level-governance.md](data-and-governance/statement-level-governance.md) |
| [iam/](iam/) | The IAM guide, the permission matrix and the route manifest (both generated) | [README.md](iam/README.md) |
| [initiatives/](initiatives/) | Larger pieces of work and their running records: Tibi (`sme-interviewer/`), knowledge spaces, content management | each folder's README |
| [validation/](validation/) | Validation protocols and methods from DT603 | [answer-grounding-validation.md](validation/answer-grounding-validation.md) |
| [ways-of-working/](ways-of-working/) | How the work is run: the definition of done, effort sizing, agent collaboration, the handover log | [Ways-of-Working.md](ways-of-working/Ways-of-Working.md) |

**Files the code reads.** Some files here are inputs, not only reading matter. Do not move or rename them without
the code that reads them:

- `initiatives/sme-interviewer/tibi-engine-versions.json` and `latency-budget.json`, Tibi's engine gate.
- The evidence references of the Validation page, such as `validation/answer-grounding-validation.md` and
  `benchmark/oag/README.md`.

The plan is to move the inputs to `config/` (AUDIT F14). Until then, check with `git grep "docs/"` before a clean-up.

**Retired features.** Pages about the compliance-reasoning service, the simulator, the Process Stress Lab and value
analytics carry a dated note at the top. Those features live in OpsAtlas Classic.

**Not committed.** `context/` and `evidence/` hold local reference material and stay out of the repository.
