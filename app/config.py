"""Application configuration loaded from environment variables / .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["openai", "anthropic", "ollama", "mock"]


class Settings(BaseSettings):
    """Centralized, type-safe application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- LLM provider -----------------------------------------------------
    llm_provider: ProviderName = Field(default="openai", alias="LLM_PROVIDER")

    # ---- OpenAI -----------------------------------------------------------
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    # ---- Anthropic --------------------------------------------------------
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-haiku-4-5", alias="ANTHROPIC_MODEL")

    # ---- Ollama -----------------------------------------------------------
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.1:8b", alias="OLLAMA_MODEL")

    # ---- App --------------------------------------------------------------
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")

    # ---- Write/API protection --------------------------------------------
    insightloop_api_key: str = Field(default="", alias="INSIGHTLOOP_API_KEY")
    admin_username: str = Field(default="admin", alias="ADMIN_USERNAME")
    admin_password: str = Field(default="", alias="ADMIN_PASSWORD")
    session_secret: str = Field(default="", alias="SESSION_SECRET")
    secure_cookies: bool = Field(default=False, alias="SECURE_COOKIES")

    # ---- Persistence ------------------------------------------------------
    database_url: str = Field(default="sqlite:///./data/insightloop.db", alias="DATABASE_URL")

    # ---- Storage ----------------------------------------------------------
    data_dir: Path = Field(default=Path("./data"), alias="DATA_DIR")

    # ---- Derived ----------------------------------------------------------
    @property
    def project_root(self) -> Path:
        """Root of the project (where `main.py` lives)."""
        return Path(__file__).resolve().parent.parent

    @property
    def templates_dir(self) -> Path:
        return self.project_root / "templates"

    @property
    def static_dir(self) -> Path:
        return self.project_root / "static"

    def ensure_data_dir(self) -> None:
        """Create the data directory if it does not exist yet."""
        self.data_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached `Settings` instance."""
    s = Settings()
    s.ensure_data_dir()
    return s
