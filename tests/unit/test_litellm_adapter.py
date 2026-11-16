import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock
import pytest
import litellm

from src.domain.enums import LLMProvider
from src.domain.exceptions import (
    LLMAuthError,
    LLMError,
    LLMModelNotFoundError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from src.infrastructure.config import settings
from src.infrastructure.llm.litellm_adapter import LiteLLMAdapter
from src.ports.llm_gateway import (
    ILLMGateway,
    LLMMessage,
    LLMRequest,
    ToolCall,
    ToolDefinition,
    ToolParameterSchema,
)


def _mock_litellm_response(
    content: str | None = "Response text",
    tool_calls: list[Any] | None = None,
    prompt_tokens: int = 20,
    completion_tokens: int = 30,
    finish_reason: str = "stop",
):
    choice = MagicMock()
    choice.message = MagicMock()
    choice.message.content = content
    choice.message.tool_calls = tool_calls
    choice.finish_reason = finish_reason

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = prompt_tokens + completion_tokens

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


def test_litellm_adapter_implements_protocol():
    adapter = LiteLLMAdapter()
    assert isinstance(adapter, ILLMGateway)


def test_litellm_adapter_supported_providers():
    adapter = LiteLLMAdapter()
    assert LLMProvider.GEMINI in adapter.SUPPORTED_PROVIDERS
    assert LLMProvider.GROQ in adapter.SUPPORTED_PROVIDERS
    assert LLMProvider.OPENROUTER in adapter.SUPPORTED_PROVIDERS
    assert LLMProvider.OLLAMA not in adapter.SUPPORTED_PROVIDERS


def test_litellm_adapter_resolves_json_defaults():
    adapter = LiteLLMAdapter()
    gemini_def = adapter.get_default_model(LLMProvider.GEMINI)
    groq_def = adapter.get_default_model(LLMProvider.GROQ)
    openrouter_def = adapter.get_default_model(LLMProvider.OPENROUTER)

    assert gemini_def in ("gemini-3-flash-preview", "gemini-3.8-flash", "gemini-3.5-flash-lite")
    assert groq_def == "openai/gpt-oss-120b"
    assert openrouter_def == "openai/gpt-oss-120b"


@pytest.mark.asyncio
async def test_litellm_missing_api_key_raises_auth_error(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    adapter = LiteLLMAdapter()
    req = LLMRequest(
        provider=LLMProvider.GEMINI,
        model="gemini-3.8-flash",
        messages=[LLMMessage(role="user", content="Test")],
    )
    with pytest.raises(LLMAuthError) as exc_info:
        await adapter.complete(req)
    assert "Missing API key" in str(exc_info.value)
    assert exc_info.value.provider == "gemini"


@pytest.mark.asyncio
async def test_litellm_gemini_completion_success(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "mock-gemini-key-12345")
    mock_resp = _mock_litellm_response(content="Gemini spec analysis result")
    mock_acompletion = AsyncMock(return_value=mock_resp)
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    adapter = LiteLLMAdapter()
    req = LLMRequest(
        provider=LLMProvider.GEMINI,
        model="gemini-3.8-flash",
        messages=[LLMMessage(role="user", content="Analyze requirements")],
    )
    resp = await adapter.complete(req)

    assert resp.provider == LLMProvider.GEMINI
    assert resp.model == "gemini-3.8-flash"
    assert resp.content == "Gemini spec analysis result"
    assert resp.usage.total_tokens == 50
    assert resp.finish_reason == "stop"

    # Verify model prefix routing
    call_kwargs = mock_acompletion.call_args.kwargs
    assert call_kwargs["model"] == "gemini/gemini-3.8-flash"
    assert call_kwargs["api_key"] == "mock-gemini-key-12345"


@pytest.mark.asyncio
async def test_litellm_groq_completion_success(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "mock-groq-key-67890")
    mock_resp = _mock_litellm_response(content="Groq mock server code")
    mock_acompletion = AsyncMock(return_value=mock_resp)
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    adapter = LiteLLMAdapter()
    req = LLMRequest(
        provider=LLMProvider.GROQ,
        model="openai/gpt-oss-120b",
        messages=[LLMMessage(role="user", content="Implement mock")],
    )
    resp = await adapter.complete(req)

    assert resp.provider == LLMProvider.GROQ
    assert resp.content == "Groq mock server code"
    call_kwargs = mock_acompletion.call_args.kwargs
    assert call_kwargs["model"] == "groq/openai/gpt-oss-120b"


@pytest.mark.asyncio
async def test_litellm_openrouter_completion_success(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "mock-openrouter-key-999")
    mock_resp = _mock_litellm_response(content="OpenRouter test results")
    mock_acompletion = AsyncMock(return_value=mock_resp)
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    adapter = LiteLLMAdapter()
    req = LLMRequest(
        provider=LLMProvider.OPENROUTER,
        model="openai/gpt-oss-120b",
        messages=[LLMMessage(role="user", content="Run QA tests")],
    )
    resp = await adapter.complete(req)

    assert resp.provider == LLMProvider.OPENROUTER
    assert resp.content == "OpenRouter test results"
    call_kwargs = mock_acompletion.call_args.kwargs
    assert call_kwargs["model"] == "openrouter/openai/gpt-oss-120b"


@pytest.mark.asyncio
async def test_litellm_tool_calling_translation(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "mock-gemini-key")
    raw_tc = MagicMock()
    raw_tc.id = "call_abc123"
    raw_tc.function = MagicMock()
    raw_tc.function.name = "fetch_schema"
    raw_tc.function.arguments = json.dumps({"table_name": "projects"})

    mock_resp = _mock_litellm_response(content=None, tool_calls=[raw_tc], finish_reason="tool_calls")
    mock_acompletion = AsyncMock(return_value=mock_resp)
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    tool = ToolDefinition(
        name="fetch_schema",
        description="Fetch database schema for table",
        parameters=ToolParameterSchema(
            properties={"table_name": {"type": "string"}},
            required=["table_name"],
        ),
    )
    adapter = LiteLLMAdapter()
    req = LLMRequest(
        provider=LLMProvider.GEMINI,
        model="gemini-3.8-flash",
        messages=[LLMMessage(role="user", content="Check schema")],
        tools=[tool],
    )
    resp = await adapter.complete(req)

    assert resp.tool_calls is not None
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "fetch_schema"
    assert resp.tool_calls[0].arguments == {"table_name": "projects"}
    assert resp.finish_reason == "tool_calls"


@pytest.mark.asyncio
async def test_litellm_structured_output_payload(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "mock-groq-key")
    mock_resp = _mock_litellm_response(content='{"status": "PASS"}')
    mock_acompletion = AsyncMock(return_value=mock_resp)
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    schema = {"type": "object", "properties": {"status": {"type": "string"}}}
    adapter = LiteLLMAdapter()
    req = LLMRequest(
        provider=LLMProvider.GROQ,
        model="qwen/qwen3.8-27b",
        messages=[LLMMessage(role="user", content="Check status")],
        response_schema=schema,
    )
    await adapter.complete(req)

    call_kwargs = mock_acompletion.call_args.kwargs
    assert "response_format" in call_kwargs
    assert call_kwargs["response_format"]["type"] == "json_object"


@pytest.mark.asyncio
async def test_litellm_authentication_error_and_redaction(monkeypatch):
    secret_key = "sk-live-secret-never-expose-this"
    monkeypatch.setattr(settings, "GROQ_API_KEY", secret_key)

    async def mock_fail(**kwargs):
        raise litellm.AuthenticationError(
            message=f"Invalid API Key: {secret_key}",
            model="openai/gpt-oss-120b",
            llm_provider="groq",
        )

    monkeypatch.setattr(litellm, "acompletion", mock_fail)

    adapter = LiteLLMAdapter()
    req = LLMRequest(
        provider=LLMProvider.GROQ,
        model="openai/gpt-oss-120b",
        messages=[LLMMessage(role="user", content="Hello")],
        max_retries=0,
    )

    with pytest.raises(LLMAuthError) as exc_info:
        await adapter.complete(req)
    err_str = str(exc_info.value)
    assert secret_key not in err_str
    assert "[REDACTED]" in err_str


@pytest.mark.asyncio
async def test_litellm_model_not_found_error(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "mock-or-key")

    async def mock_fail(**kwargs):
        raise litellm.NotFoundError(
            message="Model does not exist",
            model="invalid-model-x",
            llm_provider="openrouter",
        )

    monkeypatch.setattr(litellm, "acompletion", mock_fail)

    adapter = LiteLLMAdapter()
    req = LLMRequest(
        provider=LLMProvider.OPENROUTER,
        model="invalid-model-x",
        messages=[LLMMessage(role="user", content="Test")],
        max_retries=0,
    )

    with pytest.raises(LLMModelNotFoundError):
        await adapter.complete(req)


@pytest.mark.asyncio
async def test_litellm_rate_limit_error(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "mock-gem-key")

    async def mock_fail(**kwargs):
        raise litellm.RateLimitError(
            message="429 Rate limit exceeded",
            model="gemini-3.8-flash",
            llm_provider="gemini",
        )

    monkeypatch.setattr(litellm, "acompletion", mock_fail)

    adapter = LiteLLMAdapter()
    req = LLMRequest(
        provider=LLMProvider.GEMINI,
        model="gemini-3.8-flash",
        messages=[LLMMessage(role="user", content="Test")],
        max_retries=0,
    )

    with pytest.raises(LLMRateLimitError):
        await adapter.complete(req)


@pytest.mark.asyncio
async def test_litellm_timeout_error(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "mock-groq-key")

    async def mock_fail(**kwargs):
        raise litellm.Timeout(
            message="Request timed out after 30s",
            model="qwen/qwen3.8-27b",
            llm_provider="groq",
        )

    monkeypatch.setattr(litellm, "acompletion", mock_fail)

    adapter = LiteLLMAdapter()
    req = LLMRequest(
        provider=LLMProvider.GROQ,
        model="qwen/qwen3.8-27b",
        messages=[LLMMessage(role="user", content="Test")],
        max_retries=0,
    )

    with pytest.raises(LLMTimeoutError):
        await adapter.complete(req)


@pytest.mark.asyncio
async def test_litellm_list_models_returns_configured_candidates():
    adapter = LiteLLMAdapter()
    gemini_models = await adapter.list_models(LLMProvider.GEMINI)
    groq_models = await adapter.list_models(LLMProvider.GROQ)
    or_models = await adapter.list_models(LLMProvider.OPENROUTER)

    assert "gemini-3.8-flash" in gemini_models
    assert "openai/gpt-oss-120b" in groq_models
    assert "openai/gpt-oss-120b" in or_models


@pytest.mark.asyncio
async def test_litellm_list_models_unsupported_provider():
    adapter = LiteLLMAdapter()
    with pytest.raises(ValueError, match="does not support"):
        await adapter.list_models(LLMProvider.OLLAMA)
