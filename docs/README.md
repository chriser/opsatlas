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
| [benchmark/](benchmark/) | Write-ups of measured results: RAG against OAG, the Sales hypotheses and checks (one dated record each), the governance judges. The sets and raw results are in [`../evaluation/`](../evaluation/README.md) | [oag/README.md](benchmark/oag/README.md), `sales/` |
| [data-and-governance/](data-and-governance/) | How data is handled: anonymisation and synthetic-data rules, the learning packs, statement-level governance, external sources | [statement-level-governance.md](data-and-governance/statement-level-governance.md) |
| [iam/](iam/) | The IAM guide, the permission matrix and the route manifest (both generated) | [README.md](iam/README.md) |
| [initiatives/](initiatives/) | Larger pieces of work and their running records: Tibi (`sme-interviewer/`), knowledge spaces, content management | each folder's README |
| [validation/](validation/) | Validation protocols and methods from DT603 | [answer-grounding-validation.md](validation/answer-grounding-validation.md) |
| [ways-of-working/](ways-of-working/) | How the work is run: the definition of done, effort sizing, agent collaboration, the handover log | [Ways-of-Working.md](ways-of-working/Ways-of-Working.md) |

**Files the code reads are not here.** Since AUDIT F14 they live outside `docs/`: Tibi's engine registry and latency
budget in [`../config/`](../config/README.md), and every evaluation set, result and archived run dump in
[`../evaluation/`](../evaluation/README.md). Two kinds of reference into `docs/` remain, and neither breaks code when a
page moves: the Validation page names documents as evidence (it shows the paths and does not read the files), and two
tests check DT603 content (`architecture/industry-context-and-decisions.md` and the article-setup learning pack). Check
with `git grep "docs/"` before moving those.

**Retired features.** Pages about the compliance-reasoning service, the simulator, the Process Stress Lab and value
analytics carry a dated note at the top. Those features live in OpsAtlas Classic.

**Not committed.** `context/` and `evidence/` hold local reference material and stay out of the repository.
