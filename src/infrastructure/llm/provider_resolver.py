import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domain.enums import AgentType, LLMProvider
from src.domain.exceptions import EntityNotFoundError, ValidationError
from src.infrastructure.config import settings
from src.infrastructure.db.models import ProjectAgentConfigORM
from src.infrastructure.llm.litellm_adapter import LiteLLMAdapter
from src.infrastructure.llm.ollama_adapter import OllamaAdapter
from src.ports.llm_gateway import (
    ILLMGateway,
    LLMMessage,
    LLMRequest,
    LLMResponse,
)


class ResolvedAgentExecutionConfig:
    def __init__(
        self,
        project_id: uuid.UUID,
        agent_type: str,
        provider: LLMProvider,
        model: str,
        adapter: ILLMGateway,
        custom_system_prompt: str | None = None,
    ) -> None:
        self.project_id = project_id
        self.agent_type = agent_type
        self.provider = provider
        self.model = model
        self.adapter = adapter
        self.custom_system_prompt = custom_system_prompt


class LLMProviderResolver:
    def __init__(
        self,
        ollama_adapter: ILLMGateway | None = None,
        litellm_adapter: ILLMGateway | None = None,
    ) -> None:
        self.ollama_adapter = ollama_adapter or OllamaAdapter()
        self.litellm_adapter = litellm_adapter or LiteLLMAdapter()

    def _get_adapter(self, provider: LLMProvider) -> ILLMGateway:
        if provider == LLMProvider.OLLAMA:
            return self.ollama_adapter
        if provider in (LLMProvider.GEMINI, LLMProvider.GROQ, LLMProvider.OPENROUTER):
            return self.litellm_adapter
        raise ValidationError("provider", f"Unsupported LLM provider '{provider.value}'")

    def _parse_provider(self, provider_str: str) -> LLMProvider:
        clean = provider_str.strip().lower()
        try:
            return LLMProvider(clean)
        except ValueError:
            valid_providers = [p.value for p in LLMProvider]
            raise ValidationError(
                "provider",
                f"Invalid provider '{provider_str}'. Valid providers are: {valid_providers}",
            )

    def resolve_agent_config(
        self,
        session: Session,
        project_id: uuid.UUID,
        agent: AgentType | str,
    ) -> ResolvedAgentExecutionConfig:
        agent_str = agent.value if isinstance(agent, AgentType) else str(agent)

        stmt = select(ProjectAgentConfigORM).where(
            ProjectAgentConfigORM.project_id == project_id,
            ProjectAgentConfigORM.agent_type == agent_str,
        )
        config_orm = session.scalar(stmt)

        if config_orm is None:
            raise EntityNotFoundError("ProjectAgentConfig", f"project={project_id}, agent={agent_str}")

        if not config_orm.is_enabled:
            raise ValidationError(
                "agent_status",
                f"Agent '{agent_str}' is disabled for project '{project_id}'. Execution rejected.",
            )

        provider = self._parse_provider(config_orm.provider)
        adapter = self._get_adapter(provider)

        model = config_orm.model_name.strip() if config_orm.model_name else ""
        if not model:
            provider_cfg = settings.llm_config.providers.get(provider)
            if provider_cfg and provider_cfg.default_model:
                model = provider_cfg.default_model
            else:
                raise ValidationError(
                    "model_name",
                    f"No model configured for agent '{agent_str}' and no default model found in llm_config.json for provider '{provider.value}'",
                )

        return ResolvedAgentExecutionConfig(
            project_id=project_id,
            agent_type=agent_str,
            provider=provider,
            model=model,
            adapter=adapter,
            custom_system_prompt=config_orm.custom_system_prompt,
        )

    def build_agent_request(
        self,
        resolved_config: ResolvedAgentExecutionConfig,
        messages: list[LLMMessage],
        base_system_prompt: str | None = None,
        **kwargs: Any,
    ) -> LLMRequest:
        prepared_messages: list[LLMMessage] = []

        system_parts: list[str] = []
        if base_system_prompt and base_system_prompt.strip():
            system_parts.append(base_system_prompt.strip())
        if resolved_config.custom_system_prompt and resolved_config.custom_system_prompt.strip():
            system_parts.append(
                f"[Project Custom Instructions (Supplementary - Mandatory Base Instructions Take Precedence)]:\n{resolved_config.custom_system_prompt.strip()}"
            )

        if system_parts:
            prepared_messages.append(LLMMessage(role="system", content="\n\n".join(system_parts)))

        for msg in messages:
            if msg.role != "system":
                prepared_messages.append(msg)

        if not prepared_messages:
            raise ValidationError("messages", "Cannot build an LLMRequest with no messages.")

        return LLMRequest(
            provider=resolved_config.provider,
            model=resolved_config.model,
            messages=prepared_messages,
            **kwargs,
        )

    async def execute_agent(
        self,
        session: Session,
        project_id: uuid.UUID,
        agent: AgentType | str,
        messages: list[LLMMessage],
        base_system_prompt: str | None = None,
        **request_kwargs: Any,
    ) -> LLMResponse:
        resolved = self.resolve_agent_config(session, project_id, agent)
        request = self.build_agent_request(
            resolved,
            messages=messages,
            base_system_prompt=base_system_prompt,
            **request_kwargs,
        )
        return await resolved.adapter.complete(request)
