"""Synthetic Atlas HTTP workload, launched only in a fresh benchmark directory.

Uses the existing Ask route/service with lexical retrieval and real local Ollama.
This intentionally excludes production data, OAG, rewrite, rerank and validation.
"""

import hashlib
import os
from pathlib import Path


def create_fixture():
    directory = Path(os.environ["SME_BENCHMARK_DATA"]).resolve()
    if not directory.name.startswith("sme-atlas-benchmark-") or directory != Path.cwd():
        raise RuntimeError("Run only in the benchmark's temporary directory")
    os.environ["KP_DATA_DIR"] = str(directory / "data")
    # Import only after isolation is established: Atlas creates a module-global app.
    from assistant.answer.generator import OllamaGenerator
    from assistant.answer.service import AnswerService
    from assistant.api.app import create_app
    from assistant.api.auth import AuthService
    from assistant.ingestion.sections import build_sections
    from assistant.ingestion.store import SectionStore
    from assistant.retrieval.service import RetrievalService
    from assistant.sources.models import SourceRecord
    from assistant.sources.register import SourceRegister

    register = SourceRegister(directory / "data")
    content = (
        "# Synthetic supplier activation\n\nFinance approves supplier activation after due diligence. "
        "The supplier record stays on hold until approval. Emergency requests require a documented owner decision.\n"
    )
    register.add(
        SourceRecord(
            id="synthetic-supplier",
            filename="supplier.md",
            title="Synthetic supplier activation",
            sensitivity="synthetic",
            processing_state="ingested",
            approval_status="approved",
            section_count=1,
            size_bytes=len(content.encode()),
            content_sha256=hashlib.sha256(content.encode()).hexdigest(),
            created_at="2026-09-19T00:00:00Z",
        ),
        content.encode(),
    )
    store = SectionStore(register.base_dir)
    store.replace_for_source("synthetic-supplier", build_sections("synthetic-supplier", content))
    retrieval = RetrievalService(register, store)

    class RagAnswer(AnswerService):
        def answer(self, question, top_k=5, **kwargs):
            return super().answer(question, top_k, routing_mode="rag_only", **kwargs)

    answer = RagAnswer(retrieval, OllamaGenerator(model="qwen2.5:7b-instruct", num_ctx=8192, temperature=0.1))
    return create_app(register, AuthService("synthetic-benchmark"), retrieval, answer)
