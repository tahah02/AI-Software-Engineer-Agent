from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    OLLAMA_CHAT_MODEL: str = "qwen2.5:3b"
    OLLAMA_CODING_MODEL: str = "qwen2.5-coder:7b"

    API_TITLE: str = "AAISE Platform API"
    API_VERSION: str = "0.1.0"
    DEBUG: bool = False
    CORS_ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    def ensure_data_dir(self) -> None:
        if self.DATABASE_URL.startswith("sqlite:///"):
            raw_path = self.DATABASE_URL.replace("sqlite:///", "")
            path = Path(raw_path)
            if not path.is_absolute():
                path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_data_dir()
