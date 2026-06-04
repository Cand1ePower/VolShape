import asyncio
import datetime
import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.auth import get_current_user_id
from app.database.models import ConversationMessage, ConversationSession, Events
from app.database.session import get_db
from app.graphs.workflow import app_workflow
from app.services.errors import error_payload
from app.services.memory import should_capture_long_term_memory
from app.services.quota import QuotaService
from app.services.tracing import create_trace, finish_trace

router = APIRouter()


class ChatRequest(BaseModel):
    user_input: str
    session_id: Optional[str] = "default_session"
    mode: Optional[str] = "quick"
    use_training_sheet: Optional[bool] = False


class ConversationSessionCreateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=120)


class ConversationSessionActionRequest(BaseModel):
    pinned: bool


NODE_MESSAGE_MAP = {
    "intent_classifier": "正在分析用户意图...",
    "profile_retrieval": "正在同步用户画像...",
    "planner": "正在制定训练策略...",
    "quick_combined": "正在生成训练计划...",
    "executor": "正在细化训练动作...",
    "evaluator": "正在审核计划安全性...",
    "corrector": "正在修正训练计划...",
    "response_builder": "正在生成最终回复...",
}


def _session_ordering():
    return (
        desc(case((ConversationSession.pinned_at.is_not(None), 1), else_=0)),
        desc(ConversationSession.pinned_at),
        desc(func.coalesce(ConversationSession.last_message_at, ConversationSession.updated_at)),
    )

DEFAULT_HISTORY_LIMIT = 50
MAX_HISTORY_LIMIT = 100


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
    now = datetime.datetime.utcnow()
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
            created_at=first_at or datetime.datetime.utcnow(),
            updated_at=last_at or datetime.datetime.utcnow(),
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
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow(),
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


async def _resolve_session_id(
    user_id: str,
    session_id: Optional[str],
    db: AsyncSession,
    *,
    allow_create: bool = False,
) -> str:
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


async def _load_history(
    user_id: str,
    session_id: str,
    db: AsyncSession,
    *,
    limit: int = DEFAULT_HISTORY_LIMIT,
    before: Optional[datetime.datetime] = None,
) -> list[dict]:
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


async def _save_message(
    user_id: str,
    session_id: str,
    role: str,
    content: str,
    db: AsyncSession,
    *,
    custom_card: Optional[dict] = None,
    title_hint: Optional[str] = None,
) -> None:
    if custom_card:
        stored_content = json.dumps({"text": content, "customCard": custom_card}, ensure_ascii=False)
    else:
        stored_content = content

    created_at = datetime.datetime.utcnow()
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


async def live_agent_stream(
    user_input: str,
    user_id: str,
    mode: str,
    session_id: str,
    db: AsyncSession,
    use_training_sheet: bool = False,
):
    history = await _load_history(user_id, session_id, db)

    initial_state = {
        "user_input": user_input,
        "user_id": user_id,
        "session_id": session_id,
        "mode": mode,
        "use_training_sheet": use_training_sheet,
        "intent": "",
        "user_profile": {},
        "mem0_context": "",
        "recent_events": [],
        "conversation_history": history[-10:],
        "plan_steps": [],
        "execution_results": {},
        "tavily_results": [],
        "reflection_result": {},
        "error_count": 0,
        "corrector_feedback": "",
        "final_response": "",
        "ui_components": None,
        "route": "",
    }

    langfuse_trace, _trace_id = create_trace(
        user_id=user_id,
        session_id=session_id,
        mode=mode,
        user_input=user_input,
    )

    config = {"configurable": {"db": db, "langfuse_trace": langfuse_trace}}
    final_state_snapshot: dict = {}

    await _save_message(user_id, session_id, "user", user_input, db, title_hint=user_input)

    if should_capture_long_term_memory(user_input):
        try:
            from app.services.mem0_client import add_memory_async, search_memory_async

            asyncio.create_task(add_memory_async([{"role": "user", "content": user_input}], user_id))
            initial_state["mem0_context"] = await search_memory_async(user_input, user_id)
        except Exception as exc:
            print(f"[mem0 Error] {exc}")

    try:
        async for chunk in app_workflow.astream(initial_state, config=config):
            for node_name, updates in chunk.items():
                final_state_snapshot.update(updates)
                message = NODE_MESSAGE_MAP.get(node_name, f"正在执行 {node_name}...")
                yield {
                    "event": "state",
                    "data": json.dumps({"node": node_name.replace("_", " ").title(), "message": message}),
                }

        final_text = final_state_snapshot.get("final_response", "已完成处理。")
        ui_card = final_state_snapshot.get("ui_components")

        await _save_message(user_id, session_id, "assistant", final_text, db, custom_card=ui_card)

        try:
            count_stmt = select(func.count(ConversationMessage.id)).where(ConversationMessage.user_id == user_id)
            count_res = await db.execute(count_stmt)
            msg_count = count_res.scalar() or 0
            if msg_count > 0 and msg_count % 20 == 0:
                from app.services.memory import MemoryService

                asyncio.create_task(MemoryService.prune_garbage_episodic_memory(user_id, db))
                print(f"[Memory GC Trigger] User {user_id} has reached {msg_count // 2} rounds.")
        except Exception as exc:
            print(f"[Memory GC Trigger Error] {exc}")

        for index in range(0, len(final_text), 30):
            yield {"event": "token", "data": json.dumps({"text": final_text[index : index + 30]})}
            await asyncio.sleep(0.01)

        if ui_card:
            yield {"event": "ui", "data": json.dumps(ui_card)}

        finish_trace(
            langfuse_trace,
            final_response=final_text,
            intent=final_state_snapshot.get("intent", ""),
            metadata={
                "mode": mode,
                "session_id": session_id,
                "has_ui_card": ui_card is not None,
                "intent": final_state_snapshot.get("intent", ""),
            },
        )
        yield {"event": "done", "data": ""}

    except Exception as exc:
        payload = error_payload(exc)
        await _save_message(user_id, session_id, "assistant", f"⚠️ {payload['message']}", db)
        yield {"event": "error", "data": json.dumps(payload, ensure_ascii=False)}
        yield {"event": "done", "data": ""}


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
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
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
    resolved_session_id = await _resolve_session_id(user_id, session_id, db)
    session = await db.get(ConversationSession, resolved_session_id)
    if not session or session.user_id != user_id or session.archived_at is not None:
        raise HTTPException(status_code=404, detail="对话不存在")
    session.pinned_at = datetime.datetime.utcnow() if request.pinned else None
    session.updated_at = datetime.datetime.utcnow()
    await db.commit()
    await db.refresh(session)
    return {"session": _session_to_dict(session)}


@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    resolved_session_id = await _resolve_session_id(user_id, session_id, db)
    session = await db.get(ConversationSession, resolved_session_id)
    if not session or session.user_id != user_id or session.archived_at is not None:
        raise HTTPException(status_code=404, detail="对话不存在")

    await db.execute(
        delete(ConversationMessage).where(
            ConversationMessage.user_id == user_id,
            ConversationMessage.session_id == resolved_session_id,
        )
    )
    session.archived_at = datetime.datetime.utcnow()
    session.updated_at = datetime.datetime.utcnow()
    await db.commit()

    sessions = await _ensure_conversation_sessions(user_id, db)
    return {
        "deleted_session_id": resolved_session_id,
        "sessions": [_session_to_dict(item) for item in sessions],
        "active_session_id": sessions[0].id if sessions else None,
    }


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await QuotaService.assert_can_chat(user_id, db, request.mode or "quick")
    await QuotaService.increment_message(user_id, db)
    session_id = await _resolve_session_id(user_id, request.session_id, db, allow_create=True)
    return EventSourceResponse(
        live_agent_stream(
            request.user_input,
            user_id,
            request.mode or "quick",
            session_id,
            db,
            request.use_training_sheet or False,
        ),
        media_type="text/event-stream",
    )


@router.get("/history")
async def get_chat_history(
    user_id: str = Depends(get_current_user_id),
    session_id: Optional[str] = None,
    limit: int = Query(DEFAULT_HISTORY_LIMIT, ge=1, le=MAX_HISTORY_LIMIT),
    before: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    resolved_session_id = await _resolve_session_id(user_id, session_id, db)
    before_dt = None
    if before:
        try:
            before_dt = datetime.datetime.fromisoformat(before.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="before 参数格式无效") from exc
    history = await _load_history(user_id, resolved_session_id, db, limit=limit, before=before_dt)
    return {"session_id": resolved_session_id, "messages": history}


@router.delete("/session")
async def clear_session(
    user_id: str = Depends(get_current_user_id),
    session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    resolved_session_id = await _resolve_session_id(user_id, session_id, db)
    await db.execute(
        delete(ConversationMessage).where(
            ConversationMessage.user_id == user_id,
            ConversationMessage.session_id == resolved_session_id,
        )
    )
    session = await db.get(ConversationSession, resolved_session_id)
    if session:
        session.last_message_at = None
        session.updated_at = datetime.datetime.utcnow()
        if session.title != "新的对话":
            session.title = "新的对话"
    await db.commit()
    return {"status": "cleared", "session_id": resolved_session_id}


@router.get("/mem0")
async def get_mem0_memory(user_id: str = Depends(get_current_user_id)):
    from app.services.mem0_client import get_all_memory_async

    memories = await get_all_memory_async(user_id)
    return {"memories": memories}


@router.get("/profile")
async def get_user_aggregated_profile(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    from app.services.memory import MemoryService
    from app.database.models import WeeklySummary

    profile = await MemoryService.retrieve_aggregated_profile(user_id, db)

    event_stmt = select(Events).where(Events.user_id == user_id).order_by(desc(Events.event_date)).limit(30)
    event_result = await db.execute(event_stmt)
    events = event_result.scalars().all()
    recent_events = [{"type": event.event_type, "date": str(event.event_date), "payload": event.payload} for event in events]

    summary_stmt = (
        select(WeeklySummary)
        .where(WeeklySummary.user_id == user_id)
        .order_by(desc(WeeklySummary.week_start))
        .limit(4)
    )
    summary_result = await db.execute(summary_stmt)
    summaries = summary_result.scalars().all()
    weekly_summaries = [
        {"week_start": str(summary.week_start), "text": summary.summary_text, "snapshot": summary.metrics_snapshot}
        for summary in summaries
    ]

    return {"profile": profile, "recent_events": recent_events, "weekly_summaries": weekly_summaries}
