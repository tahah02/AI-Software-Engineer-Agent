import tempfile
import uuid
import pytest
from pathlib import Path

from src.domain.agent_base import BaseAgent
from src.domain.enums import AgentType
from src.domain.tools import (
    execute_file_read,
    execute_file_write,
    execute_list_files,
    get_file_read_tool,
    get_file_write_tool,
    get_list_files_tool,
)
from src.ports.agent import AgentContext, AgentResult, IAgent
from src.ports.llm_gateway import ToolDefinition


class DummyAgent(BaseAgent):
    def get_system_prompt(self, context: AgentContext) -> str:
        return "You are a test agent."

    def get_tools(self) -> list[ToolDefinition]:
        return [get_file_read_tool(), get_file_write_tool(), get_list_files_tool()]

    async def execute(self, context: AgentContext, input_text: str) -> AgentResult:
        return AgentResult(
            success=True,
            summary="Execution completed successfully",
            artifacts_created=["dummy.txt"],
        )


def test_agent_implements_protocol():
    agent = DummyAgent(
        agent_type=AgentType.DOC_REVIEWER,
        resolver=None,  # type: ignore
    )
    assert isinstance(agent, IAgent)
    assert agent.agent_type == AgentType.DOC_REVIEWER


def test_agent_context_and_result():
    context = AgentContext(
        project_id=uuid.uuid4(),
        task_id=uuid.uuid4(),
        agent_execution_id=uuid.uuid4(),
        workspace_path="/tmp/test",
    )
    assert context.target_framework == "fastapi"

    result = AgentResult(success=True, summary="All good")
    assert result.success is True
    assert result.error_message is None


def test_tools_file_operations_in_workspace():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # 1. Write file
        msg = execute_file_write(tmp_dir, "docs/test.md", "# Test Content")
        assert "Successfully wrote" in msg
        assert (Path(tmp_dir) / "docs/test.md").exists()

        # 2. Read file
        content = execute_file_read(tmp_dir, "docs/test.md")
        assert content == "# Test Content"

        # 3. List files
        files = execute_list_files(tmp_dir)
        assert "docs/test.md" in files


def test_tools_reject_path_traversal():
    with tempfile.TemporaryDirectory() as tmp_dir:
        with pytest.raises(PermissionError):
            execute_file_write(tmp_dir, "../outside.txt", "evil")

        with pytest.raises(PermissionError):
            execute_file_read(tmp_dir, "../../secret.txt")
