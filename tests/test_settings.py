"""Every setting in one registry (AUDIT F12): reads use it, the Sales profile names only registered settings, and
.env.example is generated from it."""
import os
import re
from pathlib import Path

import pytest

from assistant import settings
from assistant.models import provider

ROOT = Path(__file__).resolve().parents[1]
CODE = [p for folder in ("src", "services/opsatlas_sales", "services/process_diagram") for p in (ROOT / folder).rglob("*.py")]


def test_no_setting_is_read_around_the_registry():
    direct = re.compile(r"os\.environ\.get\(|os\.getenv\(|os\.environ\[['\"][A-Z_]+['\"]\](?!\s*=)")
    offenders = [f"{p.relative_to(ROOT)}:{n}" for p in CODE if p.name != "settings.py"
                 for n, line in enumerate(p.read_text().splitlines(), 1) if direct.search(line)]
    assert not offenders, offenders


def test_every_name_read_is_registered():
    names = {m for p in CODE for m in re.findall(r"settings\.get\(\s*['\"]([A-Z_]+)['\"]", p.read_text())}
    assert names and names <= set(settings.SETTINGS), sorted(names - set(settings.SETTINGS))
    with pytest.raises(KeyError):
        settings.get("KP_NO_SUCH_SETTING")


def test_the_defaults_are_what_the_code_used_to_say(monkeypatch):
    for name in settings.SETTINGS:
        monkeypatch.delenv(name, raising=False)
    assert (provider.DEFAULT_OLLAMA_URL, provider.DEFAULT_LLM_MODEL, provider.DEFAULT_EMBED_MODEL) == (
        "http://127.0.0.1:11434", "qwen2.5:7b-instruct", "nomic-embed-text")
    assert settings.get("KP_LLM_NUM_PREDICT") == "1536" and settings.get("KP_QUERY_REWRITE") == "1"
    assert settings.get("OPSATLAS_ORIGIN") == "http://127.0.0.1:8780" and settings.get("SME_TIBI_VOICE_URL") == "http://127.0.0.1:8773"
    assert settings.get("KP_GOVERNANCE_LLM_NUM_CTX", "fallback") == "fallback"
    monkeypatch.setenv("KP_RERANK", "0")
    assert settings.get("KP_RERANK") == "0"  # read when used, not cached


def test_env_example_is_generated_from_the_registry():
    assert (ROOT / ".env.example").read_text() == settings.env_example()
    assert "ANAM_API_KEY=\n" in settings.env_example()  # secrets carry no value


def test_the_sales_profile_names_only_registered_settings_and_is_applied(monkeypatch):
    from services.opsatlas_sales.app import PROFILE, apply_profile
    monkeypatch.setattr(os, "environ", os.environ.copy())
    os.environ["KP_OPERATOR_PASSWORD"] = "shared"
    os.environ["KP_OPERATOR_NAME"] = "Someone else"
    os.environ["KP_LLM_MODEL"] = "something-else"
    apply_profile(PROFILE)
    assert os.environ["KP_LLM_MODEL"] == settings.SALES_ANSWER_MODEL  # 'set' wins
    assert os.environ["KP_OPERATOR_NAME"] == "Someone else"  # 'default' only fills a gap
    assert "KP_OPERATOR_PASSWORD" not in os.environ  # 'remove' clears
    assert os.environ["KP_QUERY_REWRITE"] == "0" and os.environ["KP_RERANK"] == "0"
