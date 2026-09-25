from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
