import json
from pathlib import Path
from sqlalchemy.orm import Session

from src.domain.agent_base import BaseAgent
from src.domain.enums import AgentType, RepositoryType
from src.domain.tools import execute_file_read, execute_file_write, get_file_read_tool, get_file_write_tool
from src.infrastructure.git.git_service import GitService
from src.infrastructure.llm.provider_resolver import LLMProviderResolver
from src.infrastructure.llm.token_tracker import TokenTrackerService
from src.ports.agent import AgentContext, AgentResult
from src.ports.llm_gateway import LLMRequest, ToolDefinition


MAIN_CODER_SYSTEM_PROMPT = """You are Agent 3: Main Coding Agent.
Your responsibility:
1. Read and fully understand the Technical Design Document provided.
2. Implement complete, production-ready source code for the channel application.
3. Every API endpoint, schema, validation rule, and error handler specified in the design must be implemented.
4. Do not add placeholder methods, TODOs, or stub implementations. All code must be complete and functional.
5. Follow clean code principles. No unnecessary comments or decorative docstrings.

Respond with a JSON object containing all relative file paths and their complete source code:
{
  "files": {
    "src/main.py": "# complete application code...",
    "src/models.py": "# complete model code...",
    "requirements.txt": "fastapi\\npydantic\\n"
  }
}
"""


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
        return MAIN_CODER_SYSTEM_PROMPT

    def get_tools(self) -> list[ToolDefinition]:
        return [get_file_read_tool(), get_file_write_tool()]

    def _read_technical_design(self, workspace_path: str) -> str:
        try:
            return execute_file_read(workspace_path, "docs/TECHNICAL_DESIGN.md")
        except FileNotFoundError:
            return ""

    async def execute(self, context: AgentContext, input_text: str) -> AgentResult:
        # Read the technical design document from workspace
        tech_design = self._read_technical_design(context.workspace_path)

        user_content = input_text
        if tech_design:
            user_content = (
                f"## Technical Design Document:\n\n{tech_design}\n\n"
                f"## Additional Instructions:\n\n{input_text}"
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
            temperature=0.1,
            max_tokens=6000,
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
            files_dict = content_data.get("files", {})
        except Exception:
            files_dict = {
                "src/main.py": f"# Channel Application\n\n{response.content}"
            }

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

        artifacts = []
        for rel_path, content in files_dict.items():
            execute_file_write(channel_repo_path, rel_path, content)
            artifacts.append(rel_path)

        commit_hash = self.git_service.commit_changes(
            project_id=context.project_id,
            repo_type=RepositoryType.CHANNEL_APP,
            message=f"feat: implement channel application for task {context.task_id.hex[:8]}",
        )

        return AgentResult(
            success=True,
            summary=f"Channel application implemented across {len(artifacts)} files.",
            artifacts_created=artifacts,
            metadata={
                "commit_hash": commit_hash,
                "branch": branch_name,
                "repo": "channel-app",
                "files_count": len(artifacts),
            },
        )
