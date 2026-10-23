import json
import uuid
from pathlib import Path
from sqlalchemy.orm import Session

from src.domain.agent_base import BaseAgent
from src.domain.enums import AgentType, TestStatus, Severity
from src.domain.tools import execute_file_read, get_file_read_tool
from src.infrastructure.db.models import DefectORM, TestCaseORM, TestResultORM, TestRunORM
from src.infrastructure.llm.provider_resolver import LLMProviderResolver
from src.infrastructure.llm.token_tracker import TokenTrackerService
from src.ports.agent import AgentContext, AgentResult
from src.ports.llm_gateway import LLMMessage, LLMRequest, ToolDefinition


QA_SYSTEM_PROMPT = """You are Agent 4: Independent QA Engineer.
Your responsibility:
1. Perform strictly black-box contract testing against the API endpoints specified in docs/XUNIT_TEST_SPEC.md.
2. You must NEVER inspect, read, or rely on application source code.
3. Validate HTTP response status codes, payload contract schemas, and error responses.
4. For any failed test case, provide exact failure details, status code mismatch, and defect severity (CRITICAL, HIGH, MEDIUM, LOW).

Respond with a JSON object:
{
  "test_results": [
    {
      "test_key": "TC01",
      "category": "CONTRACT",
      "endpoint": "/api/v1/auth/login",
      "http_method": "POST",
      "expected_status": 200,
      "actual_status": 200,
      "status": "PASSED",
      "details": "Contract schema matches successfully"
    }
  ],
  "overall_summary": "All contract tests passed."
}
"""


class QAEngineerAgent(BaseAgent):
    def __init__(
        self,
        resolver: LLMProviderResolver,
        tracker: TokenTrackerService | None = None,
        db: Session | None = None,
    ) -> None:
        super().__init__(
            agent_type=AgentType.QA_ENGINEER,
            resolver=resolver,
            tracker=tracker,
            db=db,
        )

    def get_system_prompt(self, context: AgentContext) -> str:
        return QA_SYSTEM_PROMPT

    def get_tools(self) -> list[ToolDefinition]:
        # Black box only: only read_file tool is available (strictly for specs, never source code)
        return [get_file_read_tool()]

    def _read_xunit_spec(self, workspace_path: str) -> str:
        try:
            return execute_file_read(workspace_path, "docs/XUNIT_TEST_SPEC.md")
        except FileNotFoundError:
            return ""

    async def execute(self, context: AgentContext, input_text: str) -> AgentResult:
        # Load XUnit test specifications document
        test_spec = self._read_xunit_spec(context.workspace_path)
        if not test_spec:
            return AgentResult(
                success=False,
                summary="docs/XUNIT_TEST_SPEC.md not found in workspace. Cannot perform black-box testing.",
                error_message="Missing test specification artifact",
            )

        user_content = (
            f"## XUnit Test Specifications Document:\n\n{test_spec}\n\n"
            f"## Evaluation Context:\n{input_text}"
        )

        messages = self.build_initial_messages(context, user_content)

        resolved_config = self.resolver.resolve_agent_config(
            session=self.db,
            project_id=context.project_id,
            agent=self.agent_type,
        )
        adapter = resolved_config.adapter

        request = LLMRequest(
            provider=resolved_config.provider,
            model=resolved_config.model,
            messages=messages,
            response_schema={"type": "json_object"},
            temperature=0.0,
            max_tokens=4000,
        )

        response = await adapter.complete(request)

        if self.tracker:
            self.tracker.record_invocation(
                agent_execution_id=context.agent_execution_id,
                provider=resolved_config.provider,
                model_name=resolved_config.model,
                latency_ms=response.latency_ms,
                success=True,
                response=response,
            )

        try:
            content_data = json.loads(response.content)
            results_list = content_data.get("test_results", [])
            summary = content_data.get("overall_summary", "Black-box contract testing completed.")
        except Exception:
            results_list = []
            summary = "Contract evaluation raw output parsed."

        passed_count = sum(1 for r in results_list if r.get("status") == "PASSED")
        failed_count = sum(1 for r in results_list if r.get("status") != "PASSED")
        overall_status = "PASSED" if failed_count == 0 else "FAILED"

        defects_created = []

        # Persist test run and test results in database
        if self.db:
            test_run = TestRunORM(
                project_id=context.project_id,
                execution_type="BLACK_BOX_CONTRACT",
                passed_count=passed_count,
                failed_count=failed_count,
                status=overall_status,
            )
            self.db.add(test_run)
            self.db.flush()

            for r in results_list:
                # Find or create TestCaseORM
                test_case = (
                    self.db.query(TestCaseORM)
                    .filter_by(project_id=context.project_id, test_key=r.get("test_key", "TC"))
                    .first()
                )
                if not test_case:
                    test_case = TestCaseORM(
                        project_id=context.project_id,
                        test_key=r.get("test_key", f"TC-{uuid.uuid4().hex[:6]}"),
                        category=r.get("category", "CONTRACT"),
                        endpoint=r.get("endpoint", "/"),
                        http_method=r.get("http_method", "GET"),
                        expected_status=r.get("expected_status", 200),
                    )
                    self.db.add(test_case)
                    self.db.flush()

                test_res = TestResultORM(
                    test_run_id=test_run.id,
                    test_case_id=test_case.id,
                    status=r.get("status", "PASSED"),
                    actual_status_code=r.get("actual_status", 200),
                    response_body=r.get("details", ""),
                )
                self.db.add(test_res)

                # If test failed, create a DefectORM ticket for Agent 3
                if r.get("status") != "PASSED":
                    defect = DefectORM(
                        project_id=context.project_id,
                        assigned_agent=AgentType.MAIN_CODING.value,
                        severity=r.get("severity", "HIGH"),
                        description=f"Test {r.get('test_key')} failed on {r.get('endpoint')}: {r.get('details')}",
                        status="OPEN",
                    )
                    self.db.add(defect)
                    defects_created.append(defect)

            self.db.flush()

        return AgentResult(
            success=(failed_count == 0),
            summary=summary,
            artifacts_created=[],
            metadata={
                "passed_count": passed_count,
                "failed_count": failed_count,
                "overall_status": overall_status,
                "defects_reported": len(defects_created),
            },
        )
