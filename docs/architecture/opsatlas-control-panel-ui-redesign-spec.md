# OpsAtlas Control Panel UI Redesign — Specification & Handover to Claude

**Initiative / Scope:** OpsAtlas Control Panel UI Modernization  
**Author:** Antigravity (Design Prototype & Architecture)  
**Target Implementer / Reviewer:** Claude (Architecture, Review & Backend Coordination)  
**Base Branch:** `claude/tiberius-speed-safety` (commit `339d228`)  
**Design Branch:** `ui/opsatlas-design`  
**Date:** 2026-09-26  

---

## 1. Executive Summary

This specification establishes the new executive design system for the **OpsAtlas Control Panel**, translating operator requirements and reference design inspirations into a high-density, square-edge, modern enterprise console.

### Key Objectives
1. **Modernize Aesthetic**: Transition from a flat, high-contrast dark layout to a luminous working canvas (`#f4f6fa`) with floating white panels, diffused ambient shadows, and purposeful accenting.
2. **Strict Geometric Precision**: Enforce sharp, square edges across all components (`border-radius: 0 !important;`), replacing all rounded corners, pill shapes, and oval badges with crisp square architecture.
3. **Structured Navigation (Top-to-Bottom Long)**: Maintain the long left-hand menu while enhancing it with an operator identity block, category sections, tree connector branches for sub-items, and a docked bottom quick-action card.
4. **Cognitive Clarity for High-Density Operations**: Complex knowledge operations (governance conflicts, citation checks, ontology graphs, telemetry) require clear visual hierarchy without overwhelming the operator.

---

## 2. Design Inspirations & Translation

| Reference Element | Source Concept | OpsAtlas Implementation |
|---|---|---|
| **Luminous Floating Cards** | Sugus Modern UI Reference (`media_1790435260368.png`) | `#ffffff` cards on `#f4f6fa` canvas with multi-layered ambient shadows (`--shadow-md`, `--shadow-hover`), subtle lift on hover (`translateY(-2px)`). |
| **KPI Metric Strips** | Sugus Modern UI Reference | Standardized 4-card metric strip atop the dashboard (Total Queries, Answer Rate, Grounded Rate, Avg Citations) featuring bold typography (`28px`) and uppercase micro-labels (`11px`). |
| **Pastel Category Chips** | Sugus Modern UI Reference | Color-coded status badges with soft pastel backgrounds and saturated square indicator chips (`--blue`, `--purple`, `--pink`, `--green`, `--amber`). |
| **Operator Profile Header** | macOS Pro Sidebar Reference (`media_1790435280675.png`) | Square monogram avatar (`OP`), online status indicator, role descriptor (`PLATFORM OPERATOR`), and console versioning. |
| **Section Categorization** | macOS Pro Sidebar Reference | Uppercase letter-spaced category headers: `MAIN`, `INTELLIGENCE & SPEECH`, `GOVERNANCE & ARCHITECTURE`, `SYSTEM & CONFIGURATION`. |
| **Tree Sub-Navigation** | macOS Pro Sidebar Reference | Structural branch lines (`|-- Sublink`) for collapsible groups (`Ask`, `Tibi`, `System`), visually communicating parent-child hierarchy. |
| **Docked System Card** | macOS Pro Sidebar Reference | Pinned bottom card displaying local system readiness and a direct action CTA button (`Talk with Tibi →` / `Run Query →`). |
| **Square Edge Constraint** | Explicit Operator Mandate | Universal `0px` radius on cards, buttons, inputs, pills, table frames, dropdowns, and badges. |

---

## 3. Design Tokens & Variables

All tokens are defined in `frontend/src/App.css` under `:root`:

```css
:root {
  /* Architecture & Canvas */
  --sidebar: #0b111e;
  --sidebar-dark: #070b14;
  --sidebar-hover: rgba(255, 255, 255, 0.05);
  --sidebar-active: rgba(255, 255, 255, 0.09);
  --sidebar-border: rgba(255, 255, 255, 0.08);
  --sidebar-text: #f8fafc;
  --sidebar-muted: #94a3b8;
  
  --ink: #0f172a;
  --ink-secondary: #334155;
  --muted: #64748b;
  --muted-light: #94a3b8;
  
  --line: #e2e8f0;
  --line-subtle: #f1f5f9;
  --line-strong: #cbd5e1;
  
  --canvas: #f4f6fa;
  --surface: #ffffff;
  --surface-raised: #ffffff;
  --soft: #f8fafc;
  --soft-alt: #f1f5f9;
  
  /* Brand Accents */
  --pink: #f0066f;
  --pink-dark: #d90066;
  --pink-soft: #fff1f6;
  --pink-border: #fecdd3;
  
  --indigo: #6366f1;
  --indigo-soft: #eef2ff;
  --indigo-border: #c7d2fe;
  
  --purple: #8b5cf6;
  --purple-soft: #f5f3ff;
  --purple-border: #ddd6fe;
  
  --blue: #0284c7;
  --blue-soft: #f0f9ff;
  --blue-border: #bae6fd;
  
  --green: #10b981;
  --green-soft: #ecfdf5;
  --green-border: #a7f3d0;
  
  --amber: #f59e0b;
  --amber-soft: #fffbeb;
  --amber-border: #fde68a;
  
  --red: #ef4444;
  --red-soft: #fef2f2;
  --red-border: #fecaca;
  
  /* Soft Ambient Multi-Layer Shadows */
  --shadow-sm: 0 1px 3px 0 rgba(15, 23, 42, 0.04), 0 1px 2px -1px rgba(15, 23, 42, 0.03);
  --shadow-md: 0 4px 18px -2px rgba(15, 23, 42, 0.05), 0 2px 6px -1px rgba(15, 23, 42, 0.03);
  --shadow-lg: 0 12px 30px -4px rgba(15, 23, 42, 0.07), 0 4px 12px -2px rgba(15, 23, 42, 0.03);
  --shadow-hover: 0 14px 34px -4px rgba(15, 23, 42, 0.09), 0 6px 14px -2px rgba(15, 23, 42, 0.04);
  
  /* Typography */
  --font-display: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --font-body: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
}
```

---

## 4. Component Structure & Architectural Changes

### 4.1. Navigation (`Sidebar`)
- **Container**: Fixed width `300px`, full height (`100vh`).
- **Operator Card**: Monogram avatar (`OP`), online status indicator square (`8px × 8px #10b981`), title `PLATFORM OPERATOR` and `OpsAtlas Console`.
- **Navigation Sections**:
  - `MAIN`: Dashboard
  - `INTELLIGENCE & SPEECH`: Ask Assistant (`avatar`, `ask`, `rag`), Tibi Voice (`tibi`, `tibi-knowledge`)
  - `GOVERNANCE & ARCHITECTURE`: Governance Review (`governance`), Enterprise Activity Model (`operating-model`), Analytics & Telemetry (`analytics`)
  - `SYSTEM & CONFIGURATION`: Platform Services (`system`, `sources`, `external`, `processes`, `simulator`, `stress-lab`)
- **Tree Sub-Nav**: Children inside `.sidebar-subnav` feature a 1px vertical tree guide with a horizontal connecting tick mark (`.sidebar-sublink::before`). Active sub-link turns tick mark and square dot to `var(--pink)`.
- **Docked Bottom Card**: `.sidebar-docked-card` displays `LOCAL READY` status badge and a direct action trigger button.

### 4.2. Topbar & Header
- **Breadcrumbs**: Replaced static header text with breadcrumbs (`OpsAtlas / [View Name]`).
- **Health Indicator**: Clean status badge with live square indicator.
- **Actions**: Square Sign-out button with subtle hover elevation.

### 4.3. Dashboard (`DashboardView`)
- **KPI Metric Strip**: 4-card metric strip (`Total Queries`, `Answer Rate`, `Grounded Rate`, `Avg Citations`).
- **Dual-Column Layout**:
  - *Left Column*: Quick Workflows (Upload source, Review conflicts, Check citations, Enterprise activity model) + Local Engine Status (FastAPI, Compliance Reasoner, Vector Index).
  - *Right Column*: Assistant Scorecard + Question Topic Distribution.

### 4.4. Common Components across Workbenches
- **Panels**: `.panel` has crisp 1px borders, subtle white elevation, and clean divider under `.panel-heading`.
- **Tables**: `.table-frame` with uppercase tracking headers (`th`) and subtle hover effect on rows (`tr:hover td`).
- **Status Pills**: `.status-pill` features crisp square geometry, uppercase 11px font, and pastel backgrounds with rich indicator dots.
- **Inputs & Controls**: Square inputs with 1px border (`#e2e8f0`) and subtle focus ring (`0 0 0 2px rgba(240, 6, 111, 0.18)`).

---

## 5. File Inventory

| File | Status | Summary of Changes |
|---|---|---|
| `frontend/src/App.css` | Modified | Core design system tokens, global square edge reset, ambient shadows, tree subnav styles, KPI strip, elevated quick cards, pastel square pills, and table styles. |
| `frontend/src/App.tsx` | Modified | Added `section` metadata to `NAV_ITEMS`, operator identity card, section dividers, tree branch connectors, docked bottom card, topbar breadcrumb, and dashboard KPI metric strip. |
| `frontend/src/GovernancePage.tsx` | Modified | Replaced inline circular `borderRadius: "50%"` with square indicator chips (`8px × 8px`). |
| `frontend/src/ReviewWorkbench.tsx` | Modified | Removed inline `borderRadius` from document viewer frame and search hit marks. |
| `frontend/src/ComplianceFindingWorkbench.tsx` | Modified | Removed inline `borderRadius` from text highlight marks. |
| `frontend/src/Markdown.tsx` | Modified | Removed inline `borderRadius` from hot-match highlights. |
| `frontend/src/SimulatorPage.tsx` | Modified | Removed inline `borderRadius` from simulation parameter inputs and selects. |
| `frontend/src/ExternalSourcesPage.tsx` | Modified | Removed inline `borderRadius` from snapshot URL and topic inputs. |

---

## 6. Verification & Build Health

The design prototype has been validated against local build gates:
1. **TypeScript Typecheck**:
   ```bash
   cd frontend && npm run lint
   # Output: tsc --noEmit (0 errors)
   ```
2. **Production Build**:
   ```bash
   cd frontend && npm run build
   # Output: built in 1.05s, zero errors
   ```
3. **Local Dev Server Execution**:
   ```bash
   cd frontend && npm start
   # Server online at http://localhost:5200
   ```

---

## 7. Handover Checklist for Claude

Claude can pick up this work from branch `ui/opsatlas-design`:

1. **Review & Visual Inspection**:
   - Inspect the branch `ui/opsatlas-design` using `git diff origin/claude/tiberius-speed-safety`.
   - Run the frontend locally via `cd frontend && npm start` to inspect all views (`Dashboard`, `Ask`, `Governance`, `Tibi`, `EAM`, `Analytics`, `System`).
2. **Integration into Feature Branch / PR**:
   - Merge or cherry-pick `ui/opsatlas-design` into the working branch (`claude/tiberius-speed-safety` or target PR).
3. **Optional Refinements for Claude**:
   - Component extraction: consider extracting `Sidebar` or `DashboardView` into dedicated files (`frontend/src/Sidebar.tsx`, `frontend/src/DashboardPage.tsx`) if desired for component modularity.
   - Any backend integration or real-time WebSocket telemetry hooks can be connected to the new KPI cards.
