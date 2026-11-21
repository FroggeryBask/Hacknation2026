"""Runtime configuration. Every value comes from environment variables (prefix FORMGEN_),
so secrets are only supplied when the container starts (task requirement)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Later env files win: api/.env overrides the repo-root .env.local (when run from api/).
    # Real environment variables override both.
    model_config = SettingsConfigDict(
        env_prefix="FORMGEN_",
        env_file=("../.env.local", ".env"),
        extra="ignore",
        populate_by_name=True,
    )

    # Upload limits
    max_upload_mb: float = 20.0

    # JWT (HS256 shared secret). auth_enabled=False only for local development.
    auth_enabled: bool = True
    jwt_secret: SecretStr | None = None
    jwt_algorithm: str = "HS256"
    jwt_audience: str | None = None

    # Local LLM served by Ollama (no external APIs allowed by the task rules)
    ollama_url: str = "http://localhost:11434"
    llm_model: str = "qwen3-vl:8b"
    llm_timeout_s: float = 600.0
    llm_num_ctx: int = 16384
    max_pdf_pages: int = 6

    # LLM provider. "eden" (Eden AI, open-weight models only) is for local development and tests only;
    # docker-compose forces "ollama" for the delivered solution.
    llm_provider: Literal["ollama", "eden"] = "ollama"
    eden_base_url: str = "https://api.edenai.run/v3"
    # Read from EDENAI_API_KEY (no prefix: the organizers' name, already in .env.local)
    eden_api_key: SecretStr | None = Field(default=None, validation_alias="EDENAI_API_KEY")
    eden_model: str | None = None

    # LibreOffice binary for legacy formats (.doc, .ods)
    soffice_bin: str = "soffice"

    # Frontend origins allowed by CORS (comma-separated)
    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
