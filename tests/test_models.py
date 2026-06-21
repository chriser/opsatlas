"""Model provider tests (offline)."""

from assistant.models.provider import DEFAULT_LLM_MODEL, OllamaProvider, provider_from_env


def test_provider_from_env_defaults(monkeypatch):
    for var in ("KP_OLLAMA_URL", "KP_LLM_MODEL", "KP_EMBED_MODEL"):
        monkeypatch.delenv(var, raising=False)
    assert provider_from_env().llm_model == DEFAULT_LLM_MODEL


def test_provider_from_env_reads_config(monkeypatch):
    monkeypatch.setenv("KP_LLM_MODEL", "qwen3:30b-a3b")
    monkeypatch.setenv("KP_EMBED_MODEL", "bge-m3")
    monkeypatch.setenv("KP_OLLAMA_URL", "http://example:1234")
    p = provider_from_env()
    assert p.llm_model == "qwen3:30b-a3b"
    assert p.embed_model == "bge-m3"
    assert p.base_url == "http://example:1234"


def test_provider_exposes_interface():
    p = OllamaProvider(llm_model="m1", embed_model="m2")
    assert p.info() == {"backend": "ollama", "llm": "m1", "embed": "m2"}
    assert callable(p.embed) and callable(p.generate) and callable(p.health)
