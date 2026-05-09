"""LLM runtime provider tests."""
import json

from app.llm.chat_runtime import generate_reasoning_texts


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_generate_reasoning_texts_returns_prompts_when_disabled(monkeypatch):
    monkeypatch.setenv("ORGANIC4D_LLM_CHAT_ENABLED", "0")
    prompts = ["agent prompt"]
    assert generate_reasoning_texts(prompts, task="thought") == prompts


def test_generate_reasoning_texts_uses_openai_compatible(monkeypatch):
    monkeypatch.setenv("ORGANIC4D_LLM_CHAT_ENABLED", "1")
    monkeypatch.setenv("ORGANIC4D_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("ORGANIC4D_LLM_BASE_URL", "http://localhost:8001/v1")
    monkeypatch.setenv("ORGANIC4D_LLM_MODEL", "local-model")

    def fake_urlopen(request, timeout=0):
        assert request.full_url == "http://localhost:8001/v1/chat/completions"
        payload = json.loads(request.data.decode("utf-8"))
        assert payload["model"] == "local-model"
        return _FakeResponse(
            {"choices": [{"message": {"content": "generated thought text"}}]}
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    out = generate_reasoning_texts(["prompt a"], task="thought")
    assert out == ["generated thought text"]


def test_generate_reasoning_texts_uses_ollama(monkeypatch):
    monkeypatch.setenv("ORGANIC4D_LLM_CHAT_ENABLED", "1")
    monkeypatch.setenv("ORGANIC4D_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("ORGANIC4D_LLM_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("ORGANIC4D_LLM_MODEL", "llama3.1")

    def fake_urlopen(request, timeout=0):
        assert request.full_url == "http://127.0.0.1:11434/api/generate"
        payload = json.loads(request.data.decode("utf-8"))
        assert payload["model"] == "llama3.1"
        return _FakeResponse({"response": "ollama worldview text"})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    out = generate_reasoning_texts(["prompt b"], task="worldview")
    assert out == ["ollama worldview text"]


def test_generate_reasoning_texts_caps_batch(monkeypatch):
    monkeypatch.setenv("ORGANIC4D_LLM_CHAT_ENABLED", "1")
    monkeypatch.setenv("ORGANIC4D_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("ORGANIC4D_LLM_BASE_URL", "http://localhost:8001/v1")
    monkeypatch.setenv("ORGANIC4D_LLM_MAX_PROMPTS_PER_TASK", "1")

    calls = []

    def fake_urlopen(request, timeout=0):
        calls.append(request.data)
        return _FakeResponse(
            {"choices": [{"message": {"content": "generated once"}}]}
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    out = generate_reasoning_texts(["prompt a", "prompt b"], task="dialogue")
    assert out == ["generated once", "prompt b"]
    assert len(calls) == 1
