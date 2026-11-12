import json
import shutil
import tempfile
import uuid
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.application.agents.mock_developer import MockVendorDeveloperAgent
from src.domain.enums import AgentType, LLMProvider, RepositoryType
from src.infrastructure.db.models import (
    Base,
    ProjectORM,
    ProjectAgentConfigORM,
    AgentTaskORM,
    AgentExecutionORM,
)
from src.infrastructure.git.git_service import GitService
from src.infrastructure.llm.provider_resolver import LLMProviderResolver
from src.infrastructure.llm.token_tracker import TokenTrackerService
from src.ports.agent import AgentContext
from src.ports.llm_gateway import ILLMGateway, LLMRequest, LLMResponse, TokenUsage


class FakeMockLLMAdapter(ILLMGateway):
    async def complete(self, request: LLMRequest) -> LLMResponse:
        data = {
            "files": {
                "main.py": "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/vendor/ping')\ndef ping(): return {'status': 'mock_ok'}\n",
                "requirements.txt": "fastapi==0.115.0\n",
            }
        }
        return LLMResponse(
            provider=request.provider,
            model=request.model or "fake-model",
            finish_reason="stop",
            content=json.dumps(data),
            usage=TokenUsage(
                prompt_tokens=150,
                completion_tokens=80,
                total_tokens=230,
            ),
            latency_ms=120,
        )

    async def list_models(self, provider: LLMProvider) -> list[str]:
        return ["fake-model"]


@pytest.fixture
def mock_agent_setup():
    tmp_workspace = tempfile.mkdtemp(prefix="aaise_agent2_test_")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    project = ProjectORM(name="Mock Dev Test Project", target_framework="fastapi")
    session.add(project)
    session.flush()

    config = ProjectAgentConfigORM(
        project_id=project.id,
        agent_type=AgentType.MOCK_DEVELOPER.value,
        is_enabled=True,
        provider="groq",
        model_name="openai/gpt-oss-120b",
    )
    session.add(config)

    task = AgentTaskORM(
        project_id=project.id,
        agent_name="Agent 2: Mock Vendor API Developer",
        task_type="MOCK_DEVELOPMENT",
    )
    session.add(task)
    session.flush()

    execution = AgentExecutionORM(agent_task_id=task.id)
    session.add(execution)
    session.commit()

    git_service = GitService(db=session, base_workspace_dir=tmp_workspace)
    # Initialize mock repo beforehand
    git_service.initialize_repository(project.id, RepositoryType.MOCK_VENDOR_API)

    yield session, project, task, execution, tmp_workspace, git_service

    session.close()
    shutil.rmtree(tmp_workspace, ignore_errors=True)


@pytest.mark.asyncio
async def test_mock_developer_generates_code_and_commits(mock_agent_setup):
    session, project, task, execution, tmp_workspace, git_service = mock_agent_setup

    resolver = LLMProviderResolver(litellm_adapter=FakeMockLLMAdapter())
    tracker = TokenTrackerService(db=session)

    agent = MockVendorDeveloperAgent(
        resolver=resolver,
        git_service=git_service,
        tracker=tracker,
        db=session,
    )

    context = AgentContext(
        project_id=project.id,
        task_id=task.id,
        agent_execution_id=execution.id,
        workspace_path=tmp_workspace,
    )

    tdd_input = """
    Third Party Dependency:
    - GET /vendor/ping (External Core Banking ping)
    """

    result = await agent.execute(context, tdd_input)

    assert result.success is True
    assert "main.py" in result.artifacts_created
    assert "requirements.txt" in result.artifacts_created

    # Verify physical file existence in mock repo
    mock_repo_path = Path(git_service.get_repository_path(project.id, RepositoryType.MOCK_VENDOR_API))
    main_file = mock_repo_path / "main.py"
    req_file = mock_repo_path / "requirements.txt"
    assert main_file.exists()
    assert req_file.exists()
    assert "mock_ok" in main_file.read_text(encoding="utf-8")

    # Verify files committed to mock repo branch
    assert result.metadata["commit_hash"] is not None
    assert "mock-apis" in result.metadata["branch"]
    assert result.metadata["repo"] == "mock-vendor-api"


@pytest.mark.asyncio
async def test_mock_developer_reads_tdd_from_workspace_when_input_empty(mock_agent_setup):
    session, project, task, execution, tmp_workspace, git_service = mock_agent_setup

    resolver = LLMProviderResolver(litellm_adapter=FakeMockLLMAdapter())
    tracker = TokenTrackerService(db=session)

    agent = MockVendorDeveloperAgent(
        resolver=resolver,
        git_service=git_service,
        tracker=tracker,
        db=session,
    )

    context = AgentContext(
        project_id=project.id,
        task_id=task.id,
        agent_execution_id=execution.id,
        workspace_path=tmp_workspace,
    )

    # Write a real TDD in the workspace
    docs_dir = Path(tmp_workspace) / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    tdd_file = docs_dir / "TECHNICAL_DESIGN.md"
    tdd_file.write_text("# Technical Design\nExternal Mock Endpoint: GET /api/mock/value -> {'value': 1}", encoding="utf-8")

    # Call with empty input text
    result = await agent.execute(context, "")

    assert result.success is True
    assert "main.py" in result.artifacts_created
    mock_repo_path = Path(git_service.get_repository_path(project.id, RepositoryType.MOCK_VENDOR_API))
    assert (mock_repo_path / "main.py").exists()


@pytest.mark.asyncio
async def test_mock_developer_skipped_when_tdd_states_not_applicable(mock_agent_setup):
    session, project, task, execution, tmp_workspace, git_service = mock_agent_setup

    resolver = LLMProviderResolver(litellm_adapter=FakeMockLLMAdapter())
    agent = MockVendorDeveloperAgent(
        resolver=resolver,
        git_service=git_service,
        db=session,
    )

    context = AgentContext(
        project_id=project.id,
        task_id=task.id,
        agent_execution_id=execution.id,
        workspace_path=tmp_workspace,
    )

    skipped_tdd = (
        "# Technical Design Document\n"
        "* **Workflow Confirmation:** Agent 2 (Mock API Developer) is **SKIPPED / NOT APPLICABLE** for this implementation.\n"
        "No out-of-scope CRUD, frontend, or vendor APIs.\n"
    )

    result = await agent.execute(context, skipped_tdd)

    assert result.success is True
    assert result.metadata.get("skipped") is True
    assert len(result.artifacts_created) == 0
    assert "skipped" in result.summary.lower()
