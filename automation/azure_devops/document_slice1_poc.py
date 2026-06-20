"""Document the supplier-avatar PoC as the delivered Slice 1 MVP under Epic #113.

Additive only: creates a Feature + User Story + Tasks + Test Case + limitation
Issues beneath Epic #113, marks the delivered work Resolved/Closed, attaches the
demo recording as evidence, and appends a note to the Epic description.
Does NOT modify or remove the existing #25/#26/#27 pipeline items.

Idempotency guard: aborts if the delivered Feature title already exists under #113.
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
EPIC = 113
SPRINT1 = "ai-knowledge-and-analytics-assistant\\Sprint 1 - Governance Foundation"
VIDEO = Path("poc/supplier-avatar/AI Assistant.mp4")


def auth(ct="application/json"):
    tok = base64.b64encode(f":{PAT}".encode()).decode()
    return {"Authorization": f"Basic {tok}", "Accept": "application/json", "Content-Type": ct}


def wi_url(i):
    return f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/wit/workItems/{i}"


def create(wtype, fields, parent=None, related=None):
    body = [{"op": "add", "path": f"/fields/{k}", "value": v} for k, v in fields.items()]
    if parent:
        body.append({"op": "add", "path": "/relations/-",
                     "value": {"rel": "System.LinkTypes.Hierarchy-Reverse", "url": wi_url(parent)}})
    if related:
        body.append({"op": "add", "path": "/relations/-",
                     "value": {"rel": "System.LinkTypes.Related", "url": wi_url(related)}})
    url = f"{BASE}/workitems/${quote(wtype)}?api-version=7.1"
    r = requests.post(url, headers=auth("application/json-patch+json"), json=body, timeout=30)
    if r.status_code not in (200, 201):
        print("  ! create failed", wtype, r.status_code, r.text[:300]); return None
    i = r.json()["id"]
    print(f"  + #{i} [{wtype}] {fields['System.Title']}")
    return i


def set_state(i, state):
    r = requests.patch(f"{BASE}/workitems/{i}?api-version=7.1",
                       headers=auth("application/json-patch+json"),
                       json=[{"op": "add", "path": "/fields/System.State", "value": state}], timeout=30)
    if r.status_code not in (200, 201):
        print(f"  ! state {state} on #{i} -> {r.status_code} {r.text[:200]}")


def exists_feature(title):
    q = {"query": f"SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject]=@project "
                  f"AND [System.WorkItemType]='Feature' AND [System.Title]='{title}'"}
    r = requests.post(f"{BASE}/wiql?api-version=7.1", headers=auth(), json=q, timeout=30).json()
    return [x["id"] for x in r.get("workItems", [])]


def attach(story_id, path: Path):
    if not path.exists():
        print("  ! video not found, skipping attachment"); return
    data = path.read_bytes()
    up = requests.post(f"{BASE}/attachments?fileName={quote(path.name)}&api-version=7.1",
                       headers={**auth("application/octet-stream")}, data=data, timeout=120)
    if up.status_code not in (200, 201):
        print("  ! attach upload failed", up.status_code, up.text[:200]); return
    url = up.json()["url"]
    r = requests.patch(f"{BASE}/workitems/{story_id}?api-version=7.1",
                       headers=auth("application/json-patch+json"),
                       json=[{"op": "add", "path": "/relations/-",
                              "value": {"rel": "AttachedFile", "url": url,
                                        "attributes": {"comment": "Demo recording of the avatar grounded-Q&A PoC"}}}],
                       timeout=60)
    print("  + attached demo video to #%s -> %s" % (story_id, r.status_code))


TAGS = "Slice 1; MVP; PoC; Avatar"


def main():
    if exists_feature("Avatar grounded Q&A MVP (vendor proof of concept)"):
        print("Feature already exists under #113 — aborting to avoid duplicates.")
        return

    # --- Feature ---
    feat = create("Feature", {
        "System.Title": "Avatar grounded Q&A MVP (vendor proof of concept)",
        "System.Tags": TAGS,
        "System.IterationPath": SPRINT1,
        "Microsoft.VSTS.Scheduling.Effort": 5,
        "System.Description": (
            "Delivered proof of concept that proves the target end-to-end grounded-Q&A "
            "experience for the anonymised supplier-setup process: a spoken question is "
            "transcribed, answered by retrieval-augmented generation over an approved "
            "anonymised knowledge base, and spoken back by a lip-synced avatar with "
            "scope guardrails (explains process only; refuses off-topic; never invents "
            "or approves).<br><br>Implemented as a local Node/Express app that brokers "
            "credentials to two managed services (one for STT + RAG + answer, one for "
            "avatar rendering). Code lives in <b>poc/supplier-avatar/</b>. This validates "
            "the experience; the open-source platform rebuild is tracked for later slices."),
    }, parent=EPIC)
    set_state(feat, "Resolved")

    # --- User Story ---
    story = create("User Story", {
        "System.Title": "Spoken grounded Q&A over the supplier-setup knowledge, voiced by an avatar",
        "System.Tags": TAGS,
        "System.IterationPath": SPRINT1,
        "Microsoft.VSTS.Scheduling.StoryPoints": 5,
        "System.Description": (
            "As a user, I can ask spoken questions about the anonymised supplier-setup "
            "and master-data process and receive a grounded answer, drawn only from the "
            "approved knowledge base, spoken by a lip-synced avatar."),
        "Microsoft.VSTS.Common.AcceptanceCriteria": (
            "- App starts in LIVE mode with credentials present; serves at 127.0.0.1:5180.<br>"
            "- Start Conversation requests the microphone; the avatar stream appears.<br>"
            "- A spoken question shows as a 'You' transcript line.<br>"
            "- A short retrieval wait shows 'Checking approved process documentation'; "
            "the avatar speaks only a fixed holding phrase, never an unsolicited answer.<br>"
            "- The approved answer appears as an 'Assistant' line and is spoken with lip sync.<br>"
            "- Off-topic questions are declined rather than answered.<br>"
            "- Offline mock mode plays a scripted Q&A with no external calls.<br>"
            "- Verified running on macOS (server boots LIVE; page returns 200)."),
    }, parent=feat)
    set_state(story, "Resolved")
    attach(story, VIDEO)

    # --- Tasks (delivered; Task type has no Resolved state -> Closed) ---
    tasks = [
        "Local Express server and static frontend (port 5180)",
        "Credential-broker API endpoints (server-side keys; short-lived browser credentials)",
        "Conversational AI integration (microphone, speech-to-text, RAG, answer)",
        "Avatar integration (render-only; input audio disabled so it never self-answers)",
        "Single-answer-pipeline state machine and answer guardrails (holding phrase, error fallback)",
        "Offline mock mode (scripted Q&A demonstration)",
        "Relocate PoC into project repo (poc/supplier-avatar) and add cross-platform run notes",
    ]
    for t in tasks:
        tid = create("Task", {"System.Title": t, "System.Tags": TAGS,
                              "System.IterationPath": SPRINT1}, parent=story)
        if tid:
            set_state(tid, "Closed")

    # --- Test Case (UAT checklist) ---
    tc = create("Test Case", {
        "System.Title": "UAT - Avatar grounded Q&A (live + mock checklist)",
        "System.Tags": TAGS, "System.IterationPath": SPRINT1,
        "System.Description": "Manual UAT checklist for the avatar grounded-Q&A PoC "
                              "(live and mock modes). See poc/supplier-avatar/README.md test checklist."},
        related=story)

    # --- Limitations / follow-ups (Issue: Active/Closed only) ---
    for title, desc in [
        ("PoC knowledge base and guardrails live in vendor config, not reproducible from the repo",
         "The retrieval knowledge base and answer guardrails are configured in the managed "
         "service dashboard, not in source control. Capture that configuration as evidence and "
         "plan a repo-owned, reproducible knowledge + guardrail definition in the platform build."),
        ("PoC depends on paid managed services and runtime CDN SDKs - open-source rebuild required",
         "The answer/voice pipeline uses paid managed services and loads browser SDKs from a CDN "
         "at runtime. The platform target is open-source models for the knowledge/answer pipeline "
         "(managed service likely retained only for the front-end voice/avatar). Tracked for later slices."),
    ]:
        iid = create("Issue", {"System.Title": title, "System.Tags": "Slice 1; PoC; Limitation",
                              "System.Description": desc}, related=story)

    # --- Epic note (append, non-destructive) ---
    cur = requests.get(f"{BASE}/workitems/{EPIC}?fields=System.Description&api-version=7.1",
                       headers=auth(), timeout=30).json()
    existing = cur.get("fields", {}).get("System.Description", "") or ""
    note = ("<hr><b>Slice 1 status note:</b> The MVP grounded-Q&A outcome has been proven by a "
            "delivered avatar PoC (see child Feature 'Avatar grounded Q&A MVP'). The existing "
            "from-scratch ingestion/index/RAG items remain valid and are re-scoped toward the "
            "open-source platform rebuild; their sprint sequencing is to be confirmed in planning.")
    if "Slice 1 status note" not in existing:
        requests.patch(f"{BASE}/workitems/{EPIC}?api-version=7.1",
                       headers=auth("application/json-patch+json"),
                       json=[{"op": "add", "path": "/fields/System.Description", "value": existing + note}],
                       timeout=30)
        print(f"  ~ appended Slice 1 status note to Epic #{EPIC}")

    print("\nDone. Created delivered Slice 1 PoC documentation under Epic #%d." % EPIC)


if __name__ == "__main__":
    main()
