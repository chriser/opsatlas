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


PAGES = {
    "/Delivery-Management/Decision-Log": """# Decision Log

This page records key architecture, delivery, data, ethics and implementation decisions for the AI Knowledge and Analytics Assistant project.

## Purpose

The decision log provides traceability. It explains why major choices were made, what alternatives were considered and what impact the decision has on delivery, risk, ethics or technical design.

## Decision log

| ID | Date | Decision | Rationale | Alternatives considered | Impact | Status |
|---|---|---|---|---|---|---|
| DEC-001 | 2026-06-06 | Use Azure DevOps as the delivery governance platform | Provides backlog, repo, Wiki, test case and delivery plan evidence in one controlled environment | Local-only documentation; manual spreadsheet tracking | Stronger traceability and better DT602/DT603 evidence | Accepted |
| DEC-002 | 2026-06-06 | Use a modular monolith for the first implementation | Keeps delivery practical while preserving internal module boundaries | Microservices; single unstructured prototype | Reduces complexity and supports controlled iteration | Accepted |
| DEC-003 | 2026-06-06 | Use vertical delivery slices rather than horizontal module delivery | Allows the MVP to run end-to-end early, then harden progressively | Build all modules first, integrate later | Reduces late discovery risk | Accepted |
| DEC-004 | 2026-06-06 | Use anonymised or synthetic learning data for the PoC | Avoids exposing confidential, personal or commercially sensitive material outside approved controls | Use real internal data; use public generic data only | Supports ethical and policy-aligned delivery | Accepted |
| DEC-005 | 2026-06-06 | Use RAG as the core answer pattern | Keeps answers grounded in controlled source evidence rather than model memory | General chatbot; rules-only search | Reduces hallucination risk and improves explainability | Accepted |
| DEC-006 | 2026-06-06 | Treat voice as an optional interaction channel, not a separate answer pipeline | Ensures spoken answers use the same validated canonical response | Separate voice assistant flow | Avoids uncontrolled paraphrasing or bypassing validation | Accepted |
| DEC-007 | 2026-06-06 | Use Azure DevOps Wiki as the living architecture and evidence space | Keeps planning, architecture and delivery evidence visible and auditable | Word documents only; repo markdown only | Better governance and easier screenshots for assessment | Accepted |

## Future decision areas

| Area | Decision still required |
|---|---|
| Model runtime | Whether to use local model runtime only, cloud model, or hybrid provider abstraction during build |
| Vector store | Whether to use a local vector index, lightweight database or managed vector service |
| UI implementation | Whether the MVP uses API-only, simple web UI, or both |
| Logging implementation | Format and storage approach for trace logs and usage events |
| Analytics output | Whether to use Python notebook, CSV output, dashboard, or simple web report |
| Voice proof | Which speech-to-text and text-to-speech option is used for the proof |
""",

    "/Delivery-Management/Risk-Log": """# Risk Log

This page records key delivery, technical, ethical, security and evidence risks for the AI Knowledge and Analytics Assistant project.

## Purpose

The risk log supports controlled delivery. It helps show that risks are identified early, reviewed regularly and linked to mitigation actions.

## Risk rating

| Rating | Meaning |
|---|---|
| Low | Manageable through normal delivery controls |
| Medium | Needs active mitigation and review |
| High | Could affect delivery quality, ethics, security or submission evidence if not managed |

## Risk log

| ID | Risk | Category | Likelihood | Impact | Rating | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|---|---|
| R-001 | Confidential or sensitive data could be exposed if real process material is used incorrectly | Data / Ethics | Medium | High | High | Use anonymised or synthetic material unless approved controls exist; maintain source register and sanitisation rules | Project owner | Open |
| R-002 | Assistant may hallucinate or produce unsupported process claims | AI quality | Medium | High | High | Use RAG, evidence packs, citation checks, validation rules and refusal handling | Project owner | Open |
| R-003 | MVP may be delayed if too much is built before the first end-to-end flow | Delivery | Medium | Medium | Medium | Use vertical slices; prove MVP grounded Q&A by Sprint 3 | Project owner | Open |
| R-004 | Azure DevOps planning may become over-engineered and delay actual build work | Delivery | Medium | Medium | Medium | Limit planning enhancements after governance pages, test links and pipeline placeholder | Project owner | Open |
| R-005 | Voice interaction could bypass validation if implemented as a separate answer path | AI safety | Low | High | Medium | Voice must reuse canonical validated text response | Project owner | Open |
| R-006 | Analytics may overstate business impact if based on limited synthetic data | Analytics / Ethics | Medium | Medium | Medium | Clearly label analytics as proof-of-concept; avoid unsupported commercial claims | Project owner | Open |
| R-007 | AI coding assistance could create unreviewed or broad changes across the repository | Delivery governance | Medium | Medium | Medium | Link AI-assisted work to backlog items, restrict scope and review diffs/tests | Project owner | Open |
| R-008 | Test evidence may be incomplete if not captured progressively | Evidence | Medium | Medium | Medium | Maintain Evidence Index and capture screenshots after each slice | Project owner | Open |
| R-009 | Model/provider choice may change during build and affect architecture assumptions | Technical | Medium | Low | Low | Use provider abstraction and document model decisions in the decision log | Project owner | Open |
| R-010 | Retrieval quality may be weak if source sections are poorly structured | Technical / Quality | Medium | Medium | Medium | Use section builder, metadata tagging, golden questions and retrieval hardening in Sprint 4 | Project owner | Open |

## Review cadence

Risks should be reviewed at the end of each sprint and updated when new evidence, constraints or build issues appear.
""",

    "/Delivery-Management/AI-Assisted-Development-Log": """# AI-Assisted Development Log

This page records where AI assistance is used during planning, documentation, coding, testing or analysis.

## Purpose

The project may use AI tools to accelerate boilerplate creation, documentation, testing and implementation. This log provides transparency and supports responsible use of AI-assisted development.

## Control principles

| Control | Expected practice |
|---|---|
| Backlog link | AI-assisted work should relate to an Epic, Feature, User Story or Task |
| Scope control | The prompt or instruction should define what can and cannot be changed |
| Review | Outputs should be reviewed before being accepted |
| Testing | Code outputs should be tested or inspected |
| Documentation | Significant AI-assisted decisions or limitations should be recorded |
| Confidentiality | No confidential, personal or commercially sensitive data should be shared with unapproved tools |

## AI-assisted development log

| ID | Date | Tool / assistant | Linked work item | Purpose | Input sensitivity | Output produced | Review / validation | Status |
|---|---|---|---|---|---|---|---|---|
| AI-001 | 2026-06-06 | ChatGPT | Slice 0 governance setup | Create Azure DevOps planning structure and automation scripts | Non-confidential project planning data | Scripts for project, work items, sprints, Wiki, Delivery Plan and diagnostics | User executed scripts and reviewed Azure DevOps output | Accepted |
| AI-002 | 2026-06-06 | ChatGPT | Architecture documentation | Enhance architecture artefact with vertical slice delivery model | Non-confidential architecture content | Updated architecture document and Wiki publishing script | User reviewed document and Wiki output | Accepted |
| AI-003 | 2026-06-06 | ChatGPT | Evidence Index | Create evidence index Wiki page | Non-confidential project planning data | Evidence Index page | User reviewed Wiki output | Accepted |

## Future entries

Add new rows when AI is used for:

| Use case | Example evidence |
|---|---|
| Code generation | Prompt summary, files changed, tests run |
| Test generation | Test scope, expected behaviour, validation output |
| Refactoring | Reason for change, affected modules, regression result |
| Documentation drafting | Source material used, review outcome |
| Data generation | Synthetic data rules, confidentiality check |
""",

    "/Delivery-Management/Module-Status": """# Module Status

This page tracks the maturity of each architecture module across the delivery slices.

## Purpose

The module status page prevents the project from becoming unclear as the build grows. It shows what exists, what is planned, what is blocked and what evidence is available.

## Status scale

| Status | Meaning |
|---|---|
| Not started | No implementation or evidence yet |
| Planned | Backlog item exists but no build evidence yet |
| In progress | Work has started |
| MVP | Basic working version exists |
| Hardened | Tested and improved version exists |
| Evidence captured | Screenshots, logs or tests are available |
| Deferred | Out of scope for current submission |

## Module status table

| Module | Related slice | Current status | Target outcome | Evidence location |
|---|---|---|---|---|
| Source and Data Governance | Slice 0 / Slice 1 | Planned | Source register, data rules, anonymised/synthetic data controls | Evidence Index |
| Ingestion and Preparation | Slice 1 | Planned | Source loading, section builder and metadata tagging | Evidence Index |
| Knowledge and Indexing | Slice 1 / Slice 2 | Planned | Basic retrieval index, then retrieval quality improvement | Evidence Index |
| Assistant API and UI | Slice 1 | Planned | User can ask a process question and receive structured answer | Evidence Index |
| RAG Orchestration | Slice 1 / Slice 2 | Planned | Evidence pack, constrained prompt and grounded answer | Evidence Index |
| Model Runtime | Slice 1 / Slice 2 | Planned | Provider abstraction and draft answer generation | Evidence Index |
| Validation and Safety | Slice 2 | Planned | Citation support checks, confidence and refusal handling | Evidence Index |
| Observability and Audit | Slice 2 / Slice 5 | Planned | Trace logs, model/prompt version and validation outcomes | Evidence Index |
| Analytics and Insight | Slice 3 | Planned | Usage logs and knowledge-gap analysis | Evidence Index |
| Voice Services | Slice 4 | Planned | Speech-to-text and text-to-speech around canonical answer | Evidence Index |
| Build and Evaluation | Slice 0 / Slice 5 | Planned | Test cases, golden questions, regression checks | Evidence Index |
| Delivery Governance | Slice 0 | In progress | Azure DevOps backlog, Wiki, repo, Delivery Plan and governance logs | Azure DevOps |

## Review notes

Update this page after each sprint review. The status should reflect actual evidence, not optimistic intent.
"""
}


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

    for path, content in PAGES.items():
        put_page(wiki_id, path, content)

    print()
    print("Governance Wiki pages created/updated successfully.")
    print("Check Azure DevOps > Wiki > Delivery-Management")


if __name__ == "__main__":
    main()
