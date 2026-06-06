import os
from pathlib import Path

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
    pat = os.environ["ADO_PAT"].strip()

    url = f"https://dev.azure.com/{org}/_apis/projects?api-version=7.1"

    response = requests.get(
        url,
        auth=HTTPBasicAuth("", pat),
        headers={"Accept": "application/json"},
        timeout=30,
        allow_redirects=False,
    )

    print("Status code:", response.status_code)
    print("Content-Type:", response.headers.get("Content-Type"))

    if response.status_code == 302:
        print("Redirect location:", response.headers.get("Location"))
        print("Authentication failed or PAT not accepted.")
        raise SystemExit(1)

    if response.status_code != 200:
        print(response.text[:1000])
        raise SystemExit(1)

    projects = response.json().get("value", [])

    print("Connection successful.")
    print("Existing Azure DevOps projects:")
    for project in projects:
        print("-", project.get("name"))


if __name__ == "__main__":
    main()
