import logging
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    anthropic_api_key: str

    brandvoice_command: str = "uvx"
    brandvoice_args: list[str] = ["brandvoice-mcp"]

    default_model: str = "claude-sonnet-4-20250514"
    max_retries: int = 3
    alignment_threshold: int = 70

    database_url: str = "sqlite:///content_app.db"

    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
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
