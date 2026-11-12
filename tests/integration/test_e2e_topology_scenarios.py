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
    GitReleaseManifestORM,
    HumanApprovalORM,
    ProjectAgentConfigORM,
    ProjectORM,
    WorkflowRunORM,
)
from src.infrastructure.git.git_service import GitService
from src.infrastructure.llm.provider_resolver import LLMProviderResolver
from src.infrastructure.llm.token_tracker import TokenTrackerService
from src.ports.llm_gateway import ILLMGateway, LLMRequest, LLMResponse, TokenUsage


class FakeTopologyLLMAdapter(ILLMGateway):
    async def complete(self, request: LLMRequest) -> LLMResponse:
        prompt_content = "\n".join(m.content for m in request.messages)

        # Agent 1 Doc Reviewer response
        if "Agent 1" in prompt_content:
            data = {
                "technical_design": "# Technical Design Document\n\n## Endpoints\n- POST /api/v1/auth/login",
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
def topology_env():
    tmp = tempfile.mkdtemp(prefix="aaise_topo_test_")
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    git_service = GitService(db=session, base_workspace_dir=tmp)
    resolver = LLMProviderResolver(litellm_adapter=FakeTopologyLLMAdapter())
    tracker = TokenTrackerService(db=session)

    yield session, git_service, resolver, tracker, tmp

    session.close()
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.asyncio
async def test_scenario_a_full_5_agent_enterprise_topology(topology_env):
    """Scenario A: All 5 agents enabled."""
    session, git_service, resolver, tracker, tmp = topology_env

    project = ProjectORM(name="Full 5-Agent Banking System", target_framework="fastapi")
    session.add(project)
    session.flush()

    for agent_enum in AgentType:
        config = ProjectAgentConfigORM(
            project_id=project.id,
            agent_type=agent_enum.value,
            is_enabled=True,
            provider="gemini",
            model_name="test-model",
        )
        session.add(config)
    session.commit()

    service = OrchestratorService(
        db=session,
        resolver=resolver,
        git_service=git_service,
        tracker=tracker,
    )

    # Step 1: Agent 1 generates specifications and requests human approval
    spec_state = await service.start_workflow(
        project_id=project.id,
        user_requirement="Build core banking payment gateway with external vendor mock.",
    )
    assert spec_state["spec_approved"] is False

    # Human approves specification
    approval = session.query(HumanApprovalORM).filter_by(gate_type="SPECIFICATION", status="PENDING").first()
    assert approval is not None
    service.approval_engine.resolve_approval(approval.id, approved=True)

    # Step 2: Resume with approval -> runs Agent 2, Agent 3, Agent 4, Agent 5
    result_state = await service.start_workflow(
        project_id=project.id,
        user_requirement="Specifications approved. Proceed with full application implementation.",
    )

    assert result_state["is_completed"] is True
    assert result_state["current_phase"] == "COMPLETED"
    assert result_state["qa_status"] == "PASSED"
    assert result_state["security_status"] == "PASSED"
    assert result_state["channel_commit_hash"] is not None
    assert result_state["mock_commit_hash"] is not None
    assert result_state["release_tag"] is not None

    manifest = session.query(GitReleaseManifestORM).filter_by(project_id=project.id).first()
    assert manifest is not None
    assert len(manifest.channel_commit_hash) == 40
    assert len(manifest.mock_commit_hash) == 40


@pytest.mark.asyncio
async def test_scenario_b_standalone_microservice_agent2_disabled(topology_env):
    """Scenario B: Standalone microservice with Agent 2 (Mock Vendor) disabled."""
    session, git_service, resolver, tracker, tmp = topology_env

    project = ProjectORM(name="Standalone Microservice", target_framework="fastapi")
    session.add(project)
    session.flush()

    for agent_enum in AgentType:
        # Agent 2 is disabled
        is_enabled = (agent_enum != AgentType.MOCK_DEVELOPER)
        config = ProjectAgentConfigORM(
            project_id=project.id,
            agent_type=agent_enum.value,
            is_enabled=is_enabled,
            provider="groq",
            model_name="test-model",
        )
        session.add(config)
    session.commit()

    service = OrchestratorService(
        db=session,
        resolver=resolver,
        git_service=git_service,
        tracker=tracker,
    )

    # Step 1: Agent 1 generates specifications and requests human approval
    spec_state = await service.start_workflow(
        project_id=project.id,
        user_requirement="Build standalone user profile CRUD service with zero external vendor APIs.",
    )
    assert spec_state["spec_approved"] is False

    # Human approves specification
    approval = session.query(HumanApprovalORM).filter_by(gate_type="SPECIFICATION", status="PENDING").first()
    assert approval is not None
    service.approval_engine.resolve_approval(approval.id, approved=True)

    # Step 2: Resume with approval -> runs Agent 3, Agent 4, Agent 5 (Agent 2 skipped)
    result_state = await service.start_workflow(
        project_id=project.id,
        user_requirement="Specifications approved. Proceed with full application implementation.",
    )

    assert result_state["is_completed"] is True
    assert result_state["current_phase"] == "COMPLETED"
    assert result_state["mock_repo_path"] is None, "Mock repo must not be initialized when Agent 2 disabled"
    assert result_state["qa_status"] == "PASSED"
    assert result_state["security_status"] == "PASSED"
    assert result_state["channel_commit_hash"] is not None
    assert result_state.get("mock_commit_hash") is None, "Mock commit hash must be None when mock repo is omitted"


@pytest.mark.asyncio
async def test_scenario_c_rapid_prototype_agent4_disabled_honest_reporting(topology_env):
    """Scenario C: Rapid prototype flow with Agent 4 (QA) disabled. Honest reporting: SKIPPED."""
    session, git_service, resolver, tracker, tmp = topology_env

    project = ProjectORM(name="Rapid Prototype System", target_framework="fastapi")
    session.add(project)
    session.flush()

    for agent_enum in AgentType:
        # Agent 2 and Agent 4 disabled
        is_enabled = (agent_enum not in (AgentType.MOCK_DEVELOPER, AgentType.QA_ENGINEER))
        config = ProjectAgentConfigORM(
            project_id=project.id,
            agent_type=agent_enum.value,
            is_enabled=is_enabled,
            provider="groq",
            model_name="test-model",
        )
        session.add(config)
    session.commit()

    service = OrchestratorService(
        db=session,
        resolver=resolver,
        git_service=git_service,
        tracker=tracker,
    )

    # Step 1: Agent 1 generates specifications and requests human approval
    spec_state = await service.start_workflow(
        project_id=project.id,
        user_requirement="Build quick prototype dashboard, manual QA elected.",
    )
    assert spec_state["spec_approved"] is False

    # Human approves specification
    approval = session.query(HumanApprovalORM).filter_by(gate_type="SPECIFICATION", status="PENDING").first()
    assert approval is not None
    service.approval_engine.resolve_approval(approval.id, approved=True)

    # Step 2: Resume with approval -> runs Agent 3, Agent 5 (Agent 2 and Agent 4 skipped)
    result_state = await service.start_workflow(
        project_id=project.id,
        user_requirement="Specifications approved. Proceed with full application implementation.",
    )

    assert result_state["is_completed"] is True
    assert result_state["current_phase"] == "COMPLETED"
    assert result_state["qa_status"] == "SKIPPED", "Disabled QA must strictly record SKIPPED (never reported as passed)"
    assert result_state["security_status"] == "PASSED"
    assert result_state["channel_commit_hash"] is not None
