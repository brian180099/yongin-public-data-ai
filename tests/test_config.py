import logging

from yongin_data.config import Settings, configure_logging


def test_settings_accept_missing_optional_secrets() -> None:
    settings = Settings()
    assert settings.database_url is None
    assert settings.supabase_analysis_db_url is None
    assert settings.openai_api_key is None


def test_settings_reject_non_postgresql_url() -> None:
    try:
        Settings(database_url="https://example.com")
    except ValueError as exc:
        assert "PostgreSQL" in str(exc)
    else:
        raise AssertionError("non-PostgreSQL URL should be rejected")
    try:
        Settings(supabase_analysis_db_url="https://example.com")
    except ValueError as exc:
        assert "PostgreSQL" in str(exc)
    else:
        raise AssertionError("non-PostgreSQL Supabase URL should be rejected")


def test_http_client_request_logging_is_suppressed() -> None:
    configure_logging()
    assert logging.getLogger("httpx").level >= logging.WARNING
    assert logging.getLogger("httpcore").level >= logging.WARNING
