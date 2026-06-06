import os
from pathlib import Path
from urllib.parse import quote

import requests
from requests.auth import HTTPBasicAuth


def load_env(path: str = ".env") -> None:
    env_path = Path(path)
    for line in env_path.read_text().splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()


def auth():
    return HTTPBasicAuth("", os.environ["ADO_PAT"].strip())


def main():
    load_env()

    org = os.environ["ADO_ORG"].strip()
    project = os.environ["ADO_PROJECT_NAME"].strip()
    encoded_project = quote(project, safe="")

    wiql_url = f"https://dev.azure.com/{org}/{encoded_project}/_apis/wit/wiql?api-version=7.1"

    query = {
        "query": f"""
        SELECT [System.Id], [System.WorkItemType], [System.Title], [System.State]
        FROM WorkItems
        WHERE [System.TeamProject] = '{project}'
        ORDER BY [System.Id]
        """
    }

    response = requests.post(
        wiql_url,
        json=query,
        auth=auth(),
        headers={"Accept": "application/json"},
        timeout=30,
    )

    print("WIQL status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    refs = response.json().get("workItems", [])

    if not refs:
        print("No work items found.")
        return

    ids = ",".join(str(item["id"]) for item in refs)
    detail_url = f"https://dev.azure.com/{org}/{encoded_project}/_apis/wit/workitems?ids={ids}&$expand=relations&api-version=7.1"

    details = requests.get(
        detail_url,
        auth=auth(),
        headers={"Accept": "application/json"},
        timeout=30,
    )

    print("Details status:", details.status_code)

    if details.status_code != 200:
        print(details.text)
        raise SystemExit(1)

    print("\nExisting work items:\n")

    for item in details.json().get("value", []):
        fields = item.get("fields", {})
        print(f"{item['id']} | {fields.get('System.WorkItemType')} | {fields.get('System.State')} | {fields.get('System.Title')}")


if __name__ == "__main__":
    main()
