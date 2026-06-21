# Quality benchmark — supplier-setup assistant (commercial baseline)

The operator's existing PoC agent is the **quality bar** for our open-source query and
answer engine. We aim to **match or exceed** it, measured with a shared question set
(see the comparative-benchmark story in ADO). This document captures its configuration
so we can build our grounded-answer slice, guardrails and evaluation against it.

> Note: this is a commercial baseline used only as a reference target. Our build is
> entirely open-source (Ollama). Synthetic / anonymised data only.

## Model & retrieval configuration

| Setting | Baseline | Ours (current) |
|---|---|---|
| Answer LLM | Gemini 2.5 Flash | Ollama `qwen2.5:7b-instruct` (local) |
| Embedding model | `intfloat/e5-mistral-7b-instruct` | `nomic-embed-text` (smaller) |
| Small-KB strategy | **Whole doc in the prompt** (no RAG for small KBs) | chunked retrieval only — to add full-context mode |
| Chunk limit | 5 chunks / query | top_k (no cap tuning yet) |
| Character limit | 50,000 chars / query | none |
| Vector-distance threshold | drops low-similarity chunks | **none yet** (we return top_k regardless) |
| Query rewriting | rewrites last question → standalone + simplified before retrieval | **none yet** |

**Query-rewriting prompt (baseline):** rewrite the user's last question so it includes
all relevant prior context and is self-contained, then simplify it (strip chatty parts);
return only the simplified text, in the conversation's language.

## System prompt (baseline) — the template for our grounded-answer prompt

The baseline agent is instructed to: answer **only** from the approved anonymised
knowledge base; never invent, fuzzy-match, or answer from general knowledge; never
disclose real supplier/employee/system names or commercial data; use the fixed generic
vocabulary (Business Requester, Process Support Lead, Support Analyst, Finance Master
Data Lead, Credit Control Role, Supply Chain Analyst, Target Backoffice System, Finance
ERP); refuse with a fixed line when the answer is not in the KB
("I do not have that information in the approved anonymised process knowledge base");
refuse to approve onboarding or make production changes; explain open design decisions
as still requiring business confirmation; keep answers concise and natural. It also
encodes the core business rules (due-diligence/credit checks are mandatory gates; setup
is not complete until finance mapping + validation; operational vs finance IDs differ)
and a 14-step process walkthrough.

The full system prompt text is held by the operator; the points above are the contract
our Slice 3c prompt must satisfy.

## Guardrails (baseline) — maps to our validation & safety layer (#28 / #63)

**Input guardrails**
- **Focus** — keep the agent on its defined goal / system instructions; prevent off-topic drift.
- **Manipulation** — block attempts to bypass or override the system instructions (jailbreak / prompt injection).

**Output content guardrails** (execution mode: streaming; action on violation: e.g. end conversation; each at low / medium / high severity, plus custom):
- erotic / sexually explicit
- violence / physical harm
- abusive or threatening behaviour
- self-harm / suicidal content
- vulgar / explicit language
- political and religious discussion
- medical or legal topics

## How we use this
- **Slice 3c (grounded answer):** adapt the system prompt above; enforce KB-only grounding, citations, and the fixed refusal line.
- **Guardrails (#28):** implement the input (focus + manipulation) and output content-safety guardrails with a configurable refusal/abort action.
- **Evaluation:** run the same question set through our system and the baseline; compare grounding, refusals and correctness.
