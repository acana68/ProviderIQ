from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _repo_root(config_file: Path = Path(__file__)) -> Path:
    """config.py → core → app → backend → repo root.

    If the file sits shallower than that (an unusual install layout), use the highest
    ancestor there is rather than crash on import. A missing .env there is skipped anyway,
    and the scripts that read REPO_ROOT / "data" then fail with a clear file-not-found.
    """
    parents = config_file.resolve().parents
    return parents[min(3, len(parents) - 1)]


REPO_ROOT = _repo_root()


class Settings(BaseSettings):
    """App configuration, read from environment variables and the repo-root .env.

    A missing .env file is skipped (e.g. in Docker, where env vars are passed directly).
    """

    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    app_name: str = "ProviderIQ"
    app_version: str = "0.1.0"
    environment: Literal["dev", "test", "prod"] = "dev"
    api_prefix: str = "/api/v1"

    database_url: str
    # Only the test suite reads this; it must point at a separate database.
    test_database_url: str | None = None

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # Comma-separated in .env. NoDecode: read the raw string instead of parsing it as JSON.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    max_request_body_bytes: int = Field(default=65_536, gt=0)
    # Per client IP, per app process (see core/rate_limit.py).
    rate_limit_per_minute: int = Field(default=120, gt=0)

    # AI query parsing (app/ai/). "none" uses the keyword parser and needs no key.
    ai_provider: Literal["anthropic", "none"] = "none"
    # SecretStr: never shown in repr(), logs, or error messages.
    anthropic_api_key: SecretStr | None = None
    ai_model: str = "claude-haiku-4-5-20251001"
    # The most one parse waits for the model; the client doesn't retry.
    ai_timeout_seconds: float = Field(default=8, gt=0, le=60)
    # Per client IP on POST /ai/parse-query, on top of rate_limit_per_minute.
    ai_rate_limit_per_minute: int = Field(default=10, gt=0)

    @field_validator("log_level", mode="before")
    @classmethod
    def _uppercase_log_level(cls, value: Any) -> Any:
        return value.upper() if isinstance(value, str) else value

    @field_validator("ai_provider", mode="before")
    @classmethod
    def _lowercase_ai_provider(cls, value: Any) -> Any:
        return value.lower() if isinstance(value, str) else value

    @field_validator("anthropic_api_key", mode="before")
    @classmethod
    def _blank_key_is_no_key(cls, value: Any) -> Any:
        # `ANTHROPIC_API_KEY=` in .env means "not set", not an empty key.
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
