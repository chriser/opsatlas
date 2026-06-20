import base64
import html
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
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

OUT_DIR = Path("exports/wiki")
PAGES_DIR = OUT_DIR / "pages"


def auth_header(content_type: str = "application/json", accept: str = "application/json") -> Dict[str, str]:
    if not PAT:
        raise ValueError("ADO_PAT is missing. Check your .env file.")

    token = base64.b64encode(f":{PAT}".encode("utf-8")).decode("utf-8")

    return {
        "Authorization": f"Basic {token}",
        "Content-Type": content_type,
        "Accept": accept,
    }


def safe_filename(path: str) -> str:
    clean = path.strip("/").replace("/", "__")
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", clean)
    return clean or "Home"


def get_wiki() -> Dict:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wiki/wikis?api-version=7.1"
    )

    response = requests.get(url, headers=auth_header(), timeout=30)

    print("List wikis status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    wikis = response.json().get("value", [])
    if not wikis:
        raise RuntimeError("No Wiki found.")

    wiki = wikis[0]
    print("Using Wiki:", wiki.get("name"), "|", wiki.get("id"))
    return wiki


def list_wiki_pages(wiki_id: str) -> List[Dict]:
    pages: List[Dict] = []
    continuation_token: Optional[str] = None

    while True:
        url = (
            f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
            f"/_apis/wiki/wikis/{wiki_id}/pagesbatch?api-version=7.1"
        )

        payload = {"top": 100}
        if continuation_token:
            payload["continuationToken"] = continuation_token

        response = requests.post(
            url,
            headers=auth_header(),
            json=payload,
            timeout=30,
        )

        print("Pages batch status:", response.status_code)

        if response.status_code != 200:
            print(response.text)
            raise SystemExit(1)

        body = response.json()
        pages.extend(body.get("value", []))

        continuation_token = response.headers.get("x-MS-ContinuationToken")
        if not continuation_token:
            break

    # Parent pages first, then alphabetical.
    pages = sorted(
        pages,
        key=lambda p: (p.get("path", "").count("/"), p.get("path", "").lower())
    )

    return pages


def get_page_content(wiki_id: str, path: str) -> str:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wiki/wikis/{wiki_id}/pages"
        f"?path={quote(path, safe='/')}&includeContent=true&api-version=7.1"
    )

    response = requests.get(url, headers=auth_header(), timeout=30)

    if response.status_code != 200:
        print(f"Failed to fetch page: {path}")
        print(response.status_code)
        print(response.text)
        raise SystemExit(1)

    return response.json().get("content", "")


def markdown_to_basic_html(markdown_text: str) -> str:
    """
    Lightweight fallback HTML conversion.
    This is intentionally simple. Pandoc gives better output if installed.
    """
    lines = []
    in_table = False

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()

        if line.startswith("# "):
            lines.append(f"<h1>{html.escape(line[2:].strip())}</h1>")
        elif line.startswith("## "):
            lines.append(f"<h2>{html.escape(line[3:].strip())}</h2>")
        elif line.startswith("### "):
            lines.append(f"<h3>{html.escape(line[4:].strip())}</h3>")
        elif line.startswith("- "):
            lines.append(f"<li>{html.escape(line[2:].strip())}</li>")
        elif line.startswith("|") and line.endswith("|"):
            # Keep markdown tables readable as preformatted text in fallback HTML.
            if not in_table:
                lines.append("<pre>")
                in_table = True
            lines.append(html.escape(line))
        else:
            if in_table:
                lines.append("</pre>")
                in_table = False

            if not line.strip():
                lines.append("")
            else:
                lines.append(f"<p>{html.escape(line)}</p>")

    if in_table:
        lines.append("</pre>")

    return "\n".join(lines)


def create_html(combined_md: Path, combined_html: Path) -> None:
    pandoc = shutil.which("pandoc")

    if pandoc:
        result = subprocess.run(
            [
                pandoc,
                str(combined_md),
                "-f",
                "gfm",
                "-t",
                "html",
                "-s",
                "-o",
                str(combined_html),
                "--metadata",
                "title=AI Knowledge and Analytics Assistant Wiki Export",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print("HTML created with pandoc:", combined_html)
            return

        print("Pandoc HTML conversion failed, falling back to simple HTML.")
        print(result.stderr)

    md_text = combined_md.read_text(encoding="utf-8")
    body = markdown_to_basic_html(md_text)

    html_text = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>AI Knowledge and Analytics Assistant Wiki Export</title>
<style>
body {{
  font-family: Arial, sans-serif;
  line-height: 1.5;
  max-width: 1100px;
  margin: 40px auto;
  padding: 0 24px;
}}
h1, h2, h3 {{
  color: #222;
}}
pre {{
  white-space: pre-wrap;
  background: #f6f8fa;
  padding: 12px;
  border: 1px solid #ddd;
  overflow-x: auto;
}}
p {{
  margin: 0 0 12px;
}}
li {{
  margin-bottom: 4px;
}}
</style>
</head>
<body>
{body}
</body>
</html>
"""
    combined_html.write_text(html_text, encoding="utf-8")
    print("HTML created with fallback converter:", combined_html)


def create_pdf_if_possible(combined_md: Path, combined_pdf: Path) -> None:
    pandoc = shutil.which("pandoc")

    if not pandoc:
        print("PDF not created because pandoc is not installed.")
        print("Install with: brew install pandoc")
        return

    result = subprocess.run(
        [
            pandoc,
            str(combined_md),
            "-f",
            "gfm",
            "-o",
            str(combined_pdf),
            "--metadata",
            "title=AI Knowledge and Analytics Assistant Wiki Export",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print("PDF created:", combined_pdf)
    else:
        print("PDF export failed.")
        print(result.stderr)
        print("You may need a PDF engine. On macOS, try:")
        print("brew install --cask basictex")
        print("or export the generated HTML to PDF from your browser.")


def main() -> None:
    if not ORG or not PROJECT:
        raise ValueError("ADO_ORG or ADO_PROJECT_NAME missing. Check .env file.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PAGES_DIR.mkdir(parents=True, exist_ok=True)

    wiki = get_wiki()
    wiki_id = wiki["id"]

    pages = list_wiki_pages(wiki_id)
    print("Pages found:", len(pages))

    exported_pages = []

    for page in pages:
        path = page.get("path")
        if not path:
            continue

        print("Exporting:", path)

        content = get_page_content(wiki_id, path)

        page_record = {
            "id": page.get("id"),
            "path": path,
            "content": content,
            "order": page.get("order"),
            "gitItemPath": page.get("gitItemPath"),
            "remoteUrl": page.get("remoteUrl"),
        }

        exported_pages.append(page_record)

        md_file = PAGES_DIR / f"{safe_filename(path)}.md"
        md_file.write_text(content, encoding="utf-8")

    export = {
        "exportedAtUtc": datetime.now(timezone.utc).isoformat(),
        "organization": ORG,
        "project": PROJECT,
        "wiki": {
            "id": wiki.get("id"),
            "name": wiki.get("name"),
            "type": wiki.get("type"),
            "remoteUrl": wiki.get("remoteUrl"),
        },
        "pageCount": len(exported_pages),
        "pages": exported_pages,
    }

    json_path = OUT_DIR / "wiki_pages.json"
    json_path.write_text(json.dumps(export, indent=2), encoding="utf-8")

    combined_md = OUT_DIR / "wiki_combined.md"

    combined_parts = [
        "# AI Knowledge and Analytics Assistant Wiki Export",
        "",
        f"Exported at UTC: {export['exportedAtUtc']}",
        f"Project: {PROJECT}",
        f"Wiki: {wiki.get('name')}",
        "",
        "## Contents",
        "",
    ]

    for page in exported_pages:
        combined_parts.append(f"- {page['path']}")

    combined_parts.append("")
    combined_parts.append("---")
    combined_parts.append("")

    for page in exported_pages:
        combined_parts.append(f"# {page['path']}")
        combined_parts.append("")
        combined_parts.append(page["content"] or "_No content exported._")
        combined_parts.append("")
        combined_parts.append("---")
        combined_parts.append("")

    combined_md.write_text("\n".join(combined_parts), encoding="utf-8")

    combined_html = OUT_DIR / "wiki_combined.html"
    combined_pdf = OUT_DIR / "wiki_combined.pdf"

    create_html(combined_md, combined_html)
    create_pdf_if_possible(combined_md, combined_pdf)

    print()
    print("Wiki export completed.")
    print("JSON:", json_path)
    print("Combined Markdown:", combined_md)
    print("Individual Markdown pages:", PAGES_DIR)
    print("HTML:", combined_html)
    if combined_pdf.exists():
        print("PDF:", combined_pdf)


if __name__ == "__main__":
    main()
