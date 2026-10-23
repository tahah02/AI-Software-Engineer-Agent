import uuid
from typing import Any, Protocol, runtime_checkable
from pydantic import BaseModel, Field

from src.domain.enums import AgentType


class AgentContext(BaseModel):
    project_id: uuid.UUID
    task_id: uuid.UUID
    agent_execution_id: uuid.UUID
    workspace_path: str
    target_framework: str = "fastapi"
    additional_metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    success: bool
    summary: str
    artifacts_created: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None


@runtime_checkable
class IAgent(Protocol):
    agent_type: AgentType

    async def execute(self, context: AgentContext, input_text: str) -> AgentResult:
        ...
