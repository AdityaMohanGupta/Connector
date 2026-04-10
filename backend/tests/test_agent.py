import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agent import AgentService
from app.database import Base
from app.models import PendingAction, User


@pytest.mark.asyncio
async def test_write_tool_creates_pending_action() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        user = User(
            microsoft_user_id="ms-user",
            email="user@example.com",
            display_name="User",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        result = await AgentService().request_write_approval(
            db,
            user,
            "outlook_send_mail",
            {"to": ["a@example.com"], "subject": "Hi", "body": "Body"},
        )
        action = await db.get(PendingAction, result["pending_action_id"])

    assert result["status"] == "pending_approval"
    assert action is not None
    assert action.status == "pending"
