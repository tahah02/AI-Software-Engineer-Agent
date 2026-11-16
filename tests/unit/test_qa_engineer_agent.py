import json
import shutil
import tempfile
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


class FakeQALLMAdapter(ILLMGateway):
    def __init__(self, simulate_failure: bool = False):
        self.simulate_failure = simulate_failure

    async def complete(self, request: LLMRequest) -> LLMResponse:
        if self.simulate_failure:
            data = {
                "test_results": [
                    {
                        "test_key": "TC01",
                        "category": "CONTRACT",
                        "endpoint": "/api/v1/auth/login",
                        "http_method": "POST",
                        "expected_status": 200,
                        "actual_status": 500,
                        "status": "FAILED",
                        "severity": "CRITICAL",
                        "details": "Internal server error on database connection",
                    }
                ],
                "overall_summary": "1 test failed.",
            }
        else:
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
                        "details": "Contract schema matches successfully",
                    }
                ],
                "test_files": {
                    "channel-app.Tests/channel-app.Tests.csproj": "<Project Sdk=\"Microsoft.NET.Sdk\"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup><ItemGroup><PackageReference Include=\"Microsoft.NET.Test.Sdk\" Version=\"17.8.0\"/><PackageReference Include=\"xunit\" Version=\"2.6.2\"/><PackageReference Include=\"xunit.runner.visualstudio\" Version=\"2.5.4\"/></ItemGroup></Project>",
                    "channel-app.Tests/UnitTests.cs": "using Xunit;\npublic class DummyTests { [Fact] public void Test1() => Assert.True(true); }",
                },
                "overall_summary": "All tests passed.",
            }

        return LLMResponse(
            provider=request.provider,
            model=request.model or "fake-qa-model",
            finish_reason="stop",
            content=json.dumps(data),
            usage=TokenUsage(prompt_tokens=300, completion_tokens=100, total_tokens=400),
            latency_ms=150,
        )

    async def list_models(self, provider: LLMProvider) -> list[str]:
        return ["fake-qa-model"]


@pytest.fixture
def qa_setup():
    tmp = tempfile.mkdtemp(prefix="aaise_agent4_test_")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    project = ProjectORM(name="QA Test Project", target_framework="fastapi")
    session.add(project)
    session.flush()

    config = ProjectAgentConfigORM(
        project_id=project.id,
        agent_type=AgentType.QA_ENGINEER.value,
        is_enabled=True,
        provider="groq",
        model_name="openai/gpt-oss-120b",
    )
    session.add(config)

    task = AgentTaskORM(
        project_id=project.id,
        agent_name="Agent 4: Independent QA Engineer",
        task_type="QA_VERIFICATION",
    )
    session.add(task)
    session.flush()

    execution = AgentExecutionORM(agent_task_id=task.id)
    session.add(execution)
    session.commit()

    # Place an XUnit Test Specification in workspace
    spec_content = "# XUnit Test Specification\n\n- TC01: POST /api/v1/auth/login expects 200"
    execute_file_write(tmp, "docs/XUNIT_TEST_SPEC.md", spec_content)

    yield session, project, task, execution, tmp

    session.close()
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.asyncio
async def test_qa_agent_executes_specs_and_records_passed_run(qa_setup):
    session, project, task, execution, tmp = qa_setup

    resolver = LLMProviderResolver(litellm_adapter=FakeQALLMAdapter(simulate_failure=False))
    tracker = TokenTrackerService(db=session)

    agent = QAEngineerAgent(resolver=resolver, tracker=tracker, db=session)

    context = AgentContext(
        project_id=project.id,
        task_id=task.id,
        agent_execution_id=execution.id,
        workspace_path=tmp,
    )

    result = await agent.execute(context, "Verify contract conformance.")

    assert result.success is True
    assert result.metadata["overall_status"] == "PASSED"
    assert result.metadata["passed_count"] == 1
    assert result.metadata["failed_count"] == 0

    # Verify database persistence
    test_run = session.query(TestRunORM).filter_by(project_id=project.id).first()
    assert test_run is not None
    assert test_run.status == "PASSED"
    assert test_run.passed_count == 1

    res = session.query(TestResultORM).filter_by(test_run_id=test_run.id).first()
    assert res is not None
    assert res.status == "PASSED"


@pytest.mark.asyncio
async def test_qa_agent_records_failure_and_creates_defect(qa_setup):
    session, project, task, execution, tmp = qa_setup

    resolver = LLMProviderResolver(litellm_adapter=FakeQALLMAdapter(simulate_failure=True))
    tracker = TokenTrackerService(db=session)

    agent = QAEngineerAgent(resolver=resolver, tracker=tracker, db=session)

    context = AgentContext(
        project_id=project.id,
        task_id=task.id,
        agent_execution_id=execution.id,
        workspace_path=tmp,
    )

    result = await agent.execute(context, "Verify contract conformance.")

    assert result.success is False
    assert result.metadata["overall_status"] == "FAILED"
    assert result.metadata["failed_count"] == 1
    assert result.metadata["defects_reported"] == 1

    # Verify DefectORM created
    defect = session.query(DefectORM).filter_by(project_id=project.id).first()
    assert defect is not None
    assert defect.status == "OPEN"
    assert defect.severity == "CRITICAL"
    assert "TC01" in defect.description


@pytest.mark.asyncio
async def test_qa_agent_scaffolds_physical_xunit_test_project(qa_setup):
    session, project, task, execution, tmp = qa_setup

    resolver = LLMProviderResolver(litellm_adapter=FakeQALLMAdapter(simulate_failure=False))
    tracker = TokenTrackerService(db=session)

    agent = QAEngineerAgent(resolver=resolver, tracker=tracker, db=session)

    # Create dummy channel-app directory with valid target framework
    channel_dir = Path(tmp) / "channel-app"
    channel_dir.mkdir(parents=True, exist_ok=True)
    (channel_dir / "channel-app.csproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk.Web\"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>",
        encoding="utf-8"
    )

    context = AgentContext(
        project_id=project.id,
        task_id=task.id,
        agent_execution_id=execution.id,
        workspace_path=tmp,
        target_framework="csharp",
    )

    result = await agent.execute(context, "Verify contract conformance.")

    assert result.success is True
    # Verify physical test project files created dynamically
    tests_dir = Path(tmp) / "channel-app.Tests"
    assert tests_dir.exists()
    assert (tests_dir / "channel-app.Tests.csproj").exists()
    assert (tests_dir / "UnitTests.cs").exists()
    assert len(result.artifacts_created) >= 2


def test_qa_agent_parses_real_trx_results(tmp_path):
    trx_xml = """<?xml version="1.0" encoding="utf-8"?>
<TestRun id="123" name="TestRun" xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010">
  <Results>
    <UnitTestResult executionId="e1" testName="ChannelApp.Tests.UnitTests.UT_01_NameValidation" outcome="Passed" duration="00:00:00.0150000" />
    <UnitTestResult executionId="e2" testName="ChannelApp.Tests.IntegrationTests.IT_01_CreateStudent_Returns201" outcome="Passed" duration="00:00:00.0850000" />
    <UnitTestResult executionId="e3" testName="ChannelApp.Tests.IntegrationTests.IT_02_DuplicateEmail_Returns409" outcome="Failed" duration="00:00:00.0450000">
      <Output>
        <ErrorInfo>
          <Message>Assert.Equal() Failure: Expected 409, Actual 200</Message>
        </ErrorInfo>
      </Output>
    </UnitTestResult>
  </Results>
</TestRun>
"""
    trx_file = tmp_path / "test_results.trx"
    trx_file.write_text(trx_xml, encoding="utf-8")

    parsed = QAEngineerAgent._parse_trx_file(trx_file)

    assert len(parsed) == 3
    # Check UT-01
    assert parsed[0]["test_key"] == "UT-01"
    assert parsed[0]["category"] == "UNIT_TEST"
    assert parsed[0]["status"] == "PASSED"
    assert parsed[0]["duration"] == "15ms"

    # Check IT-01
    assert parsed[1]["test_key"] == "IT-01"
    assert parsed[1]["category"] == "INTEGRATION_TEST"
    assert parsed[1]["status"] == "PASSED"

    # Check IT-02 failure
    assert parsed[2]["test_key"] == "IT-02"
    assert parsed[2]["category"] == "INTEGRATION_TEST"
    assert parsed[2]["status"] == "FAILED"
    assert "Expected 409, Actual 200" in parsed[2]["details"]
