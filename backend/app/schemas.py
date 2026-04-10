from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    connected: bool


class AuthUrlOut(BaseModel):
    authorization_url: str


class SendMailIn(BaseModel):
    to: list[EmailStr]
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)
    cc: list[EmailStr] = Field(default_factory=list)
    save_to_sent_items: bool = True


class EventIn(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    body: str = ""
    start: str
    end: str
    time_zone: str = "India Standard Time"
    location: str = ""
    attendees: list[str] = Field(default_factory=list)


class EventUpdateIn(BaseModel):
    subject: str | None = None
    body: str | None = None
    start: str | None = None
    end: str | None = None
    time_zone: str = "India Standard Time"
    location: str | None = None
    attendees: list[EmailStr] | None = None


class AgentToolInvokeIn(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


class PendingActionOut(BaseModel):
    id: str
    tool_name: str
    action_type: str
    payload: dict[str, Any]
    status: str
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime
    decided_at: datetime | None


class AuditLogOut(BaseModel):
    id: str
    actor: str
    action: str
    target: str
    metadata: dict[str, Any]
    created_at: datetime


class AgentToolResult(BaseModel):
    status: Literal["completed", "pending_approval", "error"]
    tool_name: str
    data: dict[str, Any] = Field(default_factory=dict)
    pending_action_id: str | None = None
    message: str = ""
