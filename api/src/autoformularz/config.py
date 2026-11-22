"""Runtime configuration. Every value comes from environment variables (prefix AUTOFORMULARZ_),
so secrets are only supplied when the container starts (task requirement)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Later env files win: api/.env overrides the repo-root .env.local (when run from api/).
    # Real environment variables override both.
    model_config = SettingsConfigDict(
        env_prefix="AUTOFORMULARZ_",
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

    # Local LLM served by Ollama: the offline option (default provider is Eden AI, see llm_provider)
    ollama_url: str = "http://localhost:11434"
    llm_model: str = "qwen3-vl:8b"
    # CPU without GPU: the 8B model writes a few tokens/s, a large form (up to llm_max_tokens) takes 15-25 min.
    # Eden AI ends a request itself after ~400 s, so the long limit only matters for Ollama.
    llm_timeout_s: float = 1800.0
    # Prompt + answer. Largest material after presort: ~7k prompt tokens + up to llm_max_tokens (12000).
    # 24576 with qwen3-vl:8b: 9.4 GB in memory (ollama ps); docs/tasks/docker-docs.md.
    llm_num_ctx: int = 24576
    # Cap on the model's answer. A FormSpec of the largest material fits easily; a model stuck in a
    # repetition loop is cut here instead of running until the provider's limit (Eden: 400 s, ~16k tokens).
    # 12000 (was 8000): form 9 (three requests in one) needed ~7.6k tokens and hit 8000 on some runs.
    llm_max_tokens: int = 12000
    # Ollama keeps the model loaded this long after a request (its default is 5m): the next form skips
    # loading the model and reuses the cached system prompt. Ollama duration format ("30m", "1h", "-1").
    llm_keep_alive: str = "30m"
    max_pdf_pages: int = 6
    # Copy INSTRUCTION / LEGAL_BASIS blocks verbatim to the finish page. Off until the model's block roles
    # are reliable: on saved results it copied paper instructions and the GDPR clause (docs/decisions.md).
    copy_source_text: bool = False
    # Presort: the code recognises the GDPR clause, signature/paper-only lines and the template's applicant
    # data before the model, so they are left out of the prompt and the answer (presort.py).
    presort: bool = True

    # LLM provider. Default "eden": Eden AI (organizer-provided, open-weight models only), also in the delivered
    # solution (team decision 2026-11-21, docs/decisions.md). "ollama": local model, offline option
    # (docker compose --profile ollama).
    llm_provider: Literal["ollama", "eden"] = "eden"
    eden_base_url: str = "https://api.edenai.run/v3"
    # Read from EDENAI_API_KEY (no prefix: the organizers' name, already in .env.local)
    eden_api_key: SecretStr | None = Field(default=None, validation_alias="EDENAI_API_KEY")
    # The team's model on Eden (docs/eden-budzet.md: ~0.005 USD per form); its local pair is qwen3-vl.
    eden_model: str | None = "deepinfra/deepseek-ai/DeepSeek-V4.1-Flash"
    # Thinking off on Eden (like `think: false` for Ollama): `reasoning_effort` in the request and the Qwen3
    # soft switch `/no_think` in the prompt. A thinking model would spend time and paid tokens on reasoning
    # before the JSON. Empty = send neither. Eden enum: none, disable, minimal, low, medium, high, ...
    eden_reasoning_effort: str = "none"

    # LibreOffice binary for legacy formats (.doc, .ods)
    soffice_bin: str = "soffice"

    # OCR for scans (Tesseract, Apache-2.0). Found on PATH or in Program Files on Windows; without it
    # scans go to the model only as images. `tessdata_dir`: folder with pol.traineddata if not the default.
    ocr_bin: str = "tesseract"
    ocr_lang: str = "pol"
    tessdata_dir: str | None = None

    # Frontend origins allowed by CORS (comma-separated)
    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
