"""Pinned local conversation runtime for the synthetic interview trial."""

import os


def scheduling_options():
    """Candidate-only prefill bound; omitted for existing deployments."""
    return {"num_batch": 128} if os.environ.get("SME_BOUNDED_PREFILL") == "1" else {}


MODEL = "qwen3.5:35b-a3b"
REVIEW_MODEL = "qwen2.5:7b-instruct"
THINK = False
OUTPUT_TOKENS = 1536
WRITER_THINK = False
WRITER_OUTPUT_TOKENS = 1536
CONTEXT_TOKENS = 8192
KEEP_ALIVE = "30m"
PLANNING_TIMEOUT_SECONDS = 45
