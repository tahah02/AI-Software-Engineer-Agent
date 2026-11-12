import json
import shutil
import tempfile
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.application.agents.main_coder import MainCodingAgent, get_coder_prompt_for_framework
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


class FakeCoderLLMAdapter(ILLMGateway):
    async def complete(self, request: LLMRequest) -> LLMResponse:
        data = {
            "files": {
                "channel-app.csproj": "<Project Sdk=\"Microsoft.NET.Sdk.Web\"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>",
                "Program.cs": "var builder = WebApplication.CreateBuilder(args); var app = builder.Build(); app.Run();",
                "Controllers/MockVendorController.cs": "// stray mock controller that must be automatically stripped",
            }
        }
        return LLMResponse(
            provider=request.provider,
            model=request.model or "fake-coder-model",
            finish_reason="stop",
            content=json.dumps(data),
            usage=TokenUsage(
                prompt_tokens=200,
                completion_tokens=100,
                total_tokens=300,
            ),
            latency_ms=150,
        )

    async def list_models(self, provider: LLMProvider) -> list[str]:
        return ["fake-coder-model"]


@pytest.fixture
def coder_agent_setup():
    tmp_workspace = tempfile.mkdtemp(prefix="aaise_agent3_test_")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    project = ProjectORM(name="Coder Dev Test Project", target_framework="csharp")
    session.add(project)
    session.flush()

    config = ProjectAgentConfigORM(
        project_id=project.id,
        agent_type=AgentType.MAIN_CODING.value,
        is_enabled=True,
        provider="gemini",
        model_name="gemini-3-flash-preview",
    )
    session.add(config)

    task = AgentTaskORM(
        project_id=project.id,
        agent_name="Agent 3: Main Coding Agent",
        task_type="DEVELOPMENT",
    )
    session.add(task)
    session.flush()

    execution = AgentExecutionORM(agent_task_id=task.id)
    session.add(execution)
    session.commit()

    git_service = GitService(db=session, base_workspace_dir=tmp_workspace)
    git_service.initialize_repository(project.id, RepositoryType.CHANNEL_APP)

    yield session, project, task, execution, tmp_workspace, git_service

    session.close()
    shutil.rmtree(tmp_workspace, ignore_errors=True)


def test_coder_prompt_enforces_clean_architecture_and_no_mock_controllers():
    prompt = get_coder_prompt_for_framework("csharp")
    assert "NEVER create internal mock controllers" in prompt
    assert "MockVendorController" in prompt
    assert "MockVendor:BaseUrl" in prompt
    assert "504 Gateway Timeout" in prompt
    assert "502 Bad Gateway" in prompt
    assert "503 Service Unavailable" in prompt
    assert "checked" in prompt
    assert "channel-app.Tests/channel-app.Tests.csproj" in prompt
    assert "channel-app.Tests/UnitTests.cs" in prompt
    assert "channel-app.Tests/IntegrationTests.cs" in prompt


@pytest.mark.asyncio
async def test_main_coder_ingests_test_spec_from_workspace(coder_agent_setup):
    session, project, task, execution, tmp_workspace, git_service = coder_agent_setup

    captured_prompt = ""

    class CapturingLLMAdapter(ILLMGateway):
        async def complete(self, request: LLMRequest) -> LLMResponse:
            nonlocal captured_prompt
            if not captured_prompt:
                captured_prompt = request.messages[-1].content
            data = {"files": {"channel-app.csproj": "<Project Sdk=\"Microsoft.NET.Sdk.Web\"><PropertyGroup><TargetFramework>net8.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings></PropertyGroup></Project>", "Program.cs": "using Microsoft.AspNetCore.Builder;\nvar b = WebApplication.CreateBuilder(args); var a = b.Build(); a.Run();"}}
            return LLMResponse(
                provider=request.provider,
                model=request.model or "fake",
                finish_reason="stop",
                content=json.dumps(data),
                usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
                latency_ms=100,
            )

    resolver = LLMProviderResolver(litellm_adapter=CapturingLLMAdapter())
    agent = MainCodingAgent(resolver=resolver, git_service=git_service, db=session)

    # Write test spec in docs/
    docs_dir = Path(tmp_workspace) / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    test_spec_file = docs_dir / "XUNIT_TEST_SPEC.md"
    test_spec_file.write_text("# Test Spec\n### UT-01: Create student validation test", encoding="utf-8")

    context = AgentContext(
        project_id=project.id,
        task_id=task.id,
        agent_execution_id=execution.id,
        workspace_path=tmp_workspace,
        target_framework="csharp",
    )

    await agent.execute(context, "Implement application and tests")

    assert "Authoritative Test Specifications" in captured_prompt
    assert "UT-01: Create student validation test" in captured_prompt


@pytest.mark.asyncio
async def test_main_coder_removes_forbidden_mock_controllers(coder_agent_setup):
    session, project, task, execution, tmp_workspace, git_service = coder_agent_setup

    resolver = LLMProviderResolver(litellm_adapter=FakeCoderLLMAdapter())
    tracker = TokenTrackerService(db=session)

    agent = MainCodingAgent(
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
        target_framework="csharp",
    )

    result = await agent.execute(context, "Implement channel application")

    channel_repo_path = Path(git_service.get_repository_path(project.id, RepositoryType.CHANNEL_APP))
    forbidden_controller = channel_repo_path / "Controllers" / "MockVendorController.cs"

    # Must be stripped
    assert not forbidden_controller.exists()
    assert "Controllers/MockVendorController.cs" not in result.artifacts_created
    assert result.metadata["commit_hash"] is not None


class FakeFrontendLLMAdapter(ILLMGateway):
    async def complete(self, request: LLMRequest) -> LLMResponse:
        data = {
            "files": {
                "package.json": "{\"name\": \"student-portal\", \"dependencies\": {\"next\": \"15.0.0\"}}",
                "tsconfig.json": "{\"compilerOptions\": {\"paths\": {\"@/*\": [\"./*\"]}}}",
                "app/page.tsx": "'use client';\nexport default function Page() { return <div>Student Portal</div>; }",
            }
        }
        return LLMResponse(
            provider=request.provider,
            model="frontend-model",
            finish_reason="stop",
            content=json.dumps(data),
            usage=TokenUsage(prompt_tokens=100, completion_tokens=100, total_tokens=200),
            latency_ms=100,
        )

    async def list_models(self, provider: LLMProvider) -> list[str]:
        return ["frontend-model"]


@pytest.mark.asyncio
async def test_main_coder_synthesizes_frontend_in_dedicated_directory_when_incremental(coder_agent_setup):
    session, project, task, execution, tmp_workspace, git_service = coder_agent_setup

    # Pre-create backend files in channel-app
    channel_repo_path = Path(git_service.get_repository_path(project.id, RepositoryType.CHANNEL_APP))
    backend_file = channel_repo_path / "Program.cs"
    backend_file.write_text("// backend ASP.NET Core source code", encoding="utf-8")

    resolver = LLMProviderResolver(litellm_adapter=FakeFrontendLLMAdapter())
    tracker = TokenTrackerService(db=session)
    agent = MainCodingAgent(resolver=resolver, git_service=git_service, tracker=tracker, db=session)

    context = AgentContext(
        project_id=project.id,
        task_id=task.id,
        agent_execution_id=execution.id,
        workspace_path=tmp_workspace,
        target_framework="csharp",
        additional_metadata={
            "is_incremental": True,
            "target_subsystem": "frontend",
            "subsystem_framework": "TYPESCRIPT_NEXTJS",
        },
    )

    result = await agent.execute(context, "Scaffold Next.js student registration frontend portal")

    assert result.success is True
    assert result.metadata["target_subsystem"] == "frontend"
    assert result.metadata["repo"] == "frontend"

    # Verify frontend files created in workspace/frontend/
    frontend_dir = Path(tmp_workspace) / "frontend"
    assert (frontend_dir / "package.json").exists()
    assert (frontend_dir / "app/page.tsx").exists()

    # Crucial assertion: backend files MUST NOT be touched or overwritten
    assert backend_file.exists()
    assert backend_file.read_text(encoding="utf-8") == "// backend ASP.NET Core source code"
    assert not (channel_repo_path / "package.json").exists()
