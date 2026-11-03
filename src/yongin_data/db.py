"""PostgreSQL connection helpers."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, text

from yongin_data.config import Settings, get_settings


DEFAULT_CONNECT_TIMEOUT_SECONDS = 5


def _sqlalchemy_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def create_db_engine(
    settings: Settings | None = None,
    *,
    connect_timeout: int = DEFAULT_CONNECT_TIMEOUT_SECONDS,
) -> Engine:
    """Create a pooled SQLAlchemy engine without logging its URL."""

    settings = settings or get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL이 설정되지 않았습니다. .env를 확인하세요.")

    return create_engine(
        _sqlalchemy_url(settings.database_url),
        connect_args={"connect_timeout": connect_timeout},
        pool_pre_ping=True,
        pool_recycle=300,
        echo=False,
    )


def check_connection(engine: Engine) -> bool:
    """Run a read-only connectivity check."""

    with engine.connect() as connection:
        return connection.execute(text("SELECT 1")).scalar_one() == 1
