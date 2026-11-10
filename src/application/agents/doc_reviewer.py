import json
import logging
from pathlib import Path
from sqlalchemy.orm import Session

from src.domain.agent_base import BaseAgent
from src.domain.enums import AgentType
from src.domain.tools import execute_file_write, get_file_write_tool
from src.infrastructure.db.models import ProjectFileORM, ProjectORM
from src.infrastructure.llm.provider_resolver import LLMProviderResolver
from src.infrastructure.llm.token_tracker import TokenTrackerService
from src.ports.agent import AgentContext, AgentResult
from src.ports.llm_gateway import LLMRequest, ToolDefinition

logger = logging.getLogger(__name__)


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
        framework = context.target_framework or "DOTNET_CSHARP"
        return f"""You are Agent 1: Documentation Reviewer & Spec Creator.

YOUR HIGHEST PRIORITY DIRECTIVE:
1. Ingest and analyze the user's business requirements, architectural notes, uploaded PDF/text specifications, and technology stack.
2. STACK COMPLIANCE: If the user's document or prompt explicitly specifies a technology stack (for example: ASP.NET Core Web API, C#, Entity Framework Core, SQLite, FastAPI, Next.js, Rails), YOU MUST STRICTLY ADHERE TO THAT SPECIFIED STACK!
   - NEVER substitute, replace, or convert to a different technology stack than what the user's document explicitly requests.
   - If the user's document does not explicitly specify a stack, use the project target framework: {framework}.
3. Align the technical architecture and specifications strictly to the determined stack:
   - For DOTNET_CSHARP / ASP.NET: Specify an ASP.NET Core Web API with Controllers, Domain Models, Services, DTOs, EF Core DbContext, SQLite persistence, and Swagger.
   - For PYTHON_FASTAPI: Specify FastAPI routers, Pydantic schemas, SQLAlchemy models, and SQLite persistence.
   - For TYPESCRIPT_NEXTJS: Specify Next.js App Router route handlers, TypeScript types, server/client components, and state management.
   - For RUBY_RAILS: Specify a Rails API with Models, Controllers, and Migrations.
4. Generate two comprehensive, production-grade architectural artifacts:
   a) docs/TECHNICAL_DESIGN.md:
      - Complete system architecture and module boundaries strictly matching the determined tech stack.
      - Full data models with field types, constraints, and relationships.
      - Comprehensive table of all API endpoints (HTTP method, route, request payload JSON schema, response payload JSON schema, status codes, query parameters).
      - Core business logic rules, SLA calculations, validation constraints, and error codes.
      - Security requirements (auth headers, input sanitization, RBAC).
   b) docs/XUNIT_TEST_SPEC.md:
      - Complete black-box contract test specifications for the Independent QA Agent (Agent 4).
      - Test cases for every endpoint: Happy path, input validation/edge cases, error responses (400, 401, 404, 500).
      - Exact HTTP method, route, request headers/envelope, expected request payload, expected response status code, and JSON schema assertions.

Respond with a JSON object:
{{
  "target_framework": "DOTNET_CSHARP" | "PYTHON_FASTAPI" | "TYPESCRIPT_NEXTJS" | "RUBY_RAILS",
  "technical_design": "# Technical Design Document\n\n## 1. System Architecture...\n\n## 2. Domain Models & Schemas...\n\n## 3. API Route Specifications...\n\n## 4. Business Logic & Validation...",
  "test_spec": "# XUnit Test Specifications\n\n## 1. Contract Test Suite...\n\n## 2. Validation & Edge Cases...\n\n## 3. End-to-End Test Scenarios..."
}}
"""

    def get_tools(self) -> list[ToolDefinition]:
        return [get_file_write_tool()]

    async def execute(self, context: AgentContext, input_text: str) -> AgentResult:
        # Check if an existing Technical Design exists for iterative refinement
        existing_tdd = ""
        existing_tdd_path = Path(context.workspace_path) / "docs" / "TECHNICAL_DESIGN.md"
        if existing_tdd_path.exists():
            try:
                existing_tdd = existing_tdd_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(f"Could not read existing technical design: {e}")

        user_content = input_text
        if existing_tdd:
            user_content = (
                f"## Previous Technical Design Document (Iterative Revision):\n\n"
                f"{existing_tdd}\n\n"
                f"## New Requirements / Revision Directives:\n\n"
                f"{input_text}\n\n"
                f"Please update and refine docs/TECHNICAL_DESIGN.md and docs/XUNIT_TEST_SPEC.md to incorporate the new requirements while preserving all existing valid architectural sections."
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
            fallback_provider=resolved_config.fallback_provider,
            fallback_model=resolved_config.fallback_model,
            messages=messages,
            response_schema={"type": "json_object"},
            temperature=0.1,
            max_tokens=8000,
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
        raw = response.content.strip()
        if raw.startswith("```json"):
            raw = raw[7:]
        elif raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        try:
            content_data = json.loads(raw)
            tech_design = content_data.get("technical_design", "# Technical Design\n")
            test_spec = content_data.get("test_spec", "# XUnit Test Specifications\n")
            detected_stack = content_data.get("target_framework")
        except Exception as e:
            logger.warning(f"Failed to parse JSON response from Agent 1: {e}")
            tech_design = f"# Technical Design\n\n{response.content}"
            test_spec = f"# XUnit Test Specifications\n\nGenerated for: {context.project_id}"
            detected_stack = None

        if self.db and detected_stack and detected_stack in ("DOTNET_CSHARP", "PYTHON_FASTAPI", "TYPESCRIPT_NEXTJS", "RUBY_RAILS"):
            proj = self.db.query(ProjectORM).filter_by(id=context.project_id).first()
            if proj and proj.target_framework != detected_stack:
                logger.info(f"Agent 1 aligned project target_framework from {proj.target_framework} to {detected_stack}")
                proj.target_framework = detected_stack
                context.target_framework = detected_stack
                self.db.commit()

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
                existing = (
                    self.db.query(ProjectFileORM)
                    .filter_by(project_id=context.project_id, file_type=ftype)
                    .first()
                )
                if existing:
                    existing.file_path = abs_path
                    existing.file_size_bytes = size
                else:
                    file_record = ProjectFileORM(
                        project_id=context.project_id,
                        file_name=Path(rel_path).name,
                        file_path=abs_path,
                        file_type=ftype,
                        file_size_bytes=size,
                    )
                    self.db.add(file_record)
            self.db.commit()

        return AgentResult(
            success=True,
            summary="Technical Design Document and XUnit Test Specifications generated successfully.",
            artifacts_created=[tech_path, test_path],
            metadata={
                "tech_design_length": len(tech_design),
                "test_spec_length": len(test_spec),
                "target_framework": context.target_framework,
            },
        )
