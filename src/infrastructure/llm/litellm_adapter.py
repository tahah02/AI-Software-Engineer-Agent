import logging
import asyncio
import json
import time
from typing import Any

import os
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
import litellm
litellm.telemetry = False
litellm.suppress_debug_info = True

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


logger = logging.getLogger(__name__)


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
        if clean_model.startswith(prefix):
            clean_model = clean_model[len(prefix):]
        return f"{prefix}{clean_model}"

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
            kwargs["response_format"] = {"type": "json_object"}

        start_time = time.perf_counter()
        attempts = 0
        max_attempts = max(1, request.max_retries + 1)
        has_fallback = bool(getattr(request, "fallback_model", None))
        transient_max_attempts = max(max_attempts, 4 if has_fallback else 6)
        last_exception: Exception | None = None

        while attempts < transient_max_attempts:
            attempts += 1
            try:
                response = await litellm.acompletion(**kwargs)
                latency_ms = int((time.perf_counter() - start_time) * 1000)

                choice = response.choices[0]
                message = choice.message
                content = getattr(message, "content", None) or ""
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
                last_exception = LLMModelNotFoundError(
                    provider=request.provider.value,
                    model=model_name,
                    message=f"Model not found or unavailable: {clean_msg}",
                )
                break

            except litellm.RateLimitError as exc:
                clean_msg = self._redact_secrets(str(exc))
                last_exception = LLMRateLimitError(
                    provider=request.provider.value,
                    model=model_name,
                    message=f"Rate limit exceeded (attempt {attempts}/{max_attempts}): {clean_msg}",
                )
                # If prompt exceeds model's TPM quota, immediate failover to fallback without retrying
                if "too large" in clean_msg.lower() or "limit" in clean_msg.lower() and "requested" in clean_msg.lower():
                    break
                if attempts < max_attempts:
                    await asyncio.sleep(1.0 * attempts)
                    continue
                break

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
                break

            except Exception as exc:
                clean_msg = self._redact_secrets(str(exc))
                last_exception = LLMError(
                    provider=request.provider.value,
                    model=model_name,
                    message=f"Provider error: {clean_msg}",
                )
                # Retry transient connection, DNS/socket, and 503 overload / high demand errors
                transient_signals = (
                    "connection", "503", "overloaded", "unavailable", "timeout",
                    "getaddrinfo", "socket", "dns", "ssl", "high demand", "spikes in demand"
                )
                if attempts < transient_max_attempts and any(k in clean_msg.lower() for k in transient_signals):
                    backoff = 3.0 + (3.0 * attempts)
                    logger.warning(
                        f"Transient provider error on {model_name} (attempt {attempts}/{transient_max_attempts}). "
                        f"Backing off {backoff:.1f}s before retry."
                    )
                    await asyncio.sleep(backoff)
                    continue
                break

        if last_exception:
            fb_model = getattr(request, "fallback_model", None)
            fb_provider_raw = getattr(request, "fallback_provider", None)
            if fb_provider_raw is not None and not isinstance(fb_provider_raw, LLMProvider):
                try:
                    fb_provider = LLMProvider(str(fb_provider_raw).lower())
                except Exception:
                    fb_provider = request.provider
            else:
                fb_provider = fb_provider_raw or request.provider

            if fb_model and (fb_model != model_name or fb_provider != request.provider):
                fallback_req = LLMRequest(
                    provider=fb_provider,
                    model=fb_model,
                    messages=request.messages,
                    tools=request.tools,
                    response_schema=request.response_schema,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    timeout_seconds=request.timeout_seconds,
                    max_retries=request.max_retries,
                    fallback_model=None,
                    fallback_provider=None,
                )
                logger.warning(
                    f"Primary model {request.provider.value}/{model_name} failed ({last_exception}). "
                    f"Failing over to fallback {fb_provider.value}/{fb_model}..."
                )
                return await self.complete(fallback_req)
            raise last_exception
        raise LLMError(provider=request.provider.value, model=model_name, message="Unexpected retry loop termination")
