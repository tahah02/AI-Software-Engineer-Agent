from abc import ABC, abstractmethod
from typing import Any
from sqlalchemy.orm import Session

from src.domain.enums import AgentType
from src.infrastructure.llm.provider_resolver import LLMProviderResolver
from src.infrastructure.llm.token_tracker import TokenTrackerService
from src.ports.agent import AgentContext, AgentResult, IAgent
from src.ports.llm_gateway import LLMMessage, LLMRequest, ToolDefinition


class BaseAgent(ABC, IAgent):
    def __init__(
        self,
        agent_type: AgentType,
        resolver: LLMProviderResolver,
        tracker: TokenTrackerService | None = None,
        db: Session | None = None,
    ) -> None:
        self.agent_type = agent_type
        self.resolver = resolver
        self.tracker = tracker
        self.db = db

    @abstractmethod
    def get_system_prompt(self, context: AgentContext) -> str:
        ...

    @abstractmethod
    def get_tools(self) -> list[ToolDefinition]:
        ...

    @abstractmethod
    async def execute(self, context: AgentContext, input_text: str) -> AgentResult:
        ...

    def build_initial_messages(self, context: AgentContext, input_text: str) -> list[LLMMessage]:
        return [
            LLMMessage(role="system", content=self.get_system_prompt(context)),
            LLMMessage(role="user", content=input_text),
        ]
