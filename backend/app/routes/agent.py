from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import AgentService, parse_json
from app.database import get_db
from app.dependencies import get_current_user
from app.llm import LLMService
from app.models import AuditLog, ChatMessage, PendingAction, User
from app.schemas import (
    AgentToolInvokeIn,
    AgentToolResult,
    AuditLogOut,
    ChatIn,
    ChatMessageOut,
    ChatOut,
    PendingActionOut,
)

router = APIRouter(prefix="/agent", tags=["agent"])


def chat_msg_out(m: ChatMessage) -> ChatMessageOut:
    return ChatMessageOut(id=m.id, role=m.role, content=m.content, created_at=m.created_at)


def pending_out(action: PendingAction) -> PendingActionOut:
    return PendingActionOut(
        id=action.id,
        tool_name=action.tool_name,
        action_type=action.action_type,
        payload=parse_json(action.payload_json, {}),
        status=action.status,
        result=parse_json(action.result_json, None),
        error=action.error,
        created_at=action.created_at,
        decided_at=action.decided_at,
    )


def audit_out(log: AuditLog) -> AuditLogOut:
    return AuditLogOut(
        id=log.id,
        actor=log.actor,
        action=log.action,
        target=log.target,
        metadata=parse_json(log.metadata_json, {}),
        created_at=log.created_at,
    )


@router.post("/tools/{tool_name}", response_model=AgentToolResult)
async def invoke_tool(
    tool_name: str,
    payload: AgentToolInvokeIn | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    args = payload.arguments if payload else {}
    result = await AgentService().invoke_tool(db, user, tool_name, args)
    return AgentToolResult(**result)


@router.get("/actions", response_model=list[PendingActionOut])
async def actions(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return [pending_out(action) for action in await AgentService().list_pending(db, user)]


@router.post("/actions/{action_id}/approve", response_model=PendingActionOut)
async def approve_action(
    action_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return pending_out(await AgentService().approve(db, user, action_id))


@router.post("/actions/{action_id}/reject", response_model=PendingActionOut)
async def reject_action(
    action_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return pending_out(await AgentService().reject(db, user, action_id))


@router.get("/audit", response_model=list[AuditLogOut])
async def audit(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return [audit_out(log) for log in await AgentService().list_audit_logs(db, user)]


@router.get("/chat/history", response_model=list[ChatMessageOut])
async def chat_history(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    history = await LLMService().get_history(db, user.id)
    return [chat_msg_out(m) for m in history]


@router.post("/chat", response_model=ChatOut)
async def chat(
    payload: ChatIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    response_msg = await LLMService().chat(db, user, payload.message)
    return ChatOut(
        id=response_msg.id,
        role=response_msg.role,
        content=response_msg.content,
        created_at=response_msg.created_at,
    )
