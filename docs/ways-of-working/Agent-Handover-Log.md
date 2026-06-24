# Agent Handover Log

> ## ⛔ START HERE — every agent, every session
> 1. Read the [Working Agreement](/Ways-of-Working/Agent-Collaboration) **in full**.
> 2. Read the **latest entries below** before doing anything.
> 3. Work **only** where **Agent Owner = you**. Do not write code, edit tickets, or change the Wiki until both are done.

This page is the **single place** cross-agent handovers are recorded. **Do not put handovers in work-item tickets** — keeping them here makes the project state easy to inspect at a glance. Newest entry on top.

## Role reminder — who does what (re-read this every time)
| Agent | Does | Does **NOT** |
|---|---|---|
| **Human** (Operator) | Direction, approval, data/governance decisions, UAT → Closed | — |
| **Claude** | Review, coordination, backend & architecture, ADO grooming | Bulk-fix during review |
| **Codex** | Build the **assigned** module + tests; small `#id`-scoped commits | Groom backlog / change architecture / touch others' files |
| **Antigravity** | Research, evaluation, docs/Wiki, backlog **proposals** | Write code; change/close tickets it doesn't own; restructure backlog; decide architecture; act off its assigned ticket |

## How to log a handover (at the end of every working session)
Add a **new entry at the top** of the Log using this template. Keep it short and factual.

```
### YYYY-MM-DD HH:MM — <Agent> (<Role>)
- Tickets touched: #id, #id
- Done: what changed (commit hashes if code)
- Open / next: what remains, suggested next ticket
- Next owner: <Agent or "unassigned">
- Cautions: blockers, gotchas, do-not-touch areas the next agent must know
```

## Log

### 2026-06-24 10:48 — Codex (Diagram Service Settings Start Control)
- Tickets touched: bug #1015.
- Done: Implemented #1015 in commit `54c04fa` (`Fix #1015 diagram service start control`). Added protected `/api/process/diagrams/service/status` and `/api/process/diagrams/service/start` endpoints, local-only process diagram service manager, Settings > Models service status card, Start service and Refresh status actions, and regression tests.
- Validation: `.venv/bin/python -m pytest` passed (210 tests, 1 existing Starlette/httpx warning); `.venv/bin/python -m ruff check .` passed; `npm run build` passed with existing Vite chunk-size warning. Bug #1015 is Resolved in ADO.
- Open / next: Human can open Settings > Models, click Start service if the diagram service shows stopped, then rerun Avatar/Ask process walkthrough UAT.
- Next owner: Human for UAT; Codex for any follow-up if the local service still fails to start on the user's machine.
- Cautions: The start control only starts local URLs (`127.0.0.1`, `localhost`, `::1`) and logs to `data/process-diagram-service.log` by default. If backend code was already running before this commit, restart the backend first so the new endpoints exist.

### 2026-06-23 22:55 — Codex (Sprint 2 Pull-Forward Stop at #955)
- Tickets touched: #953, #952, #950, #954, #955.
- Done: Implemented and pushed five separate commits: `e0c7ff6` (`Add #953 process stress lab page`), `efc67a5` (`Add #952 analytics PDF export`), `9158c15` (`Add #950 KSB evidence mapping history`), `79f137a` (`Add #954 operating model coverage map`), and `969df5f` (`Add #955 process gap overlap visualisation`). ADO items #953/#952/#950/#954/#955 are Resolved with validation notes. User asked to stop feature work after #955; no out-of-Sprint-2 backlog review or pull-forward work was started.
- Validation: Full backend suite passed: `.venv/bin/python -m pytest` = 207 passed, 1 existing Starlette/httpx warning. Full lint passed: `.venv/bin/python -m ruff check .`. Frontend build passed: `npm run build` with the existing Vite chunk-size warning. PDF export was also smoke-rendered locally via macOS `sips` after Poppler was unavailable.
- Open / next: Human can UAT the new Process Stress Lab page, Analytics PDF export, Validation/KSB mapping/history panels, and Operating Model coverage/gap-overlap views. After UAT, close passed tickets or open bugs. Any remaining work outside Sprint 2 still needs a duplication/overlap review before being pulled in.
- Next owner: Human for UAT; Codex for any UAT fixes only.
- Cautions: `reportlab>=4.2` is now a runtime dependency for PDF export. Operating Model coverage and gap/overlap/clash findings are deterministic approved-source triage signals, not proof of live operational completeness or failure. Do not commit the untracked `frontend/.vite/` cache.

### 2026-06-23 22:18 — Codex (Avatar Transcript Scroll Fix)
- Tickets touched: bug #1006, follow-up to #1005.
- Done: Implemented #1006 in commit `b8e8c5f` (`Fix #1006 Avatar transcript scrolling`). Transcript now uses fixed responsive height, max-height and flex-basis instead of flex-growing with message content. It keeps internal vertical scrolling with stable scrollbar gutter, and Avatar Lab auto-scrolls the transcript to the newest message when entries are appended.
- Validation: `npm run build` passed with the existing Vite chunk-size warning; `git diff --check` passed. Bug #1006 is Resolved in ADO.
- Open / next: Human should restart the frontend and retest by asking multiple Avatar Lab questions. Expected behaviour: transcript scrolls internally and no longer pushes the lower grid down.
- Next owner: Human for UAT; Codex for further layout tuning if needed.
- Cautions: Keep `flex: 0 0 clamp(...)` on `.avatar-transcript`; changing it back to `flex: 1` lets the transcript negotiate a taller height again.

### 2026-06-23 22:02 — Codex (Avatar Lab Timing and Layout Polish)
- Tickets touched: bug #1005, related #986.
- Done: Implemented #1005 in commit `176ab97` (`Fix #1005 Avatar Lab timing and layout`). Main Avatar answers now ignore early Anam speech-complete events and wait on estimated speech duration plus a 3.5s settle before the process walkthrough offer is appended/spoken. Speech timing cap increased from 45s to 120s for longer Natural answers. Disconnected placeholder now displays `Kris` and `Digital SME`. Transcript is a fixed responsive scroll window, and Latest Response / Process Walkthrough panels now share desktop column proportions and fixed responsive height with internal scrolling.
- Validation: `npm run build` passed with the existing Vite chunk-size warning; `git diff --check` passed. Bug #1005 is Resolved in ADO.
- Open / next: Human should restart the frontend/backend and retest Avatar Lab with a long Natural answer plus process map. Confirm the walkthrough call-to-action is not spoken until the main answer is complete, the transcript scrolls internally, and the bottom panels align.
- Next owner: Human for UAT; Codex for any further timing or layout calibration.
- Cautions: Main-answer timing is intentionally timer-based because Anam can emit completion events before audible speech ends. Short system phrases and walkthrough narration still use speech events/pacing where appropriate.

### 2026-06-23 21:13 — Codex (Avatar Generic Process Natural Style)
- Tickets touched: bug #1004, related #991.
- Done: Implemented #1004 in commit `6bb536c` (`Fix #1004 Avatar generic process style`). Generic process Natural fallback now leads with the process subject for process-title and "what is" process questions instead of starting with "Yes". Added topic-specific purpose and short-version wording for age restriction grouping and tax handling, and fixed topic detection so tax handling is not misclassified as age restriction when the answer mentions age/tax integration testing.
- Validation: `.venv/bin/python -m pytest tests/test_avatar.py` passed (15 tests, existing Starlette/httpx warning only); `.venv/bin/python -m ruff check src/assistant/avatar/style.py tests/test_avatar.py` passed; `git diff --check` passed. Bug #1004 is Resolved in ADO.
- Open / next: Human should restart the backend and retest Avatar Lab with `Age Restriction Grouping Process` and `what is the tax handling process?`. Expected shape: starts with "The age restriction grouping process..." or "The tax handling process...", not "Yes — in plain terms...".
- Next owner: Human for UAT; Codex for any further language tuning.
- Cautions: Supplier setup intentionally keeps the accepted conversational "Yes" opener. The no-"Yes" rule is targeted to process-title / "what is" process questions.

### 2026-06-23 21:01 — Codex (Avatar Rich Natural Supplier Narrative)
- Tickets touched: bug #1003, related #991.
- Done: Implemented #1003 in commit `be54102` (`Fix #1003 Avatar natural supplier narrative`). Restored the richer accepted supplier setup Natural narrative: approved-address-book analogy, business/request trigger, Trading Support completeness check, due diligence gates, operational/finance record creation, supplier identifier mapping analogy, final activation and short-version close. Natural process LLM candidates must now include a short-version close, and valid citation markers can be drawn from structured `AnswerResult` citations when the canonical text has no inline markers.
- Validation: `.venv/bin/python -m pytest tests/test_avatar.py` passed (13 tests, existing Starlette/httpx warning only); `.venv/bin/python -m ruff check src/assistant/avatar/style.py tests/test_avatar.py` passed; `git diff --check` passed. Bug #1003 is Resolved in ADO.
- Open / next: Human should restart the backend and retest Avatar Lab with `Can you tell me how to setup supplier?` in Natural mode. Expected shape is the richer paragraph narrative, not the bland "To set up a new supplier..." paraphrase.
- Next owner: Human for UAT; Codex for any further language tuning.
- Cautions: Do not roll back frontend timing commits to address Natural answer style. Timing lives in Avatar Lab frontend; this style issue lives in `src/assistant/avatar/style.py`.

### 2026-06-23 20:52 — Codex (Avatar Natural Style Regression Fix)
- Tickets touched: bug #1002, related #991.
- Done: Implemented #1002 in commit `4f15718` (`Fix #1002 Avatar natural style list regression`). Natural spoken Avatar rendering now rejects LLM candidate rewrites that contain numbered or bulleted list lines, even when citation markers are valid. The Natural prompt now explicitly bans numbered lists, bullet lists, Markdown tables and step-heading labels. The deterministic process fallback now produces staged paragraph prose with a friendly supplier intro and short-version close.
- Validation: `.venv/bin/python -m pytest tests/test_avatar.py` passed (12 tests, existing Starlette/httpx warning only); `.venv/bin/python -m ruff check src/assistant/avatar/style.py tests/test_avatar.py` passed; `git diff --check` passed. Bug #1002 is Resolved in ADO.
- Open / next: Human should retest Avatar Lab with `Can you tell me how to setup supplier?` in Natural mode and confirm the visible/latest response is paragraph prose, not a numbered list.
- Next owner: Human for UAT; Codex for any further language tuning.
- Cautions: Citation validity alone is not enough for Natural mode now. If the LLM renderer returns a list-shaped answer, the application must treat it as invalid and use the deterministic paragraph fallback.

### 2026-06-23 20:41 — Codex (Avatar Timing Calibration)
- Tickets touched: bug #1001, related #986.
- Done: Implemented #1001 in commit `446094a` (`Fix #1001 Avatar timing calibration`). Avatar Lab now adds a 5 second settle buffer after early Anam speech-complete events for the main answer before proposing the process walkthrough. The animated process walkthrough timing constants were also shortened so step-to-step gaps feel around 2-3 seconds quicker while retaining proportional word-count pacing.
- Validation: `npm run build` passed with the existing Vite chunk-size warning; `git diff --check` passed. Bug #1001 is Resolved in ADO.
- Open / next: Human should retest the Avatar Lab with Anam connected and confirm the main answer finishes cleanly before the walkthrough offer, and that walkthrough pauses no longer feel too long.
- Next owner: Human for UAT; Codex for any further timing calibration.
- Cautions: The 5 second settle buffer is deliberately applied only to the main answer call. Walkthrough narration still relies on application-side pacing because Anam speech completion events may fire before audible playback fully finishes.

### 2026-06-23 20:12 — Codex (Avatar Viewport Polish and CI Import Fix)
- Tickets touched: bug #1000, related #986.
- Done: Implemented #1000 in commit `7ee7190` (`Fix #1000 Avatar walkthrough viewport and CI imports`). Avatar Lab panels now stretch to the same row height and the Transcript scroll area flexes to fill its panel. The animated process walkthrough now tracks the active process node and auto-scrolls the diagram frame so that node is centred while it is narrated. CI import failure was fixed by adding the repo root to pytest `pythonpath` alongside `src`, allowing `services.process_diagram` imports in Azure Pipelines.
- Validation: `npm run build` passed with the existing Vite chunk-size warning; full `.venv/bin/python -m pytest` passed (197 tests, 1 existing Starlette/httpx warning); `.venv/bin/python -m ruff check .` passed; `git diff --check` passed. Bug #1000 is Resolved in ADO.
- Open / next: Human should retest Avatar Lab layout and walkthrough scrolling with Anam connected. Next pipeline run should confirm the Azure backend test import failure is gone.
- Next owner: Human for UAT/pipeline observation; Codex for any further viewport tuning.
- Cautions: Auto-scroll centres the active process node inside the scrollable SVG frame using the rendered SVG scale. If future diagram rendering changes away from SVG viewBox scaling, retest this centring logic.

### 2026-06-23 20:05 — Codex (Avatar Walkthrough Natural Narration and Pacing)
- Tickets touched: bug #999, related #986.
- Done: Implemented #999 in commit `efc6971` (`Fix #999 natural Avatar walkthrough pacing`). Avatar process walkthrough narration now combines anchored role, action, system, control and risk nodes into natural business sentences rather than reading "Process / Who / System" labels separately. Example shape: "Category Buyer fills in the supplier setup form in Excel." Walkthrough timing is now slower and more proportional to word count, with a larger pause between spoken step read-outs and the next visual reveal.
- Validation: `npm run build` passed with the existing Vite chunk-size warning; `git diff --check` passed. Bug #999 is Resolved in ADO.
- Open / next: Human should retest with Anam connected and confirm that each spoken step finishes before the next row is drawn.
- Next owner: Human for UAT; Codex for further timing calibration if Anam still cuts off.
- Cautions: This is frontend pacing only. If Anam exposes a documented reliable speech-complete event, future work should replace the conservative word-count fallback with that event plus a small settle delay.

### 2026-06-23 19:53 — Codex (General Natural Spoken Renderer)
- Tickets touched: bug #998, related #991, #996 and #997.
- Done: Implemented #998 in commit `0c4b079` (`Fix #998 generalise natural Avatar rendering`). Natural spoken mode now uses a general constrained LLM renderer over the canonical RAG answer for all non-refusal Avatar answers. The renderer is style-only, preserves valid citation markers, rejects invented citation markers, and falls back to deterministic natural rendering if the model rewrite is unavailable or invalid. The supplier-specific primary template has been removed; supplier setup now goes through the same Natural renderer as other answer types.
- Validation: `npm run build` passed with the existing Vite chunk-size warning; `.venv/bin/python -m pytest tests/test_avatar.py tests/test_answer.py tests/test_process_diagram_integration.py tests/test_process_diagram_service.py` passed (33 tests, 1 existing Starlette/httpx warning); `.venv/bin/python -m ruff check .` passed; `git diff --check` passed.
- Open / next: Human should retest Natural style with supplier setup and at least one non-supplier process question, then compare against Formal using the toggle.
- Next owner: Human for UAT; Codex for any prompt tuning.
- Cautions: This supersedes the earlier note that Natural spoken was supplier-template-specific. The remaining known issue is still the **Start walkthrough** pacing, which can outrun Anam voice delivery and should be handled separately.

### 2026-06-23 19:45 — Codex (Avatar Style Toggle)
- Tickets touched: task #997, related #991 and bug #996.
- Done: Implemented #997 in commit `8e19f79` (`Add #997 Avatar style toggle`). Replaced the Avatar Lab style dropdown with a segmented **Natural / Formal** toggle. Natural remains selected by default; Formal remains available for exact approved-answer checks. Task #997 is Closed in ADO.
- Validation: `npm run build` passed with the existing Vite chunk-size warning; `git diff --check` passed.
- Open / next: Human should retest Avatar Lab and confirm the toggle is clearer than the previous dropdown.
- Next owner: Human for UI review; Codex for any visual polish.
- Cautions: Natural spoken is not hardcoded to one exact question string, but the current supplier setup polish uses a supplier-process-specific deterministic template. If a broader style engine is needed for all process types, create a separate story to generalise Natural spoken narration across domains.

### 2026-06-23 19:39 — Codex (Avatar Natural Spoken Supplier Polish)
- Tickets touched: bug #996, related #991.
- Done: Created and resolved UAT bug #996 in commit `ae2102d` (`Fix #996 natural spoken supplier overview`). `/api/avatar/answer` now defaults to Natural spoken when style is omitted. Supplier setup process answers now render as a stage-based spoken narrative: address-book analogy, trigger/form stage, Trading Support check, due diligence gates, operational/finance creation, identifier mapping, contract/readiness controls and short-version close. The visible numbered list, approved-answer preamble and generic citation-count outro are removed for this supplier process case.
- Validation: `npm run build` passed with the existing Vite chunk-size warning; `.venv/bin/python -m pytest tests/test_avatar.py tests/test_answer.py tests/test_process_diagram_integration.py tests/test_process_diagram_service.py` passed (31 tests, 1 existing Starlette/httpx warning); `.venv/bin/python -m ruff check .` passed; `git diff --check` passed.
- Open / next: Human should retest Avatar Lab with `Can you tell me how to setup supplier?` after restarting the backend/frontend so the running services load commit `ae2102d`.
- Next owner: Human for UAT; Codex for language calibration if the tone still needs tuning.
- Cautions: Walkthrough pacing is intentionally not changed in this fix. The remaining issue is that **Start walkthrough** can still outrun Anam voice delivery; handle that as a separate timing/pacing bug when ready.

### 2026-06-23 19:29 — Codex (Avatar Natural Overview and Opt-in Walkthrough)
- Tickets touched: #991, tasks #992-#995, related #986.
- Done: Implemented #991 in commit `5c21090` (`Make avatar process walkthrough opt-in`). Avatar Lab now defaults to Natural spoken style, passes the user question into the avatar renderer, converts numbered process answers into a plain-language spoken overview while preserving available citation markers, and offers a related process map only after the answer is finished. The step-by-step diagram reveal now starts only when the user clicks **Start walkthrough**. Tasks #992-#995 are Closed and #991 is Resolved in ADO.
- Validation: `npm run build` passed with the existing Vite chunk-size warning; `.venv/bin/python -m pytest tests/test_avatar.py tests/test_answer.py tests/test_process_diagram_integration.py tests/test_process_diagram_service.py` passed (30 tests, 1 existing Starlette/httpx warning); `.venv/bin/python -m ruff check .` passed; `git diff --check` passed.
- Open / next: Human should test Avatar Lab with `Can you tell me how to setup supplier?` and confirm the first response sounds like a helpful overview, then choose **Start walkthrough** only when a step-by-step map is wanted.
- Next owner: Human for UAT; Codex for any pacing/language calibration.
- Cautions: Anam remains render-only. The app listens for likely Anam speech-complete events when available, then falls back to conservative word-count timing so diagram steps do not advance too quickly. If Anam exposes a documented completion event later, wire that event explicitly and reduce the fallback delay.

### 2026-06-23 19:11 — Codex (Avatar Walkthrough Pacing Fix)
- Tickets touched: #986, bug #990.
- Done: Fixed UAT issue where the Avatar process walkthrough drew too quickly and Anam only audibly delivered the final line. Commit `587b4ad` (`Pace Avatar process walkthrough narration`) adds cancellable playback tokens, a delayed start to avoid React StrictMode duplicate-effect races, and per-step estimated speech-duration holds so the drawing cannot advance faster than narration delivery. Bug #990 is Resolved in ADO and #986 history was updated.
- Validation: `npm run build` passed with the existing Vite chunk-size warning; `.venv/bin/python -m pytest tests/test_avatar.py tests/test_answer.py tests/test_process_diagram_integration.py tests/test_process_diagram_service.py` passed (29 tests, 1 existing Starlette/httpx warning); `.venv/bin/python -m ruff check .` passed; `git diff --check` passed.
- Open / next: Human should re-test Avatar Lab with Anam connected and confirm each row reveal waits for the spoken narration before advancing.
- Next owner: Human for UAT re-test; Codex for any further timing calibration.
- Cautions: Anam `talk()` may return when speech is queued rather than fully spoken. Keep UI pacing authoritative unless the SDK exposes a reliable speech-complete event.

### 2026-06-23 19:00 — Codex (Avatar Animated Process Walkthrough)
- Tickets touched: #986, tasks #987-#989, parent #743.
- Done: Implemented #986 in commit `86ba3e1` (`Add animated Avatar process walkthrough`). Added a typed `AnimatedProcessDiagramPanel` that renders the local diagram chart JSON directly, reveals process rows cumulatively, displays row narration, and sends the same narration to Anam when the avatar is connected. Avatar Lab now waits until the grounded answer has been spoken before starting the animated process walkthrough. Ask page static diagram behaviour is unchanged. Tasks #987-#989 are Closed and #986 is Resolved in ADO.
- Validation: `npm run build` passed with the existing Vite chunk-size warning; `.venv/bin/python -m pytest tests/test_process_diagram_service.py tests/test_process_diagram_integration.py tests/test_avatar.py tests/test_answer.py` passed (29 tests, 1 existing Starlette/httpx warning); `.venv/bin/python -m ruff check .` passed; `git diff --check` passed.
- Open / next: Human should test Avatar Lab with a process question that resolves a map, confirm the grounded answer speaks first, then confirm the process walkthrough reveals step-by-step with Who/System/Control narration.
- Next owner: Human for visual/UAT review; Codex for any playback pacing or shape refinements.
- Cautions: Anam remains render-only. The walkthrough narration is deterministic application-generated text from the diagram chart context; it is not autonomous Anam reasoning. If Anam is not connected, the same walkthrough still plays visually at a readable fixed pace.

### 2026-06-23 18:48 — Codex (Diagram Renderer Reference Styling)
- Tickets touched: #966, task #985.
- Done: Restyled the independent local diagram renderer in commit `836787b` (`Restyle local diagrams as row-based flowcharts`). The SVG output now follows the supplied reference style: no swimlane bands, green process steps in a central vertical flow, yellow Who cards aligned to the right of task rows, blue System cards aligned to the left of related steps, purple start/end event hexagons, and compact gateway circles. Updated examples and layout tests. Task #985 is Closed in ADO.
- Validation: `.venv/bin/python -m pytest tests/test_process_diagram_service.py tests/test_process_diagram_integration.py tests/test_process_maps.py tests/test_avatar.py tests/test_answer.py` passed (35 tests, 1 existing Starlette/httpx warning); `.venv/bin/python -m ruff check .` passed; `git diff --check` passed. Generated `http://127.0.0.1:5300/examples/supplier-setup/svg` and rasterised it locally for visual inspection.
- Open / next: Human should review `http://127.0.0.1:5300/examples` and confirm whether the new visual language is close enough before any further drawing-shape refinements.
- Next owner: Human for visual review; Codex for any styling tweaks.
- Cautions: The renderer still uses deterministic layout. Multi-system or multi-role rows stack around the related process step rather than manually routing every connector like a hand-drawn diagram.

### 2026-06-23 18:08 — Codex (Diagram Service Visual Examples)
- Tickets touched: #745, task #984.
- Done: Added a browser-friendly local diagram examples gallery in commit `d387a40` (`Add diagram service visual examples gallery`). The independent diagram service now exposes `/examples`, `/examples/index`, `/examples/{id}/svg`, `/examples/{id}/json`, and `/examples/{id}/payload` using built-in supplier setup, article tax handling, and knowledge governance examples. Task #984 is Closed in ADO and #745 history was updated.
- Validation: `.venv/bin/python -m pytest tests/test_process_diagram_service.py tests/test_process_diagram_integration.py` passed (11 tests, 1 existing Starlette/httpx warning); `.venv/bin/python -m ruff check .` passed; `git diff --check` passed.
- Open / next: Human can view the gallery at `http://127.0.0.1:5300/examples` while the service is running. Direct SVG samples: `/examples/supplier-setup/svg`, `/examples/article-tax-handling/svg`, `/examples/knowledge-governance/svg`.
- Next owner: Human for visual review/UAT feedback.
- Cautions: If `/examples` returns 404, restart the diagram service with `--reload`; an old non-reload process will not have the gallery routes.

### 2026-06-23 17:53 — Codex (Ask/Avatar Local Process Map Integration)
- Tickets touched: #745, tasks #975-#980, UAT cases #981-#983, parent #743.
- Done: Implemented #745 in commit `9358a07` (`Integrate local process diagrams into answers`). Added backend `/api/process/diagrams/resolve`, process-registry-to-local-diagram payload conversion, local service failure handling, reusable frontend `ProcessDiagramPanel`, Ask page related-map display beside answer evidence, and Avatar Lab process-map display beside rendered response. Tasks #975-#980 are Closed and #745 is Resolved in ADO.
- Validation: `.venv/bin/python -m pytest tests/test_process_diagram_integration.py tests/test_process_diagram_service.py tests/test_process_maps.py tests/test_avatar.py tests/test_answer.py` passed (34 tests, 1 existing Starlette/httpx warning); `.venv/bin/python -m ruff check .` passed; `npm run build` passed with the existing Vite chunk-size warning; `git diff --check` passed.
- Open / next: Human should run UAT cases #981-#983 in suite #890. To inspect how diagrams are generated directly, use the standalone local service Swagger UI at `http://127.0.0.1:5300/docs` while the service is running. The app surfaces diagrams in Ask and Avatar Lab after the backend has loaded commit `9358a07`.
- Next owner: Human for UAT/closure of #745; Codex for any UAT fixes.
- Cautions: The diagram service remains independent and deterministic. It is a draft visualisation layer over the approved process registry, not a separate answer source. If the backend process currently running on port 8010 was started without reload, restart it before testing `/api/process/diagrams/resolve`.

### 2026-06-23 17:05 — Codex (Local Process Diagram Microservice)
- Tickets touched: #743, #966, tasks #967-#971, UAT cases #972-#974.
- Done: Pivoted Feature #743 from Lucid-first wording to local diagram engine direction. Implemented #966 in commit `df71de2` (`Add local process diagram microservice`): independent `services.process_diagram` FastAPI service, `/health`, `/process-chart/render`, `/process-chart/render.svg`, strict diagram schemas, deterministic narrative-to-model conversion, validation, lane-aware layout, animation/narration timeline, SVG renderer, service README and regression tests. Added follow-up commit `eef2df8` (`Refine diagram service lane parsing`) so explicit lane labels are retained, repeated lanes preserve order, and conditional If/Whether clauses do not become owner swimlanes. Tasks #967-#971 are Closed and #966 is Resolved in ADO.
- Validation: `.venv/bin/python -m pytest tests/test_process_diagram_service.py tests/test_process_maps.py` passed (11 tests, 1 existing Starlette/httpx warning); `.venv/bin/python -m ruff check .` passed; `git diff --check` passed.
- Open / next: Human should run UAT cases #972-#974 in suite #890. Next logical development slice is to integrate the local service into #745 so Ask/Avatar can display a related diagram beside answers, replacing the Lucid dependency for preview use.
- Next owner: Human for UAT/closure of #966; Codex for #745 integration or UAT fixes.
- Cautions: The current narrative parser is deterministic heuristic MVP, not a local LLM adapter yet. Treat generated diagrams as reviewable drafts; the structured JSON remains the source of truth.

### 2026-06-23 16:25 — Codex (Avatar Spoken-Answer Style Modes)
- Tickets touched: #951; tasks #957-#962; UAT cases #963-#965; parent #756.
- Done: Implemented #951 in commit `d1867ad` (`Add avatar spoken answer style modes`). Added `/api/avatar/answer`, which calls the same grounded `AnswerService` and returns both canonical answer metadata and avatar-rendered text. Added Formal mode (exact answer), Natural spoken mode (safe signposting/follow-up for answered responses), exact refusal preservation, Avatar Lab style selector, transcript metadata, latest rendered response display and regression tests. Tasks #957-#962 are Closed and #951 is Resolved in ADO.
- Validation: `.venv/bin/python -m pytest tests/test_avatar.py tests/test_answer.py` passed (18 tests, 1 existing Starlette/httpx warning); `.venv/bin/python -m ruff check .` passed; `npm run build` passed with the existing Vite chunk-size warning; `git diff --check` passed.
- Open / next: Human should run UAT cases #963-#965 in suite #890. Parent Feature #756 remains Active because other Avatar/Lucid-adjacent work may still be open/parked.
- Next owner: Human for UAT/closure of #951; Codex for any UAT fixes.
- Cautions: Natural spoken mode is deterministic presentation only. It must not become a second agent, summariser or uncontrolled paraphraser; Anam remains render-only and input audio stays disabled.

### 2026-06-23 15:35 — Codex (Historical Simulator and Synthetic Value Trends)
- Tickets touched: #945, #946, parent Features #756 and #767.
- Done: Implemented #945 in commit `35de574`: `/api/simulator/period-runs`, preset/custom historical periods, usage density/patterns, deterministic past synthetic timestamps, period-batch QA metadata, Simulator period controls, recent-run type labels, and real/synthetic query trend separation. Implemented #946 in commit `1b08583`: historical simulator batches now emit compact synthetic value events; Value analytics separates observed real value from synthetic pilot value, monthly trend rows and annualised projections; Analytics Value view shows observed/synthetic/projection cards and monthly trend chart. ADO #945 and #946 moved to Resolved.
- Open / next: Human UAT should run a period batch from Simulator, then check Analytics Summary and Analytics Value. Parent #756 remains Active because #951 is still New; parent #767 remains Active because #949/#778/#775 are still New.
- Next owner: Human for UAT/closure of #945/#946; Codex can continue with #949 value assumptions matrix or #951 Avatar spoken-answer style modes if Human wants more Sprint 2 pull-forward work.
- Cautions: Synthetic value projections are pilot replay evidence only. They are separated from observed/operator value and must not be presented as audited savings.

### 2026-06-23 15:18 — Codex (Analytics Information Architecture)
- Tickets touched: #944, #947, #948, #745.
- Done: Parked #745 pending Lucid API/trial access after Human confirmed current licence does not include API. Implemented Analytics split in commit `30a7945`: Summary, Value, Validation/KSB, Governance Gaps, Process Complexity and Process Detail views, stable `#analytics-*` hash references, and explanatory insight panels. ADO #944/#947/#948 moved to Resolved with build/lint evidence.
- Open / next: Human UAT for Analytics focused views. Next non-Lucid candidate is #945/#946 for historical simulator periods and value trend projection from simulated usage.
- Next owner: Codex for next build slice unless Human redirects; Human for UAT/closure of #944/#947/#948.
- Cautions: This was a frontend IA refactor only. It does not change analytics calculations or stored event data.

### 2026-06-23 14:53 — Codex (Lucidchart Process Map Integration)
- Tickets touched: #744.
- Done: Implemented Lucidchart Standard Import generation for Process Registry maps in commit `1ee9a1d`. Added `.lucid` ZIP/archive builder, protected Lucid config/download/create API endpoints, Process Registry UI actions for `Download .lucid` and `Create in Lucid`, batch exporter `.lucid` output, regression tests, and Lucid integration documentation. ADO #744 moved to Resolved with verification notes.
- Open / next: Human should add `LUCID_API_KEY` to backend `.env` and restart backend before testing live `Create in Lucid`. Optional `LUCID_PARENT_FOLDER_ID` can route created diagrams to a Lucid folder. Offline `.lucid` download is ready for immediate import/UAT in Lucid.
- Next owner: Human for premium Lucid import/API UAT; Codex for any layout/API fixes that come out of testing.
- Cautions: Live Lucid API create was not exercised because no Lucid credentials are currently configured. The first integration uses Lucid Standard Import, not a Lucid editor extension or embedded viewer; embedding next to Avatar transcript remains a later slice.

### 2026-06-23 15:55 — Codex (Value Assumptions Scenario Matrix)
- Tickets touched: #949, parent #767.
- Done: Implemented #949 and resolved it in ADO. Added a backend `assumption_matrix` projection generated from the versioned value assumptions ledger, preserving the original flat ledger as the source of truth. The Value page now shows a scenario comparison matrix with drivers/assumptions as rows and Conservative, P50 base and Stretch scenarios as columns; each cell carries value, confidence, rationale and source evidence. Added frontend API typing, table styling and regression coverage. Commit: `cbdb2cc` (`Add value assumptions scenario matrix`).
- Validation: `.venv/bin/python -m pytest tests/test_value_analytics.py` passed (5 tests, 1 existing Starlette/httpx warning); `.venv/bin/python -m ruff check .` passed; `npm run build` passed with the existing Vite chunk-size warning; `git diff --check` passed.
- Open / next: Parent Feature #767 remains Active because #778 and #775 are still open. The next logical value-analytics pull is one of those remaining children unless Human redirects to a different priority.
- Next owner: Human for UAT of the matrix; Codex for any UAT fixes or the next value analytics child.
- Cautions: Matrix values are still assumption-led and illustrative. Do not treat them as audited savings; use observed/synthetic telemetry separately when comparing assumptions with evidence.

### 2026-06-23 00:30 — Codex (Process Stress-Test Simulation Lab)
- Tickets touched: #798, #802, #805, tasks #924-#929, parent #797.
- Done: Pulled #798/#802/#805 into Sprint 2 with effort estimates and tasks #924-#929; aligned Feature #797 to Sprint 2 dates. Added process stress-rule extraction, deterministic scenario simulator, `/api/process/stress-test`, Process Registry stress-test lab UI, method documentation and regression tests.
- Open / next: Commit and close ADO #798/#802/#805/tasks after final evidence is attached. Sprint 2 pulled-forward development queue from the recommended order is now implemented pending UAT.
- Next owner: Human for UAT planning/execution after Codex creates/updates UAT scenarios.
- Cautions: Stress-test results are scenario-planning indicators from extracted registry fields, not production forecasts, queueing models or staffing calculators.

### 2026-06-23 00:25 — Codex (Exportable Analytics Evidence Report)
- Tickets touched: #742, #815, tasks #919-#923, parents #741 and #808.
- Done: Pulled #742/#815 into Sprint 2 with effort estimates and tasks #919-#923; aligned parent Features #741/#808 to Sprint 2 dates. Added export-safe markdown analytics report builder, `/api/analytics/report.md`, Analytics page export action, final analytics method write-up and report regression tests.
- Open / next: Commit and close ADO #742/#815/tasks after final evidence is attached. Next recommended pull order is #798/#802/#805 process stress-test simulation lab.
- Next owner: Codex.
- Cautions: The exported report intentionally avoids raw source text, generated answers and full prompt/answer traces. The final method write-up still frames value/regulatory/process analytics as evidence method, not verified enterprise outcome.

### 2026-06-23 00:21 — Codex (KSB Traceability and Validation Evidence)
- Tickets touched: #809, #812, tasks #913-#918, parent #808.
- Done: Pulled #809/#812 into Sprint 2 with 5 effort each and created tasks #913-#918; aligned Feature #808 to Sprint 2 dates. Added project KSB-style traceability rows, analytics/model validation protocol catalogue, `/api/analytics/validation-evidence`, Analytics page validation/KSB evidence sections, docs and regression tests.
- Open / next: Commit and close ADO #809/#812/tasks after final evidence is attached. Next recommended pull order is #742/#815 exportable analytics report and final analytics method write-up.
- Next owner: Codex.
- Cautions: KSB row IDs are project evidence IDs until the official assessment KSB mapping is supplied. Validation protocols are evidence discipline, not proof of legal, financial or operational certainty.

### 2026-06-23 00:08 — Codex (Regulatory Impact Simulation)
- Tickets touched: #790, tasks #909-#912, parent #781.
- Done: Pulled #790 into Sprint 2 with 8 effort and tasks #909-#912; aligned Feature #781 to Sprint 2 dates. Implemented deterministic regulatory change-impact simulation over approved sources and GOV.UK snapshot context, added `/api/regulatory/candidates/{candidate_id}/impact-simulation`, added `regulatory_impact_simulated` analytics events, and added Governance UI controls/results for candidate impact simulation.
- Open / next: Commit and close ADO #790/tasks after final evidence is attached. Next recommended pull order is #809/#812 KSB traceability and analytics/model validation protocol.
- Next owner: Codex.
- Cautions: Impact simulation is triage only. It must not be presented as legal advice, confirmed regulatory change, or proof that an operating process has changed.

### 2026-06-23 00:01 — Codex (Sprint 2 Value Analytics)
- Tickets touched: #764, #768, #771, tasks #900-#908, parent #767.
- Done: Completed #764 simulator QA/replay controls and updated ADO (#900-#902 Closed, #764 Resolved). Pulled #768/#771 into Sprint 2, estimated each at 5 effort, created child tasks #903-#908, and aligned Feature #767 to Sprint 2 dates. Implemented the value assumptions ledger and value dashboard slice: seeded scenario taxonomy, `/api/analytics/value`, `/api/analytics/value/events`, Analytics page scenario chart, assumptions table and value-event capture.
- Open / next: Finish ADO closure for #768/#771 after commit and test evidence are attached, then continue to #790 regulatory change-impact simulation workflow.
- Next owner: Codex.
- Cautions: Value figures are still assumption-led and illustrative until validated with live enterprise telemetry. Value events must remain aggregate only; do not store raw prompts, answers, source text or commercially sensitive detail in `value_event_recorded` metadata.

### 2026-06-22 19:32 — Codex (Sprint 2 Scope Expansion / UAT Closure)
- Tickets touched: closed #25, #39, #43, #608, #609, #613, #616, #704, #711, #714, #726, #728, #729, #730, #833, #834; moved #639, #643, #656, #669, #757, #760, #782 and child tasks #640-#647, #657-#661, #670-#672, #758-#763, #783-#785.
- Done: Closed UAT-passed Sprint 2 resolved items after Human acceptance. Expanded Sprint 2 by another 24 story points, bringing the open Sprint 2 User Story/Bug load to 49 points. Moved dependency-safe chunks: hallucination/groundedness validation, industry decision-rationale evidence, second anonymised data pack, regulatory candidate discovery, and simulator personas plus runner together. Added Original Estimate values to previously unsized moved tasks.
- Open / next: Sprint 2 execution queue is now broad. Suggested build order: #727 analytics aggregation, #752 governance history, #732/#733 diagnostics, #786/#782 external/regulatory base, then #639/#643 validation and #757/#760 simulator.
- Next owner: Codex for execution unless Human redirects.
- Cautions: #662 was set back to Active because it now has open child #669. Parent spans updated: #638/#655 Sprint 2 only; #662 Sprint 1-2; #756 Sprint 2-5; #781 Sprint 2-7; #113 Sprint 1-3; #114 Sprint 1-2.

### 2026-06-22 19:24 — Codex (Sprint Planning / Pull-Forward)
- Tickets touched: #849, #725, #727, #731, #732, #733, #752, #781, #786, #749-#751, #753-#755, #787-#789, #850-#857.
- Done: Closed #849 after Human UAT pass. Pulled 25 story points of Codex-owned build work into Sprint 2: analytics aggregation/history (#727), diagnostic analytics (#732, #733, #752) and the first external-data-source slice via GOV.UK snapshots (#786). Created estimated implementation tasks #850-#857 for #732 and #733 so the stories are executable in Sprint 2.
- Open / next: Sprint 2 now has a substantial build queue. Natural execution order is #727 first, then #752/#732/#733, then #786 once the analytics aggregation foundation is stable.
- Next owner: Codex for build stories; Claude remains review owner on parent Features #725, #731 and #781.
- Cautions: Parent Feature spans were updated by child sprint rule: #725 and #731 now span Sprint 2 only; #781 starts Sprint 2 and still ends Sprint 7 because later regulatory/external-context children remain in future sprints.

### 2026-06-22 19:07 — Codex (UAT Bug Fix)
- Tickets touched: #849, Test Case #844, Test Run #43.
- Done: Reviewed the failed Sprint 2 UAT comment for `S2 UAT 08 - Duplicate review and auto-remediation suggestion`, recorded bug #849, and fixed the zero-section ingestion path. Heading-only or otherwise sectionless content now fails ingestion with a clear operator-visible error, clears stale sections, and records the source as `failed` rather than `ingested`. Governance now explains registered, failed, and defensive ingested-with-zero-section states distinctly.
- Open / next: Human should re-run Test Case #844 after the fix is deployed/pulled, using duplicate markdown files with real body content under the headings.
- Next owner: Human for UAT re-test; Codex/Claude if #849 needs follow-up.
- Cautions: A source can still be `not_ingested` in Governance when it is merely registered; for failed ingestion, the issue detail now points to fixing content and ingesting again.

### 2026-06-22 18:08 — Codex (Build/UAT Setup)
- Tickets touched: Azure Test Plans only; Sprint 2 delivery items referenced in UAT.
- Done: Created Azure Test Plan #835 `Sprint 2 UAT - Governance Workbench, Data Pack Onboarding and Analytics Foundation`, root suite #836, with frontend-focused manual test cases #837-#848. Cases cover launch/navigation, source upload/ingest, governance approval, Ask/citations, Process Registry, governance issue detection/review/acceptance, duplicate remediation, Analytics charts, guardrail wording #834, Settings audit trace and source cleanup.
- Open / next: Human to run the UAT cases in Azure Test Plans. Passing cases can support closing Sprint 2 Resolved items; failed cases should result in bugs.
- Next owner: Human for UAT.
- Cautions: The tests intentionally avoid backend/API inspection. One Process Registry case notes that if an approved source was added during the same session and the page remains empty, a normal app restart may be needed because the registry is built from approved sources at app startup.

### 2026-06-22 17:50 — Codex (Build)
- Tickets touched: #726, #746, #747, #748, #834, #39, #40, #41, #42, #43, #44, #45, #46, #833, #664, #666, #667, plus parent state updates #25, #662, #725.
- Done: Completed Sprint 2 analytics event foundation: event schema/taxonomy (`9df1c61`), append-only JSONL event store (`72d57f4`), lifecycle instrumentation (`d753398`). Found and fixed guardrail wording bug #834 (`a78ac1b`). Completed data governance and supplier setup pack evidence: synthetic rules (`1838162`), anonymisation rules (`5d254a0`), source register template (`7d0ad99`), supplier setup overview (`7f2801a`), roles (`7b4eafe`), steps (`070175e`), structured JSON records (`c9bac8a`), metadata register (`008c494`), anonymisation validation (`3c15721`).
- Open / next: Sprint 2 delivery items are Resolved/Closed for UAT; only cross-sprint parents #724 and #725 remain Active. Next natural work is Sprint 2 UAT suite for the new analytics ledger + data-pack governance evidence, then close after human UAT.
- Next owner: Human for UAT; Claude/Codex for any UAT fixes.
- Cautions: `packs/` is intentionally git-ignored local source data, so tracked Sprint 2 data-pack evidence was placed under `docs/data-and-governance/learning-packs/supplier-setup/`. Analytics events intentionally avoid raw source text, raw questions/prompts, generated answers and issue detail.

### 2026-06-20 — Claude (Coordination)
- Tickets touched: — (governance setup, pre-backlog)
- Done: Created the **Ways-of-Working** Wiki section — [Working Agreement](/Ways-of-Working/Agent-Collaboration), this Handover Log, [Definition of Done](/Ways-of-Working/Definition-of-Done), [Effort Sizing](/Ways-of-Working/Effort-Sizing), [Build Governance](/Ways-of-Working/Build-Governance). Established the agent operating model for this project; handovers now live here (not in tickets); Antigravity's lane defined with explicit MUST-NOTs.
- Open / next: Human to review the Working Agreement (especially the Antigravity scope) and confirm. Per-agent **settings** enforcement of the "read-first" rule is still to be configured.
- Next owner: Human (review)
- Cautions: This is the new handover mechanism — update each agent's settings so its first step is to read the Working Agreement + this Log.
