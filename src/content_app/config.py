from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve `.env` from repo root so it loads even when cwd is not the project directory.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


def parse_brandvoice_args(raw: str) -> list[str]:
    """Turn ``BRANDVOICE_ARGS`` into subprocess argv (comma-separated or JSON array).

    Stored as plain ``str`` so pydantic-settings does not pre-parse JSON for ``list`` fields.
    """
    s = raw.strip()
    if not s:
        return ["brandvoice-mcp"]
    if s.startswith("["):
        data = json.loads(s)
        if not isinstance(data, list):
            raise ValueError("BRANDVOICE_ARGS JSON must be an array")
        return [str(x) for x in data]
    if s.startswith("{"):
        raise ValueError("BRANDVOICE_ARGS JSON must be an array, not an object")
    return [p.strip() for p in s.split(",") if p.strip()]


class Settings(BaseSettings):
    anthropic_api_key: str
    openai_api_key: str  # Required for brandvoice-mcp embeddings
    tavily_api_key: str = ""

    brandvoice_command: str = "uvx"
    brandvoice_args: str = "brandvoice-mcp"

    default_model: str = "claude-sonnet-4-20250514"
    max_retries: int = 3
    alignment_threshold: int = 70

    database_url: str = "sqlite:///content_app.db"

    log_level: str = "INFO"

    @model_validator(mode="after")
    def validate_brandvoice_args(self) -> Settings:
        parse_brandvoice_args(self.brandvoice_args)
        return self

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        # Allow extra fields so future env vars don't break existing configs
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def configure_logging(level: str | None = None) -> None:
    settings = get_settings()
    log_level = level or settings.log_level
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
