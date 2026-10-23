import asyncio
import json
import time
from typing import Any

import httpx

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


class OllamaAdapter(ILLMGateway):
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")

    def get_default_model(self) -> str:
        provider_cfg = settings.llm_config.providers.get(LLMProvider.OLLAMA)
        if provider_cfg:
            return provider_cfg.default_model
        return "qwen2.5-coder:7b"

    async def list_models(self, provider: LLMProvider = LLMProvider.OLLAMA) -> list[str]:
        if provider != LLMProvider.OLLAMA:
            raise ValueError(f"OllamaAdapter does not support provider '{provider}'")

        url = f"{self.base_url}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                    return models
                raise LLMError(
                    provider=LLMProvider.OLLAMA.value,
                    model="system",
                    message=f"Failed to list models (HTTP {response.status_code}): {response.text}",
                )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                provider=LLMProvider.OLLAMA.value,
                model="system",
                message="Timed out connecting to Ollama server while listing models",
            ) from exc
        except httpx.RequestError as exc:
            raise LLMError(
                provider=LLMProvider.OLLAMA.value,
                model="system",
                message=f"Network error connecting to Ollama: {exc}",
            ) from exc

    async def complete(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self.get_default_model()
        url = f"{self.base_url}/api/chat"

        messages_payload = []
        for msg in request.messages:
            m_dict: dict[str, Any] = {"role": msg.role, "content": msg.content}
            messages_payload.append(m_dict)

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages_payload,
            "stream": False,
            "options": {
                "temperature": request.temperature,
            },
        }

        if request.max_tokens is not None:
            payload["options"]["num_predict"] = request.max_tokens

        if request.response_schema is not None:
            payload["format"] = "json"

        timeout = httpx.Timeout(request.timeout_seconds, connect=10.0)
        attempts = 0
        max_attempts = max(1, request.max_retries + 1)
        last_exception: Exception | None = None

        start_time = time.perf_counter()

        while attempts < max_attempts:
            attempts += 1
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(url, json=payload)
                    latency_ms = int((time.perf_counter() - start_time) * 1000)

                    if resp.status_code == 200:
                        data = resp.json()
                        msg_data = data.get("message", {})
                        content = msg_data.get("content")

                        prompt_tokens = data.get("prompt_eval_count", 0)
                        completion_tokens = data.get("eval_count", 0)
                        total_tokens = prompt_tokens + completion_tokens

                        tool_calls = None
                        finish_reason = "stop"

                        return LLMResponse(
                            provider=LLMProvider.OLLAMA,
                            model=model,
                            content=content,
                            tool_calls=tool_calls,
                            usage=TokenUsage(
                                prompt_tokens=prompt_tokens,
                                completion_tokens=completion_tokens,
                                total_tokens=total_tokens,
                                estimated_cost_usd=0.0,
                            ),
                            latency_ms=latency_ms,
                            finish_reason=finish_reason,
                        )

                    if resp.status_code == 404:
                        raise LLMModelNotFoundError(
                            provider=LLMProvider.OLLAMA.value,
                            model=model,
                            message=f"Model '{model}' not found on Ollama server: {resp.text}",
                        )

                    if resp.status_code == 429:
                        raise LLMRateLimitError(
                            provider=LLMProvider.OLLAMA.value,
                            model=model,
                            message=f"Rate limited by Ollama server: {resp.text}",
                        )

                    if resp.status_code in (401, 403):
                        raise LLMAuthError(
                            provider=LLMProvider.OLLAMA.value,
                            model=model,
                            message=f"Authentication error from Ollama server: {resp.text}",
                        )

                    raise LLMError(
                        provider=LLMProvider.OLLAMA.value,
                        model=model,
                        message=f"Ollama returned HTTP {resp.status_code}: {resp.text}",
                    )

            except httpx.TimeoutException as exc:
                last_exception = LLMTimeoutError(
                    provider=LLMProvider.OLLAMA.value,
                    model=model,
                    message=f"Request timed out after {request.timeout_seconds}s (attempt {attempts}/{max_attempts})",
                )
                if attempts < max_attempts:
                    await asyncio.sleep(0.5 * attempts)
                    continue
                raise last_exception from exc

            except (LLMModelNotFoundError, LLMAuthError):
                raise

            except Exception as exc:
                if isinstance(exc, LLMError):
                    last_exception = exc
                else:
                    last_exception = LLMError(
                        provider=LLMProvider.OLLAMA.value,
                        model=model,
                        message=f"Error during Ollama call: {exc}",
                    )
                if attempts < max_attempts:
                    await asyncio.sleep(0.5 * attempts)
                    continue
                raise last_exception from exc

        if last_exception:
            raise last_exception
        raise LLMError(provider=LLMProvider.OLLAMA.value, model=model, message="Unexpected retry loop termination")
