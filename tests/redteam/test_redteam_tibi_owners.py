"""Red team, REF F10: attempts to break the promises of services.opsatlas_sales.tibi_owners.TibiOwners (hermetic)."""
import errno
import json
from pathlib import Path
from types import SimpleNamespace

import services.opsatlas_sales.tibi_owners as mod
from services.opsatlas_sales.tibi_owners import KEEP_SECONDS, TibiOwners


def actor(id, read_all=False):
    return SimpleNamespace(id=id, can=lambda permission, space: read_all and permission == "conversations.read_all")


def test_two_instances_on_one_folder_lose_a_recording(tmp_path, monkeypatch):
    """Two processes = two TibiOwners on one folder, each with its own threading.Lock. B records while A is between
    its read and its write; without a lock across store objects A writes its stale rows and bob's conversation loses
    its owner (bob is then refused it). B runs on its own thread, as another process would."""
    import threading
    import time
    a, b = TibiOwners(tmp_path), TibiOwners(tmp_path)
    real_write, other = mod.write_json, []

    def b_lands_meanwhile(path, rows, **kw):
        if not other:
            other.append(threading.Thread(target=b.record, args=("conv-bob", "bob", "text")))
            other[0].start()
            time.sleep(0.2)
        real_write(path, rows, **kw)

    monkeypatch.setattr(mod, "write_json", b_lands_meanwhile)
    a.record("conv-alice", "alice", "text")
    other[0].join(5)
    assert a.owner("conv-alice") == "alice"
    assert a.owner("conv-bob") == "bob"
    assert a.may(actor("bob"), "conv-bob", "sales")


def test_a_transient_read_failure_during_record_erases_every_other_owner(tmp_path, monkeypatch):
    """One read of the record fails (EMFILE, EIO, a permission blip) inside record(); _read returns {} and the write
    replaces the whole file with the one new row. The failure is not reported and alice loses her conversation."""
    o = TibiOwners(tmp_path)
    o.record("conv-alice", "alice", "text")
    real_read_text, fails = Path.read_text, [1]

    def flaky(self, *args, **kwargs):
        if self == o.path and fails:
            fails.pop()
            raise OSError(errno.EMFILE, "Too many open files")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", flaky)
    try:
        o.record("conv-bob", "bob", "interview")
    except OSError:
        pass  # reporting the failure would be fine; losing alice's row is not
    assert o.owner("conv-alice") == "alice"
    assert o.may(actor("alice"), "conv-alice", "sales")


def test_a_line_exactly_keep_seconds_old_is_pruned(tmp_path, monkeypatch):
    """Promise: the owner holds until the line is OLDER than KEEP_SECONDS at a later recording. The prune keeps
    `now - at < KEEP_SECONDS`, so a line exactly KEEP_SECONDS old is dropped (off by one at the boundary)."""
    clock = [1_000_000.0]
    monkeypatch.setattr(mod.time, "time", lambda: clock[0])
    o = TibiOwners(tmp_path)
    o.record("conv-alice", "alice", "text")
    clock[0] += KEEP_SECONDS
    o.record("conv-bob", "bob", "text")
    assert o.owner("conv-alice") == "alice"


def test_one_malformed_line_stops_every_later_recording(tmp_path):
    """Malformed input: one row with a non-numeric 'at' (or a bare string row, an older format) makes the prune raise
    TypeError/AttributeError in every later record(), so no conversation started afterwards has an owner and its
    starter is refused it."""
    (tmp_path / "tibi-owners.json").write_text(json.dumps({"old": {"owner": "x", "kind": "text", "at": "2026-10-01"}}))
    o = TibiOwners(tmp_path)
    try:
        o.record("conv-carol", "carol", "text")
    except Exception:
        pass
    assert o.owner("conv-carol") == "carol"
    assert o.may(actor("carol"), "conv-carol", "sales")
