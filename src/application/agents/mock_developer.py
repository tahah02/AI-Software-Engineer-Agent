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
1. Review the Technical Design Document for third-party external vendor APIs (e.g., core banking, payment gateways, SMS gateways).
2. Implement a standalone, runnable mock API server in Python (FastAPI).
3. Generate realistic mock responses, error states, and schema-compliant payloads.

Respond with a JSON object containing the relative file paths and their contents:
{
  "files": {
    "main.py": "# FastAPI mock server code...",
    "requirements.txt": "fastapi\\nuvicorn\\n"
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
