"""Internal reviews run one at a time (ARCH F5): a review asked for while another runs waits its turn."""
import logging
import threading
import time

from assistant.governance.review_jobs import (
    InternalReviewCache,
    InternalReviewOptions,
    InternalReviewStore,
    start_internal_review_job,
)
from assistant.sources.models import SourceRecord
from assistant.sources.register import SourceRegister


class SlowIntelligence:
    """Stands in for KnowledgeIntelligence: run n waits at gate n, and the runs count how many go at once."""

    generator = None

    def __init__(self, runs: int) -> None:
        self.gates = [threading.Event() for _ in range(runs)]
        self.started = 0
        self.running = 0
        self.most_at_once = 0
        self._lock = threading.Lock()

    def run(self) -> dict:
        with self._lock:
            gate = self.gates[self.started]
            self.started += 1
            self.running += 1
            self.most_at_once = max(self.most_at_once, self.running)
        gate.wait(timeout=10)
        with self._lock:
            self.running -= 1
        return {"issues": {}}


def _until(predicate, seconds: float = 10.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def test_reviews_run_one_at_a_time_in_the_order_asked(tmp_path, caplog):
    register = SourceRegister(tmp_path)
    register.add(SourceRecord(id="s1", filename="a.md", title="A source", size_bytes=3, content_sha256="0" * 64,
                              created_at="2026-09-30T00:00:00+00:00"), b"# A")
    store, cache = InternalReviewStore(), InternalReviewCache(tmp_path / "cache.json")
    intelligence = SlowIntelligence(3)
    options = InternalReviewOptions(force_rerun=True)  # never served from the cache
    with caplog.at_level(logging.WARNING, logger="assistant.governance"):
        jobs = [
            start_internal_review_job(store=store, cache=cache, register=register, intelligence=intelligence,
                                      options=options).status.job_id
            for _ in range(3)
        ]

    def statuses() -> list[str]:
        return [store.get(job).status.status for job in jobs]

    assert _until(lambda: statuses() == ["running", "queued", "queued"]), statuses()
    intelligence.gates[0].set()
    assert _until(lambda: statuses() == ["completed", "running", "queued"]), statuses()
    intelligence.gates[1].set()
    assert _until(lambda: statuses() == ["completed", "completed", "running"]), statuses()
    intelligence.gates[2].set()
    assert _until(lambda: statuses() == ["completed"] * 3), statuses()
    assert intelligence.most_at_once == 1
    assert "Internal review queued behind 1 other." in caplog.text
    assert "Internal review queued behind 2 others." in caplog.text
