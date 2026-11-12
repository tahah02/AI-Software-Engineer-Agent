import pytest
from pydantic import ValidationError as PydanticValidationError

from src.domain.enums import LLMProvider
from src.domain.exceptions import (
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMAuthError,
    LLMModelNotFoundError,
)
from src.ports.llm_gateway import (
    ILLMGateway,
    LLMMessage,
    LLMRequest,
    LLMResponse,
    TokenUsage,
    ToolCall,
    ToolDefinition,
    ToolParameterSchema,
)


def _base_request(**overrides) -> LLMRequest:
    defaults = dict(
        provider=LLMProvider.OLLAMA,
        model="qwen2.5-coder:7b",
        messages=[LLMMessage(role="user", content="Write a FastAPI health endpoint.")],
    )
    return LLMRequest(**(defaults | overrides))


def _base_usage() -> TokenUsage:
    return TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)


def test_llm_request_defaults():
    req = _base_request()
    assert req.temperature == 0.2
    assert req.max_retries == 2
    assert req.timeout_seconds == 60.0
    assert req.tools is None
    assert req.response_schema is None
    assert req.max_tokens is None


def test_llm_request_with_system_and_user_messages():
    req = LLMRequest(
        provider=LLMProvider.GEMINI,
        model="gemini-3.8-flash",
        messages=[
            LLMMessage(role="system", content="You are a senior Python engineer."),
            LLMMessage(role="user", content="Implement a CRUD repository for Projects."),
        ],
        temperature=0.1,
        max_tokens=4096,
    )
    assert len(req.messages) == 2
    assert req.messages[0].role == "system"
    assert req.provider == LLMProvider.GEMINI
    assert req.max_tokens == 4096


def test_llm_request_with_tool_definitions():
    tool = ToolDefinition(
        name="read_file",
        description="Read the contents of a file at the given path.",
        parameters=ToolParameterSchema(
            properties={"path": {"type": "string", "description": "Absolute file path"}},
            required=["path"],
        ),
    )
    req = _base_request(tools=[tool])
    assert req.tools is not None
    assert len(req.tools) == 1
    assert req.tools[0].name == "read_file"
    assert "path" in req.tools[0].parameters.required


def test_llm_request_with_structured_output_schema():
    schema = {
        "type": "object",
        "properties": {
            "endpoints": {"type": "array", "items": {"type": "string"}},
            "data_models": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["endpoints", "data_models"],
    }
    req = _base_request(response_schema=schema)
    assert req.response_schema is not None
    assert "endpoints" in req.response_schema["properties"]


def test_llm_request_invalid_temperature():
    with pytest.raises(PydanticValidationError):
        _base_request(temperature=3.0)


def test_llm_request_invalid_max_retries():
    with pytest.raises(PydanticValidationError):
        _base_request(max_retries=10)


def test_llm_request_empty_messages():
    with pytest.raises(PydanticValidationError):
        LLMRequest(provider=LLMProvider.GROQ, model="qwen3", messages=[])


def test_llm_response_text_finish():
    resp = LLMResponse(
        provider=LLMProvider.GROQ,
        model="qwen/qwen3.8-27b",
        content="Here is the implementation...",
        usage=_base_usage(),
        latency_ms=320,
        finish_reason="stop",
    )
    assert resp.content == "Here is the implementation..."
    assert resp.tool_calls is None
    assert resp.finish_reason == "stop"
    assert resp.usage.total_tokens == 30


def test_llm_response_tool_call_finish():
    tool_call = ToolCall(id="tc-001", name="read_file", arguments={"path": "/src/api/main.py"})
    resp = LLMResponse(
        provider=LLMProvider.OPENROUTER,
        model="openai/gpt-oss-120b",
        content=None,
        tool_calls=[tool_call],
        usage=_base_usage(),
        latency_ms=540,
        finish_reason="tool_calls",
    )
    assert resp.tool_calls is not None
    assert resp.tool_calls[0].name == "read_file"
    assert resp.tool_calls[0].arguments["path"] == "/src/api/main.py"
    assert resp.finish_reason == "tool_calls"


def test_token_usage_cost_defaults():
    usage = TokenUsage(prompt_tokens=100, completion_tokens=200, total_tokens=300)
    assert usage.estimated_cost_usd == 0.0


def test_llm_provider_enum_values():
    assert LLMProvider.GEMINI == "gemini"
    assert LLMProvider.GROQ == "groq"
    assert LLMProvider.OPENROUTER == "openrouter"
    assert LLMProvider.OLLAMA == "ollama"


def test_llm_error_hierarchy():
    err = LLMRateLimitError(provider="groq", model="qwen3", message="429 rate limited")
    assert isinstance(err, LLMError)
    assert err.provider == "groq"
    assert "429 rate limited" in str(err)

    timeout = LLMTimeoutError(provider="ollama", model="qwen2.5-coder:7b", message="Timed out after 60s")
    assert isinstance(timeout, LLMError)

    auth = LLMAuthError(provider="gemini", model="gemini-3.8-flash", message="Invalid API key")
    assert isinstance(auth, LLMError)

    notfound = LLMModelNotFoundError(provider="openrouter", model="unknown/model", message="Model not found")
    assert isinstance(notfound, LLMError)


def test_igateway_is_protocol():
    assert ILLMGateway._is_protocol is True
    assert hasattr(ILLMGateway, "complete")
    assert hasattr(ILLMGateway, "list_models")


def test_class_not_implementing_protocol_fails_isinstance():
    class NotAGateway:
        pass

    assert not isinstance(NotAGateway(), ILLMGateway)


def test_class_implementing_protocol_passes_isinstance():
    class MockGateway:
        async def complete(self, request: LLMRequest) -> LLMResponse: ...
        async def list_models(self, provider: LLMProvider) -> list[str]: ...

    assert isinstance(MockGateway(), ILLMGateway)
