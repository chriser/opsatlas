import base64
import os
from pathlib import Path
from typing import Dict, List
from urllib.parse import quote
from xml.sax.saxutils import escape

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


TEST_CASES: List[Dict] = [
    {
        "title": "Verify source register captures required governance fields",
        "description": "Checks that every knowledge source can be registered with owner, source type, sensitivity, approval state and processing state.",
        "steps": [
            ("Open the source register template", "Template is available in the repository or Wiki"),
            ("Add a sample synthetic source record", "Record can be saved with all required fields"),
            ("Check required governance fields", "Owner, source type, sensitivity, approval state and processing state are present"),
        ],
    },
    {
        "title": "Verify synthetic data contains no confidential identifiers",
        "description": "Checks that generated learning data uses neutral terms and does not expose real organisation, person, market or internal system identifiers.",
        "steps": [
            ("Review the synthetic learning data pack", "Data pack is available for review"),
            ("Search for real names, system IDs and market identifiers", "No real confidential identifiers are present"),
            ("Confirm neutral role and system naming", "Terms such as Business Requester and Target Backoffice System are used"),
        ],
    },
    {
        "title": "Verify section builder creates meaningful process sections",
        "description": "Checks that source content is split into useful retrieval sections while preserving context and metadata.",
        "steps": [
            ("Run the section builder on sample learning data", "Section output is generated"),
            ("Inspect section headings and metadata", "Each section has source, heading, process area and metadata"),
            ("Check that sections are not arbitrary text fragments", "Sections preserve meaningful business context"),
        ],
    },
    {
        "title": "Verify retrieval returns expected evidence for golden questions",
        "description": "Checks retrieval quality against predefined golden questions and expected source sections.",
        "steps": [
            ("Run retrieval test using golden question dataset", "Retrieval results are returned"),
            ("Compare retrieved evidence with expected evidence", "Expected source sections appear in top results"),
            ("Record pass/fail result", "Retrieval quality evidence is documented"),
        ],
    },
    {
        "title": "Verify grounded answer includes source evidence",
        "description": "Checks that the assistant answer is based on retrieved source evidence and includes citation-style support.",
        "steps": [
            ("Ask a supported process question", "Assistant returns an answer"),
            ("Inspect evidence references", "Answer includes relevant evidence references"),
            ("Check answer against retrieved evidence", "No unsupported claim is introduced"),
        ],
    },
    {
        "title": "Verify unsupported question is refused or qualified",
        "description": "Checks that the assistant does not invent answers when the knowledge base lacks evidence.",
        "steps": [
            ("Ask a question not covered by the source material", "Assistant recognises insufficient evidence"),
            ("Review response wording", "Response refuses or clearly qualifies the answer"),
            ("Check validation status", "Validation result flags unsupported or low-confidence evidence"),
        ],
    },
    {
        "title": "Verify observability trace is created for each assistant interaction",
        "description": "Checks that query, retrieval, model route, prompt version, validation result and timestamp are recorded.",
        "steps": [
            ("Submit a test question", "Assistant processes the request"),
            ("Open the generated trace record", "Trace record exists"),
            ("Check required trace fields", "Question, evidence IDs, model route, prompt version, validation result and timestamp are present"),
        ],
    },
    {
        "title": "Verify analytics output identifies repeated knowledge gaps",
        "description": "Checks that usage logs can be grouped and interpreted to identify repeated questions, failed retrievals and documentation gaps.",
        "steps": [
            ("Load sample usage log data", "Usage dataset is available"),
            ("Run analytics script or notebook", "Summary output is generated"),
            ("Review grouped results", "Repeated topics, failed retrievals and knowledge gaps are visible"),
        ],
    },
    {
        "title": "Verify end-to-end assistant flow",
        "description": "Checks the full PoC flow from source preparation to grounded answer, validation, logging and analytics evidence.",
        "steps": [
            ("Prepare sample learning data", "Data is available and registered"),
            ("Run ingestion and indexing flow", "Knowledge sections are searchable"),
            ("Ask a supported question", "Grounded response is returned"),
            ("Check validation and trace outputs", "Validation result and trace record are created"),
            ("Run basic analytics over usage logs", "Analytics output is produced"),
        ],
    },
]


def get_auth_header(content_type: str = "application/json-patch+json") -> Dict[str, str]:
    if not PAT:
        raise ValueError("ADO_PAT is missing. Check your .env file.")

    token = base64.b64encode(f":{PAT}".encode("utf-8")).decode("utf-8")

    return {
        "Authorization": f"Basic {token}",
        "Content-Type": content_type,
        "Accept": "application/json",
    }


def build_test_steps_xml(steps: List[tuple]) -> str:
    step_blocks = []

    for index, (action, expected) in enumerate(steps, start=1):
        step_blocks.append(
            f'<step id="{index}" type="ActionStep">'
            f'<parameterizedString isformatted="true">{escape(action)}</parameterizedString>'
            f'<parameterizedString isformatted="true">{escape(expected)}</parameterizedString>'
            f'</step>'
        )

    return f'<steps id="0" last="{len(steps)}">' + "".join(step_blocks) + "</steps>"


def create_test_case(test_case: Dict) -> Dict:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/workitems/$Test%20Case?api-version=7.1"
    )

    payload = [
        {
            "op": "add",
            "path": "/fields/System.Title",
            "value": test_case["title"],
        },
        {
            "op": "add",
            "path": "/fields/System.Description",
            "value": test_case["description"],
        },
        {
            "op": "add",
            "path": "/fields/Microsoft.VSTS.TCM.Steps",
            "value": build_test_steps_xml(test_case["steps"]),
        },
    ]

    response = requests.post(
        url,
        headers=get_auth_header(),
        json=payload,
        timeout=30,
    )

    print(f"Create Test Case: {test_case['title']}")
    print("Status:", response.status_code)

    if response.status_code not in (200, 201):
        print(response.text)
        raise SystemExit(1)

    created = response.json()
    print("Created ID:", created["id"])
    return created


def main() -> None:
    if not ORG or not PROJECT:
        raise ValueError("ADO_ORG or ADO_PROJECT_NAME missing. Check .env file.")

    for test_case in TEST_CASES:
        create_test_case(test_case)

    print("Test Cases created successfully.")


if __name__ == "__main__":
    main()
