import os
from pathlib import Path
from urllib.parse import quote

import requests
from requests.auth import HTTPBasicAuth


SPRINTS = [
    ("Sprint 1 - Governance Foundation", "2026-06-15T00:00:00Z", "2026-06-21T23:59:59Z"),
    ("Sprint 2 - Data Strategy and Source Preparation", "2026-06-22T00:00:00Z", "2026-06-28T23:59:59Z"),
    ("Sprint 3 - Ingestion and Section Building", "2026-06-29T00:00:00Z", "2026-07-05T23:59:59Z"),
    ("Sprint 4 - Knowledge Index and Retrieval", "2026-07-06T00:00:00Z", "2026-07-12T23:59:59Z"),
    ("Sprint 5 - Assistant API and RAG Flow", "2026-07-13T00:00:00Z", "2026-07-19T23:59:59Z"),
    ("Sprint 6 - Validation and Observability", "2026-07-20T00:00:00Z", "2026-07-26T23:59:59Z"),
    ("Sprint 7 - Analytics and Insight", "2026-07-27T00:00:00Z", "2026-08-02T23:59:59Z"),
    ("Sprint 8 - Evaluation and Hardening", "2026-08-03T00:00:00Z", "2026-08-09T23:59:59Z"),
    ("Sprint 9 - Final Evidence and Submission Pack", "2026-08-10T00:00:00Z", "2026-08-14T23:59:59Z"),
]


def load_env(path: str = ".env") -> None:
    env_path = Path(path)
    for line in env_path.read_text().splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()


def auth():
    return HTTPBasicAuth("", os.environ["ADO_PAT"].strip())


def create_project_iteration(org: str, project: str, sprint_name: str, start: str, finish: str) -> None:
    encoded_project = quote(project, safe="")
    encoded_sprint_name = quote(sprint_name, safe="")

    url = (
        f"https://dev.azure.com/{org}/{encoded_project}"
        f"/_apis/wit/classificationnodes/iterations/{encoded_sprint_name}"
        f"?api-version=7.1"
    )

    payload = {
        "name": sprint_name,
        "attributes": {
            "startDate": start,
            "finishDate": finish,
        },
    }

    response = requests.put(
        url,
        json=payload,
        auth=auth(),
        headers={"Accept": "application/json"},
        timeout=30,
    )

    print(f"Create/update project iteration: {sprint_name}")
    print("Status:", response.status_code)

    if response.status_code not in (200, 201):
        print(response.text)
        raise SystemExit(1)


def get_default_team(org: str, project: str) -> str:
    encoded_project = quote(project, safe="")
    url = f"https://dev.azure.com/{org}/_apis/projects/{encoded_project}/teams?api-version=7.1"

    response = requests.get(
        url,
        auth=auth(),
        headers={"Accept": "application/json"},
        timeout=30,
    )

    print("Get teams status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    teams = response.json().get("value", [])

    if not teams:
        raise RuntimeError("No teams found for project.")

    return teams[0]["name"]


def add_iteration_to_team(org: str, project: str, team: str, sprint_name: str) -> None:
    encoded_project = quote(project, safe="")
    encoded_team = quote(team, safe="")
    iteration_path = f"{project}\\{sprint_name}"

    url = (
        f"https://dev.azure.com/{org}/{encoded_project}/{encoded_team}"
        f"/_apis/work/teamsettings/iterations?api-version=7.1"
    )

    payload = {
        "id": None,
        "name": sprint_name,
        "path": iteration_path,
    }

    response = requests.post(
        url,
        json=payload,
        auth=auth(),
        headers={"Accept": "application/json"},
        timeout=30,
    )

    print(f"Assign iteration to team: {sprint_name}")
    print("Status:", response.status_code)

    if response.status_code in (200, 201):
        return

    if response.status_code == 400 and "already exists" in response.text.lower():
        print("Already assigned to team.")
        return

    print(response.text)
    raise SystemExit(1)


def main() -> None:
    load_env()

    org = os.environ["ADO_ORG"].strip()
    project = os.environ["ADO_PROJECT_NAME"].strip()

    team = get_default_team(org, project)
    print("Default team:", team)

    for sprint_name, start, finish in SPRINTS:
        create_project_iteration(org, project, sprint_name, start, finish)
        add_iteration_to_team(org, project, team, sprint_name)

    print("Sprint iterations created and assigned successfully.")


if __name__ == "__main__":
    main()
