import pytest
from unittest.mock import AsyncMock, MagicMock
from src.application.agents.supervisor import SupervisorAgent, _detect_framework_heuristically
from src.ports.llm_gateway import LLMResponse, TokenUsage
from src.domain.enums import LLMProvider


def test_detect_framework_heuristically():
    assert _detect_framework_heuristically("build an api in C#") == "DOTNET_CSHARP"
    assert _detect_framework_heuristically("make an app with .NET") == "DOTNET_CSHARP"
    assert _detect_framework_heuristically("create frontend in Next.js") == "NEXTJS_REACT"
    assert _detect_framework_heuristically("build backend in node typescript") == "NODE_TYPESCRIPT"
    assert _detect_framework_heuristically("develop microservice in FastAPI") == "PYTHON_FASTAPI"
    assert _detect_framework_heuristically("build general tool") == "PYTHON_FASTAPI"


@pytest.mark.asyncio
async def test_supervisor_llm_start_specification():
    mock_litellm = MagicMock()
    mock_litellm.complete = AsyncMock(
        return_value=LLMResponse(
            provider=LLMProvider.GROQ,
            model="openai/gpt-oss-120b",
            content='{"thought": "User wants a C# app", "reply_to_user": "Starting C# spec", "action": "START_SPECIFICATION", "detected_framework": "DOTNET_CSHARP", "tasks": ["Setup .NET"]}',
            usage=TokenUsage(prompt_tokens=50, completion_tokens=30, total_tokens=80),
        )
    )

    mock_ollama = MagicMock()
    mock_ollama.complete = AsyncMock()

    agent = SupervisorAgent(litellm_adapter=mock_litellm, ollama_adapter=mock_ollama)
    decision = await agent.evaluate(user_message="I want you to build Student Management System in C#, can you make that for me?")

    assert decision.action == "START_SPECIFICATION"
    assert decision.detected_framework == "DOTNET_CSHARP"
    assert "Starting C# spec" in decision.reply_to_user


@pytest.mark.asyncio
async def test_supervisor_fallback_when_llm_fails():
    mock_litellm = MagicMock()
    mock_litellm.complete = AsyncMock(side_effect=Exception("API Error"))

    mock_ollama = MagicMock()
    mock_ollama.complete = AsyncMock(side_effect=Exception("Ollama Error"))

    agent = SupervisorAgent(ollama_adapter=mock_ollama, litellm_adapter=mock_litellm)
    
    # 1. Build in C#
    dec1 = await agent.evaluate(user_message="I want you to build Student Management System in C#")
    assert dec1.action == "START_SPECIFICATION"
    assert dec1.detected_framework == "DOTNET_CSHARP"

    # 2. Greeting
    dec2 = await agent.evaluate(user_message="Hello, how does this work?")
    assert dec2.action == "CONVERSE"

    # 3. Approval
    dec3 = await agent.evaluate(user_message="Looks good, please proceed with coding", has_pending_approval=True)
    assert dec3.action == "APPROVE_AND_CODE"
