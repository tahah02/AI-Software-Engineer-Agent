import json
import shutil
import tempfile
import uuid
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.application.agents.doc_reviewer import DocumentationReviewerAgent
from src.application.agents.main_coder import MainCodingAgent
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
from src.api.routes.workflow import detect_target_framework, is_client_extension_intent


class MockIncrementalFullFlowAdapter(ILLMGateway):
    async def complete(self, request: LLMRequest) -> LLMResponse:
        last_msg = request.messages[-1]
        content = last_msg.content if hasattr(last_msg, "content") else last_msg["content"]

        if "Principal Enterprise Software Architect" in content:
            # Pass 1: TDD append
            tdd = (
                "# Technical Design Document\n\n"
                "## Section 1: System Architecture (ASP.NET Core Web API)\n"
                "- POST /api/students\n"
                "- GET /api/students\n\n"
                "## Section 9: Client Interface Specification (TYPESCRIPT_NEXTJS)\n"
                "- Target Subsystem Directory: frontend/\n"
                "- Technology Stack: Next.js 15 App Router, React 19, TypeScript, Tailwind CSS\n"
                "- Page & Component: StudentPortal (app/page.tsx) integrates with POST /api/students"
            )
            return LLMResponse(
                provider=request.provider,
                model="mock-llm",
                finish_reason="stop",
                content=tdd,
                usage=TokenUsage(prompt_tokens=100, completion_tokens=100, total_tokens=200),
                latency_ms=50,
            )
        elif "Principal Lead QA Architect" in content:
            # Pass 2: Test Spec append
            spec = (
                "# Test Specification\n\n"
                "## UT-01: Create student validation test\n\n"
                "## Section 15: Client Interface Contract & Component Tests\n"
                "## UI-01: Form validation test"
            )
            return LLMResponse(
                provider=request.provider,
                model="mock-llm",
                finish_reason="stop",
                content=spec,
                usage=TokenUsage(prompt_tokens=100, completion_tokens=100, total_tokens=200),
                latency_ms=50,
            )
        else:
            # Agent 3: Frontend code synthesis
            files = {
                "package.json": json.dumps({"name": "student-frontend", "dependencies": {"next": "15.0.0", "react": "19.0.0"}}),
                "tsconfig.json": json.dumps({"compilerOptions": {"target": "es5"}}),
                "app/page.tsx": "'use client';\nexport default function Page() { return <div>Student Management Portal</div>; }",
            }
            return LLMResponse(
                provider=request.provider,
                model="mock-llm",
                finish_reason="stop",
                content=json.dumps({"files": files}),
                usage=TokenUsage(prompt_tokens=150, completion_tokens=150, total_tokens=300),
                latency_ms=75,
            )

    async def list_models(self, provider: LLMProvider) -> list[str]:
        return ["mock-llm"]


@pytest.fixture
def integration_flow_setup():
    tmp_workspace = tempfile.mkdtemp(prefix="aaise_full_incremental_")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    project = ProjectORM(name="Student Fullstack System", target_framework="csharp")
    session.add(project)
    session.flush()

    for agent_enum in (AgentType.DOC_REVIEWER, AgentType.MAIN_CODING):
        config = ProjectAgentConfigORM(
            project_id=project.id,
            agent_type=agent_enum.value,
            is_enabled=True,
            provider="groq",
            model_name="openai/gpt-oss-120b",
        )
        session.add(config)

    session.commit()
    git_service = GitService(db=session, base_workspace_dir=tmp_workspace)

    yield session, project, tmp_workspace, git_service

    session.close()
    shutil.rmtree(tmp_workspace, ignore_errors=True)


@pytest.mark.asyncio
async def test_incremental_frontend_flow_end_to_end(integration_flow_setup):
    session, project, tmp_workspace, git_service = integration_flow_setup

    # 1. Setup pre-existing backend code and TDD
    proj_workspace = Path(tmp_workspace) / str(project.id)
    proj_workspace.mkdir(parents=True, exist_ok=True)

    channel_repo_path = git_service.initialize_repository(project.id, RepositoryType.CHANNEL_APP, "csharp")
    backend_file = Path(channel_repo_path) / "Program.cs"
    backend_file.write_text("// C# ASP.NET Core Student API Program.cs", encoding="utf-8")

    docs_dir = proj_workspace / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    initial_tdd = (
        "# Technical Design Document\n\n"
        "## Section 1: System Architecture (ASP.NET Core Web API)\n"
        "- POST /api/students\n"
    )
    initial_spec = "# Test Specification\n\n## UT-01: Create student validation test\n"
    (docs_dir / "TECHNICAL_DESIGN.md").write_text(initial_tdd, encoding="utf-8")
    (docs_dir / "XUNIT_TEST_SPEC.md").write_text(initial_spec, encoding="utf-8")

    # 2. User sends client request
    user_prompt = "Can you make a frontend of this on next.js?"

    # Verify detection
    detected_framework = detect_target_framework(user_prompt)
    is_client_ext = is_client_extension_intent(user_prompt)
    assert detected_framework == "TYPESCRIPT_NEXTJS"
    assert is_client_ext is True

    # 3. Execute Agent 1 (Doc Reviewer) in Incremental Mode
    mock_adapter = MockIncrementalFullFlowAdapter()
    resolver = LLMProviderResolver(litellm_adapter=mock_adapter)
    tracker = TokenTrackerService(db=session)

    agent1 = DocumentationReviewerAgent(resolver=resolver, tracker=tracker, db=session)

    task1 = AgentTaskORM(project_id=project.id, agent_name="Agent 1", task_type="SPECIFICATION")
    session.add(task1)
    session.flush()
    exec1 = AgentExecutionORM(agent_task_id=task1.id)
    session.add(exec1)
    session.commit()

    ctx1 = AgentContext(
        project_id=project.id,
        task_id=task1.id,
        agent_execution_id=exec1.id,
        workspace_path=str(proj_workspace),
        target_framework=project.target_framework,
        additional_metadata={
            "is_incremental": True,
            "target_subsystem": "frontend",
            "subsystem_framework": detected_framework,
        },
    )

    res1 = await agent1.execute(ctx1, user_prompt)
    assert res1.success is True

    # Check that TDD preserved backend and appended Section 9
    updated_tdd = (docs_dir / "TECHNICAL_DESIGN.md").read_text(encoding="utf-8")
    assert "Section 1: System Architecture (ASP.NET Core Web API)" in updated_tdd
    assert "Section 9: Client Interface Specification (TYPESCRIPT_NEXTJS)" in updated_tdd
    assert "Target Subsystem Directory: frontend/" in updated_tdd

    # Check project framework was preserved
    refreshed_proj = session.query(ProjectORM).filter_by(id=project.id).first()
    assert refreshed_proj.target_framework == "csharp"

    # 4. Execute Agent 3 (Main Coder) in Incremental Mode
    agent3 = MainCodingAgent(resolver=resolver, git_service=git_service, tracker=tracker, db=session)

    task3 = AgentTaskORM(project_id=project.id, agent_name="Agent 3", task_type="DEVELOPMENT")
    session.add(task3)
    session.flush()
    exec3 = AgentExecutionORM(agent_task_id=task3.id)
    session.add(exec3)
    session.commit()

    ctx3 = AgentContext(
        project_id=project.id,
        task_id=task3.id,
        agent_execution_id=exec3.id,
        workspace_path=str(proj_workspace),
        target_framework=project.target_framework,
        additional_metadata={
            "is_incremental": True,
            "target_subsystem": "frontend",
            "subsystem_framework": detected_framework,
        },
    )

    res3 = await agent3.execute(ctx3, "Scaffold Next.js student registration frontend portal")
    assert res3.success is True
    assert res3.metadata["target_subsystem"] == "frontend"
    assert res3.metadata["repo"] == "frontend"

    # 5. Verify physical filesystem isolation
    frontend_dir = proj_workspace / "frontend"
    assert (frontend_dir / "package.json").exists()
    assert (frontend_dir / "tsconfig.json").exists()
    assert (frontend_dir / "app/page.tsx").exists()

    # Verify backend files were completely untouched
    assert backend_file.exists()
    assert backend_file.read_text(encoding="utf-8") == "// C# ASP.NET Core Student API Program.cs"
    assert not (Path(channel_repo_path) / "package.json").exists()
