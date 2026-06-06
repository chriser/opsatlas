import base64
import os
from pathlib import Path
from typing import Dict
from urllib.parse import quote

import requests


def load_env(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        raise FileNotFoundError(".env file not found")

    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()


load_env()

ORG = os.getenv("ADO_ORG")
PROJECT = os.getenv("ADO_PROJECT_NAME")
PAT = os.getenv("ADO_PAT")

PAGE_PATH = "/Final-Evidence/Evidence-Index"

CONTENT = """# Evidence Index

This page acts as the central evidence register for the AI Knowledge and Analytics Assistant project. It links the Azure DevOps delivery plan, backlog, Wiki, repository, test evidence and build outputs to the DT602/DT603 submission evidence.

## Evidence capture principle

Evidence should be captured progressively against each delivery slice. The project should not wait until the end of delivery to collect screenshots, test outputs, decisions, limitations or validation results.

## Evidence summary

| Evidence area | Evidence to capture | Current status | Location / notes |
|---|---|---|---|
| Architecture artefact | Final high-level architecture document and architecture Wiki pages | Created | Architecture document and Architecture Wiki section |
| Delivery model | Slice-based Epic structure from Slice 0 to Slice 6 | Created | Azure Boards backlog and Delivery Plan |
| Delivery Plan | Roadmap with dependencies, markers, styling and slice milestones | Created | Boards > Delivery Plans |
| Sprint plan | Sprint 1 to Sprint 9 delivery timeline | Created | Boards > Sprints |
| Backlog hierarchy | Epics, Features, User Stories and Tasks | Created | Boards > Backlogs / Work Items |
| Repository | Repo structure, README, docs, automation scripts and pipeline YAML | Created / evolving | Azure Repos |
| Wiki documentation | Architecture, delivery management, testing, evidence and governance pages | Created / evolving | Azure DevOps Wiki |
| Test planning | Test Case work items for source, retrieval, RAG, validation, analytics and end-to-end flow | Created | Boards > Work Items > Test Case |
| Risk and decision governance | Risk log, decision log and AI-assisted development log | To maintain | Wiki and/or repo docs |
| Pipeline evidence | Pipeline run showing lint/test placeholder or build checks | To capture | Pipelines |
| MVP evidence | Screenshot/API output showing grounded Q&A with source citation | Future Slice 1 evidence | To capture by Sprint 3 |
| Retrieval hardening evidence | Golden question retrieval results, evidence assembly and confidence/fallback behaviour | Future Slice 2 evidence | To capture by Sprint 4 |
| Validation evidence | Refusal rules, citation checks, validation status and trace logs | Future Slice 2 evidence | To capture by Sprint 5 |
| Analytics evidence | Usage log summary, repeated topic analysis and knowledge-gap output | Future Slice 3 evidence | To capture by Sprint 6 |
| Voice proof evidence | Voice input/output proof using canonical validated answer path | Future Slice 4 evidence | To capture by Sprint 7 |
| Evaluation evidence | Test results, regression checks, limitations and audit notes | Future Slice 5 evidence | To capture by Sprint 8 |
| Final submission pack | Final screenshots, evidence index, limitations, next steps and lessons learned | Future Slice 6 evidence | To complete by Sprint 9 |

## Slice evidence checklist

| Slice | Evidence required | Target date |
|---|---|---|
| Slice 0 - Architecture and Governance Foundation | Architecture Wiki, backlog structure, Delivery Plan, repo, decision log, risk log, test approach | 21 Jun 2026 |
| Slice 1 - MVP Grounded Q&A Path | Source register, synthetic data pack, section output, retrieval index, first grounded answer with citation | 05 Jul 2026 |
| Slice 2 - RAG and Validation Hardening | Retrieval quality results, evidence pack, validation rules, refusal examples, audit trace | 19 Jul 2026 |
| Slice 3 - Usage Logging and Basic Analytics | Usage log schema, sample usage data, knowledge-gap analytics output | 26 Jul 2026 |
| Slice 4 - Voice Interaction Proof | Speech-to-text input, canonical request, text-to-speech output, voice contract test | 02 Aug 2026 |
| Slice 5 - Evaluation and Evidence Hardening | Regression evidence, end-to-end evaluation, limitation review, risk/decision updates | 09 Aug 2026 |
| Slice 6 - Final Submission Pack | Final screenshots, evidence index, documentation updates, lessons learned, next steps | 14 Aug 2026 |

## Screenshot checklist

| Screenshot | Purpose | Captured? |
|---|---|---|
| Azure Boards Epic hierarchy | Shows slice-based delivery structure | No |
| Delivery Plan roadmap | Shows timeline, dependencies and milestones | No |
| Sprint board | Shows planned sprint execution | No |
| Architecture Wiki pages | Shows architecture published into project governance space | No |
| Repo structure | Shows controlled source and documentation structure | No |
| Pipeline run | Shows CI/CD evidence | No |
| Test Case list | Shows test planning and evaluation intent | No |
| MVP answer output | Shows first grounded cited response | No |
| Validation trace | Shows support check, evidence trace and refusal behaviour | No |
| Analytics output | Shows knowledge-gap or usage insight | No |
| Voice proof | Shows optional channel using validated canonical answer | No |
| Final evidence folder | Shows complete submission evidence pack | No |

## Evidence naming convention

Suggested names:

- YYYY-MM-DD_delivery-plan-roadmap.png
- YYYY-MM-DD_test-cases-list.png
- YYYY-MM-DD_pipeline-run-001.png
- YYYY-MM-DD_slice-1_mvp-grounded-answer.png
- YYYY-MM-DD_slice-2_validation-trace.png
- YYYY-MM-DD_slice-3_analytics-output.png

## Notes

This page should be updated after each sprint review or major build milestone. It should become the main route into DT603 build evidence and later DT604 retrospective evaluation.
"""


def auth_header(content_type: str = "application/json", extra: Dict[str, str] | None = None) -> Dict[str, str]:
    if not PAT:
        raise ValueError("ADO_PAT is missing. Check your .env file.")

    token = base64.b64encode(f":{PAT}".encode("utf-8")).decode("utf-8")
    headers = {
        "Authorization": f"Basic {token}",
        "Content-Type": content_type,
        "Accept": "application/json",
    }

    if extra:
        headers.update(extra)

    return headers


def get_wiki_id() -> str:
    url = f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}/_apis/wiki/wikis?api-version=7.1"
    response = requests.get(url, headers=auth_header(), timeout=30)

    print("List wikis status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    wikis = response.json().get("value", [])
    if not wikis:
        raise RuntimeError("No Wiki found.")

    wiki = wikis[0]
    print("Using Wiki:", wiki.get("name"))
    return wiki["id"]


def get_existing_etag(wiki_id: str, path: str) -> str | None:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wiki/wikis/{wiki_id}/pages"
        f"?path={quote(path, safe='/')}&includeContent=true&api-version=7.1"
    )

    response = requests.get(url, headers=auth_header(), timeout=30)

    if response.status_code == 404:
        return None

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    return response.headers.get("ETag")


def put_page(wiki_id: str, path: str, content: str) -> None:
    etag = get_existing_etag(wiki_id, path)

    extra_headers = {}
    if etag:
        extra_headers["If-Match"] = etag

    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wiki/wikis/{wiki_id}/pages"
        f"?path={quote(path, safe='/')}&api-version=7.1"
    )

    response = requests.put(
        url,
        headers=auth_header(extra=extra_headers),
        json={"content": content},
        timeout=30,
    )

    print(f"Create/update Wiki page: {path}")
    print("Status:", response.status_code)

    if response.status_code not in (200, 201):
        print(response.text)
        raise SystemExit(1)


def main() -> None:
    wiki_id = get_wiki_id()
    put_page(wiki_id, PAGE_PATH, CONTENT)

    print()
    print("Evidence Index Wiki page created/updated successfully.")
    print("Check Azure DevOps > Wiki > Final-Evidence > Evidence-Index")


if __name__ == "__main__":
    main()
