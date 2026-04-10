from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import MicrosoftOAuthService
from app.config import Settings, get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import OutlookConnection, User
from app.schemas import AuthUrlOut, UserOut
from app.security import SessionCodec

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/microsoft/login", response_model=AuthUrlOut)
async def microsoft_login(
    response: Response,
    redirect: bool = Query(default=False),
    settings: Settings = Depends(get_settings),
) -> AuthUrlOut | RedirectResponse:
    try:
        flow = MicrosoftOAuthService(settings).build_auth_flow()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    SessionCodec(settings).set_cookie(response, settings.oauth_cookie_name, {"flow": flow})
    if redirect:
        redirect_response = RedirectResponse(flow["auth_uri"])
        SessionCodec(settings).set_cookie(redirect_response, settings.oauth_cookie_name, {"flow": flow})
        return redirect_response
    return AuthUrlOut(authorization_url=flow["auth_uri"])


@router.get("/microsoft/callback")
async def microsoft_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    oauth_cookie: str | None = Cookie(default=None, alias="outlook_connector_oauth"),
):
    codec = SessionCodec(settings)
    auth_flow = codec.loads(oauth_cookie).get("flow")
    if not auth_flow:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth session expired.")

    user = await MicrosoftOAuthService(settings).complete_auth_flow(
        db, auth_flow, dict(request.query_params)
    )
    response = RedirectResponse(f"{settings.resolved_frontend_origin.rstrip('/')}/?connected=1")
    codec.set_cookie(response, settings.session_cookie_name, {"user_id": user.id})
    codec.clear_cookie(response, settings.oauth_cookie_name)
    return response


@router.get("/me", response_model=UserOut)
async def me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    connection = await db.scalar(
        select(OutlookConnection).where(OutlookConnection.user_id == current_user.id)
    )
    return UserOut(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        connected=connection is not None,
    )


@router.post("/logout")
async def logout(response: Response, settings: Settings = Depends(get_settings)) -> dict[str, bool]:
    SessionCodec(settings).clear_cookie(response, settings.session_cookie_name)
    return {"ok": True}
