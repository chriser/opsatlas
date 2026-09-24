# Tiberius conversational repair and paced delivery

24 September 2026 · local internal rehearsal · owner listening acceptance pending

## What the reported conversation exposed

The product companion selected approved paragraphs rather than explaining concepts. Repeated ontology questions received topical but unhelpful passages. The voice adapter also ignored the warm/gentle style labels: the installed Chatterbox Turbo implementation does not support its documented exaggeration/CFG controls. The supplied transcript and timing JSON cannot establish that Tibi sounded angry; no recording was supplied for acoustic assessment.

Five microphone turns in the supplied trace completed. Speech-end-to-playback median was 4.868 seconds, with reported p95 6.894 seconds. Median endpoint wait was 1.122 seconds; recognition delivery 116 ms; transcript-to-speech-request 1.079 seconds; synthesis/delivery 2.422 seconds; audio arrival to browser playback 8.6 ms. Medians of separate stages are not additive. Planning milestones were missing, so the transcript-to-request interval is a proxy, not an isolated model measurement. The frontend now records planning request and response-ready milestones for social/product replies.

## Delivered conversation behaviour

- A new session introduces Tiberius/Tibi and asks the visitor's name, while explicitly allowing a direct question. Explicit names and a short first-name response are acknowledged; wellbeing replies lead to an optional introduction. Resuming an existing conversation retains its welcome-back behaviour. Names are self-declared conversation text, not authenticated contributor identity.
- Complete social utterances have short replies without fetching product evidence or invoking the model. Mixed social/product questions still use factual routing.
- Product answers select one relevant approved record, add a short acknowledgement and ask whether the answer was on point. Product facts remain exact excerpts with current approval/hash revalidation. The layer does not freely paraphrase or invent features.
- A small general teaching glossary covers ontology, ontology-assisted investigation and document retrieval. Definitions use plain language and explicitly illustrative examples; they are labelled `general_explanation`, never approved product evidence. The concept background is the [W3C RDF 1.1 Primer](https://www.w3.org/TR/rdf11-primer/) on classes, properties and relationships. These examples do not assert that a particular OpsAtlas/customer record or query capability exists.
- Definition requests and contextual simplification requests are resolved before document selection. A second explanation uses a different example; continued confusion asks which aspect needs unpacking. A confirmation such as “yes, that helps” ends explanation rather than triggering another product paragraph.
- If the model selects the immediately previous product paragraph for a new question, Tibi acknowledges that repeating it would not help and asks what needs clarification. An explicit request to repeat remains supported. Missing detail still requires richer reviewed evidence; this is not a substitute for it.

This remains bounded dialogue with a small glossary and rule-based repairs around a local model router. It is not unrestricted natural conversation, emotion recognition or general grounded answer synthesis. The replay still exposes a content gap for deeper implementation detail beyond the starter cards; the correct current response is to acknowledge that gap. Broader explanatory coverage, social variety and meaning-preserving source-based synthesis remain subsequent work requiring evaluation.

## Delivered speech behaviour

The selected Chatterbox reference stays unchanged. Generate complete phrases once, with no incremental prefix joins. Split longer comma/semicolon/colon clauses (at least five words before the punctuation), keeping numeric commas and short noun lists intact. Add 200 ms between those clauses and 320 ms between sentences. Existing model silence can make an actual pause longer.

Apply FFmpeg `atempo=0.94` to the complete phrase, preserving pitch rather than slowing the sample clock. This adds approximately 6.4% to voiced duration. The installed local FFmpeg is required; the adapter checks PATH and the standard Apple Silicon Homebrew location. Audio stays local and is passed over pipes, not temporary speech files.

Cap loud phrase active RMS and peak with a single attenuating gain; do not amplify quiet phrases or pump gain within speech. Smooth the first/last 5 ms before intentional silence. Use temperature 0.6 to reduce sampling variation. These controls do not guarantee a particular emotion; human listening is required to judge tone, expressiveness and whether tempo processing has introduced artifacts.

Synthetic worker verification produced 9.169 seconds of speech/pauses, peak 0.432 and zero clipped samples. First packet including worker startup was 2.932 seconds in this run. This is not an end-to-end latency comparison with the user's different utterances. A real FFmpeg test checks duration, retained 440 Hz pitch, attenuation and zero-valued edges. Transport remains 80 ms PCM packets with the existing playback acknowledgements.

## Validation and rollout

All 343 Python tests and 60 JavaScript tests pass; Ruff and diff checks pass. Tests cover glossary/repair continuity, social replies, product approval boundaries, concurrent revocation, mixed factual requests, repeated-answer handling, numeric commas and audio timing/pitch/edges. A read-only local-model replay of the supplied conversation plus greeting and clarification turns is retained as [replay evidence](evidence/2026-09-24/tiberius-dialogue-replay.json). [Timing/audio evidence](evidence/2026-09-24/tiberius-conversational-delivery.json) includes only derived timing aggregates and synthetic-audio measurements; no microphone recording was made.

Both isolated sales services are restarted. Refresh Tibi, then start a new session to hear the introduction; resume preserves conversation history. Existing Governance approvals and original OpsAtlas data are unchanged. ADO SME-S126 remains open for owner acceptance. Listen for comfortable comma pauses, consistent loudness and natural clause transitions before describing the voice issue as resolved.
