# Tibi: activity log, conversation log, engine versions, scorecard and the Talk with Tibi stage

ADO Epic #1818 (TIBI E2). Requested 26 September 2026, after Tibi seemed stuck when it was started several times.

## 1. The activity log (OBS F1)

Everything that happens around the control panel is written as JSON lines to
`.runtime/opsatlas-sales/logs/activity/<source>-<date>.jsonl`. Files are kept for 14 days.

| Source | What it records |
|---|---|
| `core` | Every request to OpsAtlas: method, path, status, milliseconds and the page it came from. The 30-second status checks are marked `poll`. Sign-ins and refused sign-ins, restarts, and marks on conversation turns are separate events. The live voice socket to Tibi is recorded: opened, refused, connected (with timing and set-up), Tibi's state and error messages, and closed (code, reason, duration, microphone frames and audio chunks). |
| `browser` | What the page did: pages opened, buttons pressed, page errors. For Tibi: start pressed, microphone ready or refused, conversation created, socket open and closed, ready (with seconds), slow start after 60 s, pause, resume and end. |
| `tibi` | The Tibi service: started (with the engine version), each part ready and how long it took (voice, recognition, detection, conversation model), conversation ready, failures. When the model warm-up fails, it records what the local model server had loaded at that moment. |

Nothing secret is written: passwords, tokens, keys and cookies are replaced by `[redacted]`, and the workspace key
never appears. Conversation wording is not in this log; it is in the conversation log.

Read it with:

```
scripts/opsatlas-activity --since 30m --no-polls
scripts/opsatlas-activity --source browser --source tibi --grep tibi --follow
```

**What this found on the first day.** The stuck starts at 21:30 BST were Tibi's warm-up. It loads up to three
models one after another, each with a 120 s allowance. The governance review had just used the same model server.
The page waited with no limit and then showed a generic message. There are now three changes:
- The warm-up has an overall 150 s limit and a plain message that names the likely cause.
- The page says after 60 s that the start is slow and points to **Restart services**.
- A second conversation is refused with its reason. Before, the page read the refusal as "sign in again".

## 2. The conversation log (OBS F2)

Tibi writes one line per turn to `.runtime/opsatlas-sales/logs/conversations/<date>.jsonl`. Each line has:
- the session, turn and mode;
- the engine version and fingerprint;
- the voice, and whether the turn was typed;
- what was heard and the reply;
- the route and why;
- the grounding, the records cited and the conversation guidance used;
- the timings;
- any issue, blocked wording or interruption.

**Tibi Voice → Conversation Log** lists sessions by day. A session opens to its turns. A turn can be marked
**Good**, **Odd** or **Wrong** with a note of what Tibi should have done. The **To improve** tab collects the odd and
wrong turns: that is the list to work through. Marks are kept in `logs/conversation-reviews.jsonl`; the latest
mark for a turn counts, and clearing it removes the turn from the list.

## 3. Engine versions (OBS F3)

The engine is the voice service's modules (prompts, routing rules, turn-taking, speech) and the models they use.
Its versions are in `tibi-engine-versions.json`. `services/sme_interviewer/engine.py` computes a fingerprint from
the engine's files and model names. `tests/test_sme_engine.py` fails when the engine changes without a new version,
so a version always means one engine.

To release a change to Tibi:
1. Run `.venv/bin/python -m services.sme_interviewer.engine` to see the new fingerprint.
2. Add a version to `tibi-engine-versions.json` with the fingerprint and a line on what changed, and make it current.
3. Run the scorecard (below) and the latency replay.

The Talk with Tibi page shows the engine version, and every turn and scorecard carries it. A running service whose
files differ from the release reports `<version>+changed`.

| Version | Fingerprint | What changed |
|---|---|---|
| 1.0.0 | `0565c8768f95` | Baseline, as delivered up to 26 September 2026 |
| 1.1.0 | `41c4af59816f` | Small talk (a question handed back, one question, capital letter, short answers), start-up limit and reasons, turn and lifecycle logs |

## 4. The scorecard (OBS F4)

`services/sme_interviewer/evaluate_engine.py` runs the scripted conversations in `evaluation/sets/tibi/scenarios.json`
through Tibi's own turn code, against the approved records. The scorecard is saved in `evaluations/`, stamped with
the engine and the knowledge digest, and compared with the previous one:

```
services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.evaluate_engine --runs 2 [--judge] [--replay FILE]
```

| Measure | What it is |
|---|---|
| Routing accuracy | Share of turns that took an allowed route (conversation, product, self, general, clarify) |
| Appropriateness | Share of the per-turn checks passed: one question, capital letter, length, answers about itself when asked back, no product claim in small talk, declines off-limits topics, no copied guidance, no repeated question, mentions and avoids |
| Grounding precision | For product answers: share of sentences an approved record it used supports, and every figure present in those records |
| Speed | First token and first spoken segment, p50 and p95, in the text path |
| Judge score (`--judge`) | A local judge's 1–5 rating of appropriateness and naturalness (qwen2.5:14b-instruct, on this Mac) |
| Speech (`--replay`) | End of speech to first audio (p50, p95) and recognition accuracy, from a `replay_latency` result |

Each measure is reported as improved, same or degraded, using a tolerance (3 points for shares, 10–15% for times).

## 5. The Talk with Tibi stage (OBS F5)

The transcript and Tibi are the focus:
- A central animation, with the controls beneath it.
- The transcript as a conversation, including what Tibi is saying now and what you are saying.
- A typed input.
- Mode, contributor, topic, voice, input, audio devices, what Tibi used, and an Animation switch in a side panel
  that can be hidden.

The animation adapts "The Spirit" by Edan Kwan (MIT; see `THIRD_PARTY_NOTICES.md`), the effect the Board Game
Assistant used:
- Particles are pulled towards a point on a wide looping path and pushed along curl noise, so they trail as smoke.
- It follows Tibi's voice as it plays and the microphone while you speak. The path widens and quickens, and the
  colour warms from pink towards peach and white as the voice rises.
- Idle is violet, listening teal, thinking purple and speaking pink.
- It uses 16k particles and soft points without post-processing, because Tibi's voice model shares the GPU.
- It pauses when the page is hidden.
- With reduced motion, or without WebGL, it is a soft orb that breathes with the voice.
- It loads only on this page.

## Found, not changed

- **The 50-conversation limit.** The Tibi service stops creating new conversations after 50 saved ones
  (`ledger.py`, "limited to 50 saved sessions"). There are 13 today. When it is reached, Tibi will not start. The
  conversation log now keeps every turn separately, so old conversations could be archived. That is the Human's
  decision.
