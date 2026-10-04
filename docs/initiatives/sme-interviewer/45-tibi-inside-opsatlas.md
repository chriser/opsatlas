# Tibi inside the OpsAtlas control panel

**25 September 2026 · Built by Claude · Stories #1732 (S157), #1737 (S158) and #1739 (S159) under F17 · Status: delivered for the Human's evaluation on branch `claude/tiberius-speed-safety`; nothing is merged to `main` until the Human accepts it.**

## Why

The Human asked for Tibi's review workflow to be part of OpsAtlas rather than separate pages. Offered the choice, they chose **everything**:
- talking with Tibi and reviewing its knowledge become control-panel pages;
- governance interview answers are approved on the Governance page;
- the separate pages retire.

## Where things are now

All pages are in the OpsAtlas control panel at http://127.0.0.1:8780, behind the usual OpsAtlas sign-in.

| Page | What it holds |
|---|---|
| **Tibi → Talk with Tibi** (`#tibi`) | Chat, product interviews and governance interviews, by voice or by typing. A native control-panel page since S159. |
| **Tibi → Tibi knowledge** (`#tibi-knowledge`) | Everything the separate Knowledge review page offered, in the control panel's own style: interview contributions (propose wording), spoken answers (draft, approve, reject), conversation style, the product ontology, and product records (enable or exclude, inspect originals, relationship decisions for contributed claims). |
| **Governance** | A new **Resolve issues with Tibi** panel above the Quick Scan: the open count, answers waiting for approval with their verification, and **Approve and close the issue** or **Reject**. **Resolve with Tibi** opens Talk with Tibi in governance-interview mode. |

- **Old addresses.** Any page address on the Tibi service (http://127.0.0.1:8773/, `/knowledge`, `/conversation`) redirects to the matching OpsAtlas page.
- **Links from Tibi.** A source link inside Tibi opens Tibi knowledge at that record (`#tibi-knowledge:<record>`).
- **The workspace banner** now links to Talk with Tibi.

## How it is built

This section describes the design as of S159. S157 and S158 embedded the Tibi service's conversation page; S159 replaced that with a native page and made Tibi a microservice.

- **Control panel** (`frontend/src`):
  - `TibiPage`, `TibiKnowledgePage` and `TibiGovernancePanel`, with a Tibi group in the sidebar. The group appears only when the workspace runs Tibi, so the main OpsAtlas is unchanged.
  - `TibiPage` is a native React page. Its voice client (`tibi/voice.ts`, `tibi/timing.ts` and the `tibi-voice-worklet.js` audio worklet) speaks Tibi's conversation protocol directly.
  - Pages have addresses (`#governance`, `#tibi`, `#tibi-knowledge:<record>`) that can be bookmarked and linked.
- **Sales core API** (`services/opsatlas_sales/tibi_api.py`):
  - The knowledge, governance and ontology operations are under `/api/tibi/*` behind the OpsAtlas operator sign-in.
  - They call the same `Knowledge` and `GovernanceDesk` methods, so nothing approves on its own.
  - `/api/tibi/status` asks the Tibi service's health endpoint over HTTP.
- **The gateway** (`services/opsatlas_sales/tibi_proxy.py`, `/services/tibi/api/*`): the only way the control panel reaches the Tibi service; see S159 below.
- **The Tibi service** (`sales_preview.py`): an API only; see S159 below.

## Checked

- **Tests.** 955 Python tests pass on 3.11 and 3.12, and 58 browser tests pass. The control panel builds, including the TypeScript check. New tests cover:
  - every Tibi endpoint refusing requests without the operator sign-in;
  - record and governance reviews through the control-panel API;
  - server-bound attribution for proposals;
  - the voice service's redirects and framing policy.
- **Browser check** on a throwaway workspace with its own generated key, so the Human's sign-in was not used:
  - The Tibi group and both pages render.
  - Enabling a record works, and the count moves from 0 to 1 of 27.
  - The Governance page shows the Tibi panel (22 open for Tibi).
  - **Resolve with Tibi** opens the embedded conversation already set to *Resolve governance issues*, with no console errors.
- **Live services** were restarted on the branch, and the start script now prints the OpsAtlas addresses.

## The OpsAtlas look and one audio devices card (S158)

Before trying Tibi in the control panel, the Human asked for three things:
- the embedded page should look like the rest of OpsAtlas;
- the microphone and speaker should be chosen in one place, keeping the choice and preferring the Jabra Bluetooth headset;
- the local-storage consent checkbox should go, because the operator does not need to caveat their own work.

**Now:**
- **The OpsAtlas look.** The embedded conversation uses the control panel's font, colours, panels, fields and pink primary buttons (`web/tibi-embed.css`, applied only inside OpsAtlas). Its own header and large intro are hidden, because the OpsAtlas page has them. Labels are in sentence case, and the session choices (mode, contributor, topic) sit in one row.
- **One Audio devices card.** Microphone and speaker are side by side, with Refresh devices and Test speaker below them.
- **The choice is kept.** The last microphone and speaker chosen are remembered in the browser by device name, because device IDs change between sessions.
- **Jabra is preferred.** Until a device has been chosen, a Jabra device is preferred, a Bluetooth one first. Browsers reveal device names only after microphone permission is granted, so the preference applies from the first session with permission onwards. The list refreshes after permission and whenever a device connects or disconnects.
- **No consent box or caveat notes.** Tibi still stores the conversation locally as before; the operator no longer has to tick a box to start.

**Checked.**
- A browser check on a throwaway workspace confirmed the page styling, the two-column devices card at desktop width and all controls intact.
- Injected device names tested the preference: with no saved choice, *Jabra Evolve2 65 (Bluetooth)* was selected; after choosing the built-in microphone, that choice was kept when the list changed.

## Native in the Control Panel; Tibi as a microservice (S159)

In the embedded page, choosing a speaker failed: *"Permissions-Policy disallows speaker selection"*. Chrome does not recognise the `speaker-selection` permission, so a page inside an iframe cannot choose its audio output. The Human asked for Talk with Tibi to be built natively in the Control Panel rather than embedded, and for Tibi to be rebuilt as a microservice.

**Now:**
- **A native page.** Talk with Tibi is a React page in the control panel: session choices, conversation and transcript, the Audio devices card and the evidence for each answer. There is no iframe, and the Tibi service serves no pages.
- **Tibi is its own service.** The Tibi service (port 8773) is an API: health, sessions, the live voice socket, interview contributions and spoken-wording drafts. It keeps its own conversation store. Any page address redirects to the control panel.
- **One way in: the OpsAtlas gateway.** The control panel reaches Tibi only through `/services/tibi/api/*` on its own origin:
  - The gateway requires the OpsAtlas operator sign-in on every call. On the live voice socket, the sign-in comes in the first message, because a browser socket cannot send a sign-in header.
  - It forwards only Tibi's API, and passes Tibi's own session token unchanged, so Tibi's own checks still apply.
  - It passes Tibi's close codes back to the page (for example, a refused sign-in).
  - It stores nothing.
- **No shortcuts between the services.** OpsAtlas no longer imports Tibi or reads its database:
  - Contributions come from the Tibi service's API.
  - Proposals and spoken-wording drafts are made by the Tibi service, which calls OpsAtlas's workspace API with the workspace key.
  - A proposal's contributor and original wording still come from the saved interview, never from the browser.
- **Speaker selection works** because the page and the audio are on the control panel's own origin.
- **When Tibi is not running,** Talk with Tibi says so, and the gateway answers *Tibi is not running* instead of failing.

**Checked.**
- **Tests.** 958 Python tests pass on 3.11 and 3.12, and 58 browser tests pass. The control panel builds. New or rewritten tests cover:
  - the gateway refusing calls without the sign-in, while Tibi's own session-token check still applies;
  - the live socket needing the sign-in in its first message, refusing a foreign origin, and passing Tibi's close code;
  - a stopped Tibi service reported as unavailable;
  - the Tibi service serving no pages;
  - proposal attribution taken from the saved interview on the Tibi service.
- **Browser check** on a throwaway workspace with its own generated key:
  - The native page rendered and a typed chat ran end to end through the gateway (greeting, a question, and the governed answer, since no records were enabled).
  - Speaker selection (`setSinkId`) was allowed, with no iframes on the page.
  - Tibi knowledge loaded contributions from the Tibi service.
  - The gateway answered 401 without the sign-in.
- **Live services** were restarted on the branch. The Tibi service reports healthy, and the gateway refuses unsigned calls.
