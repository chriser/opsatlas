"""Control-panel-first restructure of the near-term backlog.

1. Rename Sprint 2 and Sprint 3 to reflect the new scope (dates unchanged).
2. Create a 'Knowledge Platform Control Panel' epic with shell/design-system and
   Knowledge-Sources features/stories (incl. the look & feel reference story).
3. Resequence existing data/ingestion/RAG items into Sprint 2/3 and set
   Agent Owner / Agent Role.

Additive + idempotent: creation is skipped if the epic already exists; rename and
resequencing are safe to re-run.
"""

import base64
import os
from pathlib import Path
from urllib.parse import quote

import requests

for line in Path(".env").read_text().splitlines():
    if line.strip() and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

ORG = os.environ["ADO_ORG"].strip()
PAT = os.environ["ADO_PAT"].strip()
PROJECT = "ai-knowledge-and-analytics-assistant"
BASE = f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/wit"
PROJ = "ai-knowledge-and-analytics-assistant"

S2_OLD = "Sprint 2 - Data Strategy and Source Preparation"
S3_OLD = "Sprint 3 - MVP Grounded QnA Path"
S2_NEW = "Sprint 2 - Control Panel Foundation and Knowledge Sources"
S3_NEW = "Sprint 3 - Open-Source Ingestion and Retrieval"
S2 = f"{PROJ}\\{S2_NEW}"
S3 = f"{PROJ}\\{S3_NEW}"


def h(ct="application/json"):
    tok = base64.b64encode(f":{PAT}".encode()).decode()
    return {"Authorization": f"Basic {tok}", "Accept": "application/json", "Content-Type": ct}


def wi_url(i):
    return f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/wit/workItems/{i}"


def rename_iteration(old, new):
    url = f"{BASE}/classificationnodes/iterations/{quote(old)}?api-version=7.1"
    r = requests.patch(url, headers=h(), json={"name": new}, timeout=30)
    print(f"rename '{old}' -> '{new}': {r.status_code}{'' if r.status_code==200 else ' '+r.text[:200]}")


def create(wtype, fields, parent=None):
    body = [{"op": "add", "path": f"/fields/{k}", "value": v} for k, v in fields.items()]
    if parent:
        body.append({"op": "add", "path": "/relations/-",
                     "value": {"rel": "System.LinkTypes.Hierarchy-Reverse", "url": wi_url(parent)}})
    r = requests.post(f"{BASE}/workitems/${quote(wtype)}?api-version=7.1",
                      headers=h("application/json-patch+json"), json=body, timeout=30)
    if r.status_code not in (200, 201):
        print("  ! create", wtype, r.status_code, r.text[:300]); return None
    i = r.json()["id"]
    print(f"  + #{i} [{wtype}] {fields['System.Title']}")
    return i


def patch(i, fields, append_tag=None):
    ops = [{"op": "add", "path": f"/fields/{k}", "value": v} for k, v in fields.items()]
    if append_tag:
        cur = requests.get(f"{BASE}/workitems/{i}?fields=System.Tags&api-version=7.1", headers=h(), timeout=30).json()
        tags = cur.get("fields", {}).get("System.Tags", "") or ""
        have = [t.strip() for t in tags.split(";") if t.strip()]
        if append_tag not in have:
            have.append(append_tag)
            ops.append({"op": "add", "path": "/fields/System.Tags", "value": "; ".join(have)})
    r = requests.patch(f"{BASE}/workitems/{i}?api-version=7.1", headers=h("application/json-patch+json"), json=ops, timeout=30)
    if r.status_code not in (200, 201):
        print(f"  ! patch #{i} {r.status_code} {r.text[:150]}")
    return r.status_code


def epic_exists(title):
    q = {"query": f"SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject]=@project "
                  f"AND [System.WorkItemType]='Epic' AND [System.Title]='{title}'"}
    r = requests.post(f"{BASE}/wiql?api-version=7.1", headers=h(), json=q, timeout=30).json()
    return [x["id"] for x in r.get("workItems", [])]


def AO(owner, role):
    return {"Custom.AgentOwner": owner, "Custom.AgentRole": role}


def main():
    print("== 1. Rename sprints ==")
    rename_iteration(S2_OLD, S2_NEW)
    rename_iteration(S3_OLD, S3_NEW)

    print("\n== 2. Control Panel epic ==")
    if epic_exists("Knowledge Platform Control Panel"):
        print("  epic already exists — skipping creation")
    else:
        epic = create("Epic", {
            "System.Title": "Knowledge Platform Control Panel",
            "System.Tags": "Platform; Control Panel",
            "Microsoft.VSTS.Scheduling.Effort": 13,
            "System.Description": (
                "The web control panel that the knowledge platform is operated through: a "
                "multi-page application for managing source knowledge, the RAG setup, "
                "governance (human-in-the-loop), and later analytics. It surfaces the "
                "backend knowledge-lifecycle modules to an operator who can upload and "
                "manage documents, review duplicates/conflicts, and control what becomes "
                "queryable. Front-end stack: React + TypeScript + Vite."),
            **AO("Claude", "Build")}, parent=None)

        featA = create("Feature", {
            "System.Title": "Control panel application shell and design system",
            "System.Tags": "Platform; Control Panel", "System.IterationPath": S2,
            "Microsoft.VSTS.Scheduling.Effort": 5,
            "System.Description": "Stand up the control-panel web application and its reusable "
            "design system / component library, plus the page-navigation shell.",
            **AO("Claude", "Build")}, parent=epic)

        create("User Story", {
            "System.Title": "Scaffold the control-panel web app (React + TypeScript + Vite)",
            "System.Tags": "Platform; Control Panel", "System.IterationPath": S2,
            "Microsoft.VSTS.Scheduling.StoryPoints": 3,
            "System.Description": "Create the front-end application skeleton and wire it to the backend API.",
            "Microsoft.VSTS.Common.AcceptanceCriteria":
                "- App runs via the dev server and serves locally.<br>- Production build passes; lint clean.<br>"
                "- Talks to a backend health endpoint.",
            **AO("Codex", "Build")}, parent=featA)

        create("User Story", {
            "System.Title": "Establish the control-panel design system and look & feel",
            "System.Tags": "Platform; Control Panel; Design", "System.IterationPath": S2,
            "Microsoft.VSTS.Scheduling.StoryPoints": 3,
            "System.Description": "Define the platform's visual language as a reusable design system: a dark, "
            "multi-panel operator layout with side navigation, status pills, cards, buttons, typography and "
            "colour tokens. Reuse the established control-panel design baseline (CSS/components provided by the "
            "operator) as the starting point and capture shared tokens and components. The look & feel should "
            "match the provided design baseline / screenshots.",
            "Microsoft.VSTS.Common.AcceptanceCriteria":
                "- Shared theme tokens (colour, spacing, typography) defined.<br>"
                "- Reusable components: panel, status pill, card, button, side-nav.<br>"
                "- A sample page visibly matches the provided design baseline.",
            **AO("Claude", "Build")}, parent=featA)

        create("User Story", {
            "System.Title": "Multi-page navigation shell (Dashboard, Knowledge Sources, ...)",
            "System.Tags": "Platform; Control Panel", "System.IterationPath": S2,
            "Microsoft.VSTS.Scheduling.StoryPoints": 2,
            "System.Description": "Routed multi-page shell with side navigation and placeholder pages.",
            "Microsoft.VSTS.Common.AcceptanceCriteria":
                "- Side-nav routes between pages.<br>- Dashboard and Knowledge Sources pages exist as placeholders.",
            **AO("Codex", "Build")}, parent=featA)

        create("User Story", {
            "System.Title": "Basic login / access control for the control panel",
            "System.Tags": "Platform; Control Panel", "System.IterationPath": S2,
            "Microsoft.VSTS.Scheduling.StoryPoints": 2,
            "System.Description": "A simple authentication gate so only the operator can access the panel.",
            "Microsoft.VSTS.Common.AcceptanceCriteria":
                "- Auth gate protects all pages.<br>- Configurable credential; logout works.",
            **AO("Codex", "Build")}, parent=featA)

        featB = create("Feature", {
            "System.Title": "Knowledge Sources management",
            "System.Tags": "Platform; Knowledge", "System.IterationPath": S2,
            "Microsoft.VSTS.Scheduling.Effort": 5,
            "System.Description": "Upload and manage anonymised source documents through the control panel, "
            "backed by the source register.",
            **AO("Claude", "Build")}, parent=epic)

        create("User Story", {
            "System.Title": "Upload anonymised source documents via the control panel",
            "System.Tags": "Platform; Knowledge", "System.IterationPath": S2,
            "Microsoft.VSTS.Scheduling.StoryPoints": 3,
            "System.Description": "Operator uploads an anonymised source document; it is stored and registered. "
            "Depends on the source register backend.",
            "Microsoft.VSTS.Common.AcceptanceCriteria":
                "- Upload accepts an anonymised document (type/size validated).<br>"
                "- Stored server-side and recorded in the source register.<br>- Appears in the sources list.",
            **AO("Codex", "Build")}, parent=featB)

        create("User Story", {
            "System.Title": "View and manage registered sources (source register UI)",
            "System.Tags": "Platform; Knowledge", "System.IterationPath": S2,
            "Microsoft.VSTS.Scheduling.StoryPoints": 3,
            "System.Description": "List and manage sources with their register metadata.",
            "Microsoft.VSTS.Common.AcceptanceCriteria":
                "- List shows type, status, sensitivity, version, processing state.<br>"
                "- Operator can view and remove a source.<br>- Backed by the source register.",
            **AO("Codex", "Build")}, parent=featB)

    print("\n== 3. Resequence existing items ==")
    # Sprint 2: data prep (Research/Antigravity) + source register backend (Build/Codex)
    s2_research = [25, 39, 40, 41, 42, 43, 44, 45, 46]
    s2_build = [26, 47, 48, 49, 50]
    for i in s2_research:
        patch(i, {"System.IterationPath": S2, **AO("Antigravity", "Research")})
    for i in s2_build:
        patch(i, {"System.IterationPath": S2, **AO("Codex", "Build")})
    print("  Sprint 2: set iteration + owner on", len(s2_research) + len(s2_build), "items")

    # Sprint 3: OSS ingestion + retrieval + assistant/RAG (Build/Codex), OSS tag on index/RAG
    s3_build = [27, 51, 52, 53, 54, 91, 92, 93, 94, 55, 56, 57, 58]
    s3_build_oss = [87, 88, 89, 90, 59, 60, 61, 62]
    for i in s3_build:
        patch(i, {"System.IterationPath": S3, **AO("Codex", "Build")})
    for i in s3_build_oss:
        patch(i, {"System.IterationPath": S3, **AO("Codex", "Build")}, append_tag="OSS")
    print("  Sprint 3: set iteration + owner on", len(s3_build) + len(s3_build_oss), "items")

    print("\nDone.")


if __name__ == "__main__":
    main()
