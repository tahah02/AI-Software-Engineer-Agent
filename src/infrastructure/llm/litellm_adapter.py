import asyncio
import json
import time
from typing import Any

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
from src.ports.llm_gateway import (
    ILLMGateway,
    LLMRequest,
    LLMResponse,
    TokenUsage,
    ToolCall,
)


class LiteLLMAdapter(ILLMGateway):
    SUPPORTED_PROVIDERS = {
        LLMProvider.GEMINI,
        LLMProvider.GROQ,
        LLMProvider.OPENROUTER,
    }

    def _get_api_key(self, provider: LLMProvider) -> str | None:
        if provider == LLMProvider.GEMINI:
            return settings.GEMINI_API_KEY
        if provider == LLMProvider.GROQ:
            return settings.GROQ_API_KEY
        if provider == LLMProvider.OPENROUTER:
            return settings.OPENROUTER_API_KEY
        return None

    def get_default_model(self, provider: LLMProvider) -> str:
        provider_cfg = settings.llm_config.providers.get(provider)
        if provider_cfg:
            return provider_cfg.default_model
        raise ValueError(f"No configuration found for provider '{provider.value}'")

    def _format_model_identifier(self, provider: LLMProvider, model: str) -> str:
        # LiteLLM routes Gemini via "gemini/<model>", Groq via "groq/<model>", OpenRouter via "openrouter/<model>"
        clean_model = model.strip()
        prefix = f"{provider.value}/"
        if not clean_model.startswith(prefix):
            return f"{prefix}{clean_model}"
        return clean_model

    def _redact_secrets(self, text: str) -> str:
        redacted = text
        for key in (settings.GEMINI_API_KEY, settings.GROQ_API_KEY, settings.OPENROUTER_API_KEY):
            if key and len(key) > 4:
                redacted = redacted.replace(key, "[REDACTED]")
        return redacted

    async def list_models(self, provider: LLMProvider) -> list[str]:
        if provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(f"LiteLLMAdapter does not support provider '{provider.value}'")

        # Returns the list of pre-configured candidate models from versioned config
        provider_cfg = settings.llm_config.providers.get(provider)
        if provider_cfg and provider_cfg.available_models:
            return list(provider_cfg.available_models)
        return []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        if request.provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(
                f"LiteLLMAdapter cannot complete requests for provider '{request.provider.value}'"
            )

        api_key = self._get_api_key(request.provider)
        if not api_key:
            raise LLMAuthError(
                provider=request.provider.value,
                model=request.model,
                message=f"Missing API key for provider '{request.provider.value}'. Set in environment variables.",
            )

        model_name = request.model or self.get_default_model(request.provider)
        litellm_model = self._format_model_identifier(request.provider, model_name)

        messages_payload: list[dict[str, Any]] = []
        for msg in request.messages:
            m: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.role == "tool" and msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                m["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments) if isinstance(tc.arguments, dict) else str(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            messages_payload.append(m)

        kwargs: dict[str, Any] = {
            "model": litellm_model,
            "messages": messages_payload,
            "api_key": api_key,
            "temperature": request.temperature,
            "timeout": request.timeout_seconds,
        }

        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens

        if request.tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters.model_dump(),
                    },
                }
                for tool in request.tools
            ]

        if request.response_schema is not None:
            kwargs["response_format"] = {
                "type": "json_object",
                "response_schema": request.response_schema,
            }

        start_time = time.perf_counter()
        attempts = 0
        max_attempts = max(1, request.max_retries + 1)
        last_exception: Exception | None = None

        while attempts < max_attempts:
            attempts += 1
            try:
                response = await litellm.acompletion(**kwargs)
                latency_ms = int((time.perf_counter() - start_time) * 1000)

                choice = response.choices[0]
                message = choice.message
                content = getattr(message, "content", None)
                finish_reason_raw = getattr(choice, "finish_reason", "stop") or "stop"

                # Parse tool calls
                parsed_tool_calls: list[ToolCall] | None = None
                raw_tool_calls = getattr(message, "tool_calls", None)
                if raw_tool_calls:
                    parsed_tool_calls = []
                    for rtc in raw_tool_calls:
                        call_id = getattr(rtc, "id", "")
                        fn = getattr(rtc, "function", None)
                        fn_name = getattr(fn, "name", "") if fn else ""
                        fn_args_raw = getattr(fn, "arguments", "{}") if fn else "{}"
                        try:
                            fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else dict(fn_args_raw)
                        except Exception:
                            fn_args = {"raw": fn_args_raw}
                        parsed_tool_calls.append(ToolCall(id=call_id, name=fn_name, arguments=fn_args))

                finish_reason_map = {
                    "stop": "stop",
                    "tool_calls": "tool_calls",
                    "function_call": "tool_calls",
                    "length": "length",
                }
                finish_reason = finish_reason_map.get(finish_reason_raw, "stop")
                if parsed_tool_calls and finish_reason == "stop":
                    finish_reason = "tool_calls"

                # Usage extraction
                usage_obj = getattr(response, "usage", None)
                prompt_tokens = getattr(usage_obj, "prompt_tokens", 0) or 0
                completion_tokens = getattr(usage_obj, "completion_tokens", 0) or 0
                total_tokens = getattr(usage_obj, "total_tokens", prompt_tokens + completion_tokens) or 0

                return LLMResponse(
                    provider=request.provider,
                    model=model_name,
                    content=content,
                    tool_calls=parsed_tool_calls,
                    usage=TokenUsage(
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        estimated_cost_usd=0.0,
                    ),
                    latency_ms=latency_ms,
                    finish_reason=finish_reason,
                )

            except litellm.AuthenticationError as exc:
                clean_msg = self._redact_secrets(str(exc))
                raise LLMAuthError(
                    provider=request.provider.value,
                    model=model_name,
                    message=f"Authentication failed: {clean_msg}",
                ) from exc

            except litellm.NotFoundError as exc:
                clean_msg = self._redact_secrets(str(exc))
                raise LLMModelNotFoundError(
                    provider=request.provider.value,
                    model=model_name,
                    message=f"Model not found or unavailable: {clean_msg}",
                ) from exc

            except litellm.RateLimitError as exc:
                clean_msg = self._redact_secrets(str(exc))
                last_exception = LLMRateLimitError(
                    provider=request.provider.value,
                    model=model_name,
                    message=f"Rate limit exceeded (attempt {attempts}/{max_attempts}): {clean_msg}",
                )
                if attempts < max_attempts:
                    await asyncio.sleep(1.0 * attempts)
                    continue
                raise last_exception from exc

            except litellm.Timeout as exc:
                clean_msg = self._redact_secrets(str(exc))
                last_exception = LLMTimeoutError(
                    provider=request.provider.value,
                    model=model_name,
                    message=f"Request timed out (attempt {attempts}/{max_attempts}): {clean_msg}",
                )
                if attempts < max_attempts:
                    await asyncio.sleep(0.5 * attempts)
                    continue
                raise last_exception from exc

            except Exception as exc:
                clean_msg = self._redact_secrets(str(exc))
                last_exception = LLMError(
                    provider=request.provider.value,
                    model=model_name,
                    message=f"Provider error: {clean_msg}",
                )
                # Retry transient connection errors only
                if attempts < max_attempts and "connection" in clean_msg.lower():
                    await asyncio.sleep(0.5 * attempts)
                    continue
                raise last_exception from exc

        if last_exception:
            raise last_exception
        raise LLMError(provider=request.provider.value, model=model_name, message="Unexpected retry loop termination")
