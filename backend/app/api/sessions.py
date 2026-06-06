"""
sessions.py — 会话管理模块
负责: 会话 CRUD、历史消息加载/保存、Session 状态机
从 chat.py 拆分而来，chat.py 只保留 SSE 核心流逻辑
"""
import datetime
import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import ensure_user_profile, get_current_user_id
from app.core.time import utc_now
from app.database.models import ConversationMessage, ConversationSession
from app.database.session import get_db

router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_HISTORY_LIMIT = 50
MAX_HISTORY_LIMIT = 100


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
class ConversationSessionCreateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=120)


class ConversationSessionActionRequest(BaseModel):
    pinned: bool


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _session_ordering():
    return (
        desc(case((ConversationSession.pinned_at.is_not(None), 1), else_=0)),
        desc(ConversationSession.pinned_at),
        desc(func.coalesce(ConversationSession.last_message_at, ConversationSession.updated_at)),
    )


def _clip_session_title(text: str) -> str:
    clean = " ".join((text or "").strip().split())
    if not clean:
        return "新的对话"
    return clean[:40]


def _session_to_dict(session: ConversationSession) -> dict:
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        "pinned_at": session.pinned_at.isoformat() if session.pinned_at else None,
        "is_pinned": bool(session.pinned_at),
        "last_message_at": session.last_message_at.isoformat() if session.last_message_at else None,
    }


async def _touch_session(
    db: AsyncSession,
    user_id: str,
    session_id: str,
    *,
    title: Optional[str] = None,
    last_message_at: Optional[datetime.datetime] = None,
) -> ConversationSession:
    session = await db.get(ConversationSession, session_id)
    now = utc_now()
    if session and session.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问该对话")

    if not session:
        session = ConversationSession(
            id=session_id,
            user_id=user_id,
            title=_clip_session_title(title or "新的对话"),
            created_at=now,
            updated_at=now,
            last_message_at=last_message_at or now,
        )
        db.add(session)
        await db.flush()
        return session

    if title and (session.title == "新的对话" or session.title == "历史对话"):
        session.title = _clip_session_title(title)
    session.updated_at = now
    session.last_message_at = last_message_at or now
    if session.archived_at:
        session.archived_at = None
    await db.flush()
    return session


async def _ensure_conversation_sessions(user_id: str, db: AsyncSession) -> list[ConversationSession]:
    existing = (
        await db.execute(
            select(ConversationSession)
            .where(
                ConversationSession.user_id == user_id,
                ConversationSession.archived_at.is_(None),
            )
            .order_by(*_session_ordering())
        )
    ).scalars().all()
    session_map = {session.id: session for session in existing}

    legacy_rows = (
        await db.execute(
            select(
                ConversationMessage.session_id,
                func.min(ConversationMessage.created_at),
                func.max(ConversationMessage.created_at),
                func.count(ConversationMessage.id),
            )
            .where(ConversationMessage.user_id == user_id)
            .group_by(ConversationMessage.session_id)
        )
    ).all()

    created = False
    for legacy_session_id, first_at, last_at, msg_count in legacy_rows:
        if legacy_session_id in session_map:
            continue
        title = "历史对话"
        first_message = (
            await db.execute(
                select(ConversationMessage)
                .where(
                    ConversationMessage.user_id == user_id,
                    ConversationMessage.session_id == legacy_session_id,
                )
                .order_by(ConversationMessage.created_at.asc())
                .limit(1)
            )
        ).scalars().first()
        if first_message and first_message.role == "user":
            title = _clip_session_title(first_message.content)
        elif msg_count > 0:
            title = "历史对话"

        session = ConversationSession(
            id=legacy_session_id,
            user_id=user_id,
            title=title,
            created_at=first_at or utc_now(),
            updated_at=last_at or utc_now(),
            last_message_at=last_at,
        )
        db.add(session)
        session_map[legacy_session_id] = session
        created = True

    if not session_map:
        session = ConversationSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title="新的对话",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.add(session)
        session_map[session.id] = session
        created = True

    if created:
        await db.commit()
        existing = (
            await db.execute(
                select(ConversationSession)
                .where(
                    ConversationSession.user_id == user_id,
                    ConversationSession.archived_at.is_(None),
                )
                .order_by(*_session_ordering())
            )
        ).scalars().all()
        return existing

    return existing


async def resolve_session_id(
    user_id: str,
    session_id: Optional[str],
    db: AsyncSession,
    *,
    allow_create: bool = False,
) -> str:
    """Public alias used by chat.py and media.py."""
    sessions = await _ensure_conversation_sessions(user_id, db)
    if session_id:
        for session in sessions:
            if session.id == session_id:
                return session_id
        if allow_create:
            await _touch_session(db, user_id, session_id, title="新的对话")
            await db.commit()
            return session_id
        raise HTTPException(status_code=404, detail="对话不存在")
    return sessions[0].id


async def load_history(
    user_id: str,
    session_id: str,
    db: AsyncSession,
    *,
    limit: int = DEFAULT_HISTORY_LIMIT,
    before: Optional[datetime.datetime] = None,
) -> list[dict]:
    """Public alias used by chat.py."""
    safe_limit = max(1, min(limit, MAX_HISTORY_LIMIT))
    stmt = (
        select(ConversationMessage)
        .where(
            ConversationMessage.user_id == user_id,
            ConversationMessage.session_id == session_id,
        )
        .order_by(desc(ConversationMessage.created_at))
        .limit(safe_limit)
    )
    if before:
        stmt = (
            select(ConversationMessage)
            .where(
                ConversationMessage.user_id == user_id,
                ConversationMessage.session_id == session_id,
                ConversationMessage.created_at < before,
            )
            .order_by(desc(ConversationMessage.created_at))
            .limit(safe_limit)
        )
    result = await db.execute(stmt)
    rows = list(reversed(result.scalars().all()))

    messages: list[dict] = []
    for row in rows:
        try:
            data = json.loads(row.content)
            if isinstance(data, dict) and ("text" in data or "customCard" in data):
                messages.append(
                    {
                        "role": row.role,
                        "content": data.get("text", ""),
                        "customCard": data.get("customCard"),
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                    }
                )
                continue
        except Exception:
            pass
        messages.append(
            {
                "role": row.role,
                "content": row.content,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    return messages


async def save_message(
    user_id: str,
    session_id: str,
    role: str,
    content: str,
    db: AsyncSession,
    *,
    custom_card: Optional[dict] = None,
    title_hint: Optional[str] = None,
) -> None:
    """Public alias used by chat.py and media.py."""
    if custom_card:
        stored_content = json.dumps({"text": content, "customCard": custom_card}, ensure_ascii=False)
    else:
        stored_content = content

    try:
        created_at = utc_now()
        await ensure_user_profile(user_id, db)
        await db.flush()
        db.add(
            ConversationMessage(
                id=str(uuid.uuid4()),
                user_id=user_id,
                session_id=session_id,
                role=role,
                content=stored_content,
                created_at=created_at,
            )
        )
        await _touch_session(
            db,
            user_id,
            session_id,
            title=title_hint if role == "user" else None,
            last_message_at=created_at,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise


# ---------------------------------------------------------------------------
# Routes — /api/chat/sessions
# ---------------------------------------------------------------------------
@router.get("/sessions")
async def list_chat_sessions(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    sessions = await _ensure_conversation_sessions(user_id, db)
    return {
        "sessions": [_session_to_dict(session) for session in sessions],
        "active_session_id": sessions[0].id if sessions else None,
    }


@router.post("/sessions")
async def create_chat_session(
    request: ConversationSessionCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    session = ConversationSession(
        id=str(uuid.uuid4()),
        user_id=user_id,
        title=_clip_session_title(request.title or "新的对话"),
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(session)
    await db.commit()
    return {"session": _session_to_dict(session)}


@router.patch("/sessions/{session_id}")
async def update_chat_session(
    session_id: str,
    request: ConversationSessionActionRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    resolved_session_id = await resolve_session_id(user_id, session_id, db)
    session = await db.get(ConversationSession, resolved_session_id)
    if not session or session.user_id != user_id or session.archived_at is not None:
        raise HTTPException(status_code=404, detail="对话不存在")
    session.pinned_at = utc_now() if request.pinned else None
    session.updated_at = utc_now()
    await db.commit()
    await db.refresh(session)
    return {"session": _session_to_dict(session)}


@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    resolved_session_id = await resolve_session_id(user_id, session_id, db)
    session = await db.get(ConversationSession, resolved_session_id)
    if not session or session.user_id != user_id or session.archived_at is not None:
        raise HTTPException(status_code=404, detail="对话不存在")

    await db.execute(
        delete(ConversationMessage).where(
            ConversationMessage.user_id == user_id,
            ConversationMessage.session_id == resolved_session_id,
        )
    )
    session.archived_at = utc_now()
    session.updated_at = utc_now()
    await db.commit()

    sessions = await _ensure_conversation_sessions(user_id, db)
    return {
        "deleted_session_id": resolved_session_id,
        "sessions": [_session_to_dict(item) for item in sessions],
        "active_session_id": sessions[0].id if sessions else None,
    }


@router.get("/history")
async def get_chat_history(
    user_id: str = Depends(get_current_user_id),
    session_id: Optional[str] = None,
    limit: int = Query(DEFAULT_HISTORY_LIMIT, ge=1, le=MAX_HISTORY_LIMIT),
    before: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    resolved_session_id = await resolve_session_id(user_id, session_id, db)
    before_dt = None
    if before:
        try:
            before_dt = datetime.datetime.fromisoformat(before.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="before 参数格式无效") from exc
    history = await load_history(user_id, resolved_session_id, db, limit=limit, before=before_dt)
    return {"session_id": resolved_session_id, "messages": history}


@router.delete("/session")
async def clear_session(
    user_id: str = Depends(get_current_user_id),
    session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    resolved_session_id = await resolve_session_id(user_id, session_id, db)
    await db.execute(
        delete(ConversationMessage).where(
            ConversationMessage.user_id == user_id,
            ConversationMessage.session_id == resolved_session_id,
        )
    )
    session = await db.get(ConversationSession, resolved_session_id)
    if session:
        session.last_message_at = None
        session.updated_at = utc_now()
        if session.title != "新的对话":
            session.title = "新的对话"
    await db.commit()
    return {"status": "cleared", "session_id": resolved_session_id}
