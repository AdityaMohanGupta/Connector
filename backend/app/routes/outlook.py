import json
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import MicrosoftOAuthService
from app.database import get_db
from app.dependencies import get_current_user
from app.graph import GraphClient
from app.models import AuditLog, User
from app.schemas import EventIn, EventUpdateIn, SendMailIn

router = APIRouter(prefix="/outlook", tags=["outlook"])


async def graph_for_user(db: AsyncSession, user: User) -> GraphClient:
    token = await MicrosoftOAuthService().get_access_token(db, user)
    return GraphClient(token)


@router.get("/folders")
async def folders(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    graph = await graph_for_user(db, user)
    return {"folders": await graph.list_folders()}


@router.get("/messages")
async def messages(
    folder_id: str = "inbox",
    top: int = 20,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    graph = await graph_for_user(db, user)
    return {"messages": await graph.list_messages(folder_id, top)}


@router.get("/messages/{message_id}")
async def message(message_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    graph = await graph_for_user(db, user)
    return {"message": await graph.get_message(message_id)}


@router.post("/send")
async def send_mail(
    payload: SendMailIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    graph = await graph_for_user(db, user)
    result = await graph.send_mail(payload.model_dump())
    db.add(
        AuditLog(
            user_id=user.id,
            actor="user",
            action="outlook_send_mail",
            metadata_json=json.dumps(payload.model_dump()),
        )
    )
    await db.commit()
    return result


@router.get("/events")
async def events(
    top: int = 20, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    graph = await graph_for_user(db, user)
    return {"events": await graph.list_events(top)}


@router.post("/events")
async def create_event(
    payload: EventIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    graph = await graph_for_user(db, user)
    result = await graph.create_event(payload.model_dump())
    db.add(
        AuditLog(
            user_id=user.id,
            actor="user",
            action="outlook_create_event",
            metadata_json=json.dumps(payload.model_dump()),
        )
    )
    await db.commit()
    return result


@router.patch("/events/{event_id}")
async def update_event(
    event_id: str,
    payload: EventUpdateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    body = payload.model_dump(exclude_none=True)
    graph = await graph_for_user(db, user)
    result = await graph.update_event(event_id, body)
    db.add(
        AuditLog(
            user_id=user.id,
            actor="user",
            action="outlook_update_event",
            target=event_id,
            metadata_json=json.dumps(body),
        )
    )
    await db.commit()
    return result


@router.delete("/events/{event_id}")
async def cancel_event(
    event_id: str,
    comment: str = "",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    graph = await graph_for_user(db, user)
    result = await graph.cancel_event(event_id, comment)
    db.add(
        AuditLog(
            user_id=user.id,
            actor="user",
            action="outlook_cancel_event",
            target=event_id,
            metadata_json=json.dumps({"comment": comment}),
        )
    )
    await db.commit()
    return result
