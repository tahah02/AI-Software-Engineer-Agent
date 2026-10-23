import json
from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.domain.enums import LLMProvider


class ModelPricing(BaseModel):
    prompt_cost_per_1k: float = Field(ge=0.0)
    completion_cost_per_1k: float = Field(ge=0.0)


class ProviderConfig(BaseModel):
    default_model: str = Field(min_length=1)
    fallback_model: str | None = None
    available_models: list[str] = Field(default_factory=list)
    pricing: dict[str, ModelPricing] = Field(default_factory=dict)


class LLMConfigFile(BaseModel):
    version: str = "1.0.0"
    providers: dict[LLMProvider, ProviderConfig]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "sqlite:///./data/aaise.db"

    GEMINI_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    OPENROUTER_API_KEY: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    LLM_CONFIG_PATH: str = "config/llm_config.json"

    API_TITLE: str = "AAISE Platform API"
    API_VERSION: str = "0.1.0"
    DEBUG: bool = False
    CORS_ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    _llm_config: LLMConfigFile | None = None

    def ensure_data_dir(self) -> None:
        if self.DATABASE_URL.startswith("sqlite:///"):
            raw_path = self.DATABASE_URL.replace("sqlite:///", "")
            path = Path(raw_path)
            if not path.is_absolute():
                path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def llm_config(self) -> LLMConfigFile:
        if self._llm_config is None:
            self._llm_config = self.load_llm_config()
        return self._llm_config

    def load_llm_config(self) -> LLMConfigFile:
        path = Path(self.LLM_CONFIG_PATH)
        if not path.exists():
            raise FileNotFoundError(f"LLM configuration file not found at: {path.resolve()}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return LLMConfigFile.model_validate(data)
        except Exception as e:
            raise ValueError(f"Invalid LLM configuration in {path}: {e}") from e


settings = Settings()
settings.ensure_data_dir()
