# Voice selection reset: paid local models and custom improvement

Research checked 24 September 2026. No replacement deployed, purchases made, vendor messages sent or proprietary samples uploaded.

## Owner evidence and revised target

All five configurations are rejected by the owner. The exported file contains five greeting ratings, not ratings of every benchmark passage. Naturalness: Turbo 2/5, Qwen4 2/5, VibeVoice 1/5, Chatterbox V3 3/5, Qwen8 4/5. Qwen8 still fails accent (1/5) and pronunciation (2/5). V3 has acceptable accent (4/5) but unacceptable pace (1/5). Qwen4 is overexpressive; others are flat, rushed or audibly digital. See the [captured feedback with clip provenance](evidence/2026-09-24/tiberius-voice-owner-feedback.json).

Target: restrained warmth, authentic British delivery, declarative rather than rising question intonation, intelligibility, natural phrase boundaries and stable timbre. The completed audition used native speed: the reported drifting is real feedback but not evidence of our prior speed processing. Its cause remains unisolated. It could involve the model, reference conditioning, decoding, runtime conversion or playback. Avoid claiming quantisation is the cause from this small uncontrolled comparison.

The last audition sampled voice presets and reference choices, not the entire capability of each family. Nevertheless the owner has rejected those configurations; do not promote the least-bad result. Reset selection criteria and candidate families while preserving the functioning application.

## New shortlist

| Option | Reason to evaluate | Local and commercial position |
|---|---|---|
| Breeze TTS 2 | Reference-guided voice direction, delivery instructions and vocal events | Downloadable; separate commercial agreement required for product deployment. MLX port documented; no measurement on this Mac yet |
| Fish Audio S2 Pro | Contextual expressive control and multi-turn generation | Downloadable with fine-tuning code; business use needs separate written licence. Mac runtime/latency unverified |
| Higgs TTS 3 | Conversational model with inline emotion/prosody/pause controls | Downloadable; product integration needs commercial licence; creator-content exception does not cover Tibi |
| Rime Coda | Vendor focuses on conversational recordings and delivery | Vendor offers on-premise deployment. Quote, British voices, Mac support and customisation rights need confirmation |
| ElevenLabs local models | Commercial quality reference plus custom voice programme | On-premise/on-device early-access offers; purpose-built local models, not necessarily the same as hosted flagship. No verified Mac Studio package or public local price |

Primary sources: [Breeze features](https://github.com/breezeblue-ai/breeze-tts), [Breeze licence](https://huggingface.co/BreezeBlue/Breeze-TTS-2/blob/main/LICENSE), [MLX implementation](https://blaizzy.github.io/mlx-audio/models/tts/breeze-tts/), [Fish project](https://github.com/fishaudio/fish-speech), [Fish licence](https://github.com/fishaudio/fish-speech/blob/main/LICENSE), [Higgs model card](https://huggingface.co/bosonai/higgs-tts-3-4b), [Rime Coda](https://www.rime.ai/resources/coda-tts), [ElevenLabs local deployment](https://elevenlabs.io/on-prem-deployments), [ElevenLabs on-device distinction](https://elevenlabs.io/blog/enterprise-voice-ai-deployed-locally).

These are promising candidates, not demonstrated improvements on Chris's material. Start with Breeze for local feasibility and Rime for a paid conversational alternative. Keep Fish/Higgs as distinct follow-on candidates. CosyVoice3 is a secondary permissively licensed training-stack option ([publisher card](https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512)); it has not demonstrated superior British delivery here.

## Paid does not mean API-only

There are separate markets: hosted API subscriptions, downloadable weights with a negotiated commercial licence, and enterprise self-hosted runtimes. Buying an API subscription normally does not buy weights, offline execution, redistribution or training rights. A VPC is still cloud infrastructure. On-premise may require Linux/NVIDIA servers and does not mean Apple Silicon. ElevenLabs describes an annual licence plus a usage component and requires hardware scoping. No verified local quote was obtained.

For any paid candidate, request the exact model/version, British voice samples, hardware/OS support, offline operation and licence checks, custom voice/adapter support, internal demo versus customer deployment rights, annual minimums, usage fees and exit/portability terms. Evaluate the exact locally deliverable model, not a different flagship API. No vendors contacted in this research turn.

## How commercial quality is built

It is not safe to assume proprietary TTS is merely a fine-tuned open TTS checkpoint. Some reuse components; others develop different architectures, data and serving stacks. Fish reports adapting Qwen3-4B with audio modules, pretraining on over ten million hours, supervised expressive data and multi-objective reinforcement learning. This is substantially more than voice cloning ([technical report](https://arxiv.org/html/2603.08823v1)). Rime describes proprietary conversational recordings and jointly trained semantic/acoustic decoders. Cartesia describes its own state-space architecture and inference stack ([Sonic development](https://www.cartesia.ai/blog/sonic)). Closed vendors do not disclose complete recipes.

A useful abstraction is: collect and clean speech → align words/audio → preserve expressive annotations → train the audio representation and generation model → supervised delivery tuning → preference/intelligibility evaluation → optimise streaming. Codec quality and sentence-context retention matter alongside the voice model.

## A realistic Tibi improvement programme

1. Establish an acceptable human target performance before more engineering. Record a consenting British speaker in actual short exchanges: greeting, clarification, correction, gentle disagreement, technical explanation and closing. Separate speaker identity from desired delivery. Chris can direct/rate a chosen speaker; he need not be the target voice.
2. Compare two new families on a small varied script and multiple seeds. Use the same licensed reference where supported, plus a good native British voice where available. Begin at full/BF16 precision when practical. Keep raw and loudness-matched listening copies separate; no tempo edits. Record both steady delivery and transitions across turns.
3. Confirm pronunciation, accent and naturalness before building live integration. Then compare original inference with the Mac port where practical; test codec seams, buffering, sentence chunking and simultaneous ASR/LLM load. No automatic assumption that every audible issue is model quality.
4. Start customisation with native conditioning and a well-directed reference recording. If a candidate is close, create a curated speech dataset and test supported speaker/style fine-tuning. Collect a small recording pilot to validate the process before paying for a larger session; no guaranteed number of minutes or training outcome.
5. Build paired listening preferences with context, text, style, voice consent, exact settings, model version and audio hash. Hold out conversations and unseen vocabulary. Promote only after pronunciation, factual wording, expressive restraint and latency pass. User ratings are feedback signals, not complete training data by themselves.
6. Train dialogue construction separately on corrected context/reply pairs. Keep approved product facts in retrieval. Do not let a more expressive voice hide unsupported answers.

The Mac is a sensible inference target; frontier model pretraining is not a sensible project on one Mac Studio. Adapter training may be possible depending on architecture and implementation, but support and throughput need a pilot. A separate local NVIDIA training machine remains compatible with offline operation. Do not silently move training to cloud compute.

Do not assume commercial model outputs can train another model: Breeze and Fish have explicit cross-model restrictions. Use owned/licensed human recordings, or negotiate rights covering the intended improvement process. Fine-tuning a licensed base does not remove its licence.

## Next work and acceptance

Research is complete for this turn. Next proposed work is a small Breeze feasibility audition, exact-model paid-local sample evaluation, and a consented reference-performance brief. Hardware/licence feasibility remains open. Existing live voice, services and knowledge approvals are unchanged. No new candidate is claimed to beat the baseline until Chris accepts its delivery.
