from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = ""
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_redirect_uri: str = ""
    microsoft_tenant: str = "common"
    session_secret: str = ""
    token_encryption_key: str = ""
    frontend_origin: str = "http://localhost:5173"
    mcp_bearer_token: str = ""
    environment: Literal["development", "test", "production"] = "development"

    graph_base_url: str = "https://graph.microsoft.com/v1.0"
    microsoft_authority_host: str = "https://login.microsoftonline.com"
    session_cookie_name: str = "outlook_connector_session"
    oauth_cookie_name: str = "outlook_connector_oauth"

    auth_scopes: list[str] = Field(
        default_factory=lambda: [
            "email",
            "User.Read",
            "Mail.Read",
            "Mail.Send",
            "Calendars.ReadWrite",
        ]
    )
    graph_scopes: list[str] = Field(
        default_factory=lambda: ["User.Read", "Mail.Read", "Mail.Send", "Calendars.ReadWrite"]
    )

    @property
    def resolved_frontend_origin(self) -> str:
        return self.frontend_origin or "http://localhost:5173"

    @property
    def authority(self) -> str:
        return f"{self.microsoft_authority_host.rstrip('/')}/{self.microsoft_tenant}"

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return "sqlite+aiosqlite:///./outlook_connector_dev.db"

    @property
    def is_secure_cookie(self) -> bool:
        return self.environment == "production"

    def require_microsoft_oauth(self) -> None:
        missing = [
            name
            for name, value in {
                "MICROSOFT_CLIENT_ID": self.microsoft_client_id,
                "MICROSOFT_CLIENT_SECRET": self.microsoft_client_secret,
                "MICROSOFT_REDIRECT_URI": self.microsoft_redirect_uri,
                "SESSION_SECRET": self.session_secret,
                "TOKEN_ENCRYPTION_KEY": self.token_encryption_key,
            }.items()
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Fill these backend .env values before OAuth: {joined}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
