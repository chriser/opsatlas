"""The module boundaries, as checks that run in the gate (REF S59, the retrospective of 4 October 2026).

Most faults found while delivering the REF programme came from one fact kept in many places: a store written from
several modules, a rule checked at every call site, a private method called from another package. These checks make a
change that reaches across a boundary fail within seconds, instead of being found by a red team days later.

Each rule starts from today's code: what already crosses a boundary is allow-listed below, and the lists only shrink.
A check fails for a new violation, and also for an allowed one that has gone (remove it from its list, so the list
stays true). See docs/ways-of-working/Boundaries.md, which also states what the checks do not see.
"""
from __future__ import annotations

import ast
import io
import re
import sys
import tokenize
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Production code: every module under src/ (today the core, `assistant`; a new top-level package there is checked too)
# and under services/ (the Sales layer and Tibi's engine), each folder with the prefix its modules' names start with.
SOURCES = {ROOT / "src": "", ROOT / "services": "services"}


def discover(sources: dict[Path, str] = SOURCES) -> dict[str, tuple[str, bool]]:
    """Every production module: its dotted name, its source text and whether it is a package's ``__init__``."""
    found = {}
    for base, prefix in sources.items():
        for path in sorted(base.rglob("*.py")):
            parts = [p for p in path.relative_to(base).with_suffix("").parts if p != "__init__"]
            name = ".".join(filter(None, [prefix, *parts]))
            if name:
                found[name] = (path.read_text(), path.name == "__init__.py")
    return found


def _absolute(name: str, is_package: bool, node: ast.ImportFrom) -> str:
    """The module a ``from … import`` names, relative imports resolved against the importing module."""
    if not node.level:
        return node.module or ""
    base = (name if is_package else name.rsplit(".", 1)[0]).split(".")
    base = base[: len(base) - (node.level - 1)]
    return ".".join(base + ([node.module] if node.module else []))


def _imports_by_name(func: ast.expr) -> bool:
    """``importlib.import_module("…")`` or ``__import__("…")``: an import whose module is named by a string."""
    return (isinstance(func, ast.Name) and func.id in {"__import__", "import_module"}) or (
        isinstance(func, ast.Attribute) and func.attr == "import_module")


def _targets(name: str, source: str, is_package: bool):
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            target = _absolute(name, is_package, node)
            yield target
            for alias in node.names:
                yield f"{target}.{alias.name}"
        elif (isinstance(node, ast.Call) and _imports_by_name(node.func) and node.args
              and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
            yield node.args[0].value


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

SALES_AND_ENGINE = "services"
IAM = "assistant.iam"
IAM_MAY_IMPORT = {"assistant", "assistant.settings"}  # the settings (and the package root, through `from .. import`)
DOCUMENT_STORES = ("assistant.sources.register", "assistant.ingestion.store", "assistant.content.store")
ENGINE = "services.sme_interviewer"


def _package(module: str) -> str:
    parts = module.split(".")
    return ".".join(parts[:2]) if len(parts) > 1 else module


def _cycle_edges(edges: dict[str, set[str]]) -> set[tuple[str, str]]:
    """The import edges between packages (``assistant.answer``, ``services.opsatlas_sales``) inside a package cycle."""
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
        lambda e: {(m, t) for m, ts in e.items() for t in ts
                   if not _inside(m, SALES_AND_ENGINE) and _inside(t, SALES_AND_ENGINE)},
    "IAM imports outside itself, beyond the settings":
        lambda e: {(m, t) for m, ts in e.items() for t in ts
                   if _inside(m, IAM) and not _inside(t, IAM) and t not in IAM_MAY_IMPORT},
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
    "IAM imports outside itself, beyond the settings": set(),
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


# ---- private names ----------------------------------------------------------------------------------------------

def _private(name: str) -> bool:
    return name.startswith("_") and not (name.startswith("__") and name.endswith("__"))


def _dotted(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        inner = _dotted(node.value)
        return f"{inner}.{node.attr}" if inner else None
    return None


def private_uses(modules: dict[str, tuple[str, bool]]) -> set[tuple[str, str]]:
    """Each private name (``_x``, not a dunder) a production module takes from another production module, by importing
    it (``from m import _x``) or through the module's name (``m._x``): ``(user, "m._x")``. Ruff's SLF001 covers the
    private members of objects, and sees neither import; Tibi's engine may use its own modules' private names."""
    known = set(modules)
    found = set()
    for name, (source, is_package) in modules.items():
        tree = ast.parse(source)
        bound: dict[str, str] = {}  # a name this module binds to another module
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                base = _absolute(name, is_package, node)
                for alias in node.names:
                    if f"{base}.{alias.name}" in known:
                        bound[alias.asname or alias.name] = f"{base}.{alias.name}"
                    if _private(alias.name) and base in known:
                        found.add((name, f"{base}.{alias.name}"))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname:
                        bound[alias.asname] = alias.name
                    else:  # `import a.b.c` binds `a`; `a.b.c._x` is then read through it
                        bound[alias.name.split(".")[0]] = alias.name.split(".")[0]
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and _private(node.attr) and (owner := _dotted(node.value)):
                head, _, rest = owner.partition(".")
                if head in bound and (module := ".".join(filter(None, [bound[head], rest]))) in known:
                    found.add((name, f"{module}.{node.attr}"))
    # A private name is its module's (a package's, its package's): only a module outside it is reaching in.
    return {(user, used) for user, used in found
            if not _inside(user, used.rsplit(".", 1)[0]) and not (_inside(user, ENGINE) and _inside(used, ENGINE))}


# Today's, removed by REF S68 #2184 (public ways in); the engine's by its next version (its files are under its
# fingerprint).
PRIVATE_ALLOWED: set[tuple[str, str]] = {
    *{("services.opsatlas_sales.governance", f"assistant.governance.intelligence.{n}") for n in (
        "_LINK", "_expansion_matches_acronym", "_readability_sentences", "_readability_word_count")},
    ("services.opsatlas_sales.knowledge", "assistant.retrieval.service._cosine"),
    ("services.opsatlas_sales.knowledge", "assistant.retrieval.service._tokenize"),
    ("services.opsatlas_sales.service_principals", "assistant.api.access._walk"),
    ("services.sme_interviewer.tibi", "services.opsatlas_sales.claims._ALLOWED_ACRONYMS"),
    ("assistant.governance.intelligence", "assistant.retrieval.service._cosine"),
    *{("assistant.eval.oag_coverage", f"assistant.eval.rag_vs_oag.{n}") for n in (
        "_best_fact_match", "_content_tokens", "_normalise_text")},
}


def private_violations(found: set[tuple[str, str]], allowed: set | None = None) -> list[str]:
    """Private names taken from another module beyond the allow-list, and allowed ones that have gone."""
    allowed = PRIVATE_ALLOWED if allowed is None else allowed
    new = [f"new: {a} uses {b}" for a, b in sorted(found - allowed)]
    stale = [f"gone (remove it from the allow-list): {a} -> {b}" for a, b in sorted(allowed - found)]
    return new + stale


# ---- store ownership --------------------------------------------------------------------------------------------

# A store's file name: a string constant's last path component ('content.db', 'data/ontology.db', or the '/content.db'
# part of f'{root}/content.db'), also inside a SQLite URI with a query ('file:content.db?mode=ro', REF S65, S59's N1).
STORE_NAME = re.compile(r"(?:^|[/\\:])([A-Za-z0-9_.\-]+\.(?:json|jsonl|db|sqlite|sqlite3))(?:\?.*)?$")


# ---- file-level marks -------------------------------------------------------------------------------------------

# A file-level mark (ruff's file-wide noqa directive with no codes, or naming SLF001) would let every reach-in in its
# file pass without a mark of its own, unseen by the count of marks (REF S65, S59's N2). Production code has none; the
# private-member check's own exemptions are in pyproject.toml.
FILE_MARK = re.compile(r"#\s*(?:ruff|flake8)\s*:\s*noqa(?:\s*:\s*(?P<codes>[A-Za-z]+[0-9]+(?:\s*,\s*[A-Za-z]+[0-9]+)*))?",
                       re.IGNORECASE)


def _comments(source: str):
    """Each comment of a module, as written (comments only: never a docstring or a string)."""
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                yield token.string
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return


def file_level_marks(modules: dict[str, tuple[str, bool]], sources: dict[str, str] | None = None) -> list[str]:
    """Production files (Tibi's engine aside, which the check exempts) with a file-wide mark that is blanket or names
    SLF001, in any form ruff honours: the ruff or flake8 prefix, indented or not, with words after the codes (REF S65,
    its independent review's F1). Any comment that reads as such a mark counts, wherever it stands, so the check fails
    closed. ``sources`` adds files outside the modules (the scripts), by path."""
    found = []
    files = {name: source for name, (source, _) in modules.items() if not _inside(name, ENGINE)} | (sources or {})
    for name, source in sorted(files.items()):
        for comment in _comments(source):
            mark = FILE_MARK.search(comment)
            if mark is None or mark.start() != comment.index("#"):
                continue
            codes = (mark.group("codes") or "").upper().replace(" ", "").split(",") if mark.group("codes") else []
            if not codes or "SLF001" in codes:
                found.append(f"{name}: {comment.strip()}")
    return found


# Each store's file name, and the module (or package) that owns it: only the owner names it in code. A new store is
# declared here with its owner; the exceptions below are today's. S58 gives the review history one owner and S60 takes
# the content database's raw access out of the space moves. The others are wiring and tooling that name another
# owner's file, kept unless a change removes them: the apps building a store at its path (the ontology store; the
# ontology drift check), the IAM recovery command opening the IAM store, the engine's replays copying a workspace and
# its fingerprint listing the files it covers, the Sales records reading the product corpus, and the evaluations and
# the evidence report naming what they read.
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
    "concurrent-report.json": "services.sme_interviewer",
    "concurrent-turns-report.json": "services.sme_interviewer",
    "config.json": "services.sme_interviewer",
    "content.db": "assistant.content.store",
    "conversation-evaluation.json": "services.sme_interviewer",
    "conversation-reviews.jsonl": "services.opsatlas_sales.conversations",
    "conversation-runtime.json": "services.sme_interviewer",
    "conversation.json": "services.opsatlas_sales.app",
    "data-dictionary.json": "assistant.analytics.export",
    "default_assumptions.json": "assistant.evidence.validation",
    "eam_taxonomy.json": "assistant.eam.taxonomy",
    "embeddings.json": "assistant.retrieval.embedder",
    "engine-versions.json": "services.sme_interviewer",
    "feedback.jsonl": "services.sme_interviewer",
    "foundation.json": "services.opsatlas_sales.foundation",
    "governance-answers.json": "services.opsatlas_sales.governance",
    "governance-kept.json": "services.opsatlas_sales.governance",
    "governance_internal_review_cache.json": "assistant.api.routes_governance",
    "governance_reanalysis_runs.json": "assistant.governance.reanalysis",
    "gpu-voice-development.json": "services.sme_interviewer",
    "iam.db": "assistant.api.auth",
    "improvement_actions.json": "assistant.analytics.improvement",
    "interview-evaluation.json": "services.sme_interviewer",
    "interviews.sqlite": "services.sme_interviewer",
    "judgements.json": "assistant.governance.statement_judge",
    "latency-budget.json": "services.sme_interviewer",
    "manifest-cache.json": "services.sme_interviewer",
    "manifest.json": "services.opsatlas_sales.foundation",
    "measurements.json": "services.sme_interviewer",
    "model-lock.json": "services.sme_interviewer",
    "ontology.db": "assistant.ontology.store",
    "openapi.json": "assistant.api.access",  # the API schema's route, '/openapi.json', not a file
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
    "question-review-evaluation.json": "services.sme_interviewer",
    "rag_vs_oag_questions.json": "assistant.eval.rag_vs_oag",
    "ratings.jsonl": "services.sme_interviewer",
    "recognition-stress.json": "services.sme_interviewer",
    "record_scope.json": "services.opsatlas_sales.statement_governance",
    "registry_schema.json": "assistant.ontology.schema",
    "regulatory_reviews.json": "assistant.regulatory.review",
    "report.json": "services.sme_interviewer",
    "routing-models.json": "services.sme_interviewer",
    "runtime-checks.json": "services.sme_interviewer",
    "sales-corpus.json": "services.opsatlas_sales.knowledge",
    "sales-records.json": "services.opsatlas_sales.knowledge",
    "sales-review-history.jsonl": "services.opsatlas_sales.knowledge",
    "sales-spoken.json": "services.opsatlas_sales.knowledge",
    "sales-statement-review.json": "services.opsatlas_sales.statement_governance",
    "scenarios.json": "services.sme_interviewer",
    "simulator-scenarios.json": "assistant.evidence.validation",
    "source_register.json": "assistant.sources.register",
    "space-config.json": "assistant.space_config",
    "space-statements.json": "assistant.space_statements",
    "spaces.json": "services.opsatlas_sales.spaces",
    "spoken-flow-development.json": "services.sme_interviewer",
    "statement-embeddings.json": "assistant.governance.statement_index",
    "statement-review-latest.json": "assistant.governance.statement_review",
    "statements.json": "assistant.governance.statements",
    "supplier.json": "services.sme_interviewer",
    "tibi-owners.json": "services.opsatlas_sales.tibi_owners",
    "timings.sqlite": "services.sme_interviewer",
    "usage_log.json": "assistant.analytics.log",
    "workspace.json": "services.opsatlas_sales.workspace",
}
STORE_ALSO = {
    "content.db": {"services.opsatlas_sales.spaces"},
    "iam.db": {"assistant.iam.__main__", "services.sme_interviewer.replay_latency"},
    "ontology.db": {"assistant.api.app", "assistant.eval.oag_coverage"},
    "product-ontology.json": {"services.opsatlas_sales.app"},
    "product.json": {"services.opsatlas_sales.knowledge"},
    "product_ontology.json": {"services.sme_interviewer.manifest"},  # the engine's fingerprint lists the file
    "product_schema.json": {"services.sme_interviewer.manifest"},
    "rag_vs_oag_questions.json": {"assistant.evidence.validation"},
    "sales-review-history.jsonl": {"services.opsatlas_sales.content", "services.opsatlas_sales.governance",
                                   "services.opsatlas_sales.routes_spaces", "services.opsatlas_sales.tibi_api"},
    "spaces.json": {"services.sme_interviewer.replay_latency", "services.sme_interviewer.replay_process_interview"},
    "tibi-owners.json": {"services.sme_interviewer.replay_latency"},
    "workspace.json": {"services.sme_interviewer.replay_latency"},
}


def store_mentions(modules: dict[str, tuple[str, bool]]) -> dict[str, set[str]]:
    """Which production modules name each store's file (a string constant, or a constant part of an f-string)."""
    mentions: dict[str, set[str]] = defaultdict(set)
    for name, (source, _) in modules.items():
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and (found := STORE_NAME.search(node.value)):
                mentions[found.group(1)].add(name)
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
