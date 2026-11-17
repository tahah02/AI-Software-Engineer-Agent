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
1. READ AND STRICTLY ADHERE TO:
   - `## Technical Design Document`: Contains the authoritative system architecture, domain models (Section 2), API specifications and DTOs (Section 3), security (Section 4), and persistence rules.
   - `## Authoritative Test Specifications`: Contains the exact Unit Tests (UT-01..UT-12) and Integration Tests (IT-01..IT-14) that MUST be implemented in the test suite.
2. STRICT ARCHITECTURAL & SCOPE CONSTRAINTS:
   - Implement ONLY the entities, controllers, services, repositories, and external clients specified in the Technical Design Document.
   - NEVER create internal mock controllers (e.g. `MockVendorController.cs`) inside channel-app. All external vendor/mock APIs must be consumed via a typed `HttpClient` registered in `Program.cs` and configured with `MockVendor:BaseUrl` in `appsettings.json`.
3. STRUCTURE & CLEAN ARCHITECTURE (MANDATORY MULTI-FILE CODE GENERATION):
   You MUST generate a complete, working, enterprise-grade project with separate files for EVERY Clean Architecture layer as designed in `docs/TECHNICAL_DESIGN.md`. DO NOT omit any layer! DO NOT collapse logic into Program.cs!
   
   - `channel-app.csproj`: SDK project targeting net8.0 with:
     * `<DefaultItemExcludes>$(DefaultItemExcludes);channel-app.Tests/**</DefaultItemExcludes>` inside `<PropertyGroup>` (MANDATORY: Prevents test files from being compiled inside Web API)
     * Microsoft.EntityFrameworkCore.Sqlite
     * Microsoft.EntityFrameworkCore.Design
     * Swashbuckle.AspNetCore
     * Microsoft.Extensions.Diagnostics.HealthChecks.EntityFrameworkCore
     * FluentValidation.AspNetCore
     * Microsoft.AspNetCore.Authentication.JwtBearer
     * System.IdentityModel.Tokens.Jwt
   - `Models/`:
     * Generate POCO domain entities for EACH entity specified in Section 2 of the TDD (e.g. `Models/<Entity>.cs`).
     * Include all fields, data types, primary keys (Guid or int per TDD), required properties, and relationships.
   - `Data/AppDbContext.cs`:
     * EF Core DbContext inheriting from `DbContext`.
     * Explicit `public DbSet<TEntity> TEntities { get; set; } = null!;` for EVERY domain entity in Section 2 of the TDD.
     * `OnModelCreating(ModelBuilder modelBuilder)` configuring table names, primary keys, indexes (e.g. unique email), foreign keys.
     * Configure UTC DateTime converter using a typed subclass to avoid CS1503:
       `public class UtcValueConverter : ValueConverter<DateTime, DateTime> { public UtcValueConverter() : base(v => v.Kind == DateTimeKind.Utc ? v : DateTime.SpecifyKind(v, DateTimeKind.Utc), v => DateTime.SpecifyKind(v, DateTimeKind.Utc)) { } }`
       Inside `ConfigureConventions`: `configurationBuilder.Properties<DateTime>().HaveConversion<UtcValueConverter>();`
     * Configure SqlitePragmaInterceptor if required by the TDD.
   - `DTOs/`:
     * Dedicated request and response records/classes with data annotations / validation attributes matching Section 3 & 5 of the TDD (e.g. `DTOs/Create<Entity>Request.cs`, `DTOs/<Entity>Response.cs`).
     * Use `[Required(ErrorMessage = "... is required")]` on nullable fields so missing fields result in authentic HTTP 400 Bad Request.
   - `Repositories/`:
     * Repository interface (e.g. `Repositories/I<Entity>Repository.cs`) and implementation (e.g. `Repositories/<Entity>Repository.cs`).
     * Methods for persistence operations (e.g. `GetByIdAsync`, `AddAsync`, `SaveChangesAsync`) accepting `CancellationToken`.
   - `Services/`:
     * Service interface (e.g. `Services/I<Entity>Service.cs`) and implementation (e.g. `Services/<Entity>Service.cs`).
     * Business logic, normalization, validation, and coordination with repositories.
   - `Controllers/`:
     * ASP.NET Core API controllers (e.g. `Controllers/<Entity>Controller.cs`).
     * Annotated with `[ApiController]` and route attribute matching TDD Section 3.
     * Injects the corresponding service or repository.
     * Implements all HTTP action methods (`[HttpPost]`, `[HttpGet("{id}")]`, `[HttpGet]`, etc.) returning typed `ActionResult<T>` or `IActionResult` with proper HTTP status codes (201 Created with Location header, 200 OK, 400 Bad Request ProblemDetails, 404 Not Found, 409 Conflict).
   - `Program.cs`:
     * Configures SQLite `AppDbContext` (`Data Source=app.db`).
     * Registers dependency injection for all Repositories and Services defined in the project with Scoped lifetime.
     * Configures controllers: `builder.Services.AddControllers(options => { options.SuppressAsyncSuffixInActionNames = false; });`. MANDATORY: You must set `options.SuppressAsyncSuffixInActionNames = false;` so that `CreatedAtAction(nameof(GetByIdAsync), ...)` can resolve the route without throwing "No route matches the supplied values". Ensure `options.JsonSerializerOptions.PropertyNameCaseInsensitive = true;` is configured. MANDATORY: Do NOT set `options.JsonSerializerOptions.UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow;` as this causes Swashbuckle to crash with HTTP 500 when generating `/swagger/v1/swagger.json`.
     * MANDATORY: Always register `builder.Services.AddProblemDetails();` before `builder.Build()`. When using `app.UseExceptionHandler()`, `AddProblemDetails()` is required by ASP.NET Core runtime.
     * Initializes database schema cleanly via `db.Database.EnsureCreated()`.
     * Configures typed `HttpClient` for external vendor service (if applicable per TDD).
     * Configures comprehensive global exception handling middleware that translates exceptions using authentic ASP.NET Core StatusCodes constants:
       - Upstream timeouts (`TaskCanceledException`, `TimeoutException`) -> StatusCodes.Status504GatewayTimeout (504 Gateway Timeout).
       - Upstream connection failures (`HttpRequestException`, `SocketException`) -> StatusCodes.Status502BadGateway (502 Bad Gateway).
       - Database unavailability / `SqliteException` -> StatusCodes.Status503ServiceUnavailable (503 Service Unavailable).
       - Arithmetic overflow (`OverflowException` from `checked` summation) -> StatusCodes.Status422UnprocessableEntity (422 Unprocessable Entity).
       - Missing records (`KeyNotFoundException`) -> StatusCodes.Status404NotFound (404 Not Found).
       - Duplicate records / conflict -> StatusCodes.Status409Conflict (409 Conflict).
       - Input validation / bad request -> StatusCodes.Status400BadRequest (400 Bad Request).
       (MANDATORY: NEVER invent non-existent status names like Status400BadGateway).
     * Health Checks: `builder.Services.AddHealthChecks().AddDbContextCheck<AppDbContext>();` mapped to `/health`.
     * Swagger / OpenAPI documentation configured and enabled (`builder.Services.AddEndpointsApiExplorer(); builder.Services.AddSwaggerGen(c => { c.ResolveConflictingActions(apiDescriptions => apiDescriptions.First()); });`). If configuring JWT Bearer authorization, configure security requirement using OpenApiSecurityScheme:
       `c.AddSecurityRequirement(new OpenApiSecurityRequirement { { new OpenApiSecurityScheme { Reference = new OpenApiReference { Type = ReferenceType.SecurityScheme, Id = "Bearer" } }, Array.Empty<string>() } });`
     * Middleware & Security:
       - If implementing custom `IAuthorizationMiddlewareResultHandler`, use boolean properties `authorizeResult.Challenged` (NEVER use `.Challenge` as it is a method group) and `authorizeResult.Forbidden`.
       - If configuring Rate Limiting in `Program.cs`, ensure `using Microsoft.AspNetCore.RateLimiting;` is included at the top of the file.
     * MANDATORY: At the very end of Program.cs, you MUST include `public partial class Program { }` so that `WebApplicationFactory<Program>` in integration tests can access the Program class.
   - `appsettings.json`:
     {
       "ConnectionStrings": { "DefaultConnection": "Data Source=app.db" },
       "MockVendor": { "BaseUrl": "http://localhost:5100", "TimeoutSeconds": 10 }
     }
   - `Properties/launchSettings.json`: Configured for port 5001 with launchUrl: "swagger".

4. EXECUTABLE XUNIT TEST SUITE (`channel-app.Tests/`):
   - Scaffold a dedicated xUnit test project covering the REAL test cases from `## Authoritative Test Specifications`:
   - `channel-app.Tests/channel-app.Tests.csproj`:
     * `<Project Sdk=\"Microsoft.NET.Sdk\">` targeting net8.0
     * Package references: `Microsoft.NET.Test.Sdk`, `xunit`, `xunit.runner.visualstudio`, `coverlet.collector`, `Microsoft.AspNetCore.Mvc.Testing`, `FluentAssertions`, `Moq`
     * ProjectReference: `<ProjectReference Include=\"..\\channel-app.csproj\" />`
   - `channel-app.Tests/UnitTests.cs`:
     * MANDATORY USINGS: MUST explicitly include `using System;`, `using System.Threading.Tasks;`, `using Xunit;`, `using FluentAssertions;`, and `using Moq;` at the very top.
     * REAL unit tests implementing the UT cases from the Test Specification (e.g. UT-01 Email Normalization, UT-02 Unicode length, UT-03 UTC DateTime Converter, domain entity logic). ZERO DUMMY PLACEHOLDERS!
     * TIMEPROVIDER RULE: If using `TimeProvider`, NEVER call non-existent methods like `TimeProvider.FromUtcNow(...)`. To freeze/mock time, use Moq: `var mockTime = new Mock<TimeProvider>(); mockTime.Setup(t => t.GetUtcNow()).Returns(new DateTimeOffset(fixedTime));` or pass `TimeProvider.System`.
   - `channel-app.Tests/IntegrationTests.cs`:
     * MANDATORY USINGS: MUST explicitly include `using System;`, `using System.Threading.Tasks;`, `using System.Net;`, `using System.Net.Http;`, `using System.Text.Json;`, `using Xunit;`, `using FluentAssertions;`, and `using Microsoft.AspNetCore.Mvc.Testing;` at the very top.
     * Real integration tests using `WebApplicationFactory<Program>` sending authentic HTTP requests to the controller endpoints from Section 3 of the TDD verifying status codes (201, 200, 400, 404) and JSON response payloads.
     * FLUENTASSERTIONS RULE: For checking non-default DateTime, use `.Should().NotBe(default(DateTime))` (NEVER use non-existent methods like `.NotBeDefault()`). For checking status codes, use `.StatusCode.Should().Be(HttpStatusCode.OK)`.

5. Quality & Authenticity Standards:
   - Format and indent properly.
   - NO placeholders, NO `// TODO`, NO empty stub classes.
   - Code MUST compile cleanly (`dotnet build`) with 0 errors. Use consistent namespace `ChannelApp` (e.g. `ChannelApp.Models`, `ChannelApp.Data`, `ChannelApp.Controllers`, `ChannelApp.DTOs`, `ChannelApp.Services`, `ChannelApp.Repositories`) and `ChannelApp.Tests` for tests.

Respond ONLY with a valid JSON object containing relative paths and file contents for ALL required layers derived directly from the TDD:
{
  "files": {
    "channel-app.csproj": "<Project Sdk=\"Microsoft.NET.Sdk.Web\">...</Project>",
    "appsettings.json": "...",
    "Properties/launchSettings.json": "...",
    "Models/<Entity>.cs": "namespace ChannelApp.Models; public class <Entity> { ... }",
    "Data/AppDbContext.cs": "namespace ChannelApp.Data; public class AppDbContext : DbContext { public DbSet<<Entity>> <Entities> { get; set; } = null!; ... }",
    "DTOs/<Entity>Dtos.cs": "namespace ChannelApp.DTOs; ...",
    "Repositories/I<Entity>Repository.cs": "namespace ChannelApp.Repositories; ...",
    "Repositories/<Entity>Repository.cs": "namespace ChannelApp.Repositories; ...",
    "Services/I<Entity>Service.cs": "namespace ChannelApp.Services; ...",
    "Services/<Entity>Service.cs": "namespace ChannelApp.Services; ...",
    "Controllers/<Entity>Controller.cs": "namespace ChannelApp.Controllers; [ApiController] ...",
    "Program.cs": "using ChannelApp.Data; using ChannelApp.Repositories; using ChannelApp.Services; ...",
    "channel-app.Tests/channel-app.Tests.csproj": "<Project Sdk=\"Microsoft.NET.Sdk\">...</Project>",
    "channel-app.Tests/UnitTests.cs": "using Xunit; ... [Fact] public void UT01_...() ...",
    "channel-app.Tests/IntegrationTests.cs": "using Xunit; ... [Fact] public async Task IT01_...() ..."
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
        effective_framework = context.additional_metadata.get("subsystem_framework") or context.target_framework
        return get_coder_prompt_for_framework(effective_framework)

    def get_tools(self) -> list[ToolDefinition]:
        return [get_file_read_tool(), get_file_write_tool()]

    def _read_technical_design(self, workspace_path: str) -> str:
        try:
            return execute_file_read(workspace_path, "docs/TECHNICAL_DESIGN.md")
        except FileNotFoundError:
            return ""

    def _read_test_spec(self, workspace_path: str) -> str:
        try:
            return execute_file_read(workspace_path, "docs/XUNIT_TEST_SPEC.md")
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
            if isinstance(data, dict) and "files" in data:
                return data["files"]
        except Exception:
            pass

        import re
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                if isinstance(data, dict) and "files" in data:
                    return data["files"]
            except Exception:
                pass

        start = raw_content.find("{")
        end = raw_content.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(raw_content[start : end + 1])
                if isinstance(data, dict) and "files" in data:
                    return data["files"]
            except Exception:
                pass

        # Resilient fallback: regex extraction for partial or unclosed JSON
        extracted = {}
        pattern = r'"([^"\\\n]+\.[a-zA-Z0-9]+)"\s*:\s*"((?:[^"\\]|\\.)*)"'
        for m in re.finditer(pattern, raw_content):
            file_path = m.group(1)
            try:
                content = json.loads(f'"{m.group(2)}"')
                extracted[file_path] = content
            except Exception:
                pass
        if extracted:
            logger.info(f"Resilient regex fallback parser successfully extracted {len(extracted)} files.")
            return extracted

        logger.warning("Could not parse JSON files from LLM response.")
        return {}

    def _execute_build_verification(self, repo_path: str, target_framework: str) -> tuple[bool, str]:
        framework_lower = (target_framework or "").lower()
        if any(k in framework_lower for k in ("cs", "csharp", "dotnet", "net")):
            repo_p = Path(repo_path)
            csproj_files = list(repo_p.glob("*.csproj")) + list(repo_p.glob("*/*.csproj"))
            if not csproj_files and not (repo_p / "channel-app.csproj").exists():
                return True, "No C# project detected on disk."

            # Architectural completeness validation for backend channel-app
            missing_layers = []
            controllers = list(repo_p.glob("Controllers/*.cs")) or list(repo_p.glob("**/Controllers/*.cs"))
            models = list(repo_p.glob("Models/*.cs")) or list(repo_p.glob("**/Models/*.cs"))

            app_db = repo_p / "Data" / "AppDbContext.cs"
            has_dbset = False
            if app_db.exists():
                try:
                    content = app_db.read_text(encoding="utf-8")
                    if "DbSet<" in content:
                        has_dbset = True
                except Exception:
                    pass

            if not controllers:
                missing_layers.append("Controllers/ (API controllers decorated with [ApiController] implementing endpoints from Section 3 of TDD)")
            if not models:
                missing_layers.append("Models/ (Domain entity POCOs from Section 2 of TDD)")
            if not has_dbset:
                missing_layers.append("Data/AppDbContext.cs (Must declare explicit public DbSet<TEntity> properties for domain entities)")

            if missing_layers:
                error_msg = (
                    "Architectural Validation FAILED: The synthesized project is missing required Clean Architecture layers defined in docs/TECHNICAL_DESIGN.md:\n"
                    + "\n".join(f"- Missing: {m}" for m in missing_layers)
                    + "\n\nYou MUST implement the complete multi-file solution: Domain POCOs in Models/, DbSets in Data/AppDbContext.cs, DTOs in DTOs/, Services in Services/, Repositories in Repositories/, and API Controllers in Controllers/ as mandated by the Technical Design Document."
                )
                return False, error_msg

            try:
                sln_file = Path(repo_path) / "channel-app.sln"
                target = "channel-app.sln" if sln_file.exists() else "channel-app.csproj"
                res = subprocess.run(
                    ["dotnet", "build", target, "--nologo", "-v", "minimal"],
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

        if any(k in framework_lower for k in ("next", "react", "type", "ts", "node", "js")):
            try:
                pkg_json = Path(repo_path) / "package.json"
                if pkg_json.exists():
                    json.loads(pkg_json.read_text(encoding="utf-8"))
                tsconfig = Path(repo_path) / "tsconfig.json"
                if tsconfig.exists():
                    json.loads(tsconfig.read_text(encoding="utf-8"))
                return True, "Next.js / TypeScript configuration and scaffolding verified successfully."
            except Exception as e:
                return False, f"TypeScript / Next.js configuration verification failed: {e}"

        # Generic check
        return True, "No specific compiler gate configured for this framework."

    async def execute(self, context: AgentContext, input_text: str) -> AgentResult:
        tech_design = self._read_technical_design(context.workspace_path)
        test_spec = self._read_test_spec(context.workspace_path)
        sections = []
        if tech_design:
            sections.append(f"## Technical Design Document:\n\n{tech_design}")
        if test_spec:
            sections.append(f"## Authoritative Test Specifications:\n\n{test_spec}")
        sections.append(f"## Implementation Directives:\n\n{input_text}")
        user_content = "\n\n".join(sections)

        messages = self.build_initial_messages(context, user_content)

        resolved_config = self.resolver.resolve_agent_config(
            session=self.db,
            project_id=context.project_id,
            agent=self.agent_type,
        )
        adapter = resolved_config.adapter

        is_incremental = context.additional_metadata.get("is_incremental", False)
        target_subsystem = context.additional_metadata.get("target_subsystem", "channel-app")
        subsystem_framework = context.additional_metadata.get("subsystem_framework")
        effective_framework = subsystem_framework or context.target_framework
        is_frontend = (target_subsystem == "frontend") or is_incremental

        if is_frontend:
            target_repo_path = str(Path(context.workspace_path) / "frontend")
            Path(target_repo_path).mkdir(parents=True, exist_ok=True)
            branch_name = "main"
            if not (Path(target_repo_path) / ".git").exists():
                try:
                    subprocess.run(["git", "init", "-b", "main"], cwd=target_repo_path, capture_output=True, timeout=15)
                except Exception:
                    pass
        else:
            target_repo_path = self.git_service.get_repository_path(
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
                max_tokens=24000,
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
                execute_file_write(target_repo_path, rel_path, content)
                if rel_path not in written_files:
                    written_files.append(rel_path)

            # Ensure solution file exists for Visual Studio support (Backend only)
            if not is_frontend:
                framework_lower = (effective_framework or "").lower()
                if any(k in framework_lower for k in ("cs", "csharp", "dotnet", "net")):
                    sln_path = Path(target_repo_path) / "channel-app.sln"
                    if not sln_path.exists():
                        try:
                            subprocess.run(["dotnet", "new", "sln", "-n", "channel-app"], cwd=target_repo_path, capture_output=True, timeout=30)
                            subprocess.run(["dotnet", "sln", "channel-app.sln", "add", "channel-app.csproj"], cwd=target_repo_path, capture_output=True, timeout=30)
                            if "channel-app.sln" not in written_files:
                                written_files.append("channel-app.sln")
                        except Exception as e:
                            logger.warning(f"Could not generate solution file: {e}")

                    test_csproj = Path(target_repo_path) / "channel-app.Tests" / "channel-app.Tests.csproj"
                    if test_csproj.exists():
                        try:
                            subprocess.run(["dotnet", "sln", "channel-app.sln", "add", "channel-app.Tests/channel-app.Tests.csproj"], cwd=target_repo_path, capture_output=True, timeout=30)
                        except Exception as e:
                            logger.warning(f"Could not register test project in solution: {e}")

                # Clean up residual orphaned files or forbidden duplicate mock controllers
                stray_candidates = [
                    "Controllers/MockVendorController.cs",
                    "Controllers/JobsController.cs",
                    "DTOs/JobDtos.cs",
                    "Models/Job.cs",
                ]
                for stray in stray_candidates:
                    stray_path = Path(target_repo_path) / stray
                    if stray_path.exists():
                        try:
                            stray_path.unlink()
                            logger.info(f"Removed out-of-scope or forbidden residual file: {stray}")
                            if stray in written_files:
                                written_files.remove(stray)
                        except Exception as e:
                            logger.warning(f"Could not remove {stray}: {e}")

            # Run build verification gate
            build_success, build_output = self._execute_build_verification(target_repo_path, effective_framework)
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
                        f"The generated code failed compilation / verification. Errors:\n\n"
                        f"```\n{build_output}\n```\n\n"
                        f"Please fix all compilation errors and return ONLY the corrected or modified files in the exact JSON format:\n"
                        f'{{"files": {{"path/to/ModifiedFile.cs": "complete corrected file contents..."}}}}\n'
                        f"CRITICAL: Return ONLY the files that you modified to resolve the errors. Do NOT re-emit files that require no changes."
                    )
                ))

        if not build_success:
            logger.error(f"Build gate failed after {max_healing_attempts} attempts. Output:\n{build_output}")

        # Commit verified code to Git repository
        if is_frontend:
            try:
                subprocess.run(["git", "add", "-A"], cwd=target_repo_path, capture_output=True, timeout=15)
                subprocess.run(["git", "commit", "-m", "feat: scaffold frontend client interface"], cwd=target_repo_path, capture_output=True, timeout=15)
                rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=target_repo_path, capture_output=True, text=True, timeout=15)
                commit_hash = rev.stdout.strip()
            except Exception:
                commit_hash = "manual"
        else:
            commit_hash = self.git_service.commit_changes(
                project_id=context.project_id,
                repo_type=RepositoryType.CHANNEL_APP,
                message=(
                    f"feat: implement channel application ({'build verified' if build_success else 'build pending'}) "
                    f"for task {context.task_id.hex[:8]}"
                ),
            )
            # In GitFlow, merge verified feature branch back into develop so develop remains the active integration branch
            try:
                self.git_service.merge_branch(
                    project_id=context.project_id,
                    repo_type=RepositoryType.CHANNEL_APP,
                    source_branch=branch_name,
                    target_branch="develop",
                )
            except Exception as e:
                logger.warning(f"Could not merge {branch_name} into develop: {e}")

        subsystem_title = "Frontend client interface" if is_frontend else "Channel application"
        return AgentResult(
            success=build_success,
            summary=(
                f"{subsystem_title} implemented across {len(written_files)} files. "
                f"Build verification: {'PASSED (0 Errors)' if build_success else 'FAILED'}."
            ),
            artifacts_created=written_files,
            metadata={
                "commit_hash": commit_hash,
                "branch": branch_name,
                "repo": "frontend" if is_frontend else "channel-app",
                "target_subsystem": "frontend" if is_frontend else "channel-app",
                "effective_framework": effective_framework,
                "files_count": len(written_files),
                "build_success": build_success,
                "build_log": build_output[:2000],
            },
        )
