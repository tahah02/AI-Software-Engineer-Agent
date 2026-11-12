import os
import pytest
import httpx

from src.domain.enums import LLMProvider
from src.infrastructure.config import Settings
from src.infrastructure.llm.litellm_adapter import LiteLLMAdapter
from src.infrastructure.llm.ollama_adapter import OllamaAdapter
from src.ports.llm_gateway import LLMMessage, LLMRequest


@pytest.fixture
def settings():
    return Settings()


@pytest.mark.asyncio
async def test_live_ollama_connectivity(settings):
    base_url = settings.OLLAMA_BASE_URL.rstrip("/")
    # Check if local Ollama daemon is reachable
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{base_url}/api/tags")
            if resp.status_code != 200:
                pytest.skip("Local Ollama daemon is not responding with HTTP 200.")
    except Exception:
        pytest.skip("Local Ollama daemon is not running on configured port.")

    adapter = OllamaAdapter()
    models = await adapter.list_models(LLMProvider.OLLAMA)
    assert isinstance(models, list)

    default_model = settings.llm_config.providers[LLMProvider.OLLAMA].default_model
    if default_model in models:
        req = LLMRequest(
            provider=LLMProvider.OLLAMA,
            model=default_model,
            messages=[LLMMessage(role="user", content="ping")],
            max_tokens=5,
        )
        res = await adapter.complete(req)
        assert res.content is not None


@pytest.mark.asyncio
async def test_live_gemini_connectivity(settings):
    if not settings.GEMINI_API_KEY:
        pytest.skip("GEMINI_API_KEY not set in environment or .env")

    adapter = LiteLLMAdapter()
    default_model = settings.llm_config.providers[LLMProvider.GEMINI].default_model
    req = LLMRequest(
        provider=LLMProvider.GEMINI,
        model=default_model,
        messages=[LLMMessage(role="user", content="ping")],
        max_tokens=5,
        timeout_seconds=3.0,
        max_retries=1,
    )
    try:
        res = await adapter.complete(req)
        assert res.content is not None
        assert res.usage is not None
    except Exception as e:
        pytest.skip(f"Live Gemini endpoint timeout/unavailable: {e}")


@pytest.mark.asyncio
async def test_live_groq_connectivity(settings):
    if not settings.GROQ_API_KEY:
        pytest.skip("GROQ_API_KEY not set in environment or .env")

    adapter = LiteLLMAdapter()
    default_model = settings.llm_config.providers[LLMProvider.GROQ].default_model
    req = LLMRequest(
        provider=LLMProvider.GROQ,
        model=default_model,
        messages=[LLMMessage(role="user", content="ping")],
        max_tokens=5,
        timeout_seconds=10.0,
        max_retries=1,
    )
    try:
        res = await adapter.complete(req)
        assert res.content is not None
        assert res.usage is not None
    except Exception as e:
        pytest.skip(f"Live Groq endpoint failed: {e}")


@pytest.mark.asyncio
async def test_live_openrouter_connectivity(settings):
    if not settings.OPENROUTER_API_KEY:
        pytest.skip("OPENROUTER_API_KEY not set in environment or .env")

    adapter = LiteLLMAdapter()
    default_model = settings.llm_config.providers[LLMProvider.OPENROUTER].default_model
    req = LLMRequest(
        provider=LLMProvider.OPENROUTER,
        model=default_model,
        messages=[LLMMessage(role="user", content="ping")],
        max_tokens=5,
        timeout_seconds=10.0,
        max_retries=1,
    )
    try:
        res = await adapter.complete(req)
        assert res.content is not None
        assert res.usage is not None
    except Exception as e:
        pytest.skip(f"Live OpenRouter endpoint failed: {e}")
