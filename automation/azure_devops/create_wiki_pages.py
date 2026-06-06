import base64
import os
from pathlib import Path
from typing import Dict, List
from urllib.parse import quote

import requests


def load_env(path: str = ".env") -> None:
    env_path = Path(path)
    for line in env_path.read_text().splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()


load_env()

ORG = os.getenv("ADO_ORG")
PROJECT = os.getenv("ADO_PROJECT_NAME")
PAT = os.getenv("ADO_PAT")


def get_auth_header(content_type: str = "application/json") -> Dict[str, str]:
    if not PAT:
        raise ValueError("ADO_PAT is missing. Check your .env file.")

    token = base64.b64encode(f":{PAT}".encode("utf-8")).decode("utf-8")

    return {
        "Authorization": f"Basic {token}",
        "Content-Type": content_type,
        "Accept": "application/json",
    }


def get_project_id() -> str:
    url = f"https://dev.azure.com/{ORG}/_apis/projects/{quote(PROJECT, safe='')}?api-version=7.1"

    response = requests.get(url, headers=get_auth_header(), timeout=30)

    print("Get project status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    return response.json()["id"]


def get_or_create_wiki(project_id: str) -> str:
    list_url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wiki/wikis?api-version=7.1"
    )

    response = requests.get(list_url, headers=get_auth_header(), timeout=30)

    print("List wikis status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    existing = response.json().get("value", [])
    if existing:
        wiki = existing[0]
        print("Using existing wiki:", wiki["name"])
        return wiki["id"]

    create_url = f"https://dev.azure.com/{ORG}/_apis/wiki/wikis?api-version=7.1"

    payload = {
        "name": f"{PROJECT}.wiki",
        "projectId": project_id,
        "type": "projectWiki",
    }

    create_response = requests.post(
        create_url,
        headers=get_auth_header(),
        json=payload,
        timeout=30,
    )

    print("Create wiki status:", create_response.status_code)

    if create_response.status_code not in (200, 201):
        print(create_response.text)
        raise SystemExit(1)

    wiki = create_response.json()
    print("Created wiki:", wiki["name"])
    return wiki["id"]


def put_page(wiki_id: str, path: str, content: str) -> None:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wiki/wikis/{wiki_id}/pages?path={quote(path, safe='/')}&api-version=7.1"
    )

    payload = {
        "content": content
    }

    response = requests.put(
        url,
        headers=get_auth_header(),
        json=payload,
        timeout=30,
    )

    print(f"Create/update Wiki page: {path}")
    print("Status:", response.status_code)

    if response.status_code not in (200, 201):
        print(response.text)
        raise SystemExit(1)


PAGES: List[Dict[str, str]] = [
    {
        "path": "/Project-Overview",
        "content": """# Project Overview

## Purpose

This Wiki supports the DT602/DT603 planning and delivery of the AI Knowledge and Analytics Assistant proof of concept.

The assistant is intended to help users understand business process knowledge through grounded answers, controlled source evidence and usage analytics.

## Delivery context

DT602 is treated as the planning, ethical design and proposal stage. DT603 will become the execution/build stage. DT604 will provide retrospective evaluation.

## Core outcome

The project will demonstrate a safe, governed and testable approach to building an AI-enabled knowledge assistant using anonymised or synthetic learning data.
""",
    },
    {
        "path": "/Architecture",
        "content": """# Architecture

## Architectural approach

The proposed architecture is a modular monolith. This avoids unnecessary microservice complexity while keeping clear internal boundaries between ingestion, knowledge indexing, retrieval, model runtime, validation, analytics, observability and delivery governance.

## Core design pattern

The assistant will use Retrieval-Augmented Generation. The model should not act as an uncontrolled source of truth. Instead, it should answer using a controlled evidence pack retrieved from approved, anonymised or synthetic source material.

## Main architecture layers

1. Source Knowledge Layer
2. Ingestion and Governance Layer
3. Knowledge and Index Layer
4. Interaction Channels
5. Assistant API and Session Layer
6. RAG Orchestration Layer
7. Model Runtime Layer
8. Validation and Response Layer
9. Analytics and Insight Layer
10. Build, Test and Evaluation Layer
11. Delivery Governance Layer
12. Observability, Audit and Evaluation Layer
""",
    },
    {
        "path": "/Data-and-Governance",
        "content": """# Data and Governance

## Data position

The project will avoid use of live confidential organisational data outside approved controls. The preferred project route is to use anonymised and synthetic learning data.

## Data controls

- Data minimisation
- Anonymisation and generalisation
- Source registration
- Sensitivity classification
- Access assumptions
- Human review
- Auditability
- Clear distinction between confirmed facts and open design decisions

## Synthetic data rationale

Synthetic data allows the project to demonstrate the intended assistant behaviour without exposing confidential organisational information, personal data, commercial details or internal identifiers.
""",
    },
    {
        "path": "/Delivery-Management",
        "content": """# Delivery Management

## Azure DevOps operating model

Azure DevOps is used as the delivery governance layer for this proof of concept.

## Delivery artefacts

- Epic, Feature, User Story and Task backlog
- Sprint timeline
- Test Case work items
- Repository and documentation structure
- Pipeline YAML
- Wiki documentation
- Decision log
- Risk log
- Evidence records

## Sprint window

The planned delivery window runs from 15 June 2026 to 14 August 2026, allowing time before the 24 August 2026 submission deadline to complete write-up and evidence preparation.
""",
    },
    {
        "path": "/Testing-and-Evaluation",
        "content": """# Testing and Evaluation

## Testing approach

Testing will combine automated tests, structured Azure DevOps Test Case work items and manual review evidence.

## Planned test areas

- Source register validation
- Synthetic data confidentiality checks
- Section builder output
- Retrieval quality
- Grounded answer generation
- Unsupported question refusal
- Observability trace creation
- Analytics output
- End-to-end assistant flow

## Evaluation approach

The project will use golden questions, retrieval checks, validation outcomes, usage logs and feedback patterns to assess whether the assistant is accurate, useful and safe enough for proof-of-concept purposes.
""",
    },
    {
        "path": "/Final-Evidence",
        "content": """# Final Evidence

## Purpose

This section will hold links and notes for DT603 build evidence and later DT604 retrospective evaluation.

## Evidence to capture

- Azure Boards backlog screenshots
- Sprint plan screenshots
- Repo structure screenshots
- Pipeline run evidence
- Test Case evidence
- Wiki documentation screenshots
- Architecture updates
- Build screenshots
- Evaluation results
- Limitations and next steps
""",
    },
]


def main() -> None:
    if not ORG or not PROJECT:
        raise ValueError("ADO_ORG or ADO_PROJECT_NAME missing. Check .env file.")

    project_id = get_project_id()
    wiki_id = get_or_create_wiki(project_id)

    for page in PAGES:
        put_page(wiki_id, page["path"], page["content"])

    print("Wiki pages created successfully.")


if __name__ == "__main__":
    main()
