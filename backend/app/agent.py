import json
from typing import Any, Awaitable, Callable

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import MicrosoftOAuthService
from app.graph import GraphClient
from app.models import AuditLog, PendingAction, User, utc_now

READ_TOOLS = {
    "outlook_list_messages",
    "outlook_get_message",
    "outlook_list_folders",
    "outlook_list_events",
}

WRITE_TOOLS = {
    "outlook_send_mail": "send_mail",
    "outlook_create_event": "create_event",
    "outlook_update_event": "update_event",
    "outlook_cancel_event": "cancel_event",
}

# Metadata for Gemini Tool Calling
TOOLS_METADATA = [
    {
        "name": "outlook_list_messages",
        "description": "List emails from the user's Outlook inbox or a specific folder.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "folder_id": {"type": "STRING", "description": "The ID of the folder to list (defaults to 'inbox')."},
                "top": {"type": "INTEGER", "description": "Number of messages to return (default 10)."},
            },
        },
    },
    {
        "name": "outlook_get_message",
        "description": "Get the full content of a specific email by ID.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "message_id": {"type": "STRING", "description": "The unique ID of the message."},
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "outlook_list_folders",
        "description": "List all mail folders in the user's account.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "outlook_list_events",
        "description": "List upcoming calendar events.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "top": {"type": "INTEGER", "description": "Number of events to return (default 10)."},
            },
        },
    },
    {
        "name": "outlook_send_mail",
        "description": "Send a new email. Requires user approval.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "to": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "List of recipient email addresses."},
                "subject": {"type": "STRING", "description": "Subject of the email."},
                "body": {"type": "STRING", "description": "Body content of the email."},
                "cc": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Optional list of CC recipients."},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "outlook_create_event",
        "description": "Create a new calendar event. Requires user approval.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "subject": {"type": "STRING", "description": "Subject of the meeting."},
                "body": {"type": "STRING", "description": "Description of the event."},
                "start": {"type": "STRING", "description": "Start time in ISO format (e.g. 2023-10-27T10:00:00)."},
                "end": {"type": "STRING", "description": "End time in ISO format."},
                "location": {"type": "STRING", "description": "Location display name."},
                "attendees": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "List of attendee emails."},
            },
            "required": ["subject", "start", "end"],
        },
    },
]


def parse_json(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


class AgentService:
    def __init__(self, oauth: MicrosoftOAuthService | None = None) -> None:
        self.oauth = oauth or MicrosoftOAuthService()

    async def _graph(self, db: AsyncSession, user: User) -> GraphClient:
        token = await self.oauth.get_access_token(db, user)
        return GraphClient(token)

    async def invoke_read_tool(
        self, db: AsyncSession, user: User, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        graph = await self._graph(db, user)
        if tool_name == "outlook_list_folders":
            data = {"folders": await graph.list_folders()}
        elif tool_name == "outlook_list_messages":
            data = {
                "messages": await graph.list_messages(
                    folder_id=arguments.get("folder_id", "inbox"),
                    top=int(arguments.get("top", 20)),
                )
            }
        elif tool_name == "outlook_get_message":
            data = {"message": await graph.get_message(arguments["message_id"])}
        elif tool_name == "outlook_list_events":
            data = {"events": await graph.list_events(top=int(arguments.get("top", 20)))}
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown read tool.")

        db.add(AuditLog(user_id=user.id, actor="agent", action=tool_name, metadata_json=json.dumps(data)))
        await db.commit()
        return {"status": "completed", "tool_name": tool_name, "data": data, "message": "Done."}

    async def request_write_approval(
        self, db: AsyncSession, user: User, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        if tool_name not in WRITE_TOOLS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown write tool.")
        action = PendingAction(
            user_id=user.id,
            tool_name=tool_name,
            action_type=WRITE_TOOLS[tool_name],
            payload_json=json.dumps(arguments),
            status="pending",
        )
        db.add(action)
        db.add(
            AuditLog(
                user_id=user.id,
                actor="agent",
                action=f"{tool_name}.pending",
                target=action.id,
                metadata_json=json.dumps(arguments),
            )
        )
        await db.commit()
        await db.refresh(action)
        return {
            "status": "pending_approval",
            "tool_name": tool_name,
            "pending_action_id": action.id,
            "data": {"payload": arguments},
            "message": "A user must approve this Outlook write action.",
        }

    async def invoke_tool(
        self, db: AsyncSession, user: User, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        if tool_name in READ_TOOLS:
            return await self.invoke_read_tool(db, user, tool_name, arguments)
        if tool_name in WRITE_TOOLS:
            return await self.request_write_approval(db, user, tool_name, arguments)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown agent tool.")

    async def invoke_tool_by_email(
        self, db: AsyncSession, user_email: str, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        user = await db.scalar(select(User).where(User.email == user_email))
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        return await self.invoke_tool(db, user, tool_name, arguments)

    async def list_pending(self, db: AsyncSession, user: User) -> list[PendingAction]:
        result = await db.scalars(
            select(PendingAction)
            .where(PendingAction.user_id == user.id)
            .order_by(desc(PendingAction.created_at))
            .limit(50)
        )
        return list(result)

    async def list_audit_logs(self, db: AsyncSession, user: User) -> list[AuditLog]:
        result = await db.scalars(
            select(AuditLog)
            .where(AuditLog.user_id == user.id)
            .order_by(desc(AuditLog.created_at))
            .limit(50)
        )
        return list(result)

    async def approve(self, db: AsyncSession, user: User, action_id: str) -> PendingAction:
        action = await self._owned_action(db, user, action_id)
        if action.status != "pending":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Action is not pending.")

        payload = parse_json(action.payload_json, {})
        graph = await self._graph(db, user)
        executor: dict[str, Callable[[], Awaitable[dict[str, Any]]]] = {
            "send_mail": lambda: graph.send_mail(payload),
            "create_event": lambda: graph.create_event(payload),
            "update_event": lambda: graph.update_event(payload["event_id"], payload),
            "cancel_event": lambda: graph.cancel_event(payload["event_id"], payload.get("comment", "")),
        }
        try:
            result = await executor[action.action_type]()
        except Exception as exc:
            action.status = "failed"
            action.error = str(exc)
            action.decided_at = utc_now()
            db.add(action)
            await db.commit()
            raise

        action.status = "completed"
        action.result_json = json.dumps(result)
        action.decided_at = utc_now()
        db.add(action)
        db.add(
            AuditLog(
                user_id=user.id,
                actor="user",
                action=f"{action.tool_name}.approved",
                target=action.id,
                metadata_json=json.dumps(result),
            )
        )
        await db.commit()
        await db.refresh(action)
        return action

    async def reject(self, db: AsyncSession, user: User, action_id: str) -> PendingAction:
        action = await self._owned_action(db, user, action_id)
        if action.status != "pending":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Action is not pending.")
        action.status = "rejected"
        action.decided_at = utc_now()
        db.add(action)
        db.add(
            AuditLog(
                user_id=user.id,
                actor="user",
                action=f"{action.tool_name}.rejected",
                target=action.id,
                metadata_json=action.payload_json,
            )
        )
        await db.commit()
        await db.refresh(action)
        return action

    async def _owned_action(self, db: AsyncSession, user: User, action_id: str) -> PendingAction:
        action = await db.get(PendingAction, action_id)
        if not action or action.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found.")
        return action
