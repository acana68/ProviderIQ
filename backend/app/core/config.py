from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# config.py → core → app → backend → repo root
REPO_ROOT = Path(__file__).resolve().parents[3]


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

    @field_validator("log_level", mode="before")
    @classmethod
    def _uppercase_log_level(cls, value: Any) -> Any:
        return value.upper() if isinstance(value, str) else value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
