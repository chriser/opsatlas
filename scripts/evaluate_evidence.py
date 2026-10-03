#!/usr/bin/env python3
"""Phase 2 measurements (REF S19, S21, H1, H3, H4): retrieval quality, written answers and the hypotheses' candidates,
run on a disposable copy of the sales workspace (the live one is only read; nothing reaches the live services).

    python scripts/evaluate_evidence.py retrieval --label baseline            # S21: recall at k, source selection
    python scripts/evaluate_evidence.py multipart --label baseline            # H4 baseline
    python scripts/evaluate_evidence.py multipart --label h4 --with KP_PLAN_PARTS=1
    python scripts/evaluate_evidence.py scope --label baseline                # H3 baseline (plants the scope set's documents)
    python scripts/evaluate_evidence.py scope --label h3 --with KP_SCOPE_EVIDENCE=1
    python scripts/evaluate_evidence.py grounding --label baseline            # H1: the Sales set, judged independently
    python scripts/evaluate_evidence.py grounding-oag --label baseline        # H1: the RAG/OAG holdout (OpsAtlas Classic's
                                                                              # corpus, copied; Classic is only read)

Each run writes evaluation/results/evidence/<date>-<kind>-<label>.json: every row and a summary. Candidates are named by
--with SETTING=VALUE; the baseline is the same command without. Runs of one comparison belong in one session.

How things are counted (fixed before any run, REF H1-H4 pass marks):
- A required-evidence item is found when a passage from its file is among those retrieved and holds the item's heading
  or one of the question's expected facts (passages carry their document's top heading, not the sub-heading).
- "Covered" (H4) means present in the evidence given to the model ("considered").
- An answer passes when it is not a refusal and holds every expected fact (an out-of-scope question passes on a refusal).
- "Unsupported shown" (H1) is a delivered answer that an independent judge (qwen2.5:14b-instruct, temperature 0) says is
  not supported by the passages it cited (all the evidence it was given when it cited none).
- A scope violation (H3) is an answer that cites a document the question must not use, or says one of its facts.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import sys
import tempfile
import time
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
LIVE = Path("/Users/chriser/Dev/ai-knowledge-analytics-assistant/.runtime/opsatlas-sales")
CLASSIC_DATA = Path.home() / "Dev/opsatlas-classic/data"
SETS = ROOT / "evaluation/sets"
OUT = ROOT / "evaluation/results/evidence"
JUDGE = "qwen2.5:14b-instruct"
OLLAMA = "http://127.0.0.1:11434"  # this project's model server; the other project's (11435) is never used


# ---- the disposable copy ----------------------------------------------------------------------------------------------

def disposable_copy() -> Path:
    """A copy of the sales workspace's knowledge (no accounts, no logs): the live folder is only read."""
    root = Path(os.path.realpath(tempfile.mkdtemp(prefix="evidence-eval-"))) / "sales"
    root.mkdir()
    shutil.copytree(LIVE / "core", root / "core")
    if (LIVE / "spaces").is_dir():
        shutil.copytree(LIVE / "spaces", root / "spaces")
    for name in ("workspace.json", "local-access.key", "spaces.json"):
        if (LIVE / name).exists():
            shutil.copy2(LIVE / name, root / name)
    (root / "voice").mkdir()
    return root


def sales_app(root: Path):
    os.environ.update({"SME_TIBI_VOICE_URL": "http://127.0.0.1:9", "SALES_GOVERNANCE_AUTO_REVIEW": "0"})
    from services.opsatlas_sales.app import create_sales_app
    return create_sales_app(root)


# ---- scoring ----------------------------------------------------------------------------------------------------------

def _facts(answer: str, facts: list[dict]) -> tuple[list[str], list[str]]:
    from assistant.eval.rag_vs_oag import _best_fact_match, _content_tokens, _normalise_text
    text, tokens = _normalise_text(answer), set(_content_tokens(answer))
    hit, missed = [], []
    for fact in facts:
        (hit if _best_fact_match([fact["text"], *fact.get("aliases", [])], text, tokens)["hit"] else missed).append(fact["text"])
    return hit, missed


def passes(row: dict, result) -> bool:
    from assistant.eval.rag_vs_oag import _REFUSAL_RE
    _, missed = _facts(result.answer, row.get("expected_answer_facts", []))
    if row.get("category") == "out_of_scope":
        return result.refused or bool(_REFUSAL_RE.search(result.answer))
    return not result.refused and not missed


def _holds(text: str, row: dict, item: dict) -> bool:
    low = text.lower()
    if item.get("heading") and item["heading"].lower() in low:
        return True
    return any(alias.lower() in low for fact in row.get("expected_answer_facts", []) for alias in [fact["text"], *fact.get("aliases", [])])


def found(row: dict, passages: list[dict], by_file: dict[str, str]) -> list[bool]:
    """For each required item, whether a retrieved passage from its file holds its heading or an expected fact."""
    return [any(p["source_id"] == by_file.get(item["filename"]) and _holds(p["text"], row, item) for p in passages)
            for item in row.get("required_evidence", [])]


def p50(values: list[float]) -> float | None:
    return round(statistics.median(values), 1) if values else None


def share(flags: list[bool]) -> float | None:
    return round(sum(flags) / len(flags), 3) if flags else None


# ---- the independent judge (H1) ------------------------------------------------------------------------------------

def judge_supported(answer: str, passages: list[str]) -> bool:
    prompt = ("You check whether an answer is supported by passages. Passages:\n\n" + "\n\n---\n\n".join(passages)[:14000]
              + f"\n\nAnswer:\n{answer}\n\nIs every factual claim in the answer supported by the passages? A polite "
                "refusal, or a sentence saying the information is not available, counts as supported. Reply with one word: YES or NO.")
    body = json.dumps({"model": JUDGE, "prompt": prompt, "stream": False, "options": {"temperature": 0, "num_ctx": 8192}}).encode()
    request = urllib.request.Request(f"{OLLAMA}/api/generate", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=300) as response:
        verdict = json.load(response)["response"].strip().upper()
    return verdict.startswith("YES")


# ---- runs -----------------------------------------------------------------------------------------------------------

def _passages(core, ids: list[str]) -> list[dict]:
    store = core.state.section_store
    out = []
    for key in ids:
        source_id, ordinal = key.rsplit("#", 1)
        section = next((s for s in store.list_for_source(source_id) if s.ordinal == int(ordinal)), None)
        if section is not None:
            out.append({"source_id": source_id, "text": section.text})
    return out


def answer_rows(core, rows: list[dict], *, retrieve: bool) -> list[dict]:
    by_file = {r.filename: r.id for r in core.state.register.list()}
    out = []
    for row in rows:
        started = time.perf_counter()
        result = core.state.answer.answer(row["question"])
        ms = (time.perf_counter() - started) * 1000
        considered = _passages(core, result.considered)
        record = {"id": row["id"], "category": row.get("category"), "split": row.get("split"), "question": row["question"],
                  "answer": result.answer, "refused": result.refused, "mode": result.mode, "grounding": result.grounding,
                  "passed": passes(row, result), "ms": round(ms), "cited": sorted({c.source_id for c in result.citations}),
                  "considered": result.considered, "missing_parts": result.missing_parts,
                  "covered": found(row, considered, by_file)}
        if retrieve:
            ranked, _ = core.state.retrieval.search(row["question"], 5)
            passages = [{"source_id": r.source_id, "text": r.text} for r in ranked]
            record["ranked_sources"] = [r.source_id for r in ranked]
            record["recall"] = {k: found(row, passages[:k], by_file) for k in (1, 3, 5)}
            required = {by_file.get(i["filename"]) for i in row.get("required_evidence", [])}
            record["source_selected"] = bool(ranked) and ranked[0].source_id in required if required else None
        out.append(record)
        print(f"{row['id']}: {'pass' if record['passed'] else 'fail'} {record['ms']} ms", flush=True)
    return out


def summary_of(rows: list[dict]) -> dict:
    answerable = [r for r in rows if r["category"] != "out_of_scope"]
    out = {"questions": len(rows), "accuracy": share([r["passed"] for r in rows]),
           "answerable_accuracy": share([r["passed"] for r in answerable]),
           "out_of_scope_refused": share([r["passed"] for r in rows if r["category"] == "out_of_scope"]),
           "median_ms": p50([r["ms"] for r in rows]),
           "covered": share([flag for r in answerable for flag in r["covered"]])}
    if any("recall" in r for r in rows):
        for k in ("1", "3", "5"):
            out[f"recall@{k}"] = share([flag for r in answerable for flag in r["recall"][int(k)]])
        out["file_recall@5"] = share([any(flags) for r in answerable for flags in [r["recall"][5]] if flags])
        out["source_selection"] = share([r["source_selected"] for r in answerable if r["source_selected"] is not None])
    for split in ("tuning", "holdout"):
        part = [r for r in rows if r.get("split") == split]
        if part:
            out[f"{split}_accuracy"] = share([r["passed"] for r in part])
    return out


def plant(core, planted: list[dict]) -> dict[str, str]:
    """The scope set's fictional documents, uploaded, ingested, approved and given their scope in the copy (REF H3)."""
    from assistant.ingestion.service import ingest_source
    from assistant.sources.service import register_upload
    keys = {}
    for doc in planted:
        record = register_upload(core.state.register, doc["filename"], doc["text"].encode(), None)
        ingest_source(core.state.register, core.state.section_store, record.id)
        keys[doc["key"]] = record.id
    for doc in planted:
        scope = doc.get("scope", {})
        core.state.register.update(keys[doc["key"]], approval_status="approved", effective_from=scope.get("effective_from"),
                                   effective_to=scope.get("effective_to"), phases=scope.get("phases", []),
                                   applies_to=scope.get("applies_to", []),
                                   supersedes=[keys.get(k, k) for k in scope.get("supersedes", [])])
    return keys


def scope_rows(core, data: dict, keys: dict[str, str]) -> list[dict]:
    os.environ["KP_SCOPE_TODAY"] = data["today"]
    names = {key: re.sub(r"\s+", " ", doc["text"].split("\n", 1)[0].lstrip("# ")) for key, doc in
             ((d["key"], d) for d in data["planted"])}
    out = []
    for row in data["questions"]:
        started = time.perf_counter()
        result = core.state.answer.answer(row["question"])
        cited = {c.source_id for c in result.citations}
        forbidden = _facts(result.answer, [{"text": f} if isinstance(f, str) else f for f in row.get("forbidden_facts", [])])[0]
        violated = bool(cited & {keys[k] for k in row.get("must_not_use", [])}) or bool(forbidden)
        hit, missed = _facts(result.answer, row.get("expected_answer_facts", []))
        if row.get("expected_behaviour") == "ask_or_label_both":
            both = all(any(w in result.answer.lower() for w in re.findall(r"[a-z]{4,}", names[k].lower())[:1])
                       for k in row.get("must_use", []))
            correct = (not result.refused and both) or bool(re.search(r"\bwhich (site|location)\b", result.answer, re.I))
        else:
            correct = not result.refused and not missed and not violated
        out.append({"id": row["id"], "category": row["category"], "split": row.get("split"), "question": row["question"],
                    "answer": result.answer, "refused": result.refused, "cited": sorted(cited), "violated": violated,
                    "forbidden_said": forbidden, "correct": correct, "ms": round((time.perf_counter() - started) * 1000)})
        print(f"{row['id']}: {'violation' if violated else 'ok'} {'correct' if correct else 'wrong'}", flush=True)
    return out


def grounding_rows(core, rows: list[dict]) -> list[dict]:
    store = core.state.section_store
    every = [s.text for r in core.state.register.list() if r.approval_status == "approved" for s in store.list_for_source(r.id)]
    out = []
    for row in rows:
        started = time.perf_counter()
        result = core.state.answer.answer(row["question"])
        ms = (time.perf_counter() - started) * 1000
        cited = [s.text for c in result.citations if c.citation_type == "document"
                 for s in store.list_for_source(c.source_id) if s.ordinal == c.ordinal]
        supported = None if result.refused else judge_supported(result.answer, cited or every)
        out.append({"id": row["id"], "category": row["category"], "split": row.get("split"), "question": row["question"],
                    "answer": result.answer, "refused": result.refused, "grounding": result.grounding,
                    "passed": passes(row, result), "supported": supported, "ms": round(ms)})
        print(f"{row['id']}: {'refused' if result.refused else ('supported' if supported else 'UNSUPPORTED')}", flush=True)
    return out


def grounding_summary(rows: list[dict]) -> dict:
    shown = [r for r in rows if not r["refused"]]
    return {"questions": len(rows), "delivered": len(shown), "unsupported_shown": sum(1 for r in shown if r["supported"] is False),
            "accuracy": share([r["passed"] for r in rows]), "refused": sum(1 for r in rows if r["refused"]),
            "median_ms": p50([r["ms"] for r in rows])}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("kind", choices=["retrieval", "multipart", "scope", "grounding", "grounding-oag"])
    parser.add_argument("--label", required=True)
    parser.add_argument("--with", dest="settings", action="append", default=[], help="SETTING=VALUE for the candidate")
    args = parser.parse_args()
    candidate = dict(item.split("=", 1) for item in args.settings)
    started = time.perf_counter()
    temporary = None
    if args.kind == "grounding-oag":
        from assistant.eval.rag_vs_oag import load_rag_vs_oag_dataset
        temporary = Path(os.path.realpath(tempfile.mkdtemp(prefix="evidence-oag-")))
        shutil.copytree(CLASSIC_DATA, temporary / "data")  # Classic's corpus, copied: Classic itself is only read
        os.environ.update({"KP_DATA_DIR": str(temporary / "data"), **candidate})
        from assistant.api.app import create_app
        core = create_app()
        rows = [q.model_dump() for q in load_rag_vs_oag_dataset(SETS / "rag_vs_oag_questions.json").questions if q.split == "holdout"]
        results = grounding_rows(core, rows)
        summary, set_name = grounding_summary(results), "rag_vs_oag_questions.json (holdout)"
    else:
        temporary = disposable_copy()
        app = sales_app(temporary)
        os.environ.update(candidate)
        if args.kind == "grounding":
            rows = json.loads((SETS / "sales_product_questions.json").read_text())["questions"]
            results, set_name = grounding_rows(app, rows), "sales_product_questions.json"
            summary = grounding_summary(results)
        else:
            core = app.state.cores["sales-playbook"]
            name = {"retrieval": "sales_playbook_retrieval.json", "multipart": "sales_playbook_multipart.json",
                    "scope": "sales_playbook_scope.json"}[args.kind]
            data, set_name = json.loads((SETS / name).read_text()), name
            if args.kind == "scope":
                results = scope_rows(core, data, plant(core, data["planted"]))
                summary = {"questions": len(results), "violations": sum(r["violated"] for r in results),
                           "violation_rate": share([r["violated"] for r in results]),
                           "correct": share([r["correct"] for r in results]),
                           "correct_in_scope": share([r["correct"] for r in results if r["category"] in ("current", "site")]),
                           "median_ms": p50([r["ms"] for r in results])}
            else:
                results = answer_rows(core, data["questions"], retrieve=args.kind == "retrieval")
                summary = summary_of(results)
                if args.kind == "multipart":
                    summary["by_category"] = {c: summary_of([r for r in results if r["category"] == c])
                                              for c in ("multi_part", "single_part")}
    report = {"kind": args.kind, "label": args.label, "candidate": candidate, "set": set_name,
              "measured_at": datetime.now(timezone.utc).isoformat(), "seconds": round(time.perf_counter() - started),
              "summary": summary, "rows": results}
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{date.today().isoformat()}-{args.kind}-{args.label}.json"
    path.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=1), f"\n{path.relative_to(ROOT)}")
    if temporary is not None:
        shutil.rmtree(temporary.parent if temporary.name == "sales" else temporary, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
