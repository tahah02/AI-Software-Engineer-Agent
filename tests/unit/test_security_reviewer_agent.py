import json
import shutil
import tempfile
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.application.agents.security_reviewer import SecurityReviewerAgent
from src.domain.enums import AgentType, LLMProvider, RepositoryType
from src.domain.tools import execute_file_write
from src.infrastructure.db.models import (
    Base,
    ProjectORM,
    ProjectAgentConfigORM,
    AgentTaskORM,
    AgentExecutionORM,
    SecurityScanORM,
    SecurityFindingORM,
)
from src.infrastructure.git.git_service import GitService
from src.infrastructure.llm.provider_resolver import LLMProviderResolver
from src.infrastructure.llm.token_tracker import TokenTrackerService
from src.ports.agent import AgentContext
from src.ports.llm_gateway import ILLMGateway, LLMRequest, LLMResponse, TokenUsage


class FakeSecurityLLMAdapter(ILLMGateway):
    def __init__(self, simulate_vuln: bool = False):
        self.simulate_vuln = simulate_vuln

    async def complete(self, request: LLMRequest) -> LLMResponse:
        if self.simulate_vuln:
            data = {
                "findings": [
                    {
                        "severity": "CRITICAL",
                        "vulnerability_type": "HARDCODED_SECRET",
                        "target_repo": "CHANNEL_APP",
                        "file_path": "src/config.py",
                        "line_number": 5,
                        "description": "Hardcoded AWS_SECRET_KEY found in config file",
                        "remediation_advice": "Inject through environment variables",
                    }
                ],
                "overall_summary": "1 critical vulnerability detected.",
            }
        else:
            data = {
                "findings": [],
                "overall_summary": "No security vulnerabilities detected. Code clean.",
            }

        return LLMResponse(
            provider=request.provider,
            model=request.model or "fake-sec-model",
            finish_reason="stop",
            content=json.dumps(data),
            usage=TokenUsage(prompt_tokens=400, completion_tokens=120, total_tokens=520),
            latency_ms=180,
        )

    async def list_models(self, provider: LLMProvider) -> list[str]:
        return ["fake-sec-model"]


@pytest.fixture
def security_setup():
    tmp = tempfile.mkdtemp(prefix="aaise_agent5_test_")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    project = ProjectORM(name="Security Test Project", target_framework="fastapi")
    session.add(project)
    session.flush()

    config = ProjectAgentConfigORM(
        project_id=project.id,
        agent_type=AgentType.SECURITY_REVIEWER.value,
        is_enabled=True,
        provider="gemini",
        model_name="gemini-3.5-flash-lite",
    )
    session.add(config)

    task = AgentTaskORM(
        project_id=project.id,
        agent_name="Agent 5: Security Reviewer",
        task_type="SECURITY_AUDIT",
    )
    session.add(task)
    session.flush()

    execution = AgentExecutionORM(agent_task_id=task.id)
    session.add(execution)
    session.commit()

    git_service = GitService(db=session, base_workspace_dir=tmp)
    channel_path = git_service.initialize_repository(project.id, RepositoryType.CHANNEL_APP)

    # Place a sample source code file in channel-app
    execute_file_write(channel_path, "src/config.py", "AWS_SECRET_KEY = 'AKIA1234567890'\n")

    yield session, project, task, execution, tmp, git_service

    session.close()
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.asyncio
async def test_security_reviewer_detects_vulnerability_and_records_scan(security_setup):
    session, project, task, execution, tmp, git_service = security_setup

    resolver = LLMProviderResolver(litellm_adapter=FakeSecurityLLMAdapter(simulate_vuln=True))
    tracker = TokenTrackerService(db=session)

    agent = SecurityReviewerAgent(
        resolver=resolver,
        git_service=git_service,
        tracker=tracker,
        db=session,
    )

    context = AgentContext(
        project_id=project.id,
        task_id=task.id,
        agent_execution_id=execution.id,
        workspace_path=tmp,
    )

    result = await agent.execute(context, "Perform security audit.")

    assert result.success is False
    assert result.metadata["scan_status"] == "FAILED"
    assert result.metadata["critical_or_high_count"] == 1

    # Verify database persistence in security_scans and security_findings
    scan = session.query(SecurityScanORM).filter_by(project_id=project.id).first()
    assert scan is not None
    assert scan.status == "FAILED"

    finding = session.query(SecurityFindingORM).filter_by(security_scan_id=scan.id).first()
    assert finding is not None
    assert finding.severity == "CRITICAL"
    assert finding.vulnerability_type == "HARDCODED_SECRET"
    assert "AWS_SECRET_KEY" in finding.description


@pytest.mark.asyncio
async def test_security_reviewer_passes_clean_code(security_setup):
    session, project, task, execution, tmp, git_service = security_setup

    resolver = LLMProviderResolver(litellm_adapter=FakeSecurityLLMAdapter(simulate_vuln=False))
    tracker = TokenTrackerService(db=session)

    agent = SecurityReviewerAgent(
        resolver=resolver,
        git_service=git_service,
        tracker=tracker,
        db=session,
    )

    context = AgentContext(
        project_id=project.id,
        task_id=task.id,
        agent_execution_id=execution.id,
        workspace_path=tmp,
    )

    result = await agent.execute(context, "Perform security audit.")

    assert result.success is True
    assert result.metadata["scan_status"] == "PASSED"
    assert result.metadata["critical_or_high_count"] == 0

    scan = session.query(SecurityScanORM).filter_by(project_id=project.id).first()
    assert scan is not None
    assert scan.status == "PASSED"
