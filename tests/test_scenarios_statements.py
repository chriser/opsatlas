"""Random scenarios for a space's governed fixed sentences (REF S22).

Promises, checked after every step against a model kept beside the real store:
- the record is exact: every key's versions, texts and approvals are what the steps so far make them, numbered 1..n,
  never removed or renumbered;
- only approved words are said: the configuration the space speaks uses, for each key, its latest approved version;
  a pending version is never said;
- a failed write changes nothing: the store is as it was before the step, and the failure is reported, not swallowed;
- a restart loses nothing;
- an unreadable store is never taken for an empty one (which would record unapproved words as approved): it is
  reported as an error;
- two tasks at once lose no version.

Scenario kinds: the owner edits a sentence (new words, back to earlier words, unchanged), adds a note; someone approves
a pending version, an approved one, a version that does not exist, a key that does not exist; the core restarts; a
write fails partway; the file is corrupted; an edit and an approval run at once.
"""
import json
import os
import tempfile
import threading
from pathlib import Path

from scenarios import explore

from assistant.space_config import SpaceConfig
from assistant.space_statements import SpaceStatements, texts_of

WORDS = ["Please contact the sales team.", "Ask the sales team for a quote.", "We cannot say that here.",
         "That is outside the guide.", "Speak to your account manager."]


def config_from(texts: dict) -> SpaceConfig:
    data = {"refusal": texts["refusal"], "guardrails": {"scope_message": texts["scope_message"]},
            "referral": {"topics": ["price"], "sentence": texts["referral"]}}
    if texts.get("note.0"):
        data["notes"] = [{"topics": ["audit"], "sentence": texts["note.0"]}]
    return SpaceConfig.model_validate(data)


def one_run(run):
    folder = Path(tempfile.mkdtemp(prefix="statements-scenario-"))
    store = SpaceStatements(folder)
    model: dict[str, list[dict]] = {}
    texts = {"refusal": run.rng.choice(WORDS), "scope_message": run.rng.choice(WORDS), "referral": run.rng.choice(WORDS)}

    def apply_sync(model, texts):
        for key, text in texts_of(config_from(texts)).items():
            versions = model.setdefault(key, [])
            if not any(v["text"] == text for v in versions):
                versions.append({"text": text, "approved": not versions})

    def check(where):
        data = json.loads(store.path.read_text()) if store.path.exists() else {}
        run.promise("the record is exact", {k: [(v["version"], v["text"], v["approved"]) for v in vs] for k, vs in data.items()}
                    == {k: [(n + 1, v["text"], v["approved"]) for n, v in enumerate(vs)] for k, vs in model.items()}, where)
        spoken = store.governed(config_from(texts))
        said = texts_of(spoken)
        for key, versions in model.items():
            approved = [v["text"] for v in versions if v["approved"]]
            if approved and key in said:
                run.promise("only approved words are said", said[key] == approved[-1], f"{key}: says {said[key]!r}")

    store.sync(texts_of(config_from(texts)))
    apply_sync(model, texts)
    check("first start")
    for _ in range(run.rng.randint(3, 25)):
        kind = run.rng.choice(["edit", "edit", "revert", "note", "approve", "approve", "approve-bad", "restart",
                               "failed-write", "corrupt", "at-once"])
        if kind in ("edit", "revert", "note"):
            key = "note.0" if kind == "note" else run.rng.choice(["refusal", "scope_message", "referral"])
            if kind == "revert" and model.get(key):
                texts[key] = run.rng.choice(model[key])["text"]
            else:
                texts[key] = run.rng.choice(WORDS)
            run.step(kind, f"{key} -> {texts[key]!r}")
            store.sync(texts_of(config_from(texts)))
            apply_sync(model, texts)
        elif kind == "approve":
            pending = [(k, n + 1) for k, vs in model.items() for n, v in enumerate(vs) if not v["approved"]]
            if pending:
                key, version = run.rng.choice(pending)
                run.step(kind, f"{key} v{version}")
                store.approve(key, version, "Approver")
                model[key][version - 1]["approved"] = True
        elif kind == "approve-bad":
            key, version = run.rng.choice([("refusal", 99), ("nonsense", 1), ("referral", 0)])
            run.step(kind, f"{key} v{version}")
            try:
                store.approve(key, version, "Approver")
                run.promise("an unknown version is refused", False, f"{key} v{version} accepted")
            except KeyError:
                pass
        elif kind == "restart":
            run.step(kind)
            store = SpaceStatements(folder)
        elif kind == "failed-write":
            before = store.path.read_text()
            key = run.rng.choice(["refusal", "referral"])
            run.step(kind, key)
            real = os.replace
            os.replace = lambda *a, **k: (_ for _ in ()).throw(OSError("disk full"))
            try:
                store.sync(texts_of(config_from({**texts, key: texts[key] + " (draft)"})))
                run.promise("a failed write is reported", False, "no error raised")
            except OSError:
                pass
            finally:
                os.replace = real
            run.promise("a failed write changes nothing", store.path.read_text() == before)
            for leftover in folder.glob(".statements-*"):
                leftover.unlink()
        elif kind == "corrupt":
            run.step(kind)
            saved = store.path.read_text()
            store.path.write_text("{ not json")
            try:
                store.sync(texts_of(config_from(texts)))
                run.promise("an unreadable store is an error", False, "it was read as empty")
            except ValueError:
                pass
            store.path.write_text(saved)  # the operator restores the file
        elif kind == "at-once":
            key = run.rng.choice(["refusal", "scope_message"])
            texts[key] = run.rng.choice(WORDS) + " Now."
            pending = [(k, n + 1) for k, vs in model.items() for n, v in enumerate(vs) if not v["approved"]]
            run.step(kind, f"edit {key} while approving {pending[:1]}")
            jobs = [threading.Thread(target=store.sync, args=(texts_of(config_from(texts)),))]
            if pending:
                jobs.append(threading.Thread(target=store.approve, args=(*pending[0], "Approver")))
            for job in jobs:
                job.start()
            for job in jobs:
                job.join()
            apply_sync(model, texts)
            if pending:
                model[pending[0][0]][pending[0][1] - 1]["approved"] = True
        check(run.steps[-1] if run.steps else kind)


def test_governed_statements_keep_their_promises_over_random_scenarios():
    assert explore("statements", one_run, runs=max(1, int(os.environ.get("OPSATLAS_SCENARIO_RUNS", "2000")) // 4)) >= 1
