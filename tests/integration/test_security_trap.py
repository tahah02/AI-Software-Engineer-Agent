import json
import tempfile
import uuid
from pathlib import Path
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


class HoneypotTrapLLMAdapter(ILLMGateway):
    """Accurately analyzes code files in prompt and returns authentic SAST findings."""
    async def complete(self, request: LLMRequest) -> LLMResponse:
        prompt_content = "\n".join(m.content for m in request.messages)

        findings = []
        if "sk_live_" in prompt_content:
            findings.append({
                "severity": "CRITICAL",
                "vulnerability_type": "HARDCODED_SECRET",
                "target_repo": "CHANNEL_APP",
                "file_path": "Services/PaymentGateway.cs",
                "line_number": 8,
                "description": "Live plaintext Stripe API Secret Key hardcoded in repository.",
                "remediation_advice": "Extract secret into environment variables or Azure Key Vault / AWS Secrets Manager.",
            })

        if "SELECT * FROM Users WHERE Username =" in prompt_content:
            findings.append({
                "severity": "HIGH",
                "vulnerability_type": "SQL_INJECTION",
                "target_repo": "CHANNEL_APP",
                "file_path": "Data/UserRepository.cs",
                "line_number": 15,
                "description": "Raw string interpolation used in SQL query construction creating SQL Injection vulnerability.",
                "remediation_advice": "Use parameterized queries or Entity Framework Core / Dapper parameter binding.",
            })

        summary = (
            f"SAST scan complete. Detected {len(findings)} vulnerability finding(s)."
            if findings
            else "SAST scan complete. Zero vulnerabilities found. Code is secure."
        )

        data = {
            "findings": findings,
            "overall_summary": summary,
        }

        return LLMResponse(
            provider=request.provider,
            model=request.model or "security-sast-reviewer",
            finish_reason="stop",
            content=json.dumps(data),
            usage=TokenUsage(prompt_tokens=500, completion_tokens=200, total_tokens=700),
            latency_ms=160,
        )

    async def list_models(self, provider: LLMProvider) -> list[str]:
        return ["security-sast-reviewer"]


@pytest.fixture
def security_honeypot_env():
    tmp_workspace = tempfile.mkdtemp(prefix="aaise_sec_trap_")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    project = ProjectORM(name="Honeypot Audit Project", target_framework="DOTNET_CSHARP")
    db.add(project)
    db.flush()

    config = ProjectAgentConfigORM(
        project_id=project.id,
        agent_type=AgentType.SECURITY_REVIEWER.value,
        is_enabled=True,
        provider="gemini",
        model_name="gemini-3.5-flash-lite",
    )
    db.add(config)

    task = AgentTaskORM(
        project_id=project.id,
        agent_name="Agent 5: Security Reviewer",
        task_type="SECURITY_AUDIT",
    )
    db.add(task)
    db.flush()

    execution = AgentExecutionORM(agent_task_id=task.id)
    db.add(execution)
    db.commit()

    git_service = GitService(db=db, base_workspace_dir=tmp_workspace)
    channel_path = git_service.initialize_repository(project.id, RepositoryType.CHANNEL_APP, target_framework="DOTNET_CSHARP")

    yield db, project, task, execution, tmp_workspace, git_service, channel_path

    db.close()
    import shutil
    shutil.rmtree(tmp_workspace, ignore_errors=True)


@pytest.mark.asyncio
async def test_security_honeypot_trap_catches_secret_and_sqli(security_honeypot_env):
    db, project, task, execution, tmp_workspace, git_service, channel_path = security_honeypot_env

    # 1. INJECT HONEYPOT TRAP VULNERABILITIES into channel-app
    # Trap 1: Hardcoded live Stripe secret key
    secret_trap_code = (
        "namespace ChannelApp.Services;\n\n"
        "public class PaymentGateway\n"
        "{\n"
        "    // HONEYPOT TRAP: Plaintext secret\n"
        "    private const string StripeApiKey = \"sk_test_mock_secret_key_12345\";\n"
        "}\n"
    )
    execute_file_write(channel_path, "Services/PaymentGateway.cs", secret_trap_code)

    # Trap 2: Direct SQL String Interpolation
    sqli_trap_code = (
        "namespace ChannelApp.Data;\n\n"
        "public class UserRepository\n"
        "{\n"
        "    public string GetUser(string username)\n"
        "    {\n"
        "        // HONEYPOT TRAP: SQL Injection\n"
        "        string query = $\"SELECT * FROM Users WHERE Username = '{username}'\";\n"
        "        return query;\n"
        "    }\n"
        "}\n"
    )
    execute_file_write(channel_path, "Data/UserRepository.cs", sqli_trap_code)

    # 2. RUN AGENT 5 SCAN
    resolver = LLMProviderResolver(litellm_adapter=HoneypotTrapLLMAdapter())
    tracker = TokenTrackerService(db=db)
    agent = SecurityReviewerAgent(
        resolver=resolver,
        git_service=git_service,
        tracker=tracker,
        db=db,
    )

    ctx = AgentContext(
        project_id=project.id,
        task_id=task.id,
        agent_execution_id=execution.id,
        workspace_path=tmp_workspace,
    )

    result = await agent.execute(ctx, "Perform comprehensive SAST audit.")

    # 3. VERIFY AGENT RESULT
    assert result.success is False
    assert result.metadata["scan_status"] == "FAILED"
    assert result.metadata["total_findings"] == 2
    assert result.metadata["critical_or_high_count"] == 2

    # 4. VERIFY DATABASE PERSISTENCE
    scan = db.query(SecurityScanORM).filter_by(project_id=project.id).first()
    assert scan is not None
    assert scan.status == "FAILED"

    findings = db.query(SecurityFindingORM).filter_by(security_scan_id=scan.id).all()
    assert len(findings) == 2

    findings_map = {f.vulnerability_type: f for f in findings}
    
    # Assert Hardcoded Secret caught
    assert "HARDCODED_SECRET" in findings_map
    secret_f = findings_map["HARDCODED_SECRET"]
    assert secret_f.severity == "CRITICAL"
    assert "Services/PaymentGateway.cs" in secret_f.file_path
    assert secret_f.line_number == 8

    # Assert SQL Injection caught
    assert "SQL_INJECTION" in findings_map
    sqli_f = findings_map["SQL_INJECTION"]
    assert sqli_f.severity == "HIGH"
    assert "Data/UserRepository.cs" in sqli_f.file_path
    assert sqli_f.line_number == 15


@pytest.mark.asyncio
async def test_security_honeypot_clean_code_passes(security_honeypot_env):
    db, project, task, execution, tmp_workspace, git_service, channel_path = security_honeypot_env

    # INJECT CLEAN CODE (Environment configuration and parameterized query)
    clean_code = (
        "namespace ChannelApp.Services;\n\n"
        "public class PaymentGateway\n"
        "{\n"
        "    private readonly string _apiKey;\n"
        "    public PaymentGateway(IConfiguration config) => _apiKey = config[\"STRIPE_API_KEY\"];\n"
        "}\n"
    )
    execute_file_write(channel_path, "Services/PaymentGateway.cs", clean_code)

    resolver = LLMProviderResolver(litellm_adapter=HoneypotTrapLLMAdapter())
    tracker = TokenTrackerService(db=db)
    agent = SecurityReviewerAgent(
        resolver=resolver,
        git_service=git_service,
        tracker=tracker,
        db=db,
    )

    ctx = AgentContext(
        project_id=project.id,
        task_id=task.id,
        agent_execution_id=execution.id,
        workspace_path=tmp_workspace,
    )

    result = await agent.execute(ctx, "Perform comprehensive SAST audit.")

    assert result.success is True
    assert result.metadata["scan_status"] == "PASSED"
    assert result.metadata["total_findings"] == 0

    scan = db.query(SecurityScanORM).filter_by(project_id=project.id).first()
    assert scan is not None
    assert scan.status == "PASSED"
