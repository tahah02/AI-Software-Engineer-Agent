import uuid
from sqlalchemy.orm import Session

from src.domain.enums import LLMProvider
from src.infrastructure.config import Settings
from src.infrastructure.db.models import LLMInvocationORM, TokenUsageORM
from src.ports.llm_gateway import LLMResponse


class TokenTrackerService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or Settings()

    def estimate_cost(
        self,
        provider: LLMProvider | str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float | None:
        prov_key = provider.value if isinstance(provider, LLMProvider) else str(provider).lower()
        try:
            prov_enum = LLMProvider(prov_key)
        except ValueError:
            return None

        llm_cfg = self.settings.llm_config
        prov_config = llm_cfg.providers.get(prov_enum)
        if not prov_config or not prov_config.pricing:
            return None

        pricing = prov_config.pricing.get(model)
        if not pricing:
            return None

        prompt_cost = (prompt_tokens / 1000.0) * pricing.prompt_cost_per_1k
        completion_cost = (completion_tokens / 1000.0) * pricing.completion_cost_per_1k
        return round(prompt_cost + completion_cost, 6)

    def record_invocation(
        self,
        agent_execution_id: uuid.UUID,
        provider: LLMProvider | str,
        model_name: str,
        latency_ms: int,
        success: bool,
        response: LLMResponse | None = None,
        error_message: str | None = None,
    ) -> LLMInvocationORM:
        prov_str = provider.value if isinstance(provider, LLMProvider) else str(provider).lower()

        # Sanitize error message to ensure no secrets or full tracebacks leak
        sanitized_error = None
        if error_message:
            sanitized_error = error_message.strip()[:1000]

        invocation = LLMInvocationORM(
            agent_execution_id=agent_execution_id,
            provider=prov_str,
            model_name=model_name,
            latency_ms=max(0, latency_ms),
            success=success,
            error_message=sanitized_error,
        )
        self.db.add(invocation)
        self.db.flush()

        if response and response.usage:
            prompt_toks = response.usage.prompt_tokens
            comp_toks = response.usage.completion_tokens
            total_toks = response.usage.total_tokens

            # Compute estimated cost from config if available, otherwise record None
            cost = self.estimate_cost(prov_str, model_name, prompt_toks, comp_toks)

            token_usage = TokenUsageORM(
                llm_invocation_id=invocation.id,
                prompt_tokens=prompt_toks,
                completion_tokens=comp_toks,
                total_tokens=total_toks,
                estimated_cost_usd=cost,
            )
            self.db.add(token_usage)
            self.db.flush()

        return invocation
