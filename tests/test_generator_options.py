"""ARCH H3a: the core's model call switches off hidden thinking and bounds the output, unless configured otherwise."""
import json

from assistant.answer import generator as generator_module
from assistant.answer.generator import DEFAULT_NUM_PREDICT, OllamaGenerator
from assistant.models.provider import _think_setting, provider_from_env


class Response:
    def __init__(self, body):
        self.body = body

    def read(self):
        return json.dumps(self.body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_the_payload_turns_thinking_off_and_bounds_the_output(monkeypatch):
    sent = []

    def urlopen(request, timeout):
        sent.append(json.loads(request.data))
        return Response({"response": " An answer [1]. "})
    monkeypatch.setattr(generator_module.urllib.request, "urlopen", urlopen)
    assert OllamaGenerator(model="qwen3.5:4b").generate("Q?") == "An answer [1]."
    body = sent[0]
    assert body["think"] is False and body["options"]["num_predict"] == DEFAULT_NUM_PREDICT == 1536
    assert body["options"]["num_ctx"] == 8192 and body["stream"] is False


def test_none_leaves_the_models_own_behaviour():
    body = OllamaGenerator(think=None, num_predict=None).payload("Q?")
    assert "think" not in body and "num_predict" not in body["options"]


def test_the_environment_settings(monkeypatch):
    assert _think_setting("0") is False and _think_setting("false") is False and _think_setting("nonsense") is False
    assert _think_setting("1") is True and _think_setting("on") is True
    assert _think_setting("auto") is None and _think_setting("") is None
    monkeypatch.setenv("KP_LLM_THINK", "auto")
    monkeypatch.setenv("KP_LLM_NUM_PREDICT", "0")
    generator = provider_from_env()._generator
    assert generator.think is None and generator.num_predict is None
    monkeypatch.delenv("KP_LLM_THINK")
    monkeypatch.delenv("KP_LLM_NUM_PREDICT")
    generator = provider_from_env()._generator
    assert generator.think is False and generator.num_predict == 1536
