import json
import tempfile
import uuid
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.application.agents.qa_engineer import QAEngineerAgent
from src.domain.enums import AgentType, LLMProvider
from src.domain.tools import execute_file_write
from src.infrastructure.db.models import (
    Base,
    ProjectORM,
    ProjectAgentConfigORM,
    AgentTaskORM,
    AgentExecutionORM,
    TestRunORM,
    TestResultORM,
    DefectORM,
)
from src.infrastructure.llm.provider_resolver import LLMProviderResolver
from src.infrastructure.llm.token_tracker import TokenTrackerService
from src.ports.agent import AgentContext
from src.ports.llm_gateway import ILLMGateway, LLMRequest, LLMResponse, TokenUsage


class MockQAGateway(ILLMGateway):
    def __init__(self, fail_contract: bool = False):
        self.fail_contract = fail_contract

    async def complete(self, request: LLMRequest) -> LLMResponse:
        if self.fail_contract:
            results = [
                {
                    "test_key": "UT-01",
                    "category": "UNIT",
                    "endpoint": "/api/calculations",
                    "http_method": "POST",
                    "expected_status": 201,
                    "actual_status": 500,
                    "status": "FAILED",
                    "severity": "HIGH",
                    "details": "Contract schema mismatch: response missing calculation_id",
                },
                {
                    "test_key": "UT-02",
                    "category": "UNIT",
                    "endpoint": "/api/calculations/1",
                    "http_method": "GET",
                    "expected_status": 200,
                    "actual_status": 200,
                    "status": "PASSED",
                    "details": "Summation result matches contract",
                },
            ]
            summary = "1 contract test failed."
        else:
            results = [
                {
                    "test_key": "UT-01",
                    "category": "UNIT",
                    "endpoint": "/api/calculations",
                    "http_method": "POST",
                    "expected_status": 201,
                    "actual_status": 201,
                    "status": "PASSED",
                    "details": "Calculation record created successfully",
                },
                {
                    "test_key": "UT-02",
                    "category": "UNIT",
                    "endpoint": "/api/calculations/1",
                    "http_method": "GET",
                    "expected_status": 200,
                    "actual_status": 200,
                    "status": "PASSED",
                    "details": "Summation result matches contract: 1 + 1 + 1 = 3",
                },
            ]
            summary = "All contract tests passed."

        payload = {
            "test_results": results,
            "overall_summary": summary,
        }

        return LLMResponse(
            provider=request.provider,
            model=request.model or "qa-evaluator",
            finish_reason="stop",
            content=json.dumps(payload),
            usage=TokenUsage(prompt_tokens=400, completion_tokens=150, total_tokens=550),
            latency_ms=120,
        )

    async def list_models(self, provider: LLMProvider) -> list[str]:
        return ["qa-evaluator"]


@pytest.fixture
def qa_flow_env():
    workspace = tempfile.mkdtemp(prefix="aaise_qa_flow_")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    proj = ProjectORM(name="Calculation API QA Test", target_framework="DOTNET_CSHARP")
    db.add(proj)
    db.flush()

    # Create Agent 4 configuration in DB
    cfg = ProjectAgentConfigORM(
        project_id=proj.id,
        agent_type=AgentType.QA_ENGINEER.value,
        is_enabled=True,
        provider="gemini",
        model_name="gemini-3.5-flash-lite",
    )
    db.add(cfg)

    task = AgentTaskORM(
        project_id=proj.id,
        agent_name="Agent 4: Independent QA Engineer",
        task_type="QA_VERIFICATION",
    )
    db.add(task)
    db.flush()

    execution = AgentExecutionORM(agent_task_id=task.id)
    db.add(execution)
    db.commit()

    # Write realistic Calculation API XUNIT spec to docs/
    spec_md = """# xUnit Test Specification: AAISE 2+2+1 Calculation API
## 3. Unit Test Suite
### UT-01: Standard Calculation Logic
- Requirement Traced: FR-06
- Input Payload: Record ID 1
- Expected Result: Total sum is 3

### UT-02: Alternate Positive Values
- Expected Result: Total sum is 6
"""
    execute_file_write(workspace, "docs/XUNIT_TEST_SPEC.md", spec_md)

    yield db, proj, task, execution, workspace

    db.close()
    import shutil
    shutil.rmtree(workspace, ignore_errors=True)


@pytest.mark.asyncio
async def test_qa_flow_evaluates_contracts_and_persists_results(qa_flow_env):
    db, proj, task, execution, workspace = qa_flow_env

    resolver = LLMProviderResolver(litellm_adapter=MockQAGateway(fail_contract=False))
    tracker = TokenTrackerService(db=db)
    agent = QAEngineerAgent(resolver=resolver, tracker=tracker, db=db)

    ctx = AgentContext(
        project_id=proj.id,
        task_id=task.id,
        agent_execution_id=execution.id,
        workspace_path=workspace,
    )

    result = await agent.execute(ctx, "Evaluate Calculation API endpoints.")

    # 1. Verify agent result metadata
    assert result.success is True
    assert result.metadata["overall_status"] == "PASSED"
    assert result.metadata["passed_count"] == 2
    assert result.metadata["failed_count"] == 0
    assert result.metadata["defects_reported"] == 0

    # 2. Verify database records
    test_run = db.query(TestRunORM).filter_by(project_id=proj.id).first()
    assert test_run is not None
    assert test_run.status == "PASSED"
    assert test_run.passed_count == 2
    assert test_run.failed_count == 0

    results = db.query(TestResultORM).filter_by(test_run_id=test_run.id).all()
    assert len(results) == 2
    assert all(r.status == "PASSED" for r in results)


@pytest.mark.asyncio
async def test_qa_flow_defect_detection_and_remediation_trigger(qa_flow_env):
    db, proj, task, execution, workspace = qa_flow_env

    resolver = LLMProviderResolver(litellm_adapter=MockQAGateway(fail_contract=True))
    tracker = TokenTrackerService(db=db)
    agent = QAEngineerAgent(resolver=resolver, tracker=tracker, db=db)

    ctx = AgentContext(
        project_id=proj.id,
        task_id=task.id,
        agent_execution_id=execution.id,
        workspace_path=workspace,
    )

    result = await agent.execute(ctx, "Evaluate Calculation API endpoints.")

    # 1. Verify failed result
    assert result.success is False
    assert result.metadata["overall_status"] == "FAILED"
    assert result.metadata["passed_count"] == 1
    assert result.metadata["failed_count"] == 1
    assert result.metadata["defects_reported"] == 1

    # 2. Verify Defect ticket created in database assigned to Agent 3
    defect = db.query(DefectORM).filter_by(project_id=proj.id, status="OPEN").first()
    assert defect is not None
    assert defect.severity == "HIGH"
    assert defect.assigned_agent == AgentType.MAIN_CODING.value
    assert "UT-01" in defect.description
    assert "calculation_id" in defect.description
