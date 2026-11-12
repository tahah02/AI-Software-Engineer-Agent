import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.domain.enums import LLMProvider
from src.infrastructure.db.models import (
    Base,
    ProjectORM,
    AgentTaskORM,
    AgentExecutionORM,
    LLMInvocationORM,
    TokenUsageORM,
)
from src.infrastructure.llm.token_tracker import TokenTrackerService
from src.ports.llm_gateway import LLMResponse, TokenUsage


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create parent hierarchy: Project -> AgentTask -> AgentExecution
    project = ProjectORM(name="Test Project", target_framework="fastapi")
    session.add(project)
    session.flush()

    task = AgentTaskORM(
        project_id=project.id,
        agent_name="DOCUMENTATION_REVIEWER",
        task_type="SPECIFICATION",
    )
    session.add(task)
    session.flush()

    execution = AgentExecutionORM(
        agent_task_id=task.id,
        status="RUNNING",
    )
    session.add(execution)
    session.commit()

    yield session
    session.close()


def test_record_successful_invocation_with_usage(db_session):
    execution = db_session.query(AgentExecutionORM).first()
    service = TokenTrackerService(db_session)

    response = LLMResponse(
        provider=LLMProvider.GEMINI,
        model="gemini-3.8-flash",
        finish_reason="stop",
        content="Success content",
        usage=TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        ),
        latency_ms=250,
    )

    inv = service.record_invocation(
        agent_execution_id=execution.id,
        provider=LLMProvider.GEMINI,
        model_name="gemini-3.8-flash",
        latency_ms=250,
        success=True,
        response=response,
    )
    db_session.commit()

    assert inv.id is not None
    assert inv.success is True
    assert inv.latency_ms == 250
    assert inv.provider == "gemini"
    assert inv.model_name == "gemini-3.8-flash"
    assert inv.error_message is None

    # Check token usage record
    usage = db_session.query(TokenUsageORM).filter_by(llm_invocation_id=inv.id).first()
    assert usage is not None
    assert usage.prompt_tokens == 100
    assert usage.completion_tokens == 50
    assert usage.total_tokens == 150
    # Gemini pricing in config: 100 * 0.000125 / 1000 + 50 * 0.000375 / 1000 = 0.0000125 + 0.00001875 = 0.000031
    assert usage.estimated_cost_usd is not None
    assert usage.estimated_cost_usd > 0.0


def test_record_free_local_model_cost(db_session):
    execution = db_session.query(AgentExecutionORM).first()
    service = TokenTrackerService(db_session)

    response = LLMResponse(
        provider=LLMProvider.OLLAMA,
        model="qwen2.5-coder:7b",
        finish_reason="stop",
        content="Ollama output",
        usage=TokenUsage(
            prompt_tokens=500,
            completion_tokens=200,
            total_tokens=700,
        ),
        latency_ms=800,
    )

    inv = service.record_invocation(
        agent_execution_id=execution.id,
        provider=LLMProvider.OLLAMA,
        model_name="qwen2.5-coder:7b",
        latency_ms=800,
        success=True,
        response=response,
    )
    db_session.commit()

    usage = db_session.query(TokenUsageORM).filter_by(llm_invocation_id=inv.id).first()
    assert usage is not None
    assert usage.estimated_cost_usd == 0.0


def test_record_unknown_model_pricing_is_nullable(db_session):
    execution = db_session.query(AgentExecutionORM).first()
    service = TokenTrackerService(db_session)

    response = LLMResponse(
        provider=LLMProvider.OPENROUTER,
        model="unlisted-custom-model",
        finish_reason="stop",
        content="Custom model output",
        usage=TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        ),
        latency_ms=300,
    )

    inv = service.record_invocation(
        agent_execution_id=execution.id,
        provider=LLMProvider.OPENROUTER,
        model_name="unlisted-custom-model",
        latency_ms=300,
        success=True,
        response=response,
    )
    db_session.commit()

    usage = db_session.query(TokenUsageORM).filter_by(llm_invocation_id=inv.id).first()
    assert usage is not None
    assert usage.estimated_cost_usd is None


def test_record_failed_invocation_without_usage(db_session):
    execution = db_session.query(AgentExecutionORM).first()
    service = TokenTrackerService(db_session)

    inv = service.record_invocation(
        agent_execution_id=execution.id,
        provider=LLMProvider.GROQ,
        model_name="openai/gpt-oss-120b",
        latency_ms=120,
        success=False,
        error_message="Rate limit exceeded (429)",
    )
    db_session.commit()

    assert inv.id is not None
    assert inv.success is False
    assert inv.error_message == "Rate limit exceeded (429)"

    usage = db_session.query(TokenUsageORM).filter_by(llm_invocation_id=inv.id).first()
    assert usage is None
