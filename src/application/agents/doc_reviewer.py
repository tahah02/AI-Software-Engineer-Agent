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
        is_incremental = context.additional_metadata.get("is_incremental", False)
        subsystem_framework = context.additional_metadata.get("subsystem_framework") or "TYPESCRIPT_NEXTJS"

        # A specification revision request is NEVER an incremental frontend extension
        is_revision = "Human Revision Request" in input_text or "Requested Changes" in input_text
        if is_revision:
            is_incremental = False

        # Pass 1: Generate or incrementally evolve TECHNICAL_DESIGN.md in pure Markdown
        if is_incremental and existing_tdd and not is_revision:
            prompt_tdd = (
                f"You are a Principal Enterprise Software Architect.\n"
                f"The project already has an authoritative backend architecture fully specified in docs/TECHNICAL_DESIGN.md:\n\n"
                f"### Existing Technical Design Document (MUST BE PRESERVED):\n{existing_tdd}\n\n"
                f"### NEW CLIENT / FRONTEND EXTENSION DIRECTIVE:\n{input_text}\n\n"
                f"CRITICAL INCREMENTAL ARCHITECTURE DIRECTIVES:\n"
                f"1. PRESERVE the existing backend sections (Sections 1 through 8) completely intact. DO NOT delete, shorten, or alter them.\n"
                f"2. APPEND a dedicated new section: `## Section 9: Client Interface Specification ({subsystem_framework})`.\n"
                f"3. In Section 9, write out:\n"
                f"   - Target Subsystem Directory: `frontend/` (isolated from backend in `channel-app/`)\n"
                f"   - Technology Stack: {subsystem_framework} (e.g. Next.js 15 App Router, React 19, TypeScript, Tailwind CSS)\n"
                f"   - Component & Page Hierarchy (layouts, views, forms, metric summary cards)\n"
                f"   - API Integration Mapping: Concrete endpoints mapping showing how each UI action/form calls the existing backend endpoints in Section 3\n"
                f"   - State Management & Validation (matching domain validation rules in Section 5)\n\n"
                f"Output pure Markdown containing the full document with Section 9 appended. Do NOT wrap in JSON."
            )
        else:
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
                f"3. NORMATIVE ENTERPRISE IMPLEMENTATION SPECIFICATIONS:\n"
                f"   - SQLite PRAGMA & Interceptor: Mandate 'SqlitePragmaInterceptor' (DbConnectionInterceptor) in EF Core configuration to strictly enforce PRAGMA foreign_keys = ON; and PRAGMA journal_mode = WAL; on every connection.\n"
                f"   - Reverse Proxy & Headers: Mandate app.UseForwardedHeaders() at the very top of Program.cs middleware pipeline.\n"
                f"   - Strict JSON & Duplicate Key Check: Mandate Utf8JsonReader duplicate-property validation or strict System.Text.Json options (JsonUnmappedMemberHandling.Disallow, JsonNumberHandling.Strict) to reject duplicate JSON keys with HTTP 400 Bad Request.\n"
                f"   - DateTime Persistence: Mandate explicit UTC roundtrip 'ValueConverter<DateTime, DateTime>' for all entity DateTime properties.\n"
                f"   - Unicode Counting: Validate string length boundaries using Unicode scalar counting (EnumerateRunes().Count()).\n"
                f"   - RFC 9457 Problem Details: Ensure all error responses including 400, 401, 403, 404, 409, 422, 500, 502, 503, 504 emit application/problem+json.\n"
                f"   - Permissions Claims: Support both scalar string and array permissions claims for required action permissions (e.g. 'resource:action').\n"
                f"   - External Vendor Scope: If the system has NO external third-party vendor APIs, explicitly state: 'Mock Vendor Server: Not Applicable / Excluded (Agent 2 Bypassed)'.\n\n"
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
            max_tokens=16000,
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
        if is_incremental and existing_test_spec and not is_revision:
            prompt_test = (
                f"You are a Principal Lead QA Architect specializing in client contract verification and integration testing for {subsystem_framework}.\n"
                f"The project already has an authoritative backend test specification in docs/XUNIT_TEST_SPEC.md:\n\n"
                f"### Existing Test Specification (MUST BE PRESERVED):\n{existing_test_spec}\n\n"
                f"### Technical Design Reference (with Section 9 Client Interface):\n{tech_design[:6000]}\n\n"
                f"CRITICAL INCREMENTAL TEST RULES:\n"
                f"1. PRESERVE all existing backend unit and integration tests (UT-xx, IT-xx) completely intact.\n"
                f"2. APPEND a dedicated section: `## Section 15: Client Interface Contract & Component Tests`.\n"
                f"3. Specify individual client component / UI integration test cases (e.g. UI-01, UI-02, UI-03) testing client form validation, API submission, and error state rendering.\n"
                f"4. Specify the client test execution command (e.g. `npm test` or `npm run lint`).\n\n"
                f"Output pure Markdown containing the full document with Section 15 appended."
            )
        else:
            test_user_content = input_text
            if existing_test_spec:
                test_user_content = (
                    f"## Current Test Specification on Disk:\n\n{existing_test_spec}\n\n"
                    f"## MANDATORY USER REVISION REQUEST & REQUIRED CORRECTIONS:\n\n{input_text}\n\n"
                    f"Update and expand docs/XUNIT_TEST_SPEC.md to incorporate every single requested correction. Apply all revisions explicitly."
                )

            prompt_test = (
                f"You are a Principal Lead QA Architect specializing in testing and contract verification for {framework}.\n"
                f"Based on the following Technical Design and original SRS, generate the complete, exhaustive Test Specification document (docs/XUNIT_TEST_SPEC.md).\n\n"
                f"### Technical Design Reference:\n{tech_design[:6000]}\n\n"
                f"### Authoritative Requirements Specification (SRS) & Test Directives:\n{test_user_content}\n\n"
                f"CRITICAL TEST SPECIFICATION RULES:\n"
                f"1. Treat the SRS and Technical Design as the STRICT SINGLE SOURCE OF TRUTH.\n"
                f"2. Extract and preserve ALL Test Identifiers directly from the SRS: unit tests (UT-01..UT-12), integration tests (IT-01..IT-14), and supplemental/edge compliance tests (EXT-01..EXT-12). NEVER omit, summarize, or inject foreign test cases.\n"
                f"3. Output pure Markdown only. Do not wrap in JSON.\n"
                f"4. MANDATORY CONCISE 4-PART SPECIFICATION STRUCTURE FOR EVERY TEST:\n"
                f"   Every single test case (UT-01 through UT-12, IT-01 through IT-14, AND EXT-01 through EXT-12) MUST be individually written out using this crisp 4-part structure:\n"
                f"   - **Test ID & Name:** [ID] — [Descriptive Title] (Traces: FR-xx / NFR-xx / AC-xx)\n"
                f"   - **Target & Preconditions:** Target component, endpoint, or validator with auth/mock state\n"
                f"   - **Input & Execution:** Exact payload, boundary values, or steps executed\n"
                f"   - **Expected Result & Assertions:** Exact HTTP status code, returned DTO / RFC 9457 error, and assertions\n"
                f"   Be precise, informative, and avoid repetitive decorative boilerplate so the entire specification fits cleanly. Cover all 38 tests completely without skipping any.\n"
                f"5. SPECIFIC NORMATIVE EDGE ASSERTIONS:\n"
                f"   - IT-03 & IT-14: Assert RFC 9457 errors keys use camelCase property names (fullName, email, age, department) and confirm invalid/sensitive values are NOT echoed back.\n"
                f"   - EXT-01: Test duplicate JSON property names and quoted/fractional age returning 400 Bad Request.\n"
                f"   - EXT-03 & EXT-04: Assert middleware precedence (413 Payload Too Large enforced before JSON parsing; 415 Unsupported Media Type on authenticated requests).\n"
                f"   - EXT-07: Test non-BMP Unicode characters (emojis/surrogate pairs) at 1, 2, 100, 101 Unicode scalar boundaries.\n"
                f"6. Include the complete Requirements Traceability Matrix covering all Functional Requirements (FR), Non-Functional Requirements (NFR), and Acceptance Criteria (AC).\n"
                f"7. Specify the exact test runner execution command (e.g. `dotnet test --configuration Release` or `pytest`)."
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
            max_tokens=16000,
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

        # Stack detection: Only align project framework if not an incremental extension
        if not is_incremental:
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
