# Content management for OpsAtlas Sales

**26 September 2026.** The Human asked for a content-management capability that can be used anywhere in the platform. On the Governance page it must let him open and edit each source. It should replicate the editor, comments and version history of seven reference screenshots (a document editor with an audit side panel, comment threads and version history).

This page is the scope and backlog. The ADO Epic and its items mirror it (see the IDs at the end).

## What the screenshots show, and what OpsAtlas takes from them

| Screenshot element | In OpsAtlas |
|---|---|
| Breadcrumb, "Updated just now", status pill (In Progress), Submit | Breadcrumb back to the page it was opened from; autosave state; status (Published, Draft, Submitted); Submit for approval, then Approve and publish |
| Viewing / Editing toggle | Yes. A document opens in Viewing; Editing is a deliberate switch |
| Heading 1 / paragraph, bold, italic, strike-through, lists, indent and outdent, undo and redo, links | Yes |
| Capitalisation menu (Normal, lower, UPPER, Title) | Yes |
| Table insert and cell menu (insert left or right, duplicate, clear, delete) | Yes, plus rows above and below |
| Image insert | Yes. Images are stored in the workspace, never fetched from the internet |
| Selection word count ("40 words") | Yes, as a floating count of the selection, or of the document when nothing is selected |
| Download | Yes, as Markdown |
| Comment on a passage; highlight in the text; thread with author, role and time; Show more; Resolve; reply | Yes |
| Version history with Approved, Edited and Written labels, current version, authors and roles | Yes |
| Diff in the document (insertions coloured, deletions struck through) | Yes |
| Content audit: word count, readability, content suggestions, plagiarism | Word count, readability (computed locally), and suggestions from governance (wording checks and conflicts or duplicates). Plagiarism becomes *overlap with other records*, from the statement-level review |
| Last modified by, Recent activities | Yes: last modified, and an activity timeline |
| Deadline, Assignment Brief, Client Information | Become *Details*: title, type, approval, version, and scope and lifecycle (effective dates, phase, applies to). For sales records, also the evidence a record cites and the records that cite a document |

## Decisions (the Human can overturn any of them)

1. **Edits are governed.** An edit is a draft. Answers, Tibi and search keep using the approved version until the Human approves and publishes the draft. Publishing makes it a new version of the source, re-ingests it, and records the approval through the audited ontology action. This keeps the rule that only approved sources are queryable.
2. **Markdown stays the format.** Sections come from Markdown headings, and Tibi speaks a record's text, so the editor stores Markdown. Formatting Markdown cannot hold is left out, because it would put HTML into the knowledge: text colour, highlight colour, underline, superscript and subscript, and alignment.
3. **Local-first.** Grammarly, WordPress, Unsplash, Peppertype.ai, the SEO assistant and plagiarism services all send content to outside services, so none of them is built. Local equivalents stand in: readability, overlap from the statement review, and governance suggestions.
4. **One operator.** OpsAtlas has one signed-in operator, so there is no live presence (collaborator avatars, live cursors, name tags). The operator (Kris Pochopien, Platform operator) is the author of edits and comments. Tibi is the author of governance suggestions.
5. **Reusable across the platform.** There is one content engine (`src/assistant/content`), one API (`/api/content`) and one document workspace (`#document:<source id>`). Any page that shows a source can open it.

## Delivered on 26 September 2026, for the Human's testing

All 26 stories were built, except for two small parts noted below.

**Where it lives:**

| Part | Where |
|---|---|
| Engine | `src/assistant/content/`: `service.py` (drafts, workflow, publishing, versions, comments, details, images), `store.py` (SQLite at `<data>/content/content.db`), `text.py` (plain text, counts, readability, word diff, anchors) |
| API | `src/assistant/api/routes_content.py`: `/api/content/documents/{id}`, draft, submit, return, publish, versions, diff, comments, activity, suggestions, details, assets |
| Sales hooks | `services/opsatlas_sales/content.py`: record consistency, evidence follow-through, record details, governance suggestions |
| Workspace | `frontend/src/content/`: `DocumentPage.tsx`, `Editor.tsx` (TipTap 3 with official Markdown), `extensions.ts` (highlights, capitalisation, table helpers, fixes), `panels.tsx`, `markdown.ts`, `content.css` |

**How to use it:**
1. Open a document from Governance (Source approval: **Open**, or click a title), Knowledge Sources (**Open**) or Tibi Knowledge (**Open document**).
2. Switch to **Editing**. Changes save as a draft; the published version stays live.
3. Select text and use the comment button to discuss a passage. Tibi's governance suggestions appear in the same panel, with one-click fixes where they are safe.
4. **Review changes** shows the draft as a diff. Then **Submit for approval**, and **Approve and publish**. **Return to draft** and **Discard draft** are always available.
5. **Version history** compares any version, and **Restore to draft** puts an old version back into the draft.

**Checked:**
- 15 new tests (engine, API and sales records), 1,031 Python tests on 3.11 and 3.12, and 58 browser tests.
- Every action above run end to end in a throwaway copy of the sales workspace.
- A Markdown round trip over all 42 sources in the workspace. Ignoring whitespace, all 42 come back identical. Six, including five DT603 sections, lose blank lines between list items on their first edit. No words change.

**Behaviour to know when testing:**
- Publishing a record's document is the Human's review: the record is updated and enabled. A record under a review block (for example a dispute) cannot be published.
- Publishing a document that records cite updates those records to follow it. Each gets a governance note, and the confirmation names them.
- Spelling out an acronym applies at its first stand-alone use in the text. If the only stand-alone use is a record's heading (for example "RAG and OAG evaluation results", where the text only has "RAG-only"), the heading changes, and with it the record's title. Review changes shows it before approval.
- Not built: duplicating a table *column* (rows can be duplicated) and an emoji picker in replies.

## Backlog

**CM F1: Document workspace and editor**

| ID | Story | Acceptance |
|---|---|---|
| CM S1 | Document workspace | `#document:<id>` opens any source with a breadcrumb back, save state, status, the Viewing/Editing toggle, the actions, the editor, and a side rail (Overview, Comments, Versions, Activity, Details) |
| CM S2 | Markdown editor | Paragraph and H1–H3, bold, italic, strike-through, inline code, links, bullet and numbered lists, indent and outdent, quote, rule, undo and redo. Markdown reads and writes back unchanged. Read-only in Viewing |
| CM S3 | Capitalisation | Normal, lower, UPPER and Title case on the selection |
| CM S4 | Tables | Insert a table. Cell menu: rows above and below, columns left and right, duplicate row or column, clear content, delete row, column or table |
| CM S5 | Images | Upload an image into the workspace (content-addressed, local) and insert it with alt text |
| CM S6 | Word counts | Document word count; floating selection count |
| CM S7 | Autosave | Drafts save as you type; shows "Saving…", "Saved just now" or "Not saved"; detects a draft that another change has overtaken; warns before leaving with unsaved edits |
| CM S8 | Download | Download the draft or the published text as Markdown |
| CM S9 | Formats that cannot be edited | PDF, DOCX and JSON open read-only with their extracted text, and the reason is shown |

**CM F2: Governed publishing**

| ID | Story | Acceptance |
|---|---|---|
| CM S10 | Draft, submit, approve | Draft, then Submitted, then Approved and published, or returned to Draft; discard a draft; the published version stays live until approval |
| CM S11 | Publish engine | Writes the new content, increments the version, re-ingests, and approves through the audited action. It is atomic: a failed ingest restores the previous content. The statement review starts |
| CM S12 | Sales records stay consistent | Publishing a record's document updates the record (title, text, hash) so it stays enabled. It respects a record's review block (for example a dispute) and writes the review history. Records citing an edited evidence document are updated, and the publish reports them |
| CM S13 | Governance page | Source approval rows get Open and a draft or submitted status. Changes are reviewed as a diff and approved in the document |

**CM F3: Version history**

| ID | Story | Acceptance |
|---|---|---|
| CM S14 | Version store | Every publish and restore is kept with author, role, time, label (Imported, Approved, Restored) and note. Existing content is imported as its current version the first time a document is opened |
| CM S15 | Version panel | Versions newest first with label chips, the current version, and authors and roles |
| CM S16 | Compare | Word-level diff of any version against the current text or the draft, shown in the document (insertions coloured, deletions struck through) |
| CM S17 | Restore | A version is copied into the draft; nothing goes live without approval |

**CM F4: Comments and suggestions**

| ID | Story | Acceptance |
|---|---|---|
| CM S18 | Anchored comments | Select text to comment. The anchor is the quote with its context, re-found after edits; a comment whose text is gone is marked "text changed" |
| CM S19 | Threads | Quote card (Show more), author, role, time, replies, Resolve and Reopen, delete. Resolved threads are collapsed |
| CM S20 | Highlights | Commented passages are highlighted. Clicking one opens its thread, and a thread shows its passage |
| CM S21 | Governance suggestions | Wording checks and conflicts or duplicates for this document appear as suggestions from Tibi, anchored to the passage. Deterministic fixes apply in one click (for example spelling out an acronym as DT603 does) |

**CM F5: Insights and activity**

| ID | Story | Acceptance |
|---|---|---|
| CM S22 | Content audit | Word count, reading time, readability (Flesch reading ease and grade), suggestion count, and overlap with other records |
| CM S23 | Details and lifecycle | Title, type, approval, version, sensitivity. Scope and lifecycle fields (effective dates, phase, applies to) are editable and logged. For sales records, the evidence the record cites and the records citing the document |
| CM S24 | Activity | Timeline of draft saved, submitted, returned, published, restored, commented, resolved and details changed; "Last modified by" in the Overview |

**CM F6: Across the platform**

| ID | Story | Acceptance |
|---|---|---|
| CM S25 | Open from anywhere | Governance Source approval, Knowledge Sources and Tibi Knowledge each open the document |
| CM S26 | Operator identity | Edits, comments and versions carry the signed-in operator's name and role, set once on the server |

## Not built, and why

| Screenshot element | Reason |
|---|---|
| Collaborator avatars (+12), live cursors, name tags | One local operator; revisit if OpsAtlas becomes multi-user |
| Share | Local-only workspace. The document's `#document:` link works inside the control panel |
| Grammarly, WordPress, Unsplash, Peppertype.ai, SEO Writing Assistant, plagiarism | Each sends content to an outside service. Local equivalents: readability, overlap and governance suggestions |
| Text colour, highlight colour, underline, superscript and subscript, alignment | Markdown cannot store them; they would put HTML into the knowledge Tibi speaks |
| Emoji picker in replies | Not needed for governance work; emoji can still be typed |
| Deadline, assignment brief, client information | Content-agency workflow. OpsAtlas has approval and lifecycle instead (Details) |

## ADO

- **Epic:** #1776
- **Features:** CM F1 #1777 · CM F2 #1787 · CM F3 #1792 · CM F4 #1797 · CM F5 #1802 · CM F6 #1806
- **Stories:** S1 #1778 · S2 #1779 · S3 #1780 · S4 #1781 · S5 #1782 · S6 #1783 · S7 #1784 · S8 #1785 · S9 #1786 · S10 #1788 · S11 #1789 · S12 #1790 · S13 #1791 · S14 #1793 · S15 #1794 · S16 #1795 · S17 #1796 · S18 #1798 · S19 #1799 · S20 #1800 · S21 #1801 · S22 #1803 · S23 #1804 · S24 #1805 · S25 #1807 · S26 #1808
