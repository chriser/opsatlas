# Product ontology for Tibi, and corrections from the second evaluation

**25 September 2026 · Built by Claude · Stories #1724 (S152, corrections) and #1725 (S153, product ontology) · Status: delivered for the Human's evaluation on branch `claude/tiberius-speed-safety`; nothing is merged to `main` until the Human accepts it.**

## Why

After enabling all 19 paper-foundation records, the Human asked whether Tibi uses the ontology layer. It did not: the sales workspace's core ontology held one empty process object per source, and Tibi answered from records alone. The Human chose to give Tibi a product ontology ("option 2"), expecting it to help the sales pitch too. The same day's headset evaluation raised three corrections:

- A broad question ("Is it secure enough for a bank?") went straight into data anonymisation. Tibi should say which areas it can cover and ask which one is meant.
- Asked about real use, Tibi said the data would stay anonymised. That is true only of the proof-of-concept demo; an organisation adopting OpsAtlas would use its own data. Answers must separate the demo from a real deployment.
- "How accurate is it?" twice produced "could you say that again". This was a fault, not a question Tibi failed to understand.

## The product ontology (S153)

A curated graph of what OpsAtlas is, built in the platform's own `OntologyStore` with a separate schema and database, so rebuilding it never touches the core ontology.

| Object type | Count | Example |
|---|---|---|
| Capability, with delivery status | 10 | Enterprise Activity Model (delivered), Tibi (experimental), using the organisation's own data (planned) |
| Component, with where it runs | 8 | Web control panel (React and TypeScript, runs locally); Anam avatar rendering (managed external service) |
| Limitation of the proof of concept | 11 | No enterprise identity or single sign-on |
| Topic and its aspects | 1 + 4 | Security: data in the demo and in a real deployment; where processing runs; access and identity; controls on answers |
| Record (the evidence) | 21 | One per enabled curated record |

Relationships: a capability *builds on* another, *works through* components and is *limited by* limitations; a topic *has* aspects; every object is *evidenced by* the records that establish it (62 links when all records are enabled).

**Governance.** The ontology has no approval of its own. Each object names the curated records it rests on (`corpus/product_ontology.json`) and exists only while all of them are enabled; a topic exists while at least two of its aspects do. The graph is rebuilt whenever the enabled records change (61 ms). A test checks that no object's wording adds a figure, standard or claim term that the records do not state. Knowledge review shows the ontology read-only, including the objects waiting on records.

**How Tibi uses it.** The sales core matches each question against the ontology in under 1 ms, as part of the search it already makes, so there is no extra round trip:

- **Routing.** A named product part ("the ontology layer", "the Enterprise Activity Model") is a product question, not a dictionary definition. "What is an ontology?" is still answered as general knowledge. Whole-product questions such as "What is delivered and what is planned?" or "What are the limitations?" go to product evidence.
- **Evidence.** Facts about the named parts join the evidence pack, together with the records behind them. The ontology knows that the Enterprise Activity Model is used in the web control panel, which the model could not have found from record wording alone. Every spoken sentence is still checked against the records and facts before speech. Facts are citable with their own delivery status, so "Delivered: cited answers, …" is not qualified as planned.
- **Clarification.** A broad topic raised without an aspect is narrowed first, with a fixed reply built from the ontology in about 30 ms and no model call: "Security covers a few areas. I can talk about how data is handled in this demo and in a real deployment, where processing runs and which services are external, access and identity controls, or controls on answers like approvals and audit trails. Which would you like?" The next turn can name an area, choose one by position ("the second one") or ask for all of them, and is answered from that area's records. A topic is narrowed once per conversation.

## Corrections (S152)

- **The failed turn.** When no generated sentence passes its checks, Tibi speaks approved record wording instead. The evaluation record is 635 characters, but the voice worker accepts 600 per request, so the request failed and Tibi asked for a repeat. Long wording is now split into sentence groups before speech: the first group is at most 300 characters, so the voice also starts sooner. The fallback itself was caused by a false block: "80%" was not recognised as the record's "80 percent". Figures in digits and in words now compare equal.
- **The demo and a real deployment.** Two curated records join the foundation. *Security controls in the proof of concept* (available; paper pp. 8, 25–26, 39) covers local execution, local storage, controlled evidence packs, approval gates, provenance and audit traces. *Real deployment and the organisation's own data* (planned; paper pp. 5, 13, 25–27, 39–40, and the product owner's direction of 25 September) states that a real deployment would use the organisation's own data, and lists the reviews and production controls it would need. The evidence prompt treats the demo's anonymised data as a deliberate demo choice, and asks for answers about real use to say what the demo uses and what a real deployment would use and need.
- **Qualifiers follow the sentence they qualify.** "That's planned rather than available today." refers back; spoken first, it made "How accurate is it?" sound as though accuracy were planned.
- **New records reach an existing workspace.** Starting the core adds new corpus records as pending, and never changes a reviewed record. A workspace seeded from another corpus is never merged with this one.

## Measured

Text-only turns against a disposable copy with all 21 records enabled, using the real local models and pre-warming as in the live voice:

| Question | Route | First checked sentence |
|---|---|---|
| What is the ontology layer? | product (names a product part) | 0.31 s |
| Where can I find the Enterprise Activity Model? | product; answer names the web control panel | 0.43 s |
| Is it secure enough for a bank? | clarification | 0.03 s |
| Data security, please. | the chosen aspect: demo, then real deployment | 0.26 s |
| When adopted by a bank, it will hold real data. Is that correct? | "Yes, in a real deployment … not the anonymised data used in the demo" | 0.45 s |
| How accurate is it? | grounded: about 80% in the proof of concept | 0.49 s |
| What is delivered and what is planned? | product (whole-product question), from ontology facts | 0.37 s |

**Replay (the speed guard).** A 40-turn replay on the live turn path with the Higgs voice ran on a copy of the live workspace: 19 records enabled, the two new ones pending. End of speech to first audio had a median of **1.37 s (p95 1.65 s)**, within the latency budget (1.95 s / 3.1 s) and faster than the 1.82 s recorded at the review 2 delivery. There were no errors, and all 40 replies were prepared from the settled partial transcript. Product answers had a median of 1.42 s. The ontology match adds no request, and its facts add a few hundred characters to a prompt that is pre-warmed during speech. Evidence: [latency-replay-40-ontology.json](evidence/2026-09-25/latency-replay-40-ontology.json). The last small changes after the replay (qualifier order, stricter aspect choice) add no model calls.

## For the Human

1. **Enable the two new records** in Knowledge review: *Security controls in the proof of concept* and *Real deployment and the organisation's own data*. Until they are enabled, three of the four security aspects are unavailable. Tibi will then answer security questions directly instead of narrowing them, and will not use the real-deployment wording.
2. The **Product ontology** section in Knowledge review shows what Tibi now knows structurally, and what is waiting on records.
3. Suggested questions for the next evaluation:
   - "Is it secure enough for a bank?", then an area.
   - "Would a bank use its own data?"
   - "How accurate is it?"
   - "Where can I find the Enterprise Activity Model?"
   - "What is delivered and what is planned?"
   - "What are the limitations?"
