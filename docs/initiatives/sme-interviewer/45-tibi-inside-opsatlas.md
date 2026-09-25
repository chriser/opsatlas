# Tibi inside the OpsAtlas control panel

**25 September 2026 · Built by Claude · Story #1732 (S157) under F17 · Status: delivered for the Human's evaluation on branch `claude/tiberius-speed-safety`; nothing is merged to `main` until the Human accepts it.**

## Why

The Human asked for Tibi's review workflow to be part of OpsAtlas rather than separate pages. Offered the choice, they chose **everything**:
- talking with Tibi and reviewing its knowledge become control-panel pages;
- governance interview answers are approved on the Governance page;
- the separate pages retire.

## Where things are now

All pages are in the OpsAtlas control panel at http://127.0.0.1:8780, behind the usual OpsAtlas sign-in.

| Page | What it holds |
|---|---|
| **Tibi → Talk with Tibi** (`#tibi`) | Chat, product interviews and governance interviews, by voice or typed ("Type instead"). |
| **Tibi → Tibi knowledge** (`#tibi-knowledge`) | Everything the separate Knowledge review page offered, in the control panel's own style: interview contributions (propose wording), spoken answers (draft, approve, reject), conversation style, the product ontology, and product records (enable or exclude, inspect originals, relationship decisions for contributed claims). |
| **Governance** | A new **Resolve issues with Tibi** panel above the Quick Scan: the open count, answers waiting for approval with their verification, and **Approve and close the issue** or **Reject**. **Resolve with Tibi** opens Talk with Tibi in governance-interview mode. |

- **Old addresses.** http://127.0.0.1:8773/ and http://127.0.0.1:8773/knowledge now redirect to the matching OpsAtlas page.
- **Links from Tibi.** A source link inside Tibi opens Tibi knowledge at that record (`#tibi-knowledge:<record>`).
- **The workspace banner** now links to Talk with Tibi.

## How it is built

- **Control panel** (`frontend/src`):
  - `TibiPage`, `TibiKnowledgePage` and `TibiGovernancePanel` are new, along with a Tibi group in the sidebar. The group appears only when the workspace runs Tibi, so the main OpsAtlas is unchanged.
  - Pages have addresses (`#governance`, `#tibi`, `#tibi-knowledge:<record>`) that can be bookmarked and linked.
- **Sales core API** (`services/opsatlas_sales/tibi_api.py`):
  - Tibi's operations are available under `/api/tibi/*` behind the OpsAtlas operator sign-in. They were previously reachable only through the voice service with the workspace key.
  - They call the same `Knowledge` and `GovernanceDesk` methods, so nothing approves on its own.
  - Interview contributions are read directly from the voice service's session store, read-only. A proposal's contributor and original wording always come from that saved interview, never from the browser.
- **Voice service** (`sales_preview.py`):
  - It serves only the conversation embedded in OpsAtlas (`embed=1`). The framing policy allows only the OpsAtlas origin.
  - Its separate pages and the review proxies they used are removed; the old Knowledge review page is deleted.
  - The embedded page hides its own header, opens in the mode OpsAtlas asks for (for example a governance interview), and links back into OpsAtlas.

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
