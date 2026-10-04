"""Random scenarios for a space's governed fixed sentences (REF S22).

Promises, checked after every step against a model kept beside the real store:
- the record is exact: every key's versions, texts and approvals are what the steps so far make them, numbered 1..n,
  never removed or renumbered;
- only approved words are said: the configuration the space speaks uses, for each key, its latest approved version; a
  sentence with nothing approved is not said (the refusal and off-topic message fall back to the platform's defaults);
- the words in use are adopted once: only when governance starts are a key's first words approved as found; a sentence
  added later waits for approval;
- a note's words stay with its topics, whatever other notes are added or removed;
- a failed write changes nothing and is reported; a restart loses nothing; an unreadable or missing-behind-a-link store
  is reported as an error, never taken for an empty one; two tasks at once, in one store object or two, lose no version.

Scenario kinds: the owner edits a sentence (new words, back to earlier words, unchanged), adds or removes a note; someone
approves a pending version, an approved one, a version or key that does not exist; the core restarts; a write fails
partway; the file is corrupted; the file is a link to something gone; an edit and an approval run at once; another
store object (another process) edits at the same time. The red team's findings of 3 October 2026 are kinds here.
"""
import json
import os
import tempfile
import threading
from pathlib import Path

from scenarios import explore

from assistant.space_config import DEFAULT_REFUSAL, DEFAULT_SCOPE, SpaceConfig
from assistant.space_statements import SpaceStatements, note_key, texts_of

WORDS = ["Please contact the sales team.", "Ask the sales team for a quote.", "We cannot say that here.",
         "That is outside the guide.", "Speak to your account manager."]
TOPICS = [["audit"], ["returns"], ["delivery", "shipping"], ["warranty"]]


def config_from(texts: dict) -> SpaceConfig:
    data = {"refusal": texts["refusal"], "guardrails": {"scope_message": texts["scope_message"]},
            "referral": {"topics": ["price"], "sentence": texts["referral"]},
            "notes": [{"topics": list(topics), "sentence": sentence} for topics, sentence in texts["notes"]]}
    return SpaceConfig.model_validate(data)


def one_run(run):
    folder = Path(tempfile.mkdtemp(prefix="statements-scenario-"))
    store = SpaceStatements(folder)
    model: dict[str, list[dict]] = {}
    texts = {"refusal": run.rng.choice(WORDS), "scope_message": run.rng.choice(WORDS), "referral": run.rng.choice(WORDS),
             "notes": [(tuple(t), run.rng.choice(WORDS)) for t in run.rng.sample(TOPICS, run.rng.randint(0, 2))]}

    def apply_sync(texts, adopt=False):
        for key, text in texts_of(config_from(texts)).items():
            versions = model.setdefault(key, [])
            if not any(v["text"] == text for v in versions):
                versions.append({"text": text, "approved": adopt and not versions})

    def sync(texts, adopt=False, on=None):
        (on or store).sync(texts_of(config_from(texts)), adopt_new=adopt)

    def check(where):
        data = json.loads(store.path.read_text()) if store.path.exists() else {}
        run.promise("the record is exact", {k: [(v["version"], v["text"], v["approved"]) for v in vs] for k, vs in data.items()}
                    == {k: [(n + 1, v["text"], v["approved"]) for n, v in enumerate(vs)] for k, vs in model.items()}, where)
        config = config_from(texts)
        spoken = store.governed(config)
        said = {"refusal": spoken.refusal, "scope_message": spoken.guardrails.scope_message, "referral": spoken.referral.sentence}
        said.update({note_key(n): n.sentence for n in spoken.notes if n.topics})
        defaults = {"refusal": DEFAULT_REFUSAL, "scope_message": DEFAULT_SCOPE}
        for key, words in said.items():
            approved = [v["text"] for v in model.get(key, []) if v["approved"]]
            expected = approved[-1] if approved else defaults.get(key, "")
            run.promise("only approved words are said", (words or "") == expected, f"{key}: says {words!r}, approved {expected!r}")
        for note in spoken.notes:  # a note's words stay with its topics
            approved = [v["text"] for v in model.get(note_key(note), []) if v["approved"]]
            run.promise("a note's words stay with its topics", (note.sentence or "") == (approved[-1] if approved else ""),
                        f"{note.topics}: {note.sentence!r}")

    sync(texts, adopt=store.new)  # governance starts: the words in use are adopted, once
    apply_sync(texts, adopt=True)
    check("first start")
    for _ in range(run.rng.randint(3, 25)):
        kind = run.rng.choice(["edit", "edit", "revert", "add-note", "remove-note", "approve", "approve", "approve-bad",
                               "restart", "failed-write", "corrupt", "dangling", "at-once", "two-objects"])
        if kind in ("edit", "revert"):
            key = run.rng.choice(["refusal", "scope_message", "referral"])
            if kind == "revert" and model.get(key):
                texts[key] = run.rng.choice(model[key])["text"]
            else:
                texts[key] = run.rng.choice(WORDS)
            run.step(kind, f"{key} -> {texts[key]!r}")
            sync(texts)
            apply_sync(texts)
        elif kind == "add-note":  # red team: a sentence added after governance began waits for approval
            free = [t for t in TOPICS if tuple(t) not in {n[0] for n in texts["notes"]}]
            if free:
                texts["notes"].append((tuple(run.rng.choice(free)), run.rng.choice(WORDS)))
                run.step(kind, str(texts["notes"][-1]))
                sync(texts)
                apply_sync(texts)
        elif kind == "remove-note" and texts["notes"]:  # red team: removing one note must not move another's words
            texts["notes"].pop(run.rng.randrange(len(texts["notes"])))
            run.step(kind, str(texts["notes"]))
            sync(texts)
            apply_sync(texts)
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
            run.promise("a restart is not a first start", not store.new)
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
        elif kind == "corrupt":
            run.step(kind)
            saved = store.path.read_text()
            store.path.write_text("{ not json")
            try:
                sync(texts)
                run.promise("an unreadable store is an error", False, "it was read as empty")
            except ValueError:
                pass
            store.path.write_text(saved)  # the operator restores the file
        elif kind == "dangling":  # red team: the store is a link to something no longer there
            run.step(kind)
            saved = store.path.read_text()
            store.path.unlink()
            store.path.symlink_to(folder / "gone.json")
            try:
                sync(texts)
                run.promise("a store behind a broken link is an error", False, "it was read as empty")
            except ValueError:
                pass
            run.promise("the link is not written over", store.path.is_symlink())
            store.path.unlink()
            store.path.write_text(saved)
        elif kind in ("at-once", "two-objects"):
            key = run.rng.choice(["refusal", "scope_message"])
            texts[key] = run.rng.choice(WORDS) + " Now."
            pending = [(k, n + 1) for k, vs in model.items() for n, v in enumerate(vs) if not v["approved"]]
            other = store if kind == "at-once" else SpaceStatements(folder)  # another process's store object
            run.step(kind, f"edit {key} while approving {pending[:1]}")
            jobs = [threading.Thread(target=sync, args=(texts,), kwargs={"on": other})]
            if pending:
                jobs.append(threading.Thread(target=store.approve, args=(*pending[0], "Approver")))
            for job in jobs:
                job.start()
            for job in jobs:
                job.join()
            apply_sync(texts)
            if pending:
                model[pending[0][0]][pending[0][1] - 1]["approved"] = True
        check(run.steps[-1] if run.steps else kind)


def test_governed_statements_keep_their_promises_over_random_scenarios():
    assert explore("statements", one_run, runs=max(1, int(os.environ.get("OPSATLAS_SCENARIO_RUNS", "2000")) // 4)) >= 1
