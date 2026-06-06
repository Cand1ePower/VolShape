"""
chat.py — SSE 流式对话核心
职责: 接收用户消息 → 通过 LangGraph workflow 流式处理 → SSE 推送状态/Token/UI卡片

会话管理已迁移至 sessions.py
用户画像/Mem0 查询已迁移至 user_insights.py
"""
import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.auth import get_current_user_id
from app.database.models import ConversationMessage
from app.database.session import AsyncSessionLocal, get_db
from app.graphs.workflow import app_workflow
from app.services.errors import error_payload
from app.services.memory import should_capture_long_term_memory
from app.services.quota import QuotaService
from app.services.tracing import create_trace, finish_trace

# Import shared session helpers from the sessions module
from app.api.sessions import (
    load_history,
    resolve_session_id,
    save_message,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    user_input: str
    session_id: Optional[str] = "default_session"
    mode: Optional[str] = "quick"
    use_training_sheet: Optional[bool] = False


# ---------------------------------------------------------------------------
# SSE node status messages
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Internal: memory GC background task
# ---------------------------------------------------------------------------
async def _run_memory_gc_task(user_id: str) -> None:
    from app.services.memory import MemoryService

    async with AsyncSessionLocal() as db:
        await MemoryService.prune_garbage_episodic_memory(user_id, db)


# ---------------------------------------------------------------------------
# Internal: core SSE generator (owns its own DB session)
# ---------------------------------------------------------------------------
async def _live_agent_stream_with_db(
    user_input: str,
    user_id: str,
    mode: str,
    session_id: str,
    db: AsyncSession,
    use_training_sheet: bool = False,
):
    history = await load_history(user_id, session_id, db)

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

    await save_message(user_id, session_id, "user", user_input, db, title_hint=user_input)

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
                    "data": json.dumps({"event": "state", "data": {"node": node_name.replace("_", " ").title(), "message": message}}),
                }

        final_text = final_state_snapshot.get("final_response", "已完成处理。")
        ui_card = final_state_snapshot.get("ui_components")

        await save_message(user_id, session_id, "assistant", final_text, db, custom_card=ui_card)

        try:
            count_stmt = select(func.count(ConversationMessage.id)).where(ConversationMessage.user_id == user_id)
            count_res = await db.execute(count_stmt)
            msg_count = count_res.scalar() or 0
            if msg_count > 0 and msg_count % 20 == 0:
                asyncio.create_task(_run_memory_gc_task(user_id))
                print(f"[Memory GC Trigger] User {user_id} has reached {msg_count // 2} rounds.")
        except Exception as exc:
            print(f"[Memory GC Trigger Error] {exc}")

        for index in range(0, len(final_text), 30):
            yield {"data": json.dumps({"event": "token", "data": {"text": final_text[index : index + 30]}})}
            await asyncio.sleep(0.01)

        if ui_card:
            yield {"data": json.dumps({"event": "ui", "data": ui_card})}

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
        yield {"data": json.dumps({"event": "done"})}

    except Exception as exc:
        payload = error_payload(exc)
        await save_message(user_id, session_id, "assistant", f"⚠️ {payload['message']}", db)
        yield {"data": json.dumps({"event": "error", "data": payload})}
        yield {"data": json.dumps({"event": "done"})}


async def live_agent_stream(
    user_input: str,
    user_id: str,
    mode: str,
    session_id: str,
    use_training_sheet: bool = False,
):
    """Public entry point: owns its DB session to avoid SSE generator lifecycle issues."""
    async with AsyncSessionLocal() as db:
        async for event in _live_agent_stream_with_db(
            user_input,
            user_id,
            mode,
            session_id,
            db,
            use_training_sheet,
        ):
            yield event


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------
@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await QuotaService.assert_can_chat(user_id, db, request.mode or "quick")
    await QuotaService.increment_message(user_id, db)
    session_id = await resolve_session_id(user_id, request.session_id, db, allow_create=True)
    return EventSourceResponse(
        live_agent_stream(
            request.user_input,
            user_id,
            request.mode or "quick",
            session_id,
            request.use_training_sheet or False,
        ),
        media_type="text/event-stream",
    )
