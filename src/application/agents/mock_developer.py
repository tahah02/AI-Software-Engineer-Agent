import json
from pathlib import Path
from sqlalchemy.orm import Session

from src.domain.agent_base import BaseAgent
from src.domain.enums import AgentType, RepositoryType
from src.domain.tools import execute_file_write, get_file_write_tool
from src.infrastructure.git.git_service import GitService
from src.infrastructure.llm.provider_resolver import LLMProviderResolver
from src.infrastructure.llm.token_tracker import TokenTrackerService
from src.ports.agent import AgentContext, AgentResult
from src.ports.llm_gateway import LLMMessage, LLMRequest, ToolDefinition


MOCK_DEVELOPER_SYSTEM_PROMPT = """You are Agent 2: Mock Vendor API Developer.
Your responsibility:
1. Strictly analyze the Technical Design Document (TDD) provided in the prompt to identify all external vendor, mock, and third-party dependencies, contract endpoints, routes, HTTP methods, request parameters, and response schemas.
2. Implement a complete, standalone, production-quality runnable mock API server in Python (FastAPI).
3. Implement exactly the endpoints, routes, status codes, and JSON response models specified in the TDD for vendor simulation. Never hallucinate or substitute unrelated banking/payment endpoints unless explicitly specified in the TDD.
4. Always include a GET /health endpoint returning {"status": "healthy"}.
5. Generate realistic mock responses, error states, and schema-compliant payloads.

Respond strictly with a JSON object containing the relative file paths and their contents:
{
  "files": {
    "main.py": "# Complete FastAPI mock server code...",
    "requirements.txt": "fastapi>=0.100.0\\nuvicorn>=0.23.0\\npydantic>=2.0.0\\n"
  }
}
"""


class MockVendorDeveloperAgent(BaseAgent):
    def __init__(
        self,
        resolver: LLMProviderResolver,
        git_service: GitService,
        tracker: TokenTrackerService | None = None,
        db: Session | None = None,
    ) -> None:
        super().__init__(
            agent_type=AgentType.MOCK_DEVELOPER,
            resolver=resolver,
            tracker=tracker,
            db=db,
        )
        self.git_service = git_service

    def get_system_prompt(self, context: AgentContext) -> str:
        return MOCK_DEVELOPER_SYSTEM_PROMPT

    def get_tools(self) -> list[ToolDefinition]:
        return [get_file_write_tool()]

    def _read_technical_design(self, workspace_path: str) -> str:
        tdd_path = Path(workspace_path) / "docs" / "TECHNICAL_DESIGN.md"
        if tdd_path.exists():
            try:
                return tdd_path.read_text(encoding="utf-8")
            except Exception:
                pass
        return ""

    @staticmethod
    def is_vendor_mock_skipped(text: str) -> bool:
        if not text:
            return True
        lower = text.lower()
        if "agent 2" in lower and any(k in lower for k in ("skipped", "not applicable", "bypassed", "excluded")):
            return True
        if "mock api developer" in lower and any(k in lower for k in ("skipped", "not applicable", "bypassed", "excluded")):
            return True
        if "mock vendor" in lower and any(k in lower for k in ("excluded", "not applicable", "bypassed", "none", "not required", "skipped")):
            return True
        vendor_indicators = (
            "mock vendor",
            "vendor api",
            "external vendor",
            "third-party",
            "third party",
            "vendor",
            "upstream service",
            "banking core",
            "payment gateway",
        )
        # If no vendor indicators exist in the entire text, it is skipped
        return not any(v in lower for v in vendor_indicators)

    async def execute(self, context: AgentContext, input_text: str) -> AgentResult:
        tdd_text = input_text
        if not tdd_text or "Technical Design" not in tdd_text:
            workspace_tdd = self._read_technical_design(context.workspace_path)
            if workspace_tdd:
                tdd_text = (
                    f"## Technical Design Document:\n\n{workspace_tdd}\n\n"
                    f"## Directive:\n"
                    f"Analyze the Technical Design Document above. Implement a standalone, runnable FastAPI mock vendor server "
                    f"with all schema-compliant mock endpoints required by the project specifications."
                )

        if self.is_vendor_mock_skipped(tdd_text):
            return AgentResult(
                success=True,
                summary="Agent 2 skipped: Specification confirms no mock vendor APIs are required.",
                artifacts_created=[],
                metadata={"skipped": True, "branch": "skipped"},
            )

        messages = self.build_initial_messages(context, tdd_text)

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
            temperature=0.2,
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

        # Parse generated files
        try:
            content_data = json.loads(response.content)
            files_dict = content_data.get("files", {})
        except Exception:
            files_dict = {
                "main.py": f"# Mock API Server\n\n# Generated:\n# {response.content}"
            }

        # Ensure mock-vendor-api repo path
        mock_repo_path = self.git_service.get_repository_path(
            project_id=context.project_id,
            repo_type=RepositoryType.MOCK_VENDOR_API,
        )

        # Create feature branch for mock implementation
        branch_name = f"feature/mock-apis-{context.task_id.hex[:8]}"
        self.git_service.create_branch(
            project_id=context.project_id,
            repo_type=RepositoryType.MOCK_VENDOR_API,
            branch_name=branch_name,
            base_branch="develop",
        )

        artifacts = []
        for rel_path, content in files_dict.items():
            execute_file_write(mock_repo_path, rel_path, content)
            artifacts.append(rel_path)

        # Commit changes to mock-vendor-api repo
        commit_hash = self.git_service.commit_changes(
            project_id=context.project_id,
            repo_type=RepositoryType.MOCK_VENDOR_API,
            message=f"feat: implement vendor api mocks for task {context.task_id.hex[:8]}",
        )
        try:
            self.git_service.merge_branch(
                project_id=context.project_id,
                repo_type=RepositoryType.MOCK_VENDOR_API,
                source_branch=branch_name,
                target_branch="develop",
            )
        except Exception:
            pass

        return AgentResult(
            success=True,
            summary=f"Vendor API mocks implemented across {len(artifacts)} files.",
            artifacts_created=artifacts,
            metadata={
                "commit_hash": commit_hash,
                "branch": branch_name,
                "repo": "mock-vendor-api",
            },
        )
