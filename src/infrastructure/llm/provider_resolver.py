import uuid
from typing import Any
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.domain.enums import AgentType, LLMProvider
from src.domain.exceptions import ConfigurationError, EntityNotFoundError, ValidationError
from src.infrastructure.config import settings
from src.infrastructure.db.models import ProjectAgentConfigORM
from src.infrastructure.llm.litellm_adapter import LiteLLMAdapter
from src.infrastructure.llm.ollama_adapter import OllamaAdapter
from src.ports.llm_gateway import ILLMGateway, LLMMessage, LLMRequest


class ResolvedAgentExecutionConfig:
    def __init__(
        self,
        project_id: uuid.UUID | None,
        agent_type: str,
        provider: LLMProvider,
        model: str,
        adapter: ILLMGateway,
        custom_system_prompt: str | None = None,
        fallback_provider: LLMProvider | None = None,
        fallback_model: str | None = None,
        fallback_adapter: ILLMGateway | None = None,
    ) -> None:
        self.project_id = project_id
        self.agent_type = agent_type
        self.provider = provider
        self.model = model
        self.adapter = adapter
        self.custom_system_prompt = custom_system_prompt
        self.fallback_provider = fallback_provider
        self.fallback_model = fallback_model
        self.fallback_adapter = fallback_adapter


class LLMProviderResolver:
    def __init__(
        self,
        litellm_adapter: ILLMGateway | None = None,
        ollama_adapter: ILLMGateway | None = None,
    ) -> None:
        self._adapters: dict[LLMProvider, ILLMGateway] = {}
        if litellm_adapter:
            self._adapters[LLMProvider.GEMINI] = litellm_adapter
            self._adapters[LLMProvider.GROQ] = litellm_adapter
            self._adapters[LLMProvider.OPENROUTER] = litellm_adapter
        if ollama_adapter:
            self._adapters[LLMProvider.OLLAMA] = ollama_adapter

    def _get_adapter(self, provider: LLMProvider) -> ILLMGateway:
        if provider not in self._adapters:
            if provider == LLMProvider.OLLAMA:
                self._adapters[provider] = OllamaAdapter()
            elif provider in (LLMProvider.GEMINI, LLMProvider.GROQ, LLMProvider.OPENROUTER):
                self._adapters[provider] = LiteLLMAdapter()
            else:
                raise ConfigurationError(
                    f"Unsupported LLM provider '{provider.value}'. "
                    f"Supported providers are: {[p.value for p in LLMProvider]}"
                )
        return self._adapters[provider]

    def _parse_provider(self, provider_str: str) -> LLMProvider:
        try:
            return LLMProvider(provider_str.lower().strip())
        except ValueError:
            valid_providers = [p.value for p in LLMProvider]
            raise ValidationError(
                "provider",
                f"Invalid provider '{provider_str}'. Valid providers are: {valid_providers}",
            )

    def resolve_agent_config(
        self,
        session: Session | None,
        project_id: uuid.UUID | None,
        agent: AgentType | str,
    ) -> ResolvedAgentExecutionConfig:
        agent_str = agent.value if isinstance(agent, AgentType) else str(agent)
        agent_key = agent_str
        if "1" in agent_str or "Documentation" in agent_str:
            agent_key = "AGENT_1"
        elif "2" in agent_str or "Mock" in agent_str:
            agent_key = "AGENT_2"
        elif "3" in agent_str or "Main" in agent_str:
            agent_key = "AGENT_3"
        elif "4" in agent_str or "QA" in agent_str:
            agent_key = "AGENT_4"
        elif "5" in agent_str or "Security" in agent_str:
            agent_key = "AGENT_5"

        config_orm = None
        if session and project_id:
            stmt = select(ProjectAgentConfigORM).where(
                ProjectAgentConfigORM.project_id == project_id,
                or_(
                    ProjectAgentConfigORM.agent_type == agent_str,
                    ProjectAgentConfigORM.agent_type == agent_key,
                ),
            )
            config_orm = session.scalar(stmt)

        if config_orm is None:
            if session and project_id:
                raise EntityNotFoundError("ProjectAgentConfig", f"project={project_id}, agent={agent_str}")
            # Fall back directly to centralized agent_assignments in llm_config.json
            assignment = settings.llm_config.agent_assignments.get(agent_key)
            if assignment:
                provider = assignment.provider
                adapter = self._get_adapter(provider)
                fallback_adapter = None
                if assignment.fallback_provider:
                    try:
                        fallback_adapter = self._get_adapter(assignment.fallback_provider)
                    except Exception:
                        fallback_adapter = None

                return ResolvedAgentExecutionConfig(
                    project_id=project_id,
                    agent_type=agent_str,
                    provider=provider,
                    model=assignment.model,
                    adapter=adapter,
                    fallback_provider=assignment.fallback_provider,
                    fallback_model=assignment.fallback_model,
                    fallback_adapter=fallback_adapter,
                )
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

        fallback_provider = None
        fallback_model = None
        fallback_adapter = None
        assignment = settings.llm_config.agent_assignments.get(agent_key)
        if assignment and assignment.fallback_provider and assignment.fallback_model:
            fallback_provider = assignment.fallback_provider
            fallback_model = assignment.fallback_model
            try:
                fallback_adapter = self._get_adapter(fallback_provider)
            except Exception:
                fallback_adapter = None

        return ResolvedAgentExecutionConfig(
            project_id=project_id,
            agent_type=agent_str,
            provider=provider,
            model=model,
            adapter=adapter,
            custom_system_prompt=config_orm.custom_system_prompt,
            fallback_provider=fallback_provider,
            fallback_model=fallback_model,
            fallback_adapter=fallback_adapter,
        )

    def build_agent_request(
        self,
        resolved_config: ResolvedAgentExecutionConfig,
        messages: list[LLMMessage],
        base_system_prompt: str | None = None,
        **kwargs: Any,
    ) -> LLMRequest:
        prepared_messages: list[LLMMessage] = []

        system_parts = []
        if base_system_prompt:
            system_parts.append(base_system_prompt)
        if resolved_config.custom_system_prompt:
            if base_system_prompt:
                system_parts.append(
                    f"[Project Custom Instructions (Supplementary - Mandatory Base Instructions Take Precedence)]:\n{resolved_config.custom_system_prompt}"
                )
            else:
                system_parts.append(resolved_config.custom_system_prompt)

        if system_parts:
            prepared_messages.append(LLMMessage(role="system", content="\n\n".join(system_parts)))

        prepared_messages.extend(messages)

        return LLMRequest(
            provider=resolved_config.provider,
            model=resolved_config.model,
            messages=prepared_messages,
            fallback_provider=resolved_config.fallback_provider,
            fallback_model=resolved_config.fallback_model,
            **kwargs,
        )

    async def execute_agent(
        self,
        session: Session | None,
        project_id: uuid.UUID | None,
        agent: AgentType | str,
        messages: list[LLMMessage],
        base_system_prompt: str | None = None,
        **kwargs: Any,
    ) -> Any:
        resolved = self.resolve_agent_config(session, project_id, agent)
        req = self.build_agent_request(
            resolved,
            messages=messages,
            base_system_prompt=base_system_prompt,
            **kwargs,
        )
        return await resolved.adapter.complete(req)
