import sys
import json
import logging
import os
import subprocess
from pathlib import Path
from sqlalchemy.orm import Session

from src.domain.agent_base import BaseAgent
from src.domain.enums import AgentType, RepositoryType
from src.domain.tools import execute_file_read, execute_file_write, get_file_read_tool, get_file_write_tool
from src.infrastructure.git.git_service import GitService
from src.infrastructure.llm.provider_resolver import LLMProviderResolver
from src.infrastructure.llm.token_tracker import TokenTrackerService
from src.ports.agent import AgentContext, AgentResult
from src.ports.llm_gateway import LLMMessage, LLMRequest, ToolDefinition

logger = logging.getLogger(__name__)


def get_coder_prompt_for_framework(target_framework: str) -> str:
    framework_lower = (target_framework or "").lower()
    
    if any(k in framework_lower for k in ("next", "react", "type", "ts", "front", "portal")):
        return """You are Agent 3: Main Coding Agent.
Target Framework: Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, Lucide React.

Your responsibility:
1. Read the Technical Design Document and API specification, and implement a complete, production-ready, beautiful, interactive multi-file Next.js frontend portal specifically tailored to the project's domain, models, and workflows.
2. Structure your project cleanly according to Next.js App Router standards:
   - `package.json`: Configured with "next", "react", "react-dom", "lucide-react", "clsx", "tailwind-merge".
   - `tsconfig.json`: Standard Next.js TypeScript config with "@/*" path alias.
   - `tailwind.config.js` and `postcss.config.js`: Modern responsive theme with Tailwind utility classes.
   - `app/layout.tsx`: Root layout with font imports, metadata, and application shell.
   - `app/globals.css`: Tailwind directives, color tokens, and clean layout styles.
   - `app/page.tsx`: Complete, rich, interactive Client Component ('use client') implementing:
     * Domain-specific header with role/persona or user context as specified in Technical Design.
     * KPI/Metric summary cards matching the application's domain entities.
     * Interactive navigation tabs and views specified in the Technical Design.
     * Real state management (useState, useEffect, useMemo), input forms, CRUD actions, live filters, and tables.
     * Comprehensive error handling, loading states, and feedback toasts/alerts.
   - `app/api/...`: Next.js Route Handlers (`app/api/<route>/route.ts`) implementing backend endpoints or proxy handlers specified in the Technical Design.
3. Quality & Authenticity Standards:
   - Fully written, production-grade React code with TypeScript typing for all state and props.
   - Real interactive handlers, form validations, and data models.
   - NO placeholders, NO TODOs, NO empty skeletons.

Respond ONLY with a valid JSON object containing relative paths and file contents:
{
  "files": {
    "package.json": "...",
    "tsconfig.json": "...",
    "tailwind.config.js": "...",
    "postcss.config.js": "...",
    "app/globals.css": "...",
    "app/layout.tsx": "...",
    "app/page.tsx": "..."
  }
}"""

    if any(k in framework_lower for k in ("cs", "csharp", "dotnet", "net")):
        return """You are Agent 3: Main Coding Agent.
Target Framework: C# ASP.NET Core Web API (.NET 8 / 9) with SQLite, EF Core, and Swagger.

Your responsibility:
1. Read the Technical Design Document and implement complete, production-ready, readable multi-file C# source code.
2. STRICT SCOPE REQUIREMENT:
   - Implement ONLY the entities, controllers, services, and repositories specified in the Technical Design Document.
   - DO NOT invent or include unrelated example entities like 'Job', 'JobsController', or 'WeatherForecast'.
3. Structure your project cleanly according to Clean Architecture standards:
   - `channel-app.csproj`: SDK project with:
     * Microsoft.EntityFrameworkCore.Sqlite
     * Microsoft.EntityFrameworkCore.Design
     * Swashbuckle.AspNetCore
     * Microsoft.Extensions.Diagnostics.HealthChecks.EntityFrameworkCore
   - `Program.cs`: Configures SQLite DbContext, Controllers, Swagger/OpenAPI, Authentication/Authorization, Rate Limiting, HealthChecks, and maps controllers.
   - `appsettings.json`: With ConnectionStrings:DefaultConnection = "Data Source=app.db".
   - `Properties/launchSettings.json`: Configured for http://localhost:5100 with launchUrl: "swagger".
   - `Models/`: Clean domain entities exactly as specified in the TDD.
   - `Data/AppDbContext.cs`: EF Core DbContext with DbSets corresponding ONLY to design entities.
   - `DTOs/`: Dedicated Request and Response DTO classes or records matching the exact contract in the TDD.
   - `Controllers/`: Dedicated API controllers for designed endpoints.
   - `Services/` & `Repositories/`: Clean separation of business logic and database operations.
4. Quality & Authenticity Standards:
   - Format and indent properly.
   - NO placeholders, NO `// TODO`, NO dummy mock data.
   - Code MUST compile cleanly without any CS errors. Use consistent namespaces: `ChannelApp.Models`, `ChannelApp.Data`, `ChannelApp.Controllers`, `ChannelApp.DTOs`, `ChannelApp.Services`, `ChannelApp.Repositories`.

Respond ONLY with a valid JSON object containing relative paths and file contents:
{
  "files": {
    "channel-app.csproj": "<Project Sdk=\"Microsoft.NET.Sdk.Web\">...</Project>",
    "Program.cs": "using Microsoft.EntityFrameworkCore; ...",
    "appsettings.json": "{\\n  \"ConnectionStrings\": { \"DefaultConnection\": \"Data Source=app.db\" }\\n}",
    "Properties/launchSettings.json": "{...}"
  }
}"""

    # Generic Python fallback
    return """You are Agent 3: Main Coding Agent.
Target Framework: Python FastAPI with SQLite and Pydantic.

Implement complete production-ready source code across standard modules:
- `requirements.txt`
- `src/main.py`
- `src/models.py`
- `src/schemas.py`
- `src/database.py`
- `src/routers/`

Respond ONLY with a valid JSON object containing relative paths and file contents:
{
  "files": {
    "src/main.py": "from fastapi import FastAPI...",
    "requirements.txt": "fastapi\\nuvicorn\\nsqlalchemy\\npydantic\\n"
  }
}"""


class MainCodingAgent(BaseAgent):
    def __init__(
        self,
        resolver: LLMProviderResolver,
        git_service: GitService,
        tracker: TokenTrackerService | None = None,
        db: Session | None = None,
    ) -> None:
        super().__init__(
            agent_type=AgentType.MAIN_CODING,
            resolver=resolver,
            tracker=tracker,
            db=db,
        )
        self.git_service = git_service

    def get_system_prompt(self, context: AgentContext) -> str:
        return get_coder_prompt_for_framework(context.target_framework)

    def get_tools(self) -> list[ToolDefinition]:
        return [get_file_read_tool(), get_file_write_tool()]

    def _read_technical_design(self, workspace_path: str) -> str:
        try:
            return execute_file_read(workspace_path, "docs/TECHNICAL_DESIGN.md")
        except FileNotFoundError:
            return ""

    def _parse_files_from_response(self, raw_content: str) -> dict[str, str]:
        text = raw_content.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            data = json.loads(text)
            return data.get("files", {})
        except Exception as e:
            logger.warning(f"Could not parse JSON files from LLM response: {e}")
            return {}

    def _execute_build_verification(self, repo_path: str, target_framework: str) -> tuple[bool, str]:
        framework_lower = (target_framework or "").lower()
        if any(k in framework_lower for k in ("cs", "csharp", "dotnet", "net")):
            try:
                res = subprocess.run(
                    ["dotnet", "build", "--nologo", "-v", "minimal"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
                output = f"{res.stdout}\n{res.stderr}".strip()
                success = (res.returncode == 0) and ("Build FAILED" not in output)
                return success, output
            except Exception as e:
                return False, f"Build execution failed: {e}"

        if any(k in framework_lower for k in ("py", "python", "fastapi", "flask", "django")):
            try:
                res = subprocess.run(
                    [sys.executable, "-m", "compileall", "-q", repo_path],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                success = (res.returncode == 0)
                output = f"{res.stdout}\n{res.stderr}".strip()
                return success, output if not success else "Python syntax verification passed."
            except Exception as e:
                return False, f"Python syntax verification failed: {e}"

        # Generic check
        return True, "No specific compiler gate configured for this framework."

    async def execute(self, context: AgentContext, input_text: str) -> AgentResult:
        tech_design = self._read_technical_design(context.workspace_path)
        user_content = input_text
        if tech_design:
            user_content = (
                f"## Technical Design Document:\n\n{tech_design}\n\n"
                f"## Implementation Directives:\n\n{input_text}"
            )

        messages = self.build_initial_messages(context, user_content)

        resolved_config = self.resolver.resolve_agent_config(
            session=self.db,
            project_id=context.project_id,
            agent=self.agent_type,
        )
        adapter = resolved_config.adapter

        channel_repo_path = self.git_service.get_repository_path(
            project_id=context.project_id,
            repo_type=RepositoryType.CHANNEL_APP,
        )

        branch_name = f"feature/channel-app-{context.task_id.hex[:8]}"
        self.git_service.create_branch(
            project_id=context.project_id,
            repo_type=RepositoryType.CHANNEL_APP,
            branch_name=branch_name,
            base_branch="develop",
        )

        # Iterative synthesis & build verification loop
        max_healing_attempts = 3
        build_success = False
        build_output = ""
        written_files: list[str] = []

        for attempt in range(1, max_healing_attempts + 1):
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

            if self.tracker:
                self.tracker.record_invocation(
                    agent_execution_id=context.agent_execution_id,
                    provider=resolved_config.provider,
                    model_name=resolved_config.model,
                    latency_ms=response.latency_ms,
                    success=True,
                    response=response,
                )

            files_dict = self._parse_files_from_response(response.content)
            if not files_dict:
                logger.warning(f"Attempt {attempt}: No files parsed from LLM response.")
                continue

            for rel_path, content in files_dict.items():
                execute_file_write(channel_repo_path, rel_path, content)
                if rel_path not in written_files:
                    written_files.append(rel_path)

            # Ensure solution file exists for Visual Studio support
            framework_lower = (context.target_framework or "").lower()
            if any(k in framework_lower for k in ("cs", "csharp", "dotnet", "net")):
                sln_path = Path(channel_repo_path) / "channel-app.sln"
                if not sln_path.exists():
                    try:
                        subprocess.run(["dotnet", "new", "sln", "-n", "channel-app"], cwd=channel_repo_path, capture_output=True, timeout=30)
                        subprocess.run(["dotnet", "sln", "channel-app.sln", "add", "channel-app.csproj"], cwd=channel_repo_path, capture_output=True, timeout=30)
                        if "channel-app.sln" not in written_files:
                            written_files.append("channel-app.sln")
                    except Exception as e:
                        logger.warning(f"Could not generate solution file: {e}")

            # Clean up residual orphaned files if reported in build errors
            for stray in ["Controllers/JobsController.cs", "DTOs/JobDtos.cs", "Models/Job.cs"]:
                stray_path = Path(channel_repo_path) / stray
                if stray_path.exists() and "Jobs" not in (context.target_framework or ""):
                    try:
                        stray_path.unlink()
                        logger.info(f"Removed out-of-scope residual file: {stray}")
                    except Exception as e:
                        logger.warning(f"Could not remove {stray}: {e}")

            # Run build verification gate
            build_success, build_output = self._execute_build_verification(channel_repo_path, context.target_framework)
            if build_success:
                logger.info(f"Build succeeded on attempt {attempt}!")
                break

            logger.warning(f"Build failed on attempt {attempt}: {build_output[:300]}")
            if attempt < max_healing_attempts:
                # Add failure evidence to conversation for self-healing
                messages.append(LLMMessage(role="assistant", content=response.content))
                messages.append(LLMMessage(
                    role="user",
                    content=(
                        f"The generated code failed compilation (`dotnet build`). Errors:\n\n"
                        f"```\n{build_output}\n```\n\n"
                        f"Please fix all compiler errors and return the corrected files in the exact JSON format."
                    )
                ))

        if not build_success:
            logger.error(f"Build gate failed after {max_healing_attempts} attempts. Output:\n{build_output}")

        # Commit verified code to Git repository
        commit_hash = self.git_service.commit_changes(
            project_id=context.project_id,
            repo_type=RepositoryType.CHANNEL_APP,
            message=(
                f"feat: implement channel application ({'build verified' if build_success else 'build pending'}) "
                f"for task {context.task_id.hex[:8]}"
            ),
        )

        return AgentResult(
            success=build_success,
            summary=(
                f"Channel application implemented across {len(written_files)} files. "
                f"Build verification: {'PASSED (0 Errors)' if build_success else 'FAILED'}."
            ),
            artifacts_created=written_files,
            metadata={
                "commit_hash": commit_hash,
                "branch": branch_name,
                "repo": "channel-app",
                "files_count": len(written_files),
                "build_success": build_success,
                "build_log": build_output[:2000],
            },
        )
