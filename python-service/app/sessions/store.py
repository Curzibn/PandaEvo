from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.orm import selectinload

from app.db import Message, Session, async_session


@dataclass
class SessionData:
    id: str
    model: str
    title: str | None
    messages: list[dict[str, Any]]
    created_at: str


@dataclass
class SessionSummary:
    id: str
    model: str
    title: str | None
    created_at: str
    message_count: int


def _deserialize_message(m: Message) -> dict[str, Any]:
    if m.role in ("tool", "assistant"):
        try:
            parsed = json.loads(m.content)
            if isinstance(parsed, dict):
                return {"role": m.role, **parsed}
        except (json.JSONDecodeError, TypeError):
            pass
    return {"role": m.role, "content": m.content}


def _to_session_data(session: Session) -> SessionData:
    return SessionData(
        id=session.id,
        model=session.model,
        title=session.title,
        messages=[_deserialize_message(m) for m in session.messages],
        created_at=_iso(session.created_at),
    )


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


class SessionStore:
    async def create(self, model: str) -> SessionData:
        async with async_session() as db:
            session = Session(model=model)
            db.add(session)
            await db.commit()
            await db.refresh(session)
            return SessionData(
                id=session.id,
                model=session.model,
                title=None,
                messages=[],
                created_at=_iso(session.created_at),
            )

    async def get(self, session_id: str) -> SessionData | None:
        async with async_session() as db:
            result = await db.execute(
                select(Session)
                .where(Session.id == session_id)
                .options(selectinload(Session.messages))
            )
            session = result.scalar_one_or_none()
            if session is None:
                return None
            return _to_session_data(session)

    async def delete(self, session_id: str) -> bool:
        async with async_session() as db:
            result = await db.execute(
                delete(Session).where(Session.id == session_id)
            )
            await db.commit()
            return result.rowcount > 0

    async def update_model(self, session_id: str, model: str) -> SessionData | None:
        async with async_session() as db:
            result = await db.execute(
                update(Session)
                .where(Session.id == session_id)
                .values(model=model)
                .returning(Session.id)
            )
            if result.scalar_one_or_none() is None:
                return None
            await db.commit()
        return await self.get(session_id)

    async def append_message(self, session_id: str, role: str, content: str) -> None:
        async with async_session() as db:
            db.add(Message(session_id=session_id, role=role, content=content))
            await db.commit()

    async def update_title(self, session_id: str, title: str) -> None:
        async with async_session() as db:
            await db.execute(
                update(Session)
                .where(Session.id == session_id)
                .values(title=title)
            )
            await db.commit()

    async def list_sessions(self) -> list[SessionSummary]:
        async with async_session() as db:
            result = await db.execute(
                select(Session)
                .options(selectinload(Session.messages))
                .order_by(Session.created_at.desc())
            )
            sessions = result.scalars().all()
            return [
                SessionSummary(
                    id=s.id,
                    model=s.model,
                    title=s.title,
                    created_at=_iso(s.created_at),
                    message_count=len(s.messages),
                )
                for s in sessions
            ]


session_store = SessionStore()
