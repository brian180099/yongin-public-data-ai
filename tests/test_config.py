from yongin_data.config import Settings


def test_settings_accept_missing_optional_secrets() -> None:
    settings = Settings()
    assert settings.database_url is None
    assert settings.openai_api_key is None


def test_settings_reject_non_postgresql_url() -> None:
    try:
        Settings(database_url="https://example.com")
    except ValueError as exc:
        assert "PostgreSQL" in str(exc)
    else:
        raise AssertionError("non-PostgreSQL URL should be rejected")
