import base64
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from urllib.parse import quote

import requests
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


DEFAULT_DOCX_PATH = Path(
    "docs/architecture/AI_Knowledge_Assistant_High_Level_Architecture_Artefact_v5_sliced_delivery.docx"
)

WIKI_ROOT = "/Architecture"


SECTION_PAGE_NAMES = {
    "1. Executive architecture summary": "01-Executive-Summary",
    "2. Architectural intent and design principles": "02-Design-Principles",
    "3. Target high-level architecture diagram": "03-High-Level-Diagram",
    "4. Diagram element glossary": "04-Diagram-Element-Glossary",
    "5. RAG framework and hallucination control": "05-RAG-Framework",
    "6. Functional flow": "06-Functional-Flow",
    "7. Core modules and responsibilities": "07-Core-Modules",
    "8. Iterative architecture delivery slices": "08-Iterative-Delivery-Slices",
    "9. Model and voice architecture decisions": "09-Model-and-Voice-Decisions",
    "10. Proposed technology approach": "10-Technology-Approach",
    "11. Analytics and insight layer": "11-Analytics-and-Insight",
    "12. Observability, audit and evaluation": "12-Observability-Audit-Evaluation",
    "13. AI-assisted development and Azure DevOps operating model": "13-AI-Assisted-Development",
    "14. Modular build methodology": "14-Modular-Build-Methodology",
    "15. Ethics, security and data controls": "15-Ethics-Security-Data-Controls",
    "16. Immediate build implications": "16-Immediate-Build-Implications",
    "17. Conclusion": "17-Conclusion",
}


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


def get_project_id() -> str:
    url = f"https://dev.azure.com/{ORG}/_apis/projects/{quote(PROJECT, safe='')}?api-version=7.1"

    response = requests.get(url, headers=auth_header(), timeout=30)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    return response.json()["id"]


def get_or_create_wiki() -> str:
    list_url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wiki/wikis?api-version=7.1"
    )

    response = requests.get(list_url, headers=auth_header(), timeout=30)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    existing = response.json().get("value", [])
    if existing:
        print("Using existing wiki:", existing[0]["name"])
        return existing[0]["id"]

    project_id = get_project_id()

    create_url = f"https://dev.azure.com/{ORG}/_apis/wiki/wikis?api-version=7.1"

    payload = {
        "name": f"{PROJECT}.wiki",
        "projectId": project_id,
        "type": "projectWiki",
    }

    create_response = requests.post(
        create_url,
        headers=auth_header(),
        json=payload,
        timeout=30,
    )

    if create_response.status_code not in (200, 201):
        print(create_response.text)
        raise SystemExit(1)

    wiki = create_response.json()
    print("Created wiki:", wiki["name"])
    return wiki["id"]


def iter_block_items(document: Document) -> Iterable[Paragraph | Table]:
    body = document.element.body

    for child in body.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, document)
        elif child.tag.endswith("}tbl"):
            yield Table(child, document)


def clean_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def escape_table_cell(text: str) -> str:
    text = clean_text(text)
    text = text.replace("|", "\\|")
    text = text.replace("\n", "<br>")
    return text


def table_to_markdown(table: Table) -> str:
    rows: List[List[str]] = []

    for row in table.rows:
        cells = [escape_table_cell(cell.text) for cell in row.cells]
        if any(cells):
            rows.append(cells)

    if not rows:
        return ""

    max_cols = max(len(row) for row in rows)
    rows = [row + [""] * (max_cols - len(row)) for row in rows]

    header = rows[0]
    body = rows[1:]

    lines = []
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * max_cols) + " |")

    for row in body:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines) + "\n"


def paragraph_to_markdown(paragraph: Paragraph) -> str:
    text = clean_text(paragraph.text)

    if not text:
        return ""

    style_name = paragraph.style.name if paragraph.style else ""

    if style_name.startswith("Title"):
        return f"# {text}\n"

    if style_name.startswith("Heading 1"):
        return f"# {text}\n"

    if style_name.startswith("Heading 2"):
        return f"## {text}\n"

    if style_name.startswith("Heading 3"):
        return f"### {text}\n"

    # DOCX numbered sections are not always real heading styles, so detect them.
    if re.match(r"^\d+\.\s+", text):
        return f"# {text}\n"

    if re.match(r"^Figure\s+\d+\.", text):
        return f"> **{text}**\n"

    return f"{text}\n"


def extract_markdown_blocks(docx_path: Path) -> List[str]:
    document = Document(str(docx_path))
    blocks: List[str] = []

    for block in iter_block_items(document):
        if isinstance(block, Paragraph):
            md = paragraph_to_markdown(block)
        elif isinstance(block, Table):
            md = table_to_markdown(block)
        else:
            md = ""

        if md.strip():
            blocks.append(md.strip())

    return blocks


def split_into_pages(blocks: List[str]) -> Dict[str, str]:
    pages: Dict[str, List[str]] = {}
    current_key = "Home"

    pages[current_key] = []

    for block in blocks:
        first_line = block.splitlines()[0].strip()
        heading_text = first_line.lstrip("#").strip()

        if heading_text in SECTION_PAGE_NAMES:
            current_key = heading_text
            pages[current_key] = [block]
        else:
            pages.setdefault(current_key, []).append(block)

    return {key: "\n\n".join(value).strip() + "\n" for key, value in pages.items()}


def build_home_page(section_pages: Dict[str, str]) -> str:
    links = []

    for section_title, page_name in SECTION_PAGE_NAMES.items():
        if section_title in section_pages:
            links.append(f"- [{section_title}]({WIKI_ROOT}/{page_name})")

    return f"""# AI Knowledge and Analytics Assistant Architecture

This Wiki section is generated from the high-level architecture artefact and is aligned to the Azure DevOps Delivery Plan.

## Purpose

The architecture defines a modular, governed and buildable approach for an AI-enabled assistant that helps users understand business processes, onboarding material and transformation knowledge through grounded answers, optional voice interaction and an analytics insight layer.

## Key architectural position

- The first implementation should be a modular monolith with clear internal boundaries.
- The core answer pattern is Retrieval-Augmented Generation.
- The solution should use anonymised or synthetic material unless approved enterprise controls exist.
- The delivery model follows vertical slices rather than a late-integrated horizontal module build.
- The MVP should be proven early, then hardened through retrieval quality, validation, observability, analytics, voice and evidence capture.

## Wiki pages

{chr(10).join(links)}
"""


def wiki_path_for_section(section_title: str) -> str:
    if section_title == "Home":
        return WIKI_ROOT

    page_name = SECTION_PAGE_NAMES.get(section_title)

    if not page_name:
        safe_name = re.sub(r"[^A-Za-z0-9\-]+", "-", section_title).strip("-")
        page_name = safe_name or "Uncategorised"

    return f"{WIKI_ROOT}/{page_name}"


def get_existing_page_etag(wiki_id: str, path: str) -> str | None:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wiki/wikis/{wiki_id}/pages"
        f"?path={quote(path, safe='/')}&includeContent=true&api-version=7.1"
    )

    response = requests.get(url, headers=auth_header(), timeout=30)

    if response.status_code == 404:
        return None

    if response.status_code != 200:
        print(f"Failed to check page: {path}")
        print(response.status_code)
        print(response.text)
        raise SystemExit(1)

    return response.headers.get("ETag")


def put_page(wiki_id: str, path: str, content: str) -> None:
    etag = get_existing_page_etag(wiki_id, path)

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

    print(f"Publish Wiki page: {path}")
    print("Status:", response.status_code)

    if response.status_code not in (200, 201):
        print(response.text)
        raise SystemExit(1)


def main() -> None:
    if not ORG or not PROJECT:
        raise ValueError("ADO_ORG or ADO_PROJECT_NAME missing. Check .env file.")

    if len(sys.argv) > 1:
        docx_path = Path(sys.argv[1])
    else:
        docx_path = DEFAULT_DOCX_PATH

    if not docx_path.exists():
        raise FileNotFoundError(f"DOCX file not found: {docx_path}")

    print("Reading DOCX:", docx_path)

    blocks = extract_markdown_blocks(docx_path)
    pages = split_into_pages(blocks)

    # Replace generated Home with a richer architecture landing page.
    pages["Home"] = build_home_page(pages)

    wiki_id = get_or_create_wiki()

    for section_title, content in pages.items():
        path = wiki_path_for_section(section_title)
        put_page(wiki_id, path, content)

    print()
    print("Architecture Wiki publishing completed.")
    print("Pages published:", len(pages))
    print()
    print("Open Azure DevOps → Wiki → Architecture")


if __name__ == "__main__":
    main()
