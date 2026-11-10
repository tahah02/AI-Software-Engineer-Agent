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
        return f"""You are Agent 1: Senior Lead Architect, Documentation Reviewer & Specification Creator.

YOUR HIGHEST PRIORITY DIRECTIVES:
1. Ingest and thoroughly analyze the user's requirements, architectural briefs, uploaded specifications, and requested revisions/corrections.
2. STACK COMPLIANCE:
   - Strictly adhere to the technology stack explicitly requested by the user: ASP.NET Core Web API, C#, EF Core, SQLite, FastAPI, Next.js, or {framework}.
   - Never replace or convert to an unauthorized stack.
3. EXHAUSTIVE SPECIFICATION REQUIREMENT (DO NOT SUMMARIZE OR ABBREVIATE):
   - You MUST generate exhaustive, production-grade, fully written-out documentation.
   - DO NOT use placeholder bullets, ellipses ("..."), or abbreviated outlines.
   - Every single required correction or design directive provided by the user MUST be fully written out in the output documents.
"""

    def get_tools(self) -> list[ToolDefinition]:
        return [get_file_write_tool()]

    @staticmethod
    def _clean_markdown(text: str) -> str:
        s = text.strip()
        if s.startswith("```markdown"):
            s = s[11:]
        elif s.startswith("```md"):
            s = s[5:]
        elif s.startswith("```"):
            s = s[3:]
        if s.endswith("```"):
            s = s[:-3]
        return s.strip()

    async def execute(self, context: AgentContext, input_text: str) -> AgentResult:
        # Check if existing specifications exist for iterative refinement
        existing_tdd = ""
        existing_tdd_path = Path(context.workspace_path) / "docs" / "TECHNICAL_DESIGN.md"
        if existing_tdd_path.exists():
            try:
                existing_tdd = existing_tdd_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(f"Could not read existing technical design: {e}")

        existing_test_spec = ""
        existing_test_spec_path = Path(context.workspace_path) / "docs" / "XUNIT_TEST_SPEC.md"
        if existing_test_spec_path.exists():
            try:
                existing_test_spec = existing_test_spec_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(f"Could not read existing test spec: {e}")

        resolved_config = self.resolver.resolve_agent_config(
            session=self.db,
            project_id=context.project_id,
            agent=self.agent_type,
        )
        adapter = resolved_config.adapter

        framework = context.target_framework or "DOTNET_CSHARP"

        # Pass 1: Generate exhaustive TECHNICAL_DESIGN.md in pure Markdown
        tdd_user_content = input_text
        if existing_tdd:
            tdd_user_content = (
                f"## Current Technical Design on Disk:\n\n{existing_tdd}\n\n"
                f"## MANDATORY USER REVISION REQUEST & REQUIRED CORRECTIONS:\n\n{input_text}\n\n"
                f"Update and expand docs/TECHNICAL_DESIGN.md to incorporate every single requested correction. Do NOT abbreviate."
            )

        prompt_tdd = (
            f"You are a Principal Enterprise Software Architect.\n"
            f"Generate the complete, exhaustive, production-grade Technical Design Document (docs/TECHNICAL_DESIGN.md) for {framework}.\n\n"
            f"### Authoritative Requirements Specification (SRS) & Directives:\n{tdd_user_content}\n\n"
            f"CRITICAL ARCHITECTURAL DIRECTIVES:\n"
            f"1. Treat the provided SRS as the ABSOLUTE SINGLE SOURCE OF TRUTH. Strictly adhere ONLY to the entities, endpoints, database schema, functional requirements (FR), and security rules defined in the SRS above. DO NOT inject foreign entities or endpoints from any previous or unrelated projects.\n"
            f"2. MANDATORY SECTIONS TO WRITE OUT FULLY:\n"
            f"   - 1. System Architecture & Component Design (Layered pattern appropriate for {framework}, DI registrations, async flow)\n"
            f"   - 2. Database Design & Domain Model (All entity fields, types, constraints, indexes, ORM migrations, persistence lifecycle strictly per SRS)\n"
            f"   - 3. API Specifications (Exact endpoints, HTTP methods, request/response DTOs, payload constraints, status codes, RFC 9457 Problem Details strictly per SRS)\n"
            f"   - 4. Security, Authentication & Authorization (Authentication scheme, permissions/claims, identity context as specified in SRS)\n"
            f"   - 5. Audit & Validation Rules (Field lifecycle, validation rules, normalization strictly per SRS)\n"
            f"   - 6. Production Readiness (Rate limiting, structured logging, correlation IDs, health checks)\n"
            f"   - 7. Git Workflow & Branching Strategy\n"
            f"   - 8. Requirement Traceability Matrix (Mapping every FR-xx and NFR-xx from the SRS)\n\n"
            f"Output pure Markdown only. Do not wrap in JSON."
        )

        request_tdd = LLMRequest(
            provider=resolved_config.provider,
            model=resolved_config.model,
            fallback_provider=resolved_config.fallback_provider,
            fallback_model=resolved_config.fallback_model,
            messages=[
                {"role": "system", "content": self.get_system_prompt(context)},
                {"role": "user", "content": prompt_tdd},
            ],
            temperature=0.2,
            max_tokens=8000,
        )

        response_tdd = await adapter.complete(request_tdd)
        tech_design = self._clean_markdown(response_tdd.content)

        if self.tracker and context.agent_execution_id:
            try:
                self.tracker.record_invocation(
                    agent_execution_id=context.agent_execution_id,
                    provider=resolved_config.provider,
                    model_name=resolved_config.model,
                    latency_ms=response_tdd.latency_ms,
                    success=True,
                    response=response_tdd,
                )
            except Exception as e:
                logger.warning(f"Could not track tokens for TDD: {e}")

        # Pass 2: Generate exhaustive XUNIT_TEST_SPEC.md in pure Markdown
        prompt_test = (
            f"You are a Principal Lead QA Architect specializing in testing and contract verification for {framework}.\n"
            f"Based on the following Technical Design and original SRS, generate the complete, exhaustive Test Specification document (docs/XUNIT_TEST_SPEC.md).\n\n"
            f"### Technical Design Reference:\n{tech_design[:6000]}\n\n"
            f"### Authoritative Requirements Specification (SRS) & Test Criteria:\n{input_text}\n\n"
            f"CRITICAL TEST SPECIFICATION RULES:\n"
            f"1. Treat the SRS and Technical Design as the STRICT SINGLE SOURCE OF TRUTH.\n"
            f"2. Extract and preserve the EXACT Test Identifiers (e.g. UT-01..UT-xx, IT-01..IT-xx) and functional scope directly from the SRS. If the SRS specifies specific test cases or IDs, you MUST use those exact IDs and descriptions. NEVER inject unrelated test cases or entities from external domains.\n"
            f"3. Output pure Markdown only. Do not wrap in JSON.\n"
            f"4. DO NOT output just an outline, summary table, or placeholder ellipses. You MUST individually write out a dedicated detailed subsection for EVERY SINGLE test case with:\n"
            f"   - Test ID & Descriptive Name (matching SRS IDs)\n"
            f"   - Requirement Traced (FR-xx / NFR-xx)\n"
            f"   - Preconditions & Mock Configuration\n"
            f"   - Input Payload / Test Data\n"
            f"   - Execution Steps\n"
            f"   - Expected Result & Exact Assertions\n"
            f"   - Database / State Verification\n"
            f"5. Specify the exact test runner execution command (e.g. `dotnet test --configuration Release` or `pytest`)."
        )

        request_test = LLMRequest(
            provider=resolved_config.provider,
            model=resolved_config.model,
            fallback_provider=resolved_config.fallback_provider,
            fallback_model=resolved_config.fallback_model,
            messages=[
                {"role": "system", "content": "You are a Principal Lead QA Architect specializing in xUnit testing and contract verification."},
                {"role": "user", "content": prompt_test},
            ],
            temperature=0.2,
            max_tokens=8000,
        )

        response_test = await adapter.complete(request_test)
        test_spec = self._clean_markdown(response_test.content)

        if self.tracker and context.agent_execution_id:
            try:
                self.tracker.record_invocation(
                    agent_execution_id=context.agent_execution_id,
                    provider=resolved_config.provider,
                    model_name=resolved_config.model,
                    latency_ms=response_test.latency_ms,
                    success=True,
                    response=response_test,
                )
            except Exception as e:
                logger.warning(f"Could not track tokens for Test Spec: {e}")

        # Stack detection
        detected_stack = None
        lower_tdd = tech_design.lower()
        if any(w in lower_tdd for w in ["asp.net", ".net 8", "c#", "xunit"]):
            detected_stack = "DOTNET_CSHARP"
        elif any(w in lower_tdd for w in ["fastapi", "pydantic", "pytest"]):
            detected_stack = "PYTHON_FASTAPI"
        elif any(w in lower_tdd for w in ["next.js", "nextjs", "react", "typescript"]):
            detected_stack = "TYPESCRIPT_NEXTJS"

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
