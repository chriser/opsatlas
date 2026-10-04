"""The module boundaries, as checks that run in the gate (REF S59, the retrospective of 4 October 2026).

Most faults found while delivering the REF programme came from one fact kept in many places: a store written from
several modules, a rule checked at every call site, a private method called from another package. These checks make a
change that reaches across a boundary fail within seconds, instead of being found by a red team days later.

Each rule starts from today's code: what already crosses a boundary is allow-listed below, and the lists only shrink.
A check fails for a new violation, and also for an allowed one that has gone (remove it from its list, so the list
stays true). See docs/ways-of-working/Boundaries.md.
"""
from __future__ import annotations

import ast
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {"assistant": ROOT / "src" / "assistant", "services": ROOT / "services"}


def discover(sources: dict[str, Path] = SOURCES) -> dict[str, tuple[str, bool]]:
    """Every production module: its dotted name, its source text and whether it is a package's ``__init__``."""
    found = {}
    for prefix, base in sources.items():
        for path in sorted(base.rglob("*.py")):
            parts = [p for p in path.relative_to(base).with_suffix("").parts if p != "__init__"]
            found[".".join([prefix, *parts])] = (path.read_text(), path.name == "__init__.py")
    return found


def _targets(name: str, source: str, is_package: bool):
    package = name if is_package else name.rsplit(".", 1)[0]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                base = base[: len(base) - (node.level - 1)]
                target = ".".join(base + ([node.module] if node.module else []))
            else:
                target = node.module or ""
            yield target
            for alias in node.names:
                yield f"{target}.{alias.name}"


def import_graph(modules: dict[str, tuple[str, bool]]) -> dict[str, set[str]]:
    """Which production module imports which (names resolved to the modules that exist)."""
    known = set(modules)

    def resolve(target: str) -> str:
        while target and target not in known:
            target = target.rsplit(".", 1)[0] if "." in target else ""
        return target
    edges: dict[str, set[str]] = defaultdict(set)
    for name, (source, is_package) in modules.items():
        for target in _targets(name, source, is_package):
            resolved = resolve(target)
            if resolved and resolved != name:
                edges[name].add(resolved)
    return edges


def _inside(module: str, package: str) -> bool:
    return module == package or module.startswith(package + ".")


# ---- the import rules -------------------------------------------------------------------------------------------

DOMAIN = ("assistant.content", "assistant.sources", "assistant.answer", "assistant.governance", "assistant.ingestion",
          "assistant.retrieval", "assistant.ontology", "assistant.analytics", "assistant.process", "assistant.regulatory",
          "assistant.evidence", "services")
DOCUMENT_STORES = ("assistant.sources.register", "assistant.ingestion.store", "assistant.content.store")
ENGINE = "services.sme_interviewer"


def _package(module: str) -> str:
    parts = module.split(".")
    return ".".join(parts[:2]) if len(parts) > 1 else module


def _cycle_edges(edges: dict[str, set[str]]) -> set[tuple[str, str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for module, targets in edges.items():
        for target in targets:
            a, b = _package(module), _package(target)
            if a != b:
                graph[a].add(b)
    index, low, stack, on_stack, components, counter = {}, {}, [], set(), [], [0]

    def strong(v):
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on_stack.add(v)
        for w in graph.get(v, ()):
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            component = set()
            while True:
                w = stack.pop()
                on_stack.discard(w)
                component.add(w)
                if w == v:
                    break
            if len(component) > 1:
                components.append(component)
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(limit, 10_000))
    try:
        for v in list(graph):
            if v not in index:
                strong(v)
    finally:
        sys.setrecursionlimit(limit)
    return {(a, b) for component in components for a in component for b in graph[a] if b in component}


RULES = {
    "the core imports the Sales layer or Tibi's engine":
        lambda e: {(m, t) for m, ts in e.items() for t in ts if _inside(m, "assistant") and _inside(t, "services")},
    "IAM imports a domain package":
        lambda e: {(m, t) for m, ts in e.items() for t in ts if _inside(m, "assistant.iam") and t.startswith(DOMAIN)},
    "a document store's module is imported from outside it":
        lambda e: {(m, t) for m, ts in e.items() for t in ts if t in DOCUMENT_STORES and not _inside(m, t)},
    "Tibi's engine imports outside itself":
        lambda e: {(m, t) for m, ts in e.items() for t in ts if _inside(m, ENGINE) and not _inside(t, ENGINE)},
    "an import edge inside a package cycle": _cycle_edges,
}

# Today's crossings, allowed until the work that removes them (REF S60, the Documents component, takes most of the
# document stores' importers; S58 the Sales layer's). Remove an entry when its import goes; never add one without a
# reason recorded in docs/ways-of-working/Boundaries.md.
ALLOWED: dict[str, set[tuple[str, str]]] = {
    "the core imports the Sales layer or Tibi's engine": set(),
    "IAM imports a domain package": set(),
    "a document store's module is imported from outside it": {
        *{(m, "assistant.content.store") for m in ("assistant.content.service", "services.opsatlas_sales.spaces")},
        *{(m, "assistant.ingestion.store") for m in (
            "assistant.api.app", "assistant.api.routes_governance", "assistant.api.routes_ingestion",
            "assistant.api.routes_regulatory", "assistant.governance.intelligence", "assistant.ingestion.service",
            "assistant.regulatory.discovery", "assistant.regulatory.impact", "assistant.retrieval.index",
            "assistant.retrieval.service", "assistant.sources.bulk_import", "services.opsatlas_sales.knowledge",
            "services.opsatlas_sales.spaces", "services.sme_interviewer.atlas_fixture")},
        *{(m, "assistant.sources.register") for m in (
            "assistant.analytics.export", "assistant.api.app", "assistant.api.routes_analytics",
            "assistant.api.routes_governance", "assistant.api.routes_ingestion", "assistant.api.routes_process",
            "assistant.api.routes_regulatory", "assistant.api.routes_sources", "assistant.content.service",
            "assistant.governance.intelligence", "assistant.governance.reanalysis", "assistant.governance.review_jobs",
            "assistant.ingestion.service", "assistant.ontology.sync", "assistant.process.registry",
            "assistant.regulatory.discovery", "assistant.regulatory.impact", "assistant.retrieval.index",
            "assistant.retrieval.service", "assistant.sources.bulk_import", "assistant.sources.service",
            "services.opsatlas_sales.app", "services.opsatlas_sales.governance", "services.opsatlas_sales.spaces",
            "services.sme_interviewer.atlas_fixture")},
    },
    "Tibi's engine imports outside itself": {
        # The benchmark fixture builds a core of its own; the rest is the shared conversation contract and claims.
        *{("services.sme_interviewer.atlas_fixture", t) for t in (
            "assistant.answer.generator", "assistant.answer.service", "assistant.api.app", "assistant.api.auth",
            "assistant.ingestion.sections", "assistant.ingestion.store", "assistant.retrieval.service",
            "assistant.sources.models", "assistant.sources.register")},
        ("services.sme_interviewer.continuous", "services.opsatlas_sales.conversations"),
        ("services.sme_interviewer.text_channel", "services.opsatlas_sales.conversations"),
        ("services.sme_interviewer.evaluate_engine", "services.opsatlas_sales"),
        ("services.sme_interviewer.evaluate_engine", "services.opsatlas_sales.claims"),
        ("services.sme_interviewer.rehearsal", "services.opsatlas_sales"),
        ("services.sme_interviewer.rehearsal", "services.opsatlas_sales.claims"),
        ("services.sme_interviewer.tibi", "services.opsatlas_sales"),
        ("services.sme_interviewer.tibi", "services.opsatlas_sales.claims"),
        ("services.sme_interviewer.interview", "services.opsatlas_sales.foundation"),
        ("services.sme_interviewer.sales_preview", "services.opsatlas_sales.activity"),
        ("services.sme_interviewer.sales_preview", "services.opsatlas_sales.workspace"),
    },
    "an import edge inside a package cycle": {
        ("assistant.analytics", "assistant.governance"), ("assistant.answer", "assistant.analytics"),
        ("assistant.answer", "assistant.evidence"), ("assistant.answer", "assistant.retrieval"),
        ("assistant.eam", "assistant.ontology"), ("assistant.evidence", "assistant.analytics"),
        ("assistant.governance", "assistant.answer"), ("assistant.governance", "assistant.retrieval"),
        ("assistant.ingestion", "assistant.sources"), ("assistant.ontology", "assistant.ingestion"),
        ("assistant.ontology", "assistant.process"), ("assistant.ontology", "assistant.sources"),
        ("assistant.process", "assistant.eam"), ("assistant.process", "assistant.ingestion"),
        ("assistant.process", "assistant.sources"), ("assistant.retrieval", "assistant.answer"),
        ("assistant.sources", "assistant.ingestion"), ("assistant.sources", "assistant.process"),
    },
}


def import_violations(edges: dict[str, set[str]], rule: str, allowed: set | None = None) -> list[str]:
    """What breaks ``rule`` beyond its allow-list, and allowed entries that no longer occur (the list only shrinks)."""
    allowed = ALLOWED[rule] if allowed is None else allowed
    found = RULES[rule](edges)
    new = [f"new: {a} imports {b}" for a, b in sorted(found - allowed)]
    stale = [f"gone (remove it from the allow-list): {a} -> {b}" for a, b in sorted(allowed - found)]
    return new + stale


# ---- store ownership --------------------------------------------------------------------------------------------

STORE_NAME = re.compile(r"^[A-Za-z0-9_.\-]+\.(json|jsonl|db|sqlite|sqlite3)$")

# Each store's file name, and the module (or package) that owns it: only the owner names it in code. A new store is
# declared here with its owner; the exceptions below are today's, to be removed (S58 gives the review history one
# owner; S60 takes the content database's raw access out of the space moves).
STORE_OWNERS = {
    "-confirmations.json": "services.opsatlas_sales.ontology",
    "-results.json": "services.sme_interviewer",
    ".staged.json": "assistant.ingestion.store",
    "accepted_issues.json": "assistant.governance.accepted",
    "action_log.json": "assistant.ontology.actions",
    "agent_runs.json": "assistant.ontology.agent",
    "aliases.json": "services.sme_interviewer",
    "analytics_events.jsonl": "assistant.analytics.event_store",
    "answer-check-evaluation.json": "services.sme_interviewer",
    "answer_feedback.jsonl": "assistant.analytics.feedback",
    "artifacts.json": "services.sme_interviewer",
    "asr-comparison.json": "services.sme_interviewer",
    "audit_trace.json": "assistant.observability.trace",
    "benchmark-cases.json": "services.sme_interviewer",
    "compliance_reasoning_latest_review.json": "assistant.compliance.latest",
    "config.json": "services.sme_interviewer",
    "content.db": "assistant.content.store",
    "conversation-reviews.jsonl": "services.opsatlas_sales.conversations",
    "conversation-runtime.json": "services.sme_interviewer",
    "conversation.json": "services.opsatlas_sales.app",
    "data-dictionary.json": "assistant.analytics.export",
    "eam_taxonomy.json": "assistant.eam.taxonomy",
    "embeddings.json": "assistant.retrieval.embedder",
    "feedback.jsonl": "services.sme_interviewer",
    "foundation.json": "services.opsatlas_sales.foundation",
    "governance-answers.json": "services.opsatlas_sales.governance",
    "governance-kept.json": "services.opsatlas_sales.governance",
    "governance_internal_review_cache.json": "assistant.api.routes_governance",
    "governance_reanalysis_runs.json": "assistant.governance.reanalysis",
    "gpu-voice-development.json": "services.sme_interviewer",
    "iam.db": "assistant.api.auth",
    "improvement_actions.json": "assistant.analytics.improvement",
    "interviews.sqlite": "services.sme_interviewer",
    "judgements.json": "assistant.governance.statement_judge",
    "manifest-cache.json": "services.sme_interviewer",
    "manifest.json": "services.opsatlas_sales.foundation",
    "measurements.json": "services.sme_interviewer",
    "model-lock.json": "services.sme_interviewer",
    "ontology.db": "assistant.ontology.store",
    "pending_actions.json": "assistant.ontology.proposals",
    "pinned-revision.json": "services.sme_interviewer",
    "process_registry.json": "assistant.process.registry",
    "product-ontology.db": "services.opsatlas_sales.app",
    "product-ontology.json": "services.opsatlas_sales.ontology",
    "product.json": "services.opsatlas_sales.foundation",
    "product_ontology.json": "services.opsatlas_sales.ontology",
    "product_schema.json": "services.opsatlas_sales.ontology",
    "profile.json": "services.opsatlas_sales.app",
    "provision-manifest.json": "services.sme_interviewer",
    "public_snapshots.json": "assistant.external.registry",
    "public_sources.json": "assistant.external.registry",
    "ratings.jsonl": "services.sme_interviewer",
    "record_scope.json": "services.opsatlas_sales.statement_governance",
    "registry_schema.json": "assistant.ontology.schema",
    "regulatory_reviews.json": "assistant.regulatory.review",
    "report.json": "services.sme_interviewer",
    "sales-corpus.json": "services.opsatlas_sales.knowledge",
    "sales-records.json": "services.opsatlas_sales.knowledge",
    "sales-review-history.jsonl": "services.opsatlas_sales.knowledge",
    "sales-spoken.json": "services.opsatlas_sales.knowledge",
    "sales-statement-review.json": "services.opsatlas_sales.statement_governance",
    "source_register.json": "assistant.sources.register",
    "space-config.json": "assistant.space_config",
    "space-statements.json": "assistant.space_statements",
    "spaces.json": "services.opsatlas_sales.spaces",
    "statement-embeddings.json": "assistant.governance.statement_index",
    "statement-review-latest.json": "assistant.governance.statement_review",
    "statements.json": "assistant.governance.statements",
    "tibi-owners.json": "services.opsatlas_sales.tibi_owners",
    "timings.sqlite": "services.sme_interviewer",
    "usage_log.json": "assistant.analytics.log",
    "workspace.json": "services.opsatlas_sales.workspace",
}
STORE_ALSO = {
    "content.db": {"services.opsatlas_sales.spaces"},
    "iam.db": {"assistant.iam.__main__", "services.sme_interviewer.replay_latency"},
    "ontology.db": {"assistant.api.app"},
    "product-ontology.json": {"services.opsatlas_sales.app"},
    "sales-review-history.jsonl": {"services.opsatlas_sales.content", "services.opsatlas_sales.governance",
                                   "services.opsatlas_sales.routes_spaces", "services.opsatlas_sales.tibi_api"},
    "spaces.json": {"services.sme_interviewer.replay_latency", "services.sme_interviewer.replay_process_interview"},
    "tibi-owners.json": {"services.sme_interviewer.replay_latency"},
    "workspace.json": {"services.sme_interviewer.replay_latency"},
}


def store_mentions(modules: dict[str, tuple[str, bool]]) -> dict[str, set[str]]:
    """Which production modules name each store's file (as a string constant)."""
    mentions: dict[str, set[str]] = defaultdict(set)
    for name, (source, _) in modules.items():
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and STORE_NAME.match(node.value):
                mentions[node.value].add(name)
    return mentions


def store_violations(mentions: dict[str, set[str]], owners: dict | None = None, also: dict | None = None) -> list[str]:
    owners = STORE_OWNERS if owners is None else owners
    also = STORE_ALSO if also is None else also
    problems = []
    for store, modules in sorted(mentions.items()):
        if store not in owners:
            problems.append(f"undeclared store: {store} (named by {sorted(modules)}): declare its owner in STORE_OWNERS")
            continue
        for module in sorted(modules):
            if not _inside(module, owners[store]) and module not in also.get(store, set()):
                problems.append(f"new: {module} names {store}, owned by {owners[store]}")
        for module in sorted(also.get(store, set()) - modules):
            problems.append(f"gone (remove it from STORE_ALSO): {module} no longer names {store}")
    for store in sorted(set(owners) - set(mentions)):
        problems.append(f"gone (remove it from STORE_OWNERS): {store} is no longer named anywhere")
    return problems
