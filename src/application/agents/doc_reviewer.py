import json
from pathlib import Path
from sqlalchemy.orm import Session

from src.domain.agent_base import BaseAgent
from src.domain.enums import AgentType
from src.domain.tools import execute_file_write, get_file_write_tool
from src.infrastructure.db.models import ProjectFileORM
from src.infrastructure.llm.provider_resolver import LLMProviderResolver
from src.infrastructure.llm.token_tracker import TokenTrackerService
from src.ports.agent import AgentContext, AgentResult
from src.ports.llm_gateway import LLMMessage, LLMRequest, ToolDefinition


DOC_REVIEWER_SYSTEM_PROMPT = """You are Agent 1: Documentation Reviewer & Spec Creator.
Your responsibility:
1. Ingest business requirements and API specifications provided by the user.
2. Analyze all endpoints, payloads, validation rules, and error states.
3. Generate two mandatory architectural artifacts:
   a) docs/TECHNICAL_DESIGN.md: Complete technical design, module boundaries, database schemas, and request/response payloads for the Main Coding Agent (Agent 3).
   b) docs/XUNIT_TEST_SPEC.md: Complete XUnit test specifications document with all test cases (happy path, edge cases, error cases, status codes, payload assertions) for the Independent QA Agent (Agent 4).

Respond with a JSON object containing exact content for both files:
{
  "technical_design": "# Technical Design Document...",
  "test_spec": "# XUnit Test Specifications..."
}
"""


class DocumentationReviewerAgent(BaseAgent):
    def __init__(
        self,
        resolver: LLMProviderResolver,
        tracker: TokenTrackerService | None = None,
        db: Session | None = None,
    ) -> None:
        super().__init__(
            agent_type=AgentType.DOC_REVIEWER,
            resolver=resolver,
            tracker=tracker,
            db=db,
        )

    def get_system_prompt(self, context: AgentContext) -> str:
        return DOC_REVIEWER_SYSTEM_PROMPT

    def get_tools(self) -> list[ToolDefinition]:
        return [get_file_write_tool()]

    async def execute(self, context: AgentContext, input_text: str) -> AgentResult:
        messages = self.build_initial_messages(context, input_text)

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
            temperature=0.1,
            max_tokens=4000,
        )

        response = await adapter.complete(request)

        # Track tokens if tracker and db are provided
        if self.tracker:
            self.tracker.record_invocation(
                agent_execution_id=context.agent_execution_id,
                provider=resolved_config.provider,
                model_name=resolved_config.model,
                latency_ms=response.latency_ms,
                success=True,
                response=response,
            )

        # Parse generated documents
        try:
            content_data = json.loads(response.content)
            tech_design = content_data.get("technical_design", "# Technical Design\n")
            test_spec = content_data.get("test_spec", "# XUnit Test Specifications\n")
        except Exception:
            # Fallback if raw text returned
            tech_design = f"# Technical Design\n\n{response.content}"
            test_spec = f"# XUnit Test Specifications\n\nGenerated for: {context.project_id}"

        # Write files to workspace
        tech_path = "docs/TECHNICAL_DESIGN.md"
        test_path = "docs/XUNIT_TEST_SPEC.md"

        execute_file_write(context.workspace_path, tech_path, tech_design)
        execute_file_write(context.workspace_path, test_path, test_spec)

        # Track in database if db session provided
        if self.db:
            for rel_path, ftype in [(tech_path, "TECHNICAL_DESIGN"), (test_path, "TEST_SPECIFICATION")]:
                abs_path = str(Path(context.workspace_path) / rel_path)
                size = len((tech_design if "TECHNICAL" in ftype else test_spec).encode("utf-8"))
                file_record = ProjectFileORM(
                    project_id=context.project_id,
                    file_name=Path(rel_path).name,
                    file_path=abs_path,
                    file_type=ftype,
                    file_size_bytes=size,
                )
                self.db.add(file_record)
            self.db.flush()

        return AgentResult(
            success=True,
            summary="Technical Design Document and XUnit Test Specifications generated successfully.",
            artifacts_created=[tech_path, test_path],
            metadata={
                "tech_design_length": len(tech_design),
                "test_spec_length": len(test_spec),
            },
        )
