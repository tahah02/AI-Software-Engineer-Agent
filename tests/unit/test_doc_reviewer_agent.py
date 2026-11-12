import json
import shutil
import tempfile
import uuid
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.application.agents.doc_reviewer import DocumentationReviewerAgent
from src.domain.enums import AgentType, LLMProvider
from src.infrastructure.db.models import (
    Base,
    ProjectORM,
    ProjectAgentConfigORM,
    ProjectFileORM,
    AgentTaskORM,
    AgentExecutionORM,
)
from src.infrastructure.llm.provider_resolver import LLMProviderResolver
from src.infrastructure.llm.token_tracker import TokenTrackerService
from src.ports.agent import AgentContext
from src.ports.llm_gateway import ILLMGateway, LLMRequest, LLMResponse, TokenUsage


class FakeLLMAdapter(ILLMGateway):
    async def complete(self, request: LLMRequest) -> LLMResponse:
        data = {
            "technical_design": "# Technical Design Document\n\n## Endpoints\n- POST /api/v1/auth/login",
            "test_spec": "# XUnit Test Specifications\n\n## Test Case 1: Valid Login Returns 200",
        }
        return LLMResponse(
            provider=request.provider,
            model=request.model or "fake-model",
            finish_reason="stop",
            content=json.dumps(data),
            usage=TokenUsage(
                prompt_tokens=200,
                completion_tokens=150,
                total_tokens=350,
            ),
            latency_ms=100,
        )

    async def list_models(self, provider: LLMProvider) -> list[str]:
        return ["fake-model"]


@pytest.fixture
def test_setup():
    tmp_workspace = tempfile.mkdtemp(prefix="aaise_agent1_test_")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    project = ProjectORM(name="Doc Review Project", target_framework="fastapi")
    session.add(project)
    session.flush()

    config = ProjectAgentConfigORM(
        project_id=project.id,
        agent_type=AgentType.DOC_REVIEWER.value,
        is_enabled=True,
        provider="groq",
        model_name="openai/gpt-oss-120b",
    )
    session.add(config)

    task = AgentTaskORM(
        project_id=project.id,
        agent_name="Agent 1: Documentation Reviewer",
        task_type="SPECIFICATION",
    )
    session.add(task)
    session.flush()

    execution = AgentExecutionORM(agent_task_id=task.id)
    session.add(execution)
    session.commit()

    yield session, project, task, execution, tmp_workspace

    session.close()
    shutil.rmtree(tmp_workspace, ignore_errors=True)


@pytest.mark.asyncio
async def test_doc_reviewer_generates_tdd_and_xunit_specs(test_setup):
    session, project, task, execution, tmp_workspace = test_setup

    fake_adapter = FakeLLMAdapter()
    resolver = LLMProviderResolver(litellm_adapter=fake_adapter)

    tracker = TokenTrackerService(db=session)
    agent = DocumentationReviewerAgent(resolver=resolver, tracker=tracker, db=session)

    context = AgentContext(
        project_id=project.id,
        task_id=task.id,
        agent_execution_id=execution.id,
        workspace_path=tmp_workspace,
    )

    requirements_input = """
    We need an Authentication API:
    - POST /api/v1/auth/login (email, password) -> returns token
    - POST /api/v1/auth/register (name, email, password) -> returns user_id
    """

    result = await agent.execute(context, requirements_input)

    assert result.success is True
    assert "docs/TECHNICAL_DESIGN.md" in result.artifacts_created
    assert "docs/XUNIT_TEST_SPEC.md" in result.artifacts_created

    # Verify physical file creation on disk
    tdd_file = Path(tmp_workspace) / "docs/TECHNICAL_DESIGN.md"
    spec_file = Path(tmp_workspace) / "docs/XUNIT_TEST_SPEC.md"
    assert tdd_file.exists()
    assert spec_file.exists()
    assert "POST /api/v1/auth/login" in tdd_file.read_text(encoding="utf-8")
    assert "XUnit Test Specifications" in spec_file.read_text(encoding="utf-8")

    # Verify database persistence in project_files
    files = session.query(ProjectFileORM).filter_by(project_id=project.id).all()
    assert len(files) == 2
    types = {f.file_type for f in files}
    assert "TECHNICAL_DESIGN" in types
    assert "TEST_SPECIFICATION" in types


class EchoIncrementalLLMAdapter(ILLMGateway):
    async def complete(self, request: LLMRequest) -> LLMResponse:
        last_msg = request.messages[-1]
        content = last_msg.content if hasattr(last_msg, "content") else last_msg["content"]
        if "Principal Lead QA Architect" in content or "docs/XUNIT_TEST_SPEC.md" in content:
            appended_test = (
                "# Test Specification\n\n"
                "## UT-01: Backend student creation\n\n"
                "## Section 15: Client Interface Contract & Component Tests\n"
                "## UI-01: Form validation on submit"
            )
            return LLMResponse(
                provider=request.provider,
                model="echo-model",
                finish_reason="stop",
                content=appended_test,
                usage=TokenUsage(prompt_tokens=100, completion_tokens=100, total_tokens=200),
                latency_ms=50,
            )
        else:
            appended_tdd = (
                "# Technical Design Document\n\n"
                "## Section 1: Backend Architecture (ASP.NET Core)\n"
                "- POST /api/students\n\n"
                "## Section 9: Client Interface Specification (TYPESCRIPT_NEXTJS)\n"
                "- Target Directory: frontend/\n"
                "- Stack: Next.js 15 App Router, React 19, Tailwind CSS\n"
                "- Component: StudentRegistrationForm maps to POST /api/students"
            )
            return LLMResponse(
                provider=request.provider,
                model="echo-model",
                finish_reason="stop",
                content=appended_tdd,
                usage=TokenUsage(prompt_tokens=100, completion_tokens=100, total_tokens=200),
                latency_ms=50,
            )

    async def list_models(self, provider: LLMProvider) -> list[str]:
        return ["echo-model"]


@pytest.mark.asyncio
async def test_doc_reviewer_appends_incremental_frontend_specification(test_setup):
    session, project, task, execution, tmp_workspace = test_setup

    project.target_framework = "DOTNET_CSHARP"
    session.commit()

    # Pre-create backend TDD and Test Spec
    docs_dir = Path(tmp_workspace) / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    existing_tdd = "# Technical Design Document\n\n## Section 1: Backend Architecture\n- POST /api/students"
    existing_spec = "# Test Specification\n\n## UT-01: Backend student creation"
    (docs_dir / "TECHNICAL_DESIGN.md").write_text(existing_tdd, encoding="utf-8")
    (docs_dir / "XUNIT_TEST_SPEC.md").write_text(existing_spec, encoding="utf-8")

    fake_adapter = EchoIncrementalLLMAdapter()
    resolver = LLMProviderResolver(litellm_adapter=fake_adapter)
    tracker = TokenTrackerService(db=session)
    agent = DocumentationReviewerAgent(resolver=resolver, tracker=tracker, db=session)

    context = AgentContext(
        project_id=project.id,
        task_id=task.id,
        agent_execution_id=execution.id,
        workspace_path=tmp_workspace,
        target_framework="DOTNET_CSHARP",
        additional_metadata={
            "is_incremental": True,
            "target_subsystem": "frontend",
            "subsystem_framework": "TYPESCRIPT_NEXTJS",
        },
    )

    result = await agent.execute(context, "Can you make a frontend of this on next.js?")

    assert result.success is True
    assert "TECHNICAL_DESIGN.md" in result.artifacts_created[0]

    tdd_content = (docs_dir / "TECHNICAL_DESIGN.md").read_text(encoding="utf-8")
    assert "Section 1: Backend Architecture" in tdd_content
    assert "POST /api/students" in tdd_content
    assert "Section 9: Client Interface Specification (TYPESCRIPT_NEXTJS)" in tdd_content
    assert "Target Directory: frontend/" in tdd_content

    test_content = (docs_dir / "XUNIT_TEST_SPEC.md").read_text(encoding="utf-8")
    assert "UT-01: Backend student creation" in test_content
    assert "Section 15: Client Interface Contract & Component Tests" in test_content

    # Target framework must NOT be overwritten for the backend project
    refreshed_proj = session.query(ProjectORM).filter_by(id=project.id).first()
    assert refreshed_proj.target_framework == "DOTNET_CSHARP"
