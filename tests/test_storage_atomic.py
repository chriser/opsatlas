"""Atomic writes for the JSON stores (ARCH F1): a reader sees the old file or the new one, never a partial one."""
import json
import os
import stat
import threading

import pytest

from assistant.storage import write_json


def test_write_json_writes_exactly_what_json_dumps_would_and_leaves_no_temporary(tmp_path):
    path = tmp_path / "nested" / "store.json"  # the folder is made on the way
    write_json(path, {"b": 1, "a": [1, 2]}, indent=2)
    assert path.read_text() == json.dumps({"b": 1, "a": [1, 2]}, indent=2)
    write_json(path, {"b": 1, "a": None}, sort_keys=True)
    assert path.read_text() == '{"a": null, "b": 1}'
    assert [p.name for p in path.parent.iterdir()] == ["store.json"]


def test_a_failed_write_leaves_the_previous_file_intact_and_no_temporary(tmp_path, monkeypatch):
    path = tmp_path / "store.json"
    write_json(path, {"version": 1})

    def full_disk(source, target):
        raise OSError("No space left on device")
    monkeypatch.setattr(os, "replace", full_disk)
    with pytest.raises(OSError):
        write_json(path, {"version": 2})
    monkeypatch.undo()
    with pytest.raises(TypeError):  # cannot be serialised: nothing is written at all
        write_json(path, {"version": object()})
    assert json.loads(path.read_text()) == {"version": 1}
    assert [p.name for p in tmp_path.iterdir()] == ["store.json"]


def test_readers_never_see_a_partial_file_while_it_is_rewritten(tmp_path):
    """Written in place, a 1 MB store is partial for a moment on every rewrite, and a reader that parses it then fails."""
    path = tmp_path / "usage_log.json"
    rows = [{"question": "q" * 200, "n": i} for i in range(4000)]
    write_json(path, rows, indent=2)
    stop, failures, reads = threading.Event(), [], []

    def reader():
        while not stop.is_set():
            try:
                json.loads(path.read_text())
                reads.append(1)
            except ValueError as exc:
                failures.append(str(exc))
    thread = threading.Thread(target=reader)
    thread.start()
    try:
        for n in range(40):
            write_json(path, rows + [{"n": n}], indent=2)
    finally:
        stop.set()
        thread.join()
    assert not failures and reads


def test_an_existing_file_keeps_its_permissions_and_a_new_one_gets_the_usual(tmp_path):
    path = tmp_path / "keyed.json"
    write_json(path, {})
    assert stat.S_IMODE(path.stat().st_mode) == 0o644
    path.chmod(0o600)
    write_json(path, {"a": 1})
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_the_core_stores_write_through_the_helper(tmp_path):
    """The four the review named first: the source register, the embeddings cache, the usage log, the audit trace."""
    from assistant.analytics.log import UsageEntry, UsageLog
    from assistant.observability.trace import AuditTrace
    from assistant.retrieval.embedder import EmbeddingCache
    from assistant.sources.models import SourceRecord
    from assistant.sources.register import SourceRegister

    class Embedder:
        def embed(self, texts):
            return [[1.0, 0.0] for _ in texts]

    register = SourceRegister(tmp_path)
    register.add(SourceRecord(id="s1", filename="a.md", title="A source", size_bytes=3, content_sha256="0" * 64,
                              created_at="2026-09-30T00:00:00+00:00"), b"# A")
    UsageLog(tmp_path).append(UsageEntry(timestamp="2026-09-30T00:00:00+00:00", question="q", mode="retrieval", refused=False,
                                         citation_count=1, confidence="grounded"))
    AuditTrace(tmp_path).append({"question": "q"})
    EmbeddingCache(tmp_path).get_or_embed(Embedder(), ["a section"])
    names = sorted(p.name for p in tmp_path.rglob("*") if p.is_file())
    assert not [n for n in names if n.endswith(".tmp")], names
    assert {"source_register.json", "usage_log.json", "audit_trace.json", "embeddings.json"} <= set(names)
    assert json.loads((tmp_path / "usage_log.json").read_text())[0]["question"] == "q"
