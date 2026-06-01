import json
import asyncio
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from app.core.auth import get_current_user_id
from app.core.config import settings
from app.database.session import get_db
from app.database.models import ConversationMessage
from app.graphs.workflow import app_workflow
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, delete

router = APIRouter()


class ChatRequest(BaseModel):
    user_input: str
    session_id: Optional[str] = "default_session"
    mode: Optional[str] = "quick"


NODE_MESSAGE_MAP = {
    "intent_classifier": "正在分析您的意图...",
    "profile_retrieval": "正在加载您的训练画像...",
    "planner": "正在制定训练策略...",
    "quick_combined": "正在为您生成训练计划...",
    "executor": "正在细化训练动作并搜索动作图示...",
    "evaluator": "运动康复专家正在审查计划安全性...",
    "corrector": "安全审查未通过，正在修正计划...",
    "response_builder": "正在生成最终回复...",
}


async def _load_history(user_id: str, session_id: str, db: AsyncSession) -> list[dict]:
    stmt = select(ConversationMessage).where(
        ConversationMessage.user_id == user_id,
        ConversationMessage.session_id == session_id,
    ).order_by(ConversationMessage.created_at).limit(30)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    
    messages = []
    for r in rows:
        try:
            data = json.loads(r.content)
            if isinstance(data, dict) and ("text" in data or "customCard" in data):
                messages.append({
                    "role": r.role,
                    "content": data.get("text", ""),
                    "customCard": data.get("customCard", None)
                })
                continue
        except Exception:
            pass
        messages.append({"role": r.role, "content": r.content})
    return messages


async def _save_message(user_id: str, session_id: str, role: str, content: str, db: AsyncSession, custom_card: Optional[dict] = None):
    if custom_card:
        stored_content = json.dumps({"text": content, "customCard": custom_card}, ensure_ascii=False)
    else:
        stored_content = content
        
    msg = ConversationMessage(id=str(uuid.uuid4()), user_id=user_id, session_id=session_id,
                               role=role, content=stored_content)
    db.add(msg)
    await db.commit()


async def live_agent_stream(user_input: str, user_id: str, mode: str, session_id: str, db: AsyncSession):
    # Load conversation history
    history = await _load_history(user_id, session_id, db)
    hist_text = "\n".join(f"{'用户' if m['role'] == 'user' else 'AI'}: {m['content']}" for m in history[-10:])

    initial_state = {
        "user_input": user_input,
        "user_id": user_id,
        "session_id": session_id,
        "mode": mode,
        "intent": "",
        "user_profile": {},
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

    config = {"configurable": {"db": db}}
    final_state_snapshot = {}

    # Save user message immediately
    await _save_message(user_id, session_id, "user", user_input, db)

    # Langfuse observe
    langfuse_ctx = None
    try:
        from langfuse import Langfuse
        lf = Langfuse(public_key=settings.LANGFUSE_PUBLIC_KEY, secret_key=settings.LANGFUSE_SECRET_KEY, host=settings.LANGFUSE_HOST)
        langfuse_ctx = lf.observe(name=f"chat_{mode}", user_id=user_id)
        langfuse_ctx.__enter__()
    except Exception:
        pass

    try:
        async for chunk in app_workflow.astream(initial_state, config=config):
            for node_name, updates in chunk.items():
                final_state_snapshot.update(updates)
                message = NODE_MESSAGE_MAP.get(node_name, f"执行 {node_name}...")
                yield {"event": "state", "data": json.dumps({"node": node_name.replace("_", " ").title(), "message": message})}

        final_text = final_state_snapshot.get("final_response", "已完成处理。")
        ui_card = final_state_snapshot.get("ui_components")

        # Save bot response with Generative UI card payload
        await _save_message(user_id, session_id, "assistant", final_text, db, custom_card=ui_card)

        # 🌟 每 10 次对话，都对近期记忆做检查把绝对没用的信息剔除 (Episodic Memory GC)
        try:
            from sqlalchemy import func
            count_stmt = select(func.count(ConversationMessage.id)).where(
                ConversationMessage.user_id == user_id
            )
            count_res = await db.execute(count_stmt)
            msg_count = count_res.scalar() or 0

            # 1轮交互包含2条记录(user & bot)。每满 10 次对话（20条消息）即精准触发一次
            if msg_count > 0 and msg_count % 20 == 0:
                from app.services.memory import MemoryService
                # 采用非阻塞 asyncio 背景任务，保障 SSE 流吐字 100% 顺畅
                asyncio.create_task(MemoryService.prune_garbage_episodic_memory(user_id, db))
                print(f"[Memory GC Trigger] User {user_id} has reached {msg_count // 2} rounds. Firing episodic memory GC in background...")
        except Exception as e:
            print(f"[Memory GC Trigger Error] {e}")

        # Stream response
        chunk_size = 30
        for i in range(0, len(final_text), chunk_size):
            chunk = final_text[i: i + chunk_size]
            yield {"event": "token", "data": json.dumps({"text": chunk})}
            await asyncio.sleep(0.01)

        if ui_card:
            yield {"event": "ui", "data": json.dumps(ui_card)}

        if langfuse_ctx:
            try:
                langfuse_ctx.update(output=final_text)
            except Exception:
                pass

        yield {"event": "done", "data": ""}

    finally:
        if langfuse_ctx:
            try:
                langfuse_ctx.__exit__(None, None, None)
            except Exception:
                pass


@router.post("/stream")
async def chat_stream(request: ChatRequest, user_id: str = Depends(get_current_user_id),
                      db: AsyncSession = Depends(get_db)):
    return EventSourceResponse(
        live_agent_stream(request.user_input, user_id, request.mode or "quick",
                          request.session_id or "default_session", db),
        media_type="text/event-stream",
    )


@router.get("/history")
async def get_chat_history(user_id: str = Depends(get_current_user_id),
                           session_id: str = "default_session",
                           db: AsyncSession = Depends(get_db)):
    history = await _load_history(user_id, session_id, db)
    return {"session_id": session_id, "messages": history}


@router.delete("/session")
async def clear_session(user_id: str = Depends(get_current_user_id),
                        session_id: str = "default_session",
                        db: AsyncSession = Depends(get_db)):
    await db.execute(delete(ConversationMessage).where(
        ConversationMessage.user_id == user_id,
        ConversationMessage.session_id == session_id,
    ))
    await db.commit()
    return {"status": "cleared", "session_id": session_id}


@router.get("/profile")
async def get_user_aggregated_profile(user_id: str = Depends(get_current_user_id),
                                      db: AsyncSession = Depends(get_db)):
    from app.services.memory import MemoryService
    from app.database.models import Events, WeeklySummary
    from sqlalchemy import select, desc

    profile = await MemoryService.retrieve_aggregated_profile(user_id, db)

    event_stmt = select(Events).where(Events.user_id == user_id).order_by(desc(Events.event_date)).limit(30)
    event_result = await db.execute(event_stmt)
    events = event_result.scalars().all()
    recent_events = [{"type": e.event_type, "date": str(e.event_date), "payload": e.payload} for e in events]

    summary_stmt = select(WeeklySummary).where(WeeklySummary.user_id == user_id).order_by(desc(WeeklySummary.week_start)).limit(4)
    summary_result = await db.execute(summary_stmt)
    summaries = summary_result.scalars().all()
    weekly_summaries = [{"week_start": str(s.week_start), "text": s.summary_text, "snapshot": s.metrics_snapshot} for s in summaries]

    return {"profile": profile, "recent_events": recent_events, "weekly_summaries": weekly_summaries}
