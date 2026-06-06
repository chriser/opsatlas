import os
import time
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth


AGILE_PROCESS_TEMPLATE_ID = "adcc42ab-9882-485e-a3ed-7678f01f66bc"


def load_env(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        raise FileNotFoundError(".env file not found")

    for line in env_path.read_text().splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()


def get_auth():
    return HTTPBasicAuth("", os.environ["ADO_PAT"].strip())


def project_exists(org: str, project_name: str) -> bool:
    url = f"https://dev.azure.com/{org}/_apis/projects?api-version=7.1"
    response = requests.get(
        url,
        auth=get_auth(),
        headers={"Accept": "application/json"},
        timeout=30,
    )
    response.raise_for_status()

    return any(
        project.get("name", "").lower() == project_name.lower()
        for project in response.json().get("value", [])
    )


def create_project(org: str, project_name: str) -> str:
    url = f"https://dev.azure.com/{org}/_apis/projects?api-version=7.1"

    payload = {
        "name": project_name,
        "description": (
            "DT602/DT603 planning and delivery space for the AI Knowledge and Analytics Assistant. "
            "This project captures backlog, architecture, repository, pipelines, test cases, delivery plan, wiki, risks and governance evidence."
        ),
        "capabilities": {
            "versioncontrol": {
                "sourceControlType": "Git"
            },
            "processTemplate": {
                "templateTypeId": AGILE_PROCESS_TEMPLATE_ID
            }
        },
        "visibility": "private"
    }

    response = requests.post(
        url,
        json=payload,
        auth=get_auth(),
        headers={"Accept": "application/json"},
        timeout=30,
    )

    print("Create project status:", response.status_code)

    if response.status_code not in (200, 201, 202):
        print(response.text)
        raise SystemExit(1)

    return response.json().get("id", "")


def wait_for_project(org: str, project_name: str, attempts: int = 24) -> None:
    print("Waiting for project to become available...")

    for attempt in range(1, attempts + 1):
        if project_exists(org, project_name):
            print(f"Project is available after check {attempt}.")
            return
        time.sleep(5)

    raise TimeoutError("Project was created but did not become visible in time.")


def main() -> None:
    load_env()

    org = os.environ["ADO_ORG"].strip()
    project_name = os.environ["ADO_PROJECT_NAME"].strip()

    print("Organisation:", org)
    print("Target project:", project_name)
    print("Process template: Agile")
    print("Agile template ID:", AGILE_PROCESS_TEMPLATE_ID)

    if project_exists(org, project_name):
        print("Project already exists. No new project created.")
        return

    operation_id = create_project(org, project_name)
    print("Operation ID:", operation_id)

    wait_for_project(org, project_name)

    print("Project creation completed successfully.")


if __name__ == "__main__":
    main()
