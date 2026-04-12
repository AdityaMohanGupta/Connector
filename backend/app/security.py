import base64
import json
from typing import Any

from cryptography.fernet import Fernet
from fastapi import HTTPException, Response, status
from itsdangerous import BadSignature, URLSafeSerializer

from app.config import Settings, get_settings


class TokenCipher:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _fernet(self) -> Fernet:
        if not self.settings.token_encryption_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="TOKEN_ENCRYPTION_KEY is blank. Fill backend/.env before storing Outlook tokens.",
            )
        return Fernet(self.settings.token_encryption_key.encode())

    def encrypt(self, value: str) -> str:
        return self._fernet().encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        return self._fernet().decrypt(value.encode()).decode()


class SessionCodec:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        secret = self.settings.session_secret or "dev-only-session-secret-fill-env"
        self.serializer = URLSafeSerializer(secret_key=secret, salt="outlook-connector-session")

    def dumps(self, data: dict[str, Any]) -> str:
        return self.serializer.dumps(data)

    def loads(self, value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            loaded = self.serializer.loads(value)
        except BadSignature:
            return {}
        return loaded if isinstance(loaded, dict) else {}

    def set_cookie(self, response: Response, name: str, data: dict[str, Any]) -> None:
        # Cross-site OAuth requires SameSite=None and Secure=True.
        # We only use None if in production (where we have HTTPS).
        # In development (localhost), Lax is usually fine for local testing.
        is_prod = self.settings.environment == "production"
        samesite = "none" if is_prod else "lax"
        secure = True if is_prod else self.settings.is_secure_cookie

        response.set_cookie(
            name,
            self.dumps(data),
            httponly=True,
            secure=secure,
            samesite=samesite,
            max_age=60 * 60 * 24 * 14,
        )

    def clear_cookie(self, response: Response, name: str) -> None:
        is_prod = self.settings.environment == "production"
        samesite = "none" if is_prod else "lax"
        secure = True if is_prod else self.settings.is_secure_cookie
        response.delete_cookie(name, httponly=True, secure=secure, samesite=samesite)


def b64_json(data: dict[str, Any]) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode()
