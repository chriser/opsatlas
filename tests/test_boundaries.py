"""The module boundaries hold (REF S59): promises G1–G3.

- G1: a change that adds an import across a boundary, names a store's file outside its owner, or reaches into another
  module's private member (an object's, through ruff; a module's name, imported or read through the module, here)
  fails the gate within seconds. What the checks do not see is stated in docs/ways-of-working/Boundaries.md.
- G2: nothing in the running app changes (these are checks, not behaviour).
- G3: the allow-lists only shrink: an allowed crossing that has gone must be removed from its list.

The rules and their allow-lists are in tests/boundary_rules.py; the reasons in docs/ways-of-working/Boundaries.md.
"""
from __future__ import annotations

import subprocess
import sys

import boundary_rules as rules
import pytest

MODULES = rules.discover()
EDGES = rules.import_graph(MODULES)


@pytest.mark.parametrize("rule", list(rules.RULES))
def test_imports_keep_to_the_boundaries(rule):
    problems = rules.import_violations(EDGES, rule)
    assert not problems, f"{rule}:\n  " + "\n  ".join(problems)


def test_no_module_uses_another_modules_private_name():
    problems = rules.private_violations(rules.private_uses(MODULES))
    assert not problems, "\n  ".join(["private names:", *problems])


def test_each_store_is_named_only_by_its_owner():
    problems = rules.store_violations(rules.store_mentions(MODULES))
    assert not problems, "\n  ".join(["store ownership:", *problems])



# ---- the checks catch what they are for (each is proven on planted code, so none is vacuous) -----------------------

def _graph(**sources):
    return rules.import_graph({name.replace("__", "."): (text, False) for name, text in sources.items()})


def test_a_core_module_importing_the_sales_layer_is_caught():
    edges = _graph(assistant__answer__x="from services.opsatlas_sales import knowledge\n",
                   services__opsatlas_sales__knowledge="")
    assert rules.import_violations(edges, "the core imports the Sales layer or Tibi's engine", allowed=set()) == [
        "new: assistant.answer.x imports services.opsatlas_sales.knowledge"]


def test_a_core_module_importing_the_sales_layer_by_name_is_caught():
    for text in ("import importlib\nk = importlib.import_module('services.opsatlas_sales.knowledge')\n",
                 "k = __import__('services.opsatlas_sales.knowledge')\n"):
        edges = _graph(assistant__answer__x=text, services__opsatlas_sales__knowledge="")
        assert rules.import_violations(edges, "the core imports the Sales layer or Tibi's engine", allowed=set()) == [
            "new: assistant.answer.x imports services.opsatlas_sales.knowledge"], text


def test_iam_importing_anything_but_the_settings_is_caught():
    edges = _graph(assistant__iam__policy="import assistant.content.service\nfrom .. import storage, settings\n",
                   assistant__content__service="", assistant__storage="", assistant__settings="", assistant="")
    assert rules.import_violations(edges, "IAM imports outside itself, beyond the settings", allowed=set()) == [
        "new: assistant.iam.policy imports assistant.content.service",
        "new: assistant.iam.policy imports assistant.storage"]


def test_a_new_importer_of_a_document_store_is_caught_and_a_gone_one_must_leave_the_list():
    edges = _graph(assistant__answer__x="from ..sources.register import SourceRegister\n",
                   assistant__sources__register="", assistant__answer="")
    allowed = {("assistant.api.app", "assistant.sources.register")}
    assert rules.import_violations(edges, "a document store's module is imported from outside it", allowed=allowed) == [
        "new: assistant.answer.x imports assistant.sources.register",
        "gone (remove it from the allow-list): assistant.api.app -> assistant.sources.register"]


def test_tibis_engine_reaching_outside_itself_is_caught():
    edges = _graph(services__sme_interviewer__tibi="from services.opsatlas_sales.knowledge import Knowledge\n",
                   services__opsatlas_sales__knowledge="")
    assert rules.import_violations(edges, "Tibi's engine imports outside itself", allowed=set()) == [
        "new: services.sme_interviewer.tibi imports services.opsatlas_sales.knowledge"]


def test_a_new_package_cycle_is_caught():
    edges = _graph(assistant__a__m="import assistant.b.n\n", assistant__b__n="import assistant.a.m\n")
    assert rules.import_violations(edges, "an import edge inside a package cycle", allowed=set()) == [
        "new: assistant.a imports assistant.b", "new: assistant.b imports assistant.a"]


def test_a_private_name_taken_from_another_module_is_caught_and_a_gone_one_must_leave_the_list():
    modules = {name.replace("__", "."): (text, False) for name, text in {
        # caught: imported, relatively imported, read through an aliased module, through a full dotted name, and the
        # engine reading another component's module
        "services__opsatlas_sales__x": "from assistant.retrieval.service import _cosine, cosine\n",
        "assistant__eval__x": "from .rag_vs_oag import _best_fact_match as best\n",
        "assistant__answer__x": "import assistant.retrieval.service as rs\nimport assistant.ingestion.store\n"
                                "a = rs._tokenize\nb = assistant.ingestion.store._HIDDEN\n",
        "services__sme_interviewer__tibi": "from services.opsatlas_sales import claims\nx = claims._ALLOWED\n"
                                           "from . import process_model as pm\ny = pm._open_ends\n",
        # not caught: the engine's own module, a dunder, another library's name, an object's member (ruff's), and a
        # module's own name
        "assistant__answer__y": "from assistant import __version__\nfrom typing import _GenericAlias\n"
                                "def f(obj):\n    return obj._x\n_mine = 1\nz = _mine\n",
        "assistant__retrieval__service": "", "assistant__eval__rag_vs_oag": "", "assistant__ingestion__store": "",
        "services__opsatlas_sales__claims": "", "services__sme_interviewer__process_model": "", "assistant": "",
    }.items()}
    modules["assistant"] = ("", True)
    allowed = {("services.opsatlas_sales.y", "assistant.api.access._walk")}
    assert rules.private_violations(rules.private_uses(modules), allowed=allowed) == [
        "new: assistant.answer.x uses assistant.ingestion.store._HIDDEN",
        "new: assistant.answer.x uses assistant.retrieval.service._tokenize",
        "new: assistant.eval.x uses assistant.eval.rag_vs_oag._best_fact_match",
        "new: services.opsatlas_sales.x uses assistant.retrieval.service._cosine",
        "new: services.sme_interviewer.tibi uses services.opsatlas_sales.claims._ALLOWED",
        "gone (remove it from the allow-list): services.opsatlas_sales.y -> assistant.api.access._walk"]


def test_a_store_named_with_a_folder_or_in_an_f_string_is_caught():
    for text in ("P = 'content/content.db'\n", "def p(root):\n    return f'{root}/content.db'\n",
                 "P = 'data\\\\content.db'\n",
                 # inside a SQLite URI with a query (REF S65, S59's N1)
                 "import sqlite3\ndef raw(root):\n    return sqlite3.connect(f'file:{root}/content.db?mode=ro', uri=True)\n",
                 "P = 'file:data/content.db?mode=ro'\n", "P = 'file:content.db?mode=ro'\n"):
        mentions = rules.store_mentions({"assistant.content.store": ('PATH = "content.db"\n', False),
                                         "assistant.answer.x": (text, False)})
        assert rules.store_violations(mentions, owners={"content.db": "assistant.content.store"}, also={}) == [
            "new: assistant.answer.x names content.db, owned by assistant.content.store"], text



def test_store_ownership_catches_a_second_writer_an_undeclared_store_and_a_stale_allowance():
    mentions = rules.store_mentions({
        "assistant.content.store": ('PATH = "content.db"\n', False),
        "assistant.answer.x": ('OPEN = "content.db"\nNEW = "new-store.json"\n', False),
    })
    problems = rules.store_violations(mentions, owners={"content.db": "assistant.content.store", "old.json": "assistant.y"},
                                      also={"content.db": {"services.opsatlas_sales.spaces"}})
    assert problems == [
        "new: assistant.answer.x names content.db, owned by assistant.content.store",
        "gone (remove it from STORE_ALSO): services.opsatlas_sales.spaces no longer names content.db",
        "undeclared store: new-store.json (named by ['assistant.answer.x']): declare its owner in STORE_OWNERS",
        "gone (remove it from STORE_OWNERS): old.json is no longer named anywhere"]


def _ruff(path: str, source: str) -> str:
    done = subprocess.run([sys.executable, "-m", "ruff", "check", "--no-cache", "--output-format", "concise",
                           "--stdin-filename", path, "-"], input=source, capture_output=True, text=True, cwd=rules.ROOT)
    return done.stdout + done.stderr


@pytest.mark.parametrize("path, flagged", [
    ("src/assistant/answer/probe_boundary.py", True), ("services/opsatlas_sales/probe_boundary.py", True),
    ("tests/probe_boundary.py", False), ("services/sme_interviewer/probe_boundary.py", False)])
def test_private_access_across_modules_fails_the_lint_in_production_code(path, flagged):
    """The project's lint configuration flags another module's private member in production code (SLF001), and leaves
    tests and Tibi's engine (its own component, under its fingerprint) alone."""
    out = _ruff(path, "def probe(other):\n    return other._private\n")
    assert ("SLF001" in out) is flagged, out


@pytest.mark.parametrize("source, code", [
    ("X = 1  # noqa: SLF001\n", "RUF100"),  # an allowance whose private access has gone
    ("def probe(other):\n    return other._private  # noqa\n", "PGH004")])  # a blanket mark would hide it
def test_a_private_access_mark_must_be_used_and_name_its_rule(source, code):
    """The marked private accesses are an allow-list too: a mark that no longer suppresses anything fails, and so does a
    blanket mark (outside tests, which may look inside what they test)."""
    assert code in _ruff("src/assistant/answer/probe_boundary.py", source)
    assert "RUF100" not in _ruff("tests/probe_boundary.py", "X = 1  # noqa: SLF001\n")
