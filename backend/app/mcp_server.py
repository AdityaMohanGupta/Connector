from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import AgentService
from app.database import SessionLocal

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover
    FastMCP = None  # type: ignore[assignment]


async def _invoke(user_email: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async with SessionLocal() as db:
        assert isinstance(db, AsyncSession)
        return await AgentService().invoke_tool_by_email(db, user_email, tool_name, arguments)


def build_mcp_server() -> Any:
    if FastMCP is None:
        return None

    mcp = FastMCP("Outlook Connector", stateless_http=True, json_response=True)
    mcp.settings.streamable_http_path = "/"

    @mcp.tool()
    async def outlook_list_folders(user_email: str) -> dict[str, Any]:
        return await _invoke(user_email, "outlook_list_folders", {})

    @mcp.tool()
    async def outlook_list_messages(user_email: str, folder_id: str = "inbox", top: int = 20) -> dict[str, Any]:
        return await _invoke(
            user_email, "outlook_list_messages", {"folder_id": folder_id, "top": top}
        )

    @mcp.tool()
    async def outlook_get_message(user_email: str, message_id: str) -> dict[str, Any]:
        return await _invoke(user_email, "outlook_get_message", {"message_id": message_id})

    @mcp.tool()
    async def outlook_send_mail(
        user_email: str,
        to: list[str],
        subject: str,
        body: str,
        cc: list[str] | None = None,
    ) -> dict[str, Any]:
        return await _invoke(
            user_email,
            "outlook_send_mail",
            {"to": to, "subject": subject, "body": body, "cc": cc or []},
        )

    @mcp.tool()
    async def outlook_list_events(user_email: str, top: int = 20) -> dict[str, Any]:
        return await _invoke(user_email, "outlook_list_events", {"top": top})

    @mcp.tool()
    async def outlook_create_event(
        user_email: str,
        subject: str,
        start: str,
        end: str,
        body: str = "",
        time_zone: str = "India Standard Time",
        location: str = "",
        attendees: list[str] | None = None,
    ) -> dict[str, Any]:
        return await _invoke(
            user_email,
            "outlook_create_event",
            {
                "subject": subject,
                "body": body,
                "start": start,
                "end": end,
                "time_zone": time_zone,
                "location": location,
                "attendees": attendees or [],
            },
        )

    @mcp.tool()
    async def outlook_update_event(user_email: str, event_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        return await _invoke(user_email, "outlook_update_event", {"event_id": event_id, **updates})

    @mcp.tool()
    async def outlook_cancel_event(user_email: str, event_id: str, comment: str = "") -> dict[str, Any]:
        return await _invoke(
            user_email, "outlook_cancel_event", {"event_id": event_id, "comment": comment}
        )

    return mcp
