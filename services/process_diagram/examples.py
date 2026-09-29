"""Built-in visual examples for the local process diagram service."""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any

from .models import ProcessChartRenderRequest


@dataclass(frozen=True)
class ProcessDiagramExample:
    id: str
    title: str
    summary: str
    payload: dict[str, Any]


def _age_restricted_sale() -> dict[str, Any]:
    """A made-up shop sale in the process map notation: a trigger, three paths from an ANY connector, each starting with
    its condition; an interface to the age check (another process) with its reference; two roles on the steps where the
    cashier and the customer act together; systems, a control, and the join where the paths meet."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    def node(node_id: str, kind: str, label: str, **metadata: str) -> None:
        nodes.append({"id": node_id, "type": kind, "label": label, "metadata": metadata})

    def edge(source: str, target: str, label: str = "", kind: str = "sequence") -> None:
        edges.append({"from": source, "to": target, "label": label, "type": kind})

    node("start", "start", "Customer asks for a product at the till")
    node("identify", "task", "Identify the type of product asked for")
    node("split", "gateway", "", gateway="or")
    node("check_tobacco", "interface", "Carry out age verification check", reference="S.4.2")
    node("checked_tobacco", "event", "Age verification check completed")
    node("confirm", "task", "Confirm the tobacco type required")
    node("drawer", "task", "Locate it in the alphabetical drawer")
    node("scan_tobacco", "task", "Scan the product")
    node("close_tobacco", "task", "Close the age verification prompt")
    node("locate", "task", "Locate the product the customer wanted")
    node("scan_restricted", "task", "Scan the product on the till")
    node("prompt", "event", "Age verification prompt appears at the till")
    node("check_restricted", "interface", "Carry out age verification check", reference="S.4.2")
    node("checked_restricted", "event", "Age verification check completed")
    node("close_restricted", "task", "Close the age verification prompt")
    node("scan_any", "task", "Scan the product on the till")
    node("ticket", "task", "Check the product is on the virtual ticket")
    node("pay", "task", "Take payment")
    node("end", "end", "Sale completed")
    for step, role, external in (("identify", "Site staff", ""), ("identify", "Customer", "true"),
                                 ("confirm", "Site staff", ""), ("confirm", "Customer", "true")):
        role_id = f"who_{step}_{role.split()[0].lower()}"
        node(role_id, "who", role, **({"external": external} if external else {}))
        edge(role_id, step, kind="association")
    for step in ("drawer", "scan_tobacco", "close_tobacco", "locate", "scan_restricted", "close_restricted", "scan_any",
                 "ticket", "pay"):
        node(f"who_{step}", "who", "Site staff")
        edge(f"who_{step}", step, kind="association")
    for step in ("scan_tobacco", "close_tobacco", "scan_restricted", "close_restricted", "scan_any", "ticket", "pay"):
        node(f"till_{step}", "system", "Point of sale")
        edge(f"till_{step}", step, kind="association")
    node("id_rule", "control", "ID checked for anyone who looks under 25")
    edge("id_rule", "check_tobacco", kind="association")
    for source, target, label in (
            ("start", "identify", ""), ("identify", "split", ""),
            ("split", "check_tobacco", "Tobacco or e-cigarette product"), ("check_tobacco", "checked_tobacco", ""),
            ("checked_tobacco", "confirm", ""), ("confirm", "drawer", ""), ("drawer", "scan_tobacco", ""),
            ("scan_tobacco", "close_tobacco", ""), ("close_tobacco", "pay", ""),
            ("split", "locate", "Age-restricted product, not tobacco"), ("locate", "scan_restricted", ""),
            ("scan_restricted", "prompt", ""), ("prompt", "check_restricted", ""), ("check_restricted", "checked_restricted", ""),
            ("checked_restricted", "close_restricted", ""), ("close_restricted", "pay", ""),
            ("split", "scan_any", "Product without an age limit"), ("scan_any", "ticket", ""), ("ticket", "pay", ""),
            ("pay", "end", "")):
        edge(source, target, label)
    return {"style": "plain", "format": "process-flow", "animation": True,
            "process_model": {"title": "Sell an age-restricted product", "nodes": nodes, "edges": edges}}


EXAMPLES: tuple[ProcessDiagramExample, ...] = (
    ProcessDiagramExample(
        id="supplier-setup",
        title="Supplier Setup",
        summary="Cross-functional supplier onboarding with review, decision and finance activation lanes.",
        payload={
            "style": "plain",
            "format": "cross-functional-flowchart",
            "animation": True,
            "process_model": {
                "title": "Supplier Setup Process",
                "nodes": [
                    {"id": "buyer", "type": "lane", "label": "Category Buyer"},
                    {"id": "support", "type": "lane", "label": "Trading Support"},
                    {"id": "finance", "type": "lane", "label": "Finance"},
                    {"id": "complete_form", "type": "task", "label": "Complete supplier setup form", "lane": "buyer"},
                    {"id": "submit_request", "type": "task", "label": "Submit request with due diligence", "lane": "buyer"},
                    {"id": "review_request", "type": "task", "label": "Review submitted setup request", "lane": "support"},
                    {"id": "details_complete", "type": "gateway", "label": "Details complete?", "lane": "support"},
                    {"id": "create_record", "type": "task", "label": "Create supplier master record", "lane": "finance"},
                    {"id": "activate_supplier", "type": "task", "label": "Activate supplier for ordering", "lane": "finance"},
                    {"id": "excel", "type": "system", "label": "Excel", "lane": "systems"},
                    {"id": "supplier_form", "type": "system", "label": "New supplier form", "lane": "systems"},
                    {"id": "credit_check", "type": "control", "label": "Credit check gate", "lane": "support"},
                ],
                "edges": [
                    {"from": "complete_form", "to": "submit_request", "label": "prepare"},
                    {"from": "submit_request", "to": "review_request", "label": "submit"},
                    {"from": "review_request", "to": "details_complete", "label": "validate"},
                    {"from": "details_complete", "to": "create_record", "label": "yes"},
                    {"from": "create_record", "to": "activate_supplier", "label": "record created"},
                    {"from": "excel", "to": "complete_form", "label": "source", "type": "association"},
                    {"from": "supplier_form", "to": "submit_request", "label": "captures", "type": "association"},
                    {"from": "credit_check", "to": "details_complete", "label": "governs", "type": "control"},
                ],
            },
        },
    ),
    ProcessDiagramExample(
        id="article-tax-handling",
        title="Article Tax Handling",
        summary="Article activation flow showing tax validation controls before launch can proceed.",
        payload={
            "style": "executive",
            "format": "cross-functional-flowchart",
            "animation": True,
            "process_model": {
                "title": "Article Integration Tax Handling",
                "nodes": [
                    {"id": "commercial", "type": "lane", "label": "Commercial Owner"},
                    {"id": "tax", "type": "lane", "label": "Tax Team"},
                    {"id": "article_admin", "type": "lane", "label": "Article Admin"},
                    {"id": "prepare_change", "type": "task", "label": "Prepare article integration change", "lane": "commercial"},
                    {"id": "send_tax_pack", "type": "task", "label": "Send tax handling evidence", "lane": "commercial"},
                    {"id": "validate_tax", "type": "task", "label": "Validate tax handling", "lane": "tax"},
                    {"id": "tax_clear", "type": "gateway", "label": "Tax handling clear?", "lane": "tax"},
                    {"id": "resolve_exception", "type": "risk", "label": "Resolve tax exception", "lane": "tax"},
                    {"id": "activate_article", "type": "task", "label": "Activate article after validation", "lane": "article_admin"},
                    {"id": "tax_control", "type": "control", "label": "No activation before tax approval", "lane": "article_admin"},
                    {"id": "master_data", "type": "system", "label": "Article master data", "lane": "article_admin"},
                ],
                "edges": [
                    {"from": "prepare_change", "to": "send_tax_pack", "label": "package"},
                    {"from": "send_tax_pack", "to": "validate_tax", "label": "submit evidence"},
                    {"from": "validate_tax", "to": "tax_clear", "label": "decision"},
                    {"from": "tax_clear", "to": "resolve_exception", "label": "no"},
                    {"from": "tax_clear", "to": "activate_article", "label": "yes"},
                    {"from": "tax_control", "to": "activate_article", "label": "blocks early launch", "type": "control"},
                    {"from": "master_data", "to": "activate_article", "label": "updates", "type": "association"},
                ],
            },
        },
    ),
    ProcessDiagramExample(
        id="knowledge-governance",
        title="Knowledge Governance Review",
        summary="Source onboarding flow from upload and ingestion through governance review and approved answer use.",
        payload={
            "narrative": (
                "The knowledge owner uploads a source file. "
                "The platform ingests the source and extracts sections. "
                "Governance Reviewer reviews high severity issues. "
                "If the source is approved, the assistant can answer with citations."
            ),
            "style": "plain",
            "format": "cross-functional-flowchart",
            "animation": True,
        },
    ),
    ProcessDiagramExample(
        id="age-restricted-sale",
        title="Age-Restricted Sale",
        summary="A branched process in the process map notation: ANY connector, conditions as events, an interface "
                "to another process, two roles on a step, and the join where the paths meet.",
        payload=_age_restricted_sale(),
    ),
)


def list_examples() -> tuple[ProcessDiagramExample, ...]:
    return EXAMPLES


def get_example(example_id: str) -> ProcessDiagramExample | None:
    return next((example for example in EXAMPLES if example.id == example_id), None)


def example_request(example: ProcessDiagramExample) -> ProcessChartRenderRequest:
    return ProcessChartRenderRequest.model_validate(example.payload)


def examples_gallery_html() -> str:
    cards = "\n".join(_example_card(example) for example in EXAMPLES)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Local Process Diagram Examples</title>
  <style>
    body {{
      margin: 0;
      font-family: Arial, sans-serif;
      color: #0f172a;
      background: #eef2f7;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 24px 56px;
    }}
    header {{
      margin-bottom: 24px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 28px;
      letter-spacing: 0;
    }}
    p {{
      line-height: 1.5;
    }}
    .intro {{
      max-width: 820px;
      color: #475569;
      margin: 0;
    }}
    .example {{
      background: #ffffff;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      padding: 18px;
      margin-top: 18px;
      box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
    }}
    .example-header {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 12px;
    }}
    h2 {{
      margin: 0 0 4px;
      font-size: 18px;
      letter-spacing: 0;
    }}
    .summary {{
      margin: 0;
      color: #475569;
    }}
    .actions {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    a {{
      color: #0f766e;
      font-weight: 700;
      text-decoration: none;
    }}
    .action {{
      border: 1px solid #99f6e4;
      background: #f0fdfa;
      border-radius: 6px;
      padding: 8px 10px;
      white-space: nowrap;
    }}
    .frame {{
      overflow: auto;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      background: #f8fafc;
    }}
    .frame img {{
      display: block;
      min-width: 920px;
      max-width: none;
      height: auto;
    }}
    @media (max-width: 760px) {{
      .example-header {{
        display: block;
      }}
      .actions {{
        justify-content: flex-start;
        margin-top: 12px;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Local Process Diagram Examples</h1>
      <p class="intro">
        These diagrams are rendered by the local microservice from the same structured payloads used by Ask and Avatar.
        Use the SVG link to inspect the chart directly, or JSON to see the deterministic layout and animation plan.
      </p>
    </header>
    {cards}
  </main>
</body>
</html>
"""


def _example_card(example: ProcessDiagramExample) -> str:
    title = html.escape(example.title)
    summary = html.escape(example.summary)
    example_id = html.escape(example.id)
    return f"""<section class="example">
  <div class="example-header">
    <div>
      <h2>{title}</h2>
      <p class="summary">{summary}</p>
    </div>
    <div class="actions">
      <a class="action" href="/examples/{example_id}/svg" target="_blank" rel="noreferrer">Open SVG</a>
      <a class="action" href="/examples/{example_id}/json" target="_blank" rel="noreferrer">Open JSON</a>
      <a class="action" href="/examples/{example_id}/payload" target="_blank" rel="noreferrer">Open Payload</a>
    </div>
  </div>
  <div class="frame">
    <img src="/examples/{example_id}/svg" alt="{title} process diagram" />
  </div>
</section>"""
