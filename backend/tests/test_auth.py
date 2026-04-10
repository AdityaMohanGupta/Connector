from app.config import Settings


def test_authority_uses_common_tenant_by_default() -> None:
    settings = Settings()
    assert settings.authority.endswith("/common")


def test_resolved_database_url_has_local_fallback() -> None:
    settings = Settings(database_url="")
    assert settings.resolved_database_url.startswith("sqlite+aiosqlite")
