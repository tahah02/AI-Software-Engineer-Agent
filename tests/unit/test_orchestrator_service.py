import json
import shutil
import tempfile
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.application.orchestration.orchestrator_service import OrchestratorService
from src.domain.enums import AgentType, LLMProvider
from src.infrastructure.db.models import (
    Base,
    ProjectORM,
    ProjectAgentConfigORM,
    WorkflowRunORM,
    GitReleaseManifestORM,
)
from src.infrastructure.git.git_service import GitService
from src.infrastructure.llm.provider_resolver import LLMProviderResolver
from src.infrastructure.llm.token_tracker import TokenTrackerService
from src.ports.llm_gateway import ILLMGateway, LLMRequest, LLMResponse, TokenUsage


class FakeOrchestratorLLMAdapter(ILLMGateway):
    async def complete(self, request: LLMRequest) -> LLMResponse:
        prompt_content = "\n".join(m.content for m in request.messages)

        # Agent 1 Doc Reviewer response
        if "Agent 1" in prompt_content:
            data = {
                "technical_design": "# Technical Design Document\n\n## Endpoints\n- POST /api/v1/auth/login\n\n## Dependencies\n- Mock Vendor API for upstream verification",
                "test_spec": "# XUnit Test Specifications\n\n- TC01: Login returns 200",
            }
        # Agent 2 Mock Dev response
        elif "Agent 2" in prompt_content:
            data = {
                "files": {
                    "main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
                }
            }
        # Agent 3 Coder response
        elif "Agent 3" in prompt_content:
            data = {
                "files": {
                    "src/main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
                    "requirements.txt": "fastapi\n",
                }
            }
        # Agent 4 QA response
        elif "Agent 4" in prompt_content:
            data = {
                "test_results": [
                    {
                        "test_key": "TC01",
                        "category": "CONTRACT",
                        "endpoint": "/api/v1/auth/login",
                        "http_method": "POST",
                        "expected_status": 200,
                        "actual_status": 200,
                        "status": "PASSED",
                        "details": "Contract matches",
                    }
                ],
                "overall_summary": "QA passed",
            }
        # Agent 5 Security response
        elif "Agent 5" in prompt_content:
            data = {
                "findings": [],
                "overall_summary": "Zero security vulnerabilities found",
            }
        else:
            data = {"status": "ok"}

        return LLMResponse(
            provider=request.provider,
            model=request.model or "fake-model",
            finish_reason="stop",
            content=json.dumps(data),
            usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
            latency_ms=50,
        )

    async def list_models(self, provider: LLMProvider) -> list[str]:
        return ["fake-model"]


@pytest.fixture
def orchestrator_setup():
    tmp = tempfile.mkdtemp(prefix="aaise_orch_test_")
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    project = ProjectORM(name="End-to-End Orchestrator Project", target_framework="fastapi")
    session.add(project)
    session.flush()

    # Configure all 5 agents
    for agent_enum in AgentType:
        config = ProjectAgentConfigORM(
            project_id=project.id,
            agent_type=agent_enum.value,
            is_enabled=True,
            provider="groq",
            model_name="openai/gpt-oss-120b",
        )
        session.add(config)
    session.commit()

    git_service = GitService(db=session, base_workspace_dir=tmp)

    yield session, project, tmp, git_service

    session.close()
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.asyncio
async def test_orchestrator_runs_end_to_end_workflow(orchestrator_setup):
    session, project, tmp, git_service = orchestrator_setup

    resolver = LLMProviderResolver(litellm_adapter=FakeOrchestratorLLMAdapter())
    tracker = TokenTrackerService(db=session)

    service = OrchestratorService(
        db=session,
        resolver=resolver,
        git_service=git_service,
        tracker=tracker,
    )

    spec_state = await service.start_workflow(
        project_id=project.id,
        user_requirement="Create an authentication service with login endpoint.",
    )
    assert spec_state["current_phase"] == "SPEC_APPROVAL"
    assert spec_state["is_completed"] is False

    result_state = await service.start_workflow(
        project_id=project.id,
        user_requirement="approved",
    )

    assert result_state["is_completed"] is True
    assert result_state["current_phase"] == "COMPLETED"
    assert result_state["qa_status"] == "PASSED"
    assert result_state["security_status"] == "PASSED"
    assert result_state["channel_commit_hash"] is not None
    assert result_state["mock_commit_hash"] is not None
    assert result_state["release_tag"] is not None

    # Verify WorkflowRunORM updated in database
    run = session.query(WorkflowRunORM).filter_by(project_id=project.id).first()
    assert run is not None
    assert run.status == "COMPLETED"

    # Verify GitReleaseManifestORM created
    manifest = session.query(GitReleaseManifestORM).filter_by(project_id=project.id).first()
    assert manifest is not None
    assert len(manifest.channel_commit_hash) == 40
    assert len(manifest.mock_commit_hash) == 40
