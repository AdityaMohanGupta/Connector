from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.models import User
from app.security import SessionCodec


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    session_cookie: str | None = Cookie(default=None, alias="outlook_connector_session"),
) -> User:
    data = SessionCodec(settings).loads(session_cookie)
    user_id = data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in.")

    # Retry logic for transient DB connection errors (e.g. WinError 10054)
    attempts = 0
    max_attempts = 2
    while attempts < max_attempts:
        try:
            user = await db.get(User, user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="User session is invalid."
                )
            return user
        except (Exception) as e:
            attempts += 1
            if attempts >= max_attempts:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database connection error after {max_attempts} attempts."
                )
            import asyncio
            await asyncio.sleep(0.5)
