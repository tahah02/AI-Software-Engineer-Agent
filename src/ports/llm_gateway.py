from __future__ import annotations

from typing import Any, Literal
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from src.domain.enums import LLMProvider


class ToolParameterSchema(BaseModel):
    type: Literal["object"] = "object"
    properties: dict[str, Any]
    required: list[str] = Field(default_factory=list)


class ToolDefinition(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1)
    parameters: ToolParameterSchema


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class LLMMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] | None = None


class LLMRequest(BaseModel):
    provider: LLMProvider
    model: str = Field(min_length=1)
    messages: list[LLMMessage] = Field(min_length=1)
    tools: list[ToolDefinition] | None = None
    response_schema: dict[str, Any] | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    timeout_seconds: float = Field(default=60.0, gt=0.0)
    max_retries: int = Field(default=2, ge=0, le=5)


class TokenUsage(BaseModel):
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)


class LLMResponse(BaseModel):
    provider: LLMProvider
    model: str
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    usage: TokenUsage
    latency_ms: int = Field(ge=0)
    finish_reason: Literal["stop", "tool_calls", "length", "error"]


@runtime_checkable
class ILLMGateway(Protocol):
    async def complete(self, request: LLMRequest) -> LLMResponse:
        ...

    async def list_models(self, provider: LLMProvider) -> list[str]:
        ...
