"""Every setting OpsAtlas reads from the environment, in one place (AUDIT F12).

Each read in the core, the Sales workspace and the diagram service names a registered setting and takes its default
from here; a test fails on a read of an unregistered name. Values are read when used, not cached, so the Sales profile
(services/opsatlas_sales/profile.json) and the tests' environment apply. `.env.example` is generated from this file:

    python -m assistant.settings > .env.example

Tibi's engine (services/sme_interviewer) keeps its own settings: its files are fingerprinted, and a change to them is an
engine version.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

# Where things listen on this Mac.
SALES_PORT = 8780       # the Sales workspace and its control panel
TIBI_PORT = 8773        # Tibi's voice service
DIAGRAMS_PORT = 5300    # the process-diagram service
CORE_PORT = 8010        # a lone core, as OpsAtlas Classic runs it
OLLAMA_URL = "http://127.0.0.1:11434"

# The models, by role.
ANSWER_MODEL = "qwen2.5:7b-instruct"     # a lone core's answers; the Sales profile sets SALES_ANSWER_MODEL
SALES_ANSWER_MODEL = "qwen3.5:4b"        # the Product Guide's answers (ARCH H3a)
EMBED_MODEL = "nomic-embed-text"
GOVERNANCE_JUDGE_MODEL = "qwen2.5:14b-instruct"

_MISSING = object()


@dataclass(frozen=True)
class Setting:
    name: str
    default: str | None
    about: str
    group: str
    secret: bool = False


_ALL = [
    # The core
    Setting("KP_DATA_DIR", "data", "A lone core's data folder; the Sales workspace sets one per space", "core"),
    Setting("KP_OLLAMA_URL", OLLAMA_URL, "The Ollama server", "core"),
    Setting("KP_LLM_MODEL", ANSWER_MODEL, "The answer model", "core"),
    Setting("KP_EMBED_MODEL", EMBED_MODEL, "The embedding model", "core"),
    Setting("KP_LLM_NUM_CTX", "8192", "The answer model's context, in tokens", "core"),
    Setting("KP_LLM_TIMEOUT", "120", "Seconds a generation may take", "core"),
    Setting("KP_LLM_THINK", "0", "Whether the answer model may reason first: 0, 1 or auto (ARCH H3a)", "core"),
    Setting("KP_LLM_NUM_PREDICT", "1536", "The longest answer, in tokens; 0 for no bound (ARCH H3a)", "core"),
    Setting("KP_QUERY_REWRITE", "1", "Rewrite questions before retrieval: 1 or 0", "core"),
    Setting("KP_RERANK", "1", "Rerank retrieved passages with the model: 1 or 0", "core"),
    Setting("KP_MIN_SIMILARITY", "0.55", "The retrieval relevance threshold", "core"),
    Setting("KP_VALIDATE_GROUNDING", "1", "Check answers against their cited evidence: 1 or 0", "core"),
    Setting("KP_WITHHOLD_UNSUPPORTED", "0", "Withhold an answer the grounding check marks unsupported: 1 or 0 (REF H1)", "core"),
    Setting("KP_SCOPE_EVIDENCE", "0", "Let only sources in force, not replaced and for the site asked about answer: 1 or 0 (REF H3)",
            "core"),
    Setting("KP_SCOPE_TODAY", None, "The date scope treats as today, YYYY-MM-DD (evaluation only)", "core"),
    Setting("KP_PLAN_PARTS", "0", "Retrieve evidence for each part of a multi-part question: 1 or 0 (REF H4)", "core"),
    Setting("KP_EAM_TAXONOMY", None, "Another Enterprise Activity Model taxonomy file", "core"),
    Setting("KP_OPERATOR_NAME", "Operator", "Who edits when no one is signed in (start-up, tests)", "core"),
    Setting("KP_OPERATOR_ROLE", "Platform operator", "That operator's role", "core"),
    Setting("KP_OPERATOR_PASSWORD", None, "The single shared password of the test setup; personal accounts replace it", "core", True),
    Setting("OPSATLAS_ORIGIN", f"http://127.0.0.1:{SALES_PORT}",
            f"The browser's origin for cookies and links; a lone core uses http://127.0.0.1:{CORE_PORT}", "core"),
    Setting("OPSATLAS_WORKSPACE", ".runtime/opsatlas-sales", "The workspace the IAM host commands act on", "core"),
    Setting("OPSATLAS_SECURE_COOKIE", "0", "1: the session cookie is sent over HTTPS only; keep 0 on loopback HTTP (REF S6)", "core"),
    # Governance
    Setting("KP_GOVERNANCE_LLM_ENABLED", "0", "Model-assisted governance in a lone core: 1 or 0", "governance"),
    Setting("KP_GOVERNANCE_LLM_MODEL", "", "That governance model; empty means the answer model", "governance"),
    Setting("KP_GOVERNANCE_LLM_NUM_CTX", None, "Its context, in tokens; unset means KP_LLM_NUM_CTX", "governance"),
    Setting("KP_GOVERNANCE_LLM_TIMEOUT", "120", "Seconds a governance generation may take", "governance"),
    Setting("SALES_GOVERNANCE_AUTO_REVIEW", "1", "Review new Sales records automatically: 1 or 0", "governance"),
    Setting("SALES_GOVERNANCE_JUDGE", "local", "The statement judge: local, or anthropic:<model>", "governance"),
    Setting("SALES_GOVERNANCE_FRONTIER_APPROVED", "", "yes: the data owner approved sending records to a hosted judge",
            "governance"),
    # Services
    Setting("SME_TIBI_VOICE_URL", f"http://127.0.0.1:{TIBI_PORT}", "Tibi's voice service", "services"),
    Setting("SME_HIGGS_BITS", None, "Tibi's Higgs voice quantisation, passed to its service on a restart", "services"),
    Setting("PROCESS_DIAGRAM_SERVICE_URL", f"http://127.0.0.1:{DIAGRAMS_PORT}", "The process-diagram service", "services"),
    Setting("PROCESS_DIAGRAM_TIMEOUT_SECONDS", "4", "Seconds a diagram request may take", "services"),
    Setting("PROCESS_DIAGRAM_MANAGED", None, "launchd: the diagram service is launchd's, never started loose", "services"),
    Setting("PROCESS_DIAGRAM_PYTHON", None, "The Python that starts a loose diagram service", "services"),
    Setting("PROCESS_DIAGRAM_RELOAD", "0", "Start a loose diagram service with --reload: 1 or 0", "services"),
    Setting("PROCESS_DIAGRAM_LOG_PATH", None, "The diagram service's log file", "services"),
    Setting("OLLAMA_MODELS", None, "Where the model server keeps OpsAtlas's models; unset means the Ollama app's own "
            "(~/.ollama/models). The Talk with Tibi page's machine reading tells OpsAtlas's models from other apps' by it",
            "services"),
    # The Digital SME
    Setting("ANAM_API_KEY", "", "The Anam account key for the Digital SME", "avatar", True),
    Setting("ANAM_PERSONA_ID", "", "The Anam persona", "avatar"),
]
SETTINGS: dict[str, Setting] = {s.name: s for s in _ALL}


def get(name: str, default: object = _MISSING) -> str | None:
    """The setting's value now: the environment's, else the given default, else the registered one."""
    setting = SETTINGS[name]  # an unregistered name is a KeyError, on purpose
    return os.environ.get(name, setting.default if default is _MISSING else default)  # type: ignore[arg-type]


def env_example() -> str:
    """The .env.example text: every setting, commented, with its default and what it does."""
    lines = ["# OpsAtlas settings (generated: python -m assistant.settings > .env.example). Uncomment to change one.",
             "# The Sales workspace overrides some of them for its cores: services/opsatlas_sales/profile.json."]
    for group in dict.fromkeys(s.group for s in _ALL):
        lines += ["", f"# --- {group} ---"]
        for s in (s for s in _ALL if s.group == group):
            lines.append(f"# {s.about}")
            lines.append(f"# {s.name}=" + ("" if s.secret or s.default is None else s.default))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(env_example(), end="")
