"""Random scenarios for who owns each Tibi conversation (REF S14, tibi_owners.py).

Promises, checked after every step against a model:
- the owner is exact: a conversation's owner is whoever last started it, until its line is older than the keep period
  at a later recording (a line exactly that old stays), and nobody else;
- access follows ownership: a person may use a conversation if they own it or may read everyone's conversations, and
  never otherwise;
- an unreadable or lost record never opens a conversation to someone who could not use it before; a corrupt file is
  kept aside and recording starts afresh; a read that fails for a moment fails the recording and erases nobody;
- a failed write changes nothing and is reported;
- a restart loses nothing; two recordings at once lose neither.

Scenario kinds: a conversation starts (new, or the same id again by someone else); time passes (a little, to just
before or just after the keep period); the service restarts; the file is corrupted; a write fails; two conversations
start at once.
"""
import os
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

from scenarios import explore

from services.opsatlas_sales import tibi_owners
from services.opsatlas_sales.tibi_owners import KEEP_SECONDS, TibiOwners

PEOPLE = ["ann", "ben", "cai"]


def person(pid, everyone=False):
    return SimpleNamespace(id=pid, can=lambda permission, space=None: everyone and permission == "conversations.read_all")


def one_run(run):
    folder = Path(tempfile.mkdtemp(prefix="owners-scenario-"))
    clock = [1_800_000_000.0]
    real_time = tibi_owners.time
    tibi_owners.time = SimpleNamespace(time=lambda: clock[0])
    store = TibiOwners(folder)
    model: dict[str, dict] = {}
    lost = False  # after a corrupted file the record may be gone; access must then only narrow
    try:
        def record(cid, owner):
            store.record(cid, owner, "text")
            for key in [k for k, v in model.items() if clock[0] - v["at"] > KEEP_SECONDS]:
                del model[key]
            model[cid] = {"owner": owner, "at": clock[0]}

        def check(where):
            for cid in [f"c{i}" for i in range(6)]:
                expected = model.get(cid, {}).get("owner")
                got = store.owner(cid)
                if lost:
                    run.promise("a lost record only narrows", got in (None, expected), f"{cid}: {got} vs {expected}")
                else:
                    run.promise("the owner is exact", got == expected, f"{cid}: {got} vs {expected} ({where})")
                for pid in PEOPLE:
                    for everyone in (False, True):
                        allowed = store.may(person(pid, everyone), cid, "product-guide")
                        run.promise("access follows ownership", allowed == (everyone or (got is not None and got == pid)),
                                    f"{pid} on {cid}")
                        if not everyone and allowed:
                            run.promise("never opened to a non-owner", expected == pid, f"{pid} on {cid}")

        for _ in range(run.rng.randint(3, 30)):
            kind = run.rng.choice(["start", "start", "start", "time", "edge", "restart", "corrupt", "failed-write", "at-once",
                                   "two-objects", "read-blip", "malformed-line"])
            if kind == "start":
                cid, owner = f"c{run.rng.randint(0, 5)}", run.rng.choice(PEOPLE)
                run.step(kind, f"{cid} by {owner}")
                record(cid, owner)
            elif kind == "time":
                clock[0] += run.rng.choice([1, 60, 3600, 86400, 30 * 86400])
                run.step(kind, str(clock[0]))
            elif kind == "edge":
                oldest = min((v["at"] for v in model.values()), default=clock[0])
                clock[0] = oldest + KEEP_SECONDS + run.rng.choice([-1, 0, 1])
                run.step(kind, "at the keep boundary")
            elif kind == "restart":
                run.step(kind)
                store = TibiOwners(folder)
            elif kind == "corrupt":
                run.step(kind)
                store.path.write_text("{ broken")
                lost = True
                model = {}  # what is recorded from here on is exact again
            elif kind == "failed-write":
                before = store._read()  # what the store reports (a corrupt file already reads as empty)
                run.step(kind)
                real = os.replace
                os.replace = lambda *a, **k: (_ for _ in ()).throw(OSError("disk full"))
                try:
                    store.record("c9", "ann", "text")
                    run.promise("a failed write is reported", False)
                except OSError:
                    pass
                finally:
                    os.replace = real
                run.promise("a failed write changes nothing", store._read() == before)
            elif kind == "at-once":
                pairs = [(f"c{run.rng.randint(0, 5)}", run.rng.choice(PEOPLE)) for _ in range(2)]
                if pairs[0][0] == pairs[1][0]:
                    pairs = pairs[:1]
                run.step(kind, str(pairs))
                jobs = [threading.Thread(target=store.record, args=(cid, owner, "text")) for cid, owner in pairs]
                for job in jobs:
                    job.start()
                for job in jobs:
                    job.join()
                for cid, owner in pairs:
                    for key in [k for k, v in model.items() if clock[0] - v["at"] > KEEP_SECONDS]:
                        del model[key]
                    model[cid] = {"owner": owner, "at": clock[0]}
            elif kind == "two-objects":  # red team: another process's store object records at the same time
                pairs = [(f"c{run.rng.randint(0, 5)}", run.rng.choice(PEOPLE)) for _ in range(2)]
                if pairs[0][0] == pairs[1][0]:
                    pairs = pairs[:1]
                run.step(kind, str(pairs))
                other = TibiOwners(folder)
                jobs = [threading.Thread(target=s.record, args=(cid, owner, "text")) for s, (cid, owner) in zip([store, other], pairs)]
                for job in jobs:
                    job.start()
                for job in jobs:
                    job.join()
                for cid, owner in pairs:
                    for key in [k for k, v in model.items() if clock[0] - v["at"] > KEEP_SECONDS]:
                        del model[key]
                    model[cid] = {"owner": owner, "at": clock[0]}
            elif kind == "read-blip" and store.path.exists():  # red team: one read fails for a moment during a recording
                run.step(kind)
                before = store._read()
                real_read = Path.read_text
                Path.read_text = lambda self, *a, **k: (_ for _ in ()).throw(OSError(5, "I/O error"))
                try:
                    store.record("c8", "ben", "text")
                    run.promise("a failed read fails the recording", False)
                except OSError:
                    pass
                finally:
                    Path.read_text = real_read
                run.promise("a failed read erases nobody", store._read() == before)
            elif kind == "malformed-line" and store.path.exists() and not lost:  # red team: a line with a text 'at'
                run.step(kind)
                data = store._read()
                data["c7"] = {"owner": "cai", "kind": "text", "at": "yesterday"}
                store.path.write_text(__import__("json").dumps(data))
                cid, owner = f"c{run.rng.randint(0, 5)}", run.rng.choice(PEOPLE)
                record(cid, owner)  # still records; the malformed line is dropped
                run.promise("a malformed line is dropped", store.owner("c7") is None)
            check(run.steps[-1] if run.steps else kind)
    finally:
        tibi_owners.time = real_time


def test_conversation_owners_keep_their_promises_over_random_scenarios():
    assert explore("owners", one_run, runs=max(1, int(os.environ.get("OPSATLAS_SCENARIO_RUNS", "2000")) // 4)) >= 1
