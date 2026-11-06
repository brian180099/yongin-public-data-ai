"""Environment configuration and application logging."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, field_validator


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseModel):
    """Server-side settings loaded from environment variables."""

    model_config = ConfigDict(frozen=True)

    database_url: str | None = None
    supabase_analysis_db_url: str | None = None
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    data_go_kr_service_key: str | None = None

    @field_validator("database_url", "supabase_analysis_db_url")
    @classmethod
    def validate_database_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if not value.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection URL")
        return value

    @field_validator("openai_api_key", "data_go_kr_service_key")
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load local .env values without overriding process environment values."""

    load_dotenv(PROJECT_ROOT / ".runtime" / "analysis.env", override=False)
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    return Settings(
        database_url=os.getenv("DATABASE_URL"),
        supabase_analysis_db_url=os.getenv("SUPABASE_ANALYSIS_DB_URL"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL") or "gpt-4o-mini",
        data_go_kr_service_key=os.getenv("DATA_GO_KR_SERVICE_KEY"),
    )


def configure_logging(level: int = logging.INFO) -> None:
    """Configure concise application logs without secret-bearing settings."""

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    # httpx INFO logs include query strings. Public-data service keys are
    # query parameters, so request-level logs must remain disabled.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
