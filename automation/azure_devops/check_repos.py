import os
from pathlib import Path
from urllib.parse import quote

import requests
from requests.auth import HTTPBasicAuth


def load_env(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        raise FileNotFoundError(".env file not found")

    for line in env_path.read_text().splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()


def main() -> None:
    load_env()

    org = os.environ["ADO_ORG"].strip()
    project = os.environ["ADO_PROJECT_NAME"].strip()
    pat = os.environ["ADO_PAT"].strip()

    encoded_project = quote(project, safe="")
    url = f"https://dev.azure.com/{org}/{encoded_project}/_apis/git/repositories?api-version=7.1"

    response = requests.get(
        url,
        auth=HTTPBasicAuth("", pat),
        headers={"Accept": "application/json"},
        timeout=30,
    )

    print("Status code:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    repos = response.json().get("value", [])

    if not repos:
        print("No repositories found in this project.")
        return

    print("Repositories found:")
    for repo in repos:
        print("- Name:", repo.get("name"))
        print("  ID:", repo.get("id"))
        print("  Remote URL:", repo.get("remoteUrl"))
        print("  Web URL:", repo.get("webUrl"))


if __name__ == "__main__":
    main()
