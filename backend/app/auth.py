import json
from typing import Any

import msal
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models import OutlookConnection, User, utc_now
from app.security import TokenCipher


class MicrosoftOAuthService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.cipher = TokenCipher(self.settings)

    def _cache(self, serialized: str | None = None) -> msal.SerializableTokenCache:
        cache = msal.SerializableTokenCache()
        if serialized:
            cache.deserialize(serialized)
        return cache

    def _client(self, cache: msal.SerializableTokenCache | None = None) -> msal.ConfidentialClientApplication:
        return msal.ConfidentialClientApplication(
            client_id=self.settings.microsoft_client_id,
            client_credential=self.settings.microsoft_client_secret,
            authority=self.settings.authority,
            token_cache=cache,
        )

    def build_auth_flow(self) -> dict[str, Any]:
        self.settings.require_microsoft_oauth()
        return self._client(self._cache()).initiate_auth_code_flow(
            scopes=self.settings.auth_scopes,
            redirect_uri=self.settings.microsoft_redirect_uri,
        )

    async def complete_auth_flow(
        self, db: AsyncSession, auth_flow: dict[str, Any], auth_response: dict[str, Any]
    ) -> User:
        self.settings.require_microsoft_oauth()
        cache = self._cache()
        result = self._client(cache).acquire_token_by_auth_code_flow(auth_flow, auth_response)
        if "error" in result:
            detail = result.get("error_description") or result.get("error") or "Microsoft OAuth failed."
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

        claims = result.get("id_token_claims") or {}
        microsoft_user_id = claims.get("oid") or claims.get("sub")
        email = (
            claims.get("preferred_username")
            or claims.get("email")
            or claims.get("upn")
            or result.get("account", {}).get("username")
        )
        if not microsoft_user_id or not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Microsoft did not return a usable user id and email.",
            )

        existing = await db.scalar(select(User).where(User.microsoft_user_id == microsoft_user_id))
        user = existing or User(microsoft_user_id=microsoft_user_id, email=email)
        user.email = email
        user.display_name = claims.get("name") or email
        db.add(user)
        await db.flush()

        serialized_cache = cache.serialize()
        encrypted_cache = self.cipher.encrypt(serialized_cache)
        account = (cache.find(msal.TokenCache.CredentialType.ACCOUNT) or [{}])[0]
        connection = await db.scalar(select(OutlookConnection).where(OutlookConnection.user_id == user.id))
        if not connection:
            connection = OutlookConnection(user_id=user.id, encrypted_token_cache=encrypted_cache)
        connection.tenant_id = claims.get("tid") or ""
        connection.account_home_id = account.get("home_account_id", "")
        connection.scopes = json.dumps(result.get("scope", "").split())
        connection.encrypted_token_cache = encrypted_cache
        connection.connected_at = utc_now()
        db.add(connection)
        await db.commit()
        await db.refresh(user)
        return user

    async def get_access_token(self, db: AsyncSession, user: User) -> str:
        connection = await db.scalar(select(OutlookConnection).where(OutlookConnection.user_id == user.id))
        if not connection:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Outlook is not connected.")

        serialized_cache = self.cipher.decrypt(connection.encrypted_token_cache)
        cache = self._cache(serialized_cache)
        client = self._client(cache)
        accounts = client.get_accounts()
        if not accounts:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Reconnect Outlook.")

        result = client.acquire_token_silent(self.settings.graph_scopes, account=accounts[0])
        if not result or "access_token" not in result:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Reconnect Outlook.")

        if cache.has_state_changed:
            connection.encrypted_token_cache = self.cipher.encrypt(cache.serialize())
            connection.last_token_refresh_at = utc_now()
            await db.commit()
        return result["access_token"]
