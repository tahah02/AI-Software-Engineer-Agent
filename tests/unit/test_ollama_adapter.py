import json
import pytest
import httpx

from src.domain.enums import LLMProvider
from src.domain.exceptions import (
    LLMError,
    LLMModelNotFoundError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from src.infrastructure.config import settings
from src.infrastructure.llm.ollama_adapter import OllamaAdapter
from src.ports.llm_gateway import ILLMGateway, LLMMessage, LLMRequest

ORIGINAL_ASYNC_CLIENT = httpx.AsyncClient


def _make_mock_client_factory(transport: httpx.MockTransport):
    def factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return ORIGINAL_ASYNC_CLIENT(*args, transport=transport, **kwargs)
    return factory


def test_ollama_adapter_implements_protocol():
    adapter = OllamaAdapter()
    assert isinstance(adapter, ILLMGateway)


def test_ollama_adapter_uses_json_config_default_model():
    adapter = OllamaAdapter()
    expected_default = settings.llm_config.providers[LLMProvider.OLLAMA].default_model
    assert adapter.get_default_model() == expected_default
    assert expected_default == "qwen2.5-coder:7b"


def test_llm_config_validation_error_on_missing_file(monkeypatch, tmp_path):
    non_existent = tmp_path / "missing.json"
    monkeypatch.setattr(settings, "LLM_CONFIG_PATH", str(non_existent))
    monkeypatch.setattr(settings, "_llm_config", None)
    with pytest.raises(FileNotFoundError):
        settings.load_llm_config()


def test_llm_config_validation_error_on_malformed_json(monkeypatch, tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{invalid json", encoding="utf-8")
    monkeypatch.setattr(settings, "LLM_CONFIG_PATH", str(bad_file))
    monkeypatch.setattr(settings, "_llm_config", None)
    with pytest.raises(ValueError, match="Invalid LLM configuration"):
        settings.load_llm_config()


@pytest.mark.asyncio
async def test_ollama_complete_success(monkeypatch):
    mock_payload = {
        "model": "qwen2.5-coder:7b",
        "message": {"role": "assistant", "content": "def add(a, b): return a + b"},
        "prompt_eval_count": 15,
        "eval_count": 25,
        "done": True,
    }

    def mock_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        req_data = json.loads(request.content.decode("utf-8"))
        assert req_data["model"] == "qwen2.5-coder:7b"
        assert req_data["stream"] is False
        assert req_data["options"]["temperature"] == 0.2
        return httpx.Response(200, json=mock_payload)

    transport = httpx.MockTransport(mock_handler)
    monkeypatch.setattr(httpx, "AsyncClient", _make_mock_client_factory(transport))

    adapter = OllamaAdapter(base_url="http://mock-ollama:11434")
    request = LLMRequest(
        provider=LLMProvider.OLLAMA,
        model="qwen2.5-coder:7b",
        messages=[LLMMessage(role="user", content="Write an add function.")],
    )

    response = await adapter.complete(request)
    assert response.provider == LLMProvider.OLLAMA
    assert response.model == "qwen2.5-coder:7b"
    assert response.content == "def add(a, b): return a + b"
    assert response.usage.prompt_tokens == 15
    assert response.usage.completion_tokens == 25
    assert response.usage.total_tokens == 40
    assert response.finish_reason == "stop"


@pytest.mark.asyncio
async def test_ollama_complete_with_json_format_schema(monkeypatch):
    def mock_handler(request: httpx.Request) -> httpx.Response:
        req_data = json.loads(request.content.decode("utf-8"))
        assert req_data["format"] == "json"
        assert req_data["options"]["num_predict"] == 512
        return httpx.Response(
            200,
            json={
                "model": "qwen2.5:3b",
                "message": {"role": "assistant", "content": "{\"status\": \"ok\"}"},
                "prompt_eval_count": 10,
                "eval_count": 10,
            },
        )

    transport = httpx.MockTransport(mock_handler)
    monkeypatch.setattr(httpx, "AsyncClient", _make_mock_client_factory(transport))

    adapter = OllamaAdapter(base_url="http://mock-ollama:11434")
    request = LLMRequest(
        provider=LLMProvider.OLLAMA,
        model="qwen2.5:3b",
        messages=[LLMMessage(role="user", content="Return JSON.")],
        response_schema={"type": "object"},
        max_tokens=512,
    )

    response = await adapter.complete(request)
    assert response.content == "{\"status\": \"ok\"}"


@pytest.mark.asyncio
async def test_ollama_complete_model_not_found_raises_typed_error(monkeypatch):
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="model not found")

    transport = httpx.MockTransport(mock_handler)
    monkeypatch.setattr(httpx, "AsyncClient", _make_mock_client_factory(transport))

    adapter = OllamaAdapter(base_url="http://mock-ollama:11434")
    request = LLMRequest(
        provider=LLMProvider.OLLAMA,
        model="non-existent-model",
        messages=[LLMMessage(role="user", content="Hello")],
        max_retries=0,
    )

    with pytest.raises(LLMModelNotFoundError) as exc_info:
        await adapter.complete(request)
    assert "non-existent-model" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ollama_complete_rate_limit_error(monkeypatch):
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Too many requests")

    transport = httpx.MockTransport(mock_handler)
    monkeypatch.setattr(httpx, "AsyncClient", _make_mock_client_factory(transport))

    adapter = OllamaAdapter(base_url="http://mock-ollama:11434")
    request = LLMRequest(
        provider=LLMProvider.OLLAMA,
        model="qwen2.5-coder:7b",
        messages=[LLMMessage(role="user", content="Hello")],
        max_retries=0,
    )

    with pytest.raises(LLMRateLimitError):
        await adapter.complete(request)


@pytest.mark.asyncio
async def test_ollama_list_models_success(monkeypatch):
    mock_tags = {
        "models": [
            {"name": "qwen2.5-coder:7b", "size": 4700000000},
            {"name": "qwen2.5:3b", "size": 1900000000},
        ]
    }

    def mock_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json=mock_tags)

    transport = httpx.MockTransport(mock_handler)
    monkeypatch.setattr(httpx, "AsyncClient", _make_mock_client_factory(transport))

    adapter = OllamaAdapter(base_url="http://mock-ollama:11434")
    models = await adapter.list_models(LLMProvider.OLLAMA)
    assert models == ["qwen2.5-coder:7b", "qwen2.5:3b"]


@pytest.mark.asyncio
async def test_ollama_list_models_unsupported_provider():
    adapter = OllamaAdapter()
    with pytest.raises(ValueError, match="does not support"):
        await adapter.list_models(LLMProvider.GEMINI)
