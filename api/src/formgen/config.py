"""Runtime configuration. Every value comes from environment variables (prefix FORMGEN_),
so secrets are only supplied when the container starts (task requirement)."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FORMGEN_", env_file=".env", extra="ignore")

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

    # LibreOffice binary for legacy formats (.doc, .ods)
    soffice_bin: str = "soffice"

    # Frontend origins allowed by CORS (comma-separated)
    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
