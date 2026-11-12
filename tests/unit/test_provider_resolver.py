import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.domain.enums import AgentType, LLMProvider
from src.domain.exceptions import EntityNotFoundError, ValidationError
from src.infrastructure.config import settings
from src.infrastructure.db.models import Base, ProjectAgentConfigORM, ProjectORM
from src.infrastructure.llm.litellm_adapter import LiteLLMAdapter
from src.infrastructure.llm.ollama_adapter import OllamaAdapter
from src.infrastructure.llm.provider_resolver import LLMProviderResolver
from src.ports.llm_gateway import LLMMessage, LLMResponse, TokenUsage


@pytest.fixture
def in_memory_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mock_ollama():
    adapter = MagicMock(spec=OllamaAdapter)
    adapter.complete = AsyncMock(
        return_value=LLMResponse(
            provider=LLMProvider.OLLAMA,
            model="qwen2.5-coder:7b",
            content="Ollama code",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            latency_ms=150,
            finish_reason="stop",
        )
    )
    return adapter


@pytest.fixture
def mock_litellm():
    adapter = MagicMock(spec=LiteLLMAdapter)
    adapter.complete = AsyncMock(
        return_value=LLMResponse(
            provider=LLMProvider.GEMINI,
            model="gemini-3.8-flash",
            content="LiteLLM text",
            usage=TokenUsage(prompt_tokens=15, completion_tokens=25, total_tokens=40),
            latency_ms=220,
            finish_reason="stop",
        )
    )
    return adapter


def test_resolve_agent_config_with_explicit_model_and_ollama_adapter(
    in_memory_session: Session, mock_ollama, mock_litellm
):
    project_id = uuid.uuid4()
    in_memory_session.add(ProjectORM(id=project_id, name="Test P1", target_framework="python"))
    in_memory_session.add(
        ProjectAgentConfigORM(
            project_id=project_id,
            agent_type=AgentType.MAIN_CODING.value,
            provider="ollama",
            model_name="qwen2.5-coder:7b",
            is_enabled=True,
        )
    )
    in_memory_session.commit()

    resolver = LLMProviderResolver(ollama_adapter=mock_ollama, litellm_adapter=mock_litellm)
    resolved = resolver.resolve_agent_config(in_memory_session, project_id, AgentType.MAIN_CODING)

    assert resolved.provider == LLMProvider.OLLAMA
    assert resolved.model == "qwen2.5-coder:7b"
    assert resolved.adapter == mock_ollama
    assert resolved.custom_system_prompt is None


def test_resolve_agent_config_falls_back_to_json_default_when_model_empty(
    in_memory_session: Session, mock_ollama, mock_litellm
):
    project_id = uuid.uuid4()
    in_memory_session.add(ProjectORM(id=project_id, name="Test P2", target_framework="python"))
    in_memory_session.add(
        ProjectAgentConfigORM(
            project_id=project_id,
            agent_type=AgentType.DOC_REVIEWER.value,
            provider="gemini",
            model_name="",  # Empty string triggers fallback to JSON config default
            is_enabled=True,
        )
    )
    in_memory_session.commit()

    resolver = LLMProviderResolver(ollama_adapter=mock_ollama, litellm_adapter=mock_litellm)
    resolved = resolver.resolve_agent_config(in_memory_session, project_id, AgentType.DOC_REVIEWER)

    expected_default = settings.llm_config.providers[LLMProvider.GEMINI].default_model
    assert resolved.provider == LLMProvider.GEMINI
    assert resolved.model == expected_default
    assert resolved.adapter == mock_litellm


def test_resolve_agent_config_routes_all_cloud_providers_to_litellm(
    in_memory_session: Session, mock_ollama, mock_litellm
):
    project_id = uuid.uuid4()
    in_memory_session.add(ProjectORM(id=project_id, name="Test Cloud", target_framework="dotnet"))

    providers_to_test = [
        (AgentType.MOCK_DEVELOPER, "groq", "openai/gpt-oss-120b"),
        (AgentType.QA_ENGINEER, "openrouter", "openai/gpt-oss-120b"),
        (AgentType.SECURITY_REVIEWER, "gemini", "gemini-3.5-flash-lite"),
    ]
    for agent_enum, prov, mdl in providers_to_test:
        in_memory_session.add(
            ProjectAgentConfigORM(
                project_id=project_id,
                agent_type=agent_enum.value,
                provider=prov,
                model_name=mdl,
                is_enabled=True,
            )
        )
    in_memory_session.commit()

    resolver = LLMProviderResolver(ollama_adapter=mock_ollama, litellm_adapter=mock_litellm)
    for agent_enum, prov, mdl in providers_to_test:
        resolved = resolver.resolve_agent_config(in_memory_session, project_id, agent_enum)
        assert resolved.provider.value == prov
        assert resolved.model == mdl
        assert resolved.adapter == mock_litellm


def test_resolve_missing_agent_config_fails_with_entity_not_found(
    in_memory_session: Session, mock_ollama, mock_litellm
):
    project_id = uuid.uuid4()
    in_memory_session.add(ProjectORM(id=project_id, name="Empty Project", target_framework="nodejs"))
    in_memory_session.commit()

    resolver = LLMProviderResolver(ollama_adapter=mock_ollama, litellm_adapter=mock_litellm)
    with pytest.raises(EntityNotFoundError) as exc_info:
        resolver.resolve_agent_config(in_memory_session, project_id, AgentType.MAIN_CODING)
    assert "ProjectAgentConfig" in str(exc_info.value)


def test_resolve_disabled_agent_rejected_with_validation_error(
    in_memory_session: Session, mock_ollama, mock_litellm
):
    project_id = uuid.uuid4()
    in_memory_session.add(ProjectORM(id=project_id, name="Disabled Agent Project", target_framework="python"))
    in_memory_session.add(
        ProjectAgentConfigORM(
            project_id=project_id,
            agent_type=AgentType.QA_ENGINEER.value,
            provider="groq",
            model_name="qwen/qwen3.8-27b",
            is_enabled=False,  # Explicitly disabled
        )
    )
    in_memory_session.commit()

    resolver = LLMProviderResolver(ollama_adapter=mock_ollama, litellm_adapter=mock_litellm)
    with pytest.raises(ValidationError) as exc_info:
        resolver.resolve_agent_config(in_memory_session, project_id, AgentType.QA_ENGINEER)
    assert "is disabled for project" in str(exc_info.value)
    assert "Execution rejected" in str(exc_info.value)


def test_resolve_invalid_provider_fails_with_validation_error(
    in_memory_session: Session, mock_ollama, mock_litellm
):
    project_id = uuid.uuid4()
    in_memory_session.add(ProjectORM(id=project_id, name="Invalid Provider Project", target_framework="python"))
    in_memory_session.add(
        ProjectAgentConfigORM(
            project_id=project_id,
            agent_type=AgentType.MAIN_CODING.value,
            provider="unsupported-provider-xyz",
            model_name="some-model",
            is_enabled=True,
        )
    )
    in_memory_session.commit()

    resolver = LLMProviderResolver(ollama_adapter=mock_ollama, litellm_adapter=mock_litellm)
    with pytest.raises(ValidationError) as exc_info:
        resolver.resolve_agent_config(in_memory_session, project_id, AgentType.MAIN_CODING)
    assert "Invalid provider 'unsupported-provider-xyz'" in str(exc_info.value)


def test_build_agent_request_handles_custom_prompt_safely(
    in_memory_session: Session, mock_ollama, mock_litellm
):
    project_id = uuid.uuid4()
    in_memory_session.add(ProjectORM(id=project_id, name="Prompt Project", target_framework="python"))
    in_memory_session.add(
        ProjectAgentConfigORM(
            project_id=project_id,
            agent_type=AgentType.MAIN_CODING.value,
            provider="ollama",
            model_name="qwen2.5-coder:7b",
            custom_system_prompt="Always use async def for endpoints.",
            is_enabled=True,
        )
    )
    in_memory_session.commit()

    resolver = LLMProviderResolver(ollama_adapter=mock_ollama, litellm_adapter=mock_litellm)
    resolved = resolver.resolve_agent_config(in_memory_session, project_id, AgentType.MAIN_CODING)

    base_prompt = "You are Agent 3: Main Coding Agent. Never touch mock-vendor-api repository."
    req = resolver.build_agent_request(
        resolved,
        messages=[LLMMessage(role="user", content="Build router")],
        base_system_prompt=base_prompt,
    )

    assert len(req.messages) == 2
    system_msg = req.messages[0]
    assert system_msg.role == "system"
    # Mandatory base instructions must appear first
    assert system_msg.content.startswith(base_prompt)
    # Custom prompt is clearly demarcated as supplementary
    assert "[Project Custom Instructions (Supplementary - Mandatory Base Instructions Take Precedence)]:" in system_msg.content
    assert "Always use async def for endpoints." in system_msg.content


@pytest.mark.asyncio
async def test_execute_agent_successful_dispatch_and_no_unauthorized_call_on_failure(
    in_memory_session: Session, mock_ollama, mock_litellm
):
    project_id = uuid.uuid4()
    in_memory_session.add(ProjectORM(id=project_id, name="Exec Project", target_framework="python"))
    in_memory_session.add(
        ProjectAgentConfigORM(
            project_id=project_id,
            agent_type=AgentType.MAIN_CODING.value,
            provider="ollama",
            model_name="qwen2.5-coder:7b",
            is_enabled=True,
        )
    )
    in_memory_session.add(
        ProjectAgentConfigORM(
            project_id=project_id,
            agent_type=AgentType.MOCK_DEVELOPER.value,
            provider="groq",
            model_name="openai/gpt-oss-120b",
            is_enabled=False,  # Disabled
        )
    )
    in_memory_session.commit()

    resolver = LLMProviderResolver(ollama_adapter=mock_ollama, litellm_adapter=mock_litellm)

    # 1. Enabled agent executes successfully
    res = await resolver.execute_agent(
        in_memory_session,
        project_id,
        AgentType.MAIN_CODING,
        messages=[LLMMessage(role="user", content="Write code")],
    )
    assert res.content == "Ollama code"
    mock_ollama.complete.assert_called_once()
    mock_litellm.complete.assert_not_called()

    # 2. Disabled agent execution fails validation and NEVER calls adapter
    mock_litellm.complete.reset_mock()
    with pytest.raises(ValidationError):
        await resolver.execute_agent(
            in_memory_session,
            project_id,
            AgentType.MOCK_DEVELOPER,
            messages=[LLMMessage(role="user", content="Build mock")],
        )
    mock_litellm.complete.assert_not_called()
