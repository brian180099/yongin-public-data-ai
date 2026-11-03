from yongin_data.config import Settings
from yongin_data.db import _sqlalchemy_url, create_db_engine


def test_sqlalchemy_url_uses_psycopg_driver() -> None:
    assert _sqlalchemy_url("postgresql://user:pass@example/db").startswith(
        "postgresql+psycopg://"
    )


def test_engine_requires_database_url() -> None:
    try:
        create_db_engine(Settings())
    except RuntimeError as exc:
        assert "DATABASE_URL" in str(exc)
    else:
        raise AssertionError("missing DATABASE_URL should fail")
