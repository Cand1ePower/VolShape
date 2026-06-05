import json
import asyncio
import datetime
from typing import Any, Dict, List, Optional
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from app.graphs.state import AgentState
from app.graphs.acwr import calculate_acwr
from app.services.memory import MemoryService
from app.services.llm_client import llm_call_structured
from app.services.errors import LLMGatewayError
from app.services.tracing import NodeSpan, get_trace_from_config
from app.services.tavily_search import search_exercise_info
from app.database.models import UserMetrics
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from app.prompts import (
    INTENT_CLASSIFIER_SYSTEM,
    PLANNER_SYSTEM,
    EXECUTOR_SYSTEM, EXECUTOR_CORRECTION_SYSTEM,
    QUICK_COMBINED_SYSTEM,
    EVALUATOR_SYSTEM, CORRECTOR_SYSTEM,
    RESPONSE_TRAINING_SYSTEM, RESPONSE_DIET_SYSTEM,
    RESPONSE_PROFILE_SYSTEM, RESPONSE_CHAT_SYSTEM,
)
from sqlalchemy import select, desc

MAX_CORRECTION_LOOPS = 1


def _format_profile_for_prompt(profile: dict, mem0_context: str = "") -> str:
    del mem0_context
    parts = []
    if profile.get("height_cm"):
        parts.append(f"身高: {profile['height_cm']}cm")
    if profile.get("gender"):
        parts.append(f"性别: {profile['gender']}")
    if profile.get("goal"):
        goal_label = {"cut": "减脂", "bulk": "增肌", "maintain": "维持", "strength": "力量", "endurance": "耐力"}.get(profile["goal"], profile["goal"])
        parts.append(f"目标: {goal_label}")
    if profile.get("training_years"):
        parts.append(f"训练年限: {profile['training_years']}年")
    if profile.get("injuries"):
        parts.append(f"伤病/限制: {', '.join(profile['injuries'])}")
    if profile.get("medical_conditions"):
        parts.append(f"医疗情况: {', '.join(profile['medical_conditions'])}")

    metrics = profile.get("metrics", {})
    if isinstance(metrics, dict):
        for key, val in metrics.items():
            if isinstance(val, dict):
                parts.append(f"{key}: {val.get('value', '')}{val.get('unit', '')}")

    dynamic_attributes = profile.get("dynamic_attributes", {})
    if isinstance(dynamic_attributes, dict):
        for key, val in dynamic_attributes.items():
            if not isinstance(val, dict):
                continue
            value = val.get("value")
            unit = val.get("unit", "")
            if value not in (None, "", []):
                parts.append(f"{key}: {value}{unit}")

    recent = profile.get("_recent_events", [])
    if recent:
        diet_count = sum(1 for e in recent if e.get("type") == "diet")
        if diet_count:
            parts.append(f"近期饮食记录: {diet_count} 条")

    return "; ".join(parts) if parts else "新用户，暂无结构化画像数据"

def _actual_sets_by_exercise(plan_json: dict, completion_data: dict) -> Dict[int, int]:
    completed_map: Dict[int, int] = {}
    if not isinstance(completion_data, dict):
        return completed_map

    completed_keys = completion_data.get("completed_keys")
    if isinstance(completed_keys, list):
        for key in completed_keys:
            try:
                exercise_idx = int(str(key).split("-", 1)[0])
            except (TypeError, ValueError):
                continue
            completed_map[exercise_idx] = completed_map.get(exercise_idx, 0) + 1
        return completed_map

    for raw_idx, value in completion_data.items():
        if not isinstance(value, dict):
            continue
        try:
            exercise_idx = int(str(raw_idx))
        except ValueError:
            continue
        completed_map[exercise_idx] = sum(1 for done in value.values() if done)
    return completed_map


def _format_recent_training_context(profile: dict, recent_events: List[Dict[str, Any]]) -> str:
    sections: List[str] = []

    recent_plans = profile.get("recent_plans", [])
    if recent_plans:
        plan_summaries = []
        for p in recent_plans:
            plan_json = p.get("plan_json", {}) or {}
            completion_data = p.get("completion_data", {}) or {}
            title = plan_json.get("title", "今日训练")
            status_value = p.get("status")
            status_label = "【已完成】" if status_value == "completed" else "【未完成】"
            exercises = plan_json.get("exercises", [])
            actual_sets_map = _actual_sets_by_exercise(plan_json, completion_data)
            ex_details = []
            for idx, exercise in enumerate(exercises):
                name = exercise.get("name")
                if not name:
                    continue
                planned_sets = int(exercise.get("sets") or 0)
                actual_sets = actual_sets_map.get(idx)
                if actual_sets is None and status_value == "completed":
                    actual_sets = 0
                if actual_sets is None:
                    ex_details.append(f"{name}(计划{planned_sets}组)")
                else:
                    ex_details.append(f"{name}(计划{planned_sets}组, 实际{actual_sets}组)")

            completion_summary = ""
            if status_value == "completed":
                total_sets = int(completion_data.get("total_sets") or sum(int(e.get("sets") or 0) for e in exercises if isinstance(e, dict)))
                completed_sets = int(completion_data.get("completed_sets") or sum(actual_sets_map.values()))
                completion_summary = f" | 总完成 {completed_sets}/{total_sets}组"

            plan_summaries.append(
                f"- 日期: {p.get('target_date')} | 计划: {title} | 状态: {status_label}{completion_summary} | 动作: {', '.join(ex_details)}"
            )
        sections.append("[近期训练计划与实际完成]\n" + "\n".join(plan_summaries) + "\n[近期训练计划结束]")

    training_events = []
    for event in recent_events:
        payload = event.get("payload") or {}
        if event.get("type") == "training" and payload.get("total_sets"):
            training_events.append(
                f"- {event.get('date')}: 实际完成 {payload.get('completed_sets', 0)}/{payload.get('total_sets')} 组, 完成率 {payload.get('completion_rate', 0)}"
            )
    if training_events:
        sections.append("[近期训练打卡事件]\n" + "\n".join(training_events[-5:]) + "\n[近期训练打卡结束]")

    return "\n".join(sections)

def _format_current_datetime_context() -> str:
    now = datetime.datetime.now()
    today = now.date()
    yesterday = today - datetime.timedelta(days=1)
    return (
        "[真实当前日期时间]\n"
        f"- 当前本地时间: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"- 今天: {today.isoformat()}\n"
        f"- 昨天: {yesterday.isoformat()}\n"
        "[真实当前日期时间结束]"
    )

def _normalize_exercises(raw_exercises: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_exercises, list):
        return []
    normalized = []
    for item in raw_exercises:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        normalized.append(item)
    return normalized


def _build_prompt_context(
    *,
    agent_instruction: str,
    user_profile: dict,
    mem0_context: str,
    recent_events: List[Dict[str, Any]],
    user_input: str,
    history_text: str = "",
    current_plan_text: str = "",
) -> str:
    sections = [f"[Agent任务]\n{agent_instruction}\n[Agent任务结束]"]

    profile_summary = _format_profile_for_prompt(user_profile)
    if profile_summary:
        sections.append(f"[用户多层记忆]\n{profile_summary}\n[用户多层记忆结束]")

    if mem0_context:
        sections.append(f"[Mem0提取的上下文记忆]\n{mem0_context}\n[Mem0提取的上下文记忆结束]")

    recent_training = _format_recent_training_context(user_profile, recent_events)
    if recent_training:
        sections.append(recent_training)

    if history_text:
        sections.append(history_text.strip())

    sections.append(_format_current_datetime_context())

    if current_plan_text:
        sections.append(f"[当前提取/生成的训练计划]\n{current_plan_text}\n[当前提取/生成的训练计划结束]")

    conflict_resolution = """[记忆冲突处理规则]
当收到的结构化数据与非结构化语义记忆(Mem0)发生冲突时，必须遵守以下优先级：
1. 最高优先级：[用户这次的真实输入]
2. 次高优先级：[真实当前日期时间] 和 [用户多层记忆]（来自数据库的结构化事实）
3. 最低优先级：[Mem0提取的上下文记忆]（仅作补充偏好参考，若与前两者冲突，请忽略 Mem0 数据）
[记忆冲突处理规则结束]"""
    sections.append(conflict_resolution)

    sections.append(f"[用户这次的真实输入]\n{user_input}\n[用户这次的真实输入结束]")
    return "\n\n".join(section for section in sections if section)

async def _save_training_plan(user_id: str, plan_json: dict, db: AsyncSession) -> str:
    from app.database.models import TrainingPlan
    import datetime
    import uuid
    plan_id = str(uuid.uuid4())
    plan_json["plan_id"] = plan_id  # 灏嗙墿鐞?UUID 鍥炲～鑷?plan_json锛屼娇鍓嶇鍗＄墖娓叉煋鏃惰兘鑾峰彇 plan_id
    new_plan = TrainingPlan(
        id=plan_id,
        user_id=user_id,
        plan_json=plan_json,
        target_date=datetime.date.today(),
        status="active"
    )
    db.add(new_plan)
    await db.commit()
    return plan_id


def _format_history(history: List[Dict[str, Any]]) -> str:
    if not history:
        return ""
    parts = []
    for msg in history:
        role = "用户" if msg.get("role") == "user" else "AI"
        content = msg.get("content", "")
        custom_card = msg.get("customCard")
        card_info = ""
        if custom_card and custom_card.get("type") == "workout_card":
            ex_names = [e.get("name") for e in custom_card.get("exercises", []) if e.get("name")]
            card_info = f"【系统生成的卡片: {custom_card.get('title')}，包含动作: {', '.join(ex_names)}】"

        parts.append(f"{role}: {content}{card_info}")

    return "\n[历史对话上下文]\n" + "\n".join(parts) + "\n[历史对话上下文结束]\n"

async def _safe_llm_structured(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    fallback: dict,
    max_tokens: int = 1024,
    user_id: Optional[str] = None,
    db: Optional[AsyncSession] = None,
    session_id: Optional[str] = None,
    langfuse_parent: Optional[Any] = None,  # 浼犲叆 NodeSpan._span 浠ュ缓绔?Langfuse 宓屽杩借釜
) -> dict:
    try:
        return await llm_call_structured(
            system_prompt=system_prompt, user_prompt=user_prompt,
            temperature=temperature, max_tokens=max_tokens,
            user_id=user_id, db=db, session_id=session_id,
            langfuse_parent=langfuse_parent,
        )
    except Exception as e:
        print(f"[LLM Error] {e}")
        if isinstance(e, LLMGatewayError):
            raise
        raise LLMGatewayError(str(e), details={"error_type": e.__class__.__name__}) from e


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?# 1. Intent Classifier
async def intent_classifier_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    db = config["configurable"]["db"]
    user_id = state["user_id"]
    user_input = state["user_input"]
    trace = get_trace_from_config(config)

    with NodeSpan(
        trace, "intent_classifier",
        input_data={
            "user_input": user_input,
            "mode": state.get("mode", "quick"),
            "session_id": state.get("session_id"),
        },
        metadata={"node_order": 1},
    ) as span:
        # 鍚屾鎻愬彇鍜屽啓鍏ョ粨鏋勫寲璁板繂锛圠1/L2/L3 灞傦級
        changes = await MemoryService.extract_and_sync_memory(user_input, user_id, db)

        result = await _safe_llm_structured(
            system_prompt=INTENT_CLASSIFIER_SYSTEM,
            user_prompt=f"用户输入: {user_input}",
            temperature=0.0,
            max_tokens=128,
            fallback={"intent": "chat"},
            user_id=user_id,
            db=db,
            session_id=state.get("session_id"),
            langfuse_parent=span.observation,
        )
        intent = result.get("intent", "chat")
        if intent not in ("training_plan", "diet_log", "profile_update", "chat"):
            intent = "chat"

        span.set_output({
            "intent": intent,
            "memory_changes_count": len(changes),
            "raw_llm_result": result,
        })

    return {"intent": intent, "route": intent}


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?# 2. Profile Retrieval
async def profile_retrieval_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    db = config["configurable"]["db"]
    user_id = state["user_id"]
    trace = get_trace_from_config(config)

    with NodeSpan(
        trace, "profile_retrieval",
        input_data={"user_id": user_id, "intent": state.get("intent")},
        metadata={"node_order": 2},
    ) as span:
        from app.database.models import Events as Evt, TrainingPlan
        profile = await MemoryService.retrieve_aggregated_profile(user_id, db)
        stmt = select(Evt).where(Evt.user_id == user_id).order_by(desc(Evt.event_date)).limit(50)
        result = await db.execute(stmt)
        recent = [{"type": e.event_type, "date": str(e.event_date), "payload": e.payload} for e in reversed(result.scalars().all())]
        profile["_recent_events"] = recent

        # Query recent 5 days saved plans for LLM contextual continuity
        five_days_ago = datetime.date.today() - datetime.timedelta(days=5)
        plan_stmt = select(TrainingPlan).where(
            TrainingPlan.user_id == user_id,
            TrainingPlan.target_date >= five_days_ago
        ).order_by(desc(TrainingPlan.target_date))
        plan_result = await db.execute(plan_stmt)
        recent_plans = [
            {
                "id": p.id,
                "target_date": str(p.target_date),
                "status": p.status,
                "plan_json": p.plan_json,
                "completion_data": p.completion_data or {},
            }
            for p in plan_result.scalars().all()
        ]
        profile["recent_plans"] = recent_plans
        span.set_output({
            "has_profile": bool(profile.get("goal")),
            "recent_events_count": len(recent),
            "recent_plans_count": len(recent_plans),
            "profile_summary": {
                "goal": profile.get("goal"),
                "training_years": profile.get("training_years"),
                "injuries": profile.get("injuries", []),
                "metrics_keys": list(profile.get("metrics", {}).keys()),
            },
        })

    return {"user_profile": profile, "recent_events": recent, "mem0_context": state.get("mem0_context", "")}


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?# 3. Planner
async def planner_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    db = config["configurable"]["db"]
    user_id = state["user_id"]
    user_profile = state.get("user_profile", {})
    user_input = state.get("user_input", "")
    mem0_context = state.get("mem0_context", "")
    history = state.get("conversation_history", [])
    history_text = _format_history(history)
    recent_events = state.get("recent_events", [])
    trace = get_trace_from_config(config)

    with NodeSpan(
        trace, "planner",
        input_data={
            "user_input": user_input,
            "intent": state.get("intent"),
            "profile_goal": user_profile.get("goal"),
            "mem0_context_len": len(mem0_context),
        },
        metadata={"node_order": 3},
    ) as span:
        result = await _safe_llm_structured(
            system_prompt=PLANNER_SYSTEM,
            user_prompt=_build_prompt_context(
                agent_instruction="请先判断用户当前需求，再基于长期记忆、近期训练和当前时间制定本次训练策略框架。",
                user_profile=user_profile,
                mem0_context=mem0_context,
                recent_events=recent_events,
                history_text=history_text,
                user_input=user_input,
            ),
            temperature=0.4,
            fallback={"plan_steps": [
                "Step 1: 全身关节热身与动态拉伸（5-10分钟）",
                "Step 2: 主要复合动作训练",
                "Step 3: 辅助孤立动作训练",
                "Step 4: 整理拉伸与放松（5分钟）",
            ]},
            user_id=user_id,
            db=db,
            session_id=state.get("session_id"),
            langfuse_parent=span.observation,
        )
        plan_steps = result.get("plan_steps", [])
        span.set_output({"plan_steps": plan_steps, "steps_count": len(plan_steps)})

    return {"plan_steps": plan_steps}


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?# 4. Quick Combined (蹇€熸ā寮?
async def quick_combined_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    db = config["configurable"]["db"]
    user_id = state["user_id"]
    user_profile = state.get("user_profile", {})
    plan_steps = state.get("plan_steps", [])
    user_input = state.get("user_input", "")
    mem0_context = state.get("mem0_context", "")
    history = state.get("conversation_history", [])
    history_text = _format_history(history)
    recent_events = state.get("recent_events", [])
    trace = get_trace_from_config(config)

    pr_weights = {}
    for mt in ["bench_press", "squat", "deadlift"]:
        stmt = select(UserMetrics).where(UserMetrics.user_id == user_id, UserMetrics.metric_type == mt).order_by(desc(UserMetrics.recorded_at)).limit(1)
        r = await db.execute(stmt)
        latest = r.scalars().first()
        if latest:
            pr_weights[mt] = float(latest.value)
    pr_text = ", ".join(f"{k}: {v}kg" for k, v in pr_weights.items()) if pr_weights else "暂无 PR 记录"

    with NodeSpan(
        trace, "quick_combined",
        input_data={
            "user_input": user_input,
            "plan_steps": plan_steps,
            "pr_weights": pr_weights,
            "use_training_sheet": state.get("use_training_sheet", False),
        },
        metadata={"node_order": 4, "mode": "quick"},
    ) as span:
        result = await _safe_llm_structured(
            system_prompt=QUICK_COMBINED_SYSTEM,
            user_prompt=_build_prompt_context(
                agent_instruction=f"请在快速模式下一次性完成训练计划生成、动作细化、安全审查与最终回复。PR记录: {pr_text}",
                user_profile=user_profile,
                mem0_context=mem0_context,
                recent_events=recent_events,
                history_text=history_text,
                current_plan_text=json.dumps(plan_steps, ensure_ascii=False),
                user_input=user_input,
            ),
            temperature=0.5,
            max_tokens=2048,
            fallback={
                "exercises": [{"name": "动态拉伸", "sets": 3, "reps": "15", "weight": "0kg", "notes": "热身"}],
                "duration_minutes": 30, "estimated_rpe": 3, "safety_score": 85,
                "final_response": "已为您生成快速训练计划，请查看下方卡片。",
                "disclaimer": "如有疼痛请立即停止。",
            },
            user_id=user_id,
            db=db,
            session_id=state.get("session_id"),
            langfuse_parent=span.observation,
        )

        exercises = result.get("exercises", [])
        final_response = result.get("final_response", "已为您准备好训练计划。")
        disclaimer = result.get("disclaimer", "如有疼痛请立即停止。")
        safety_score = result.get("safety_score", 85)

        use_sheet = state.get("use_training_sheet", False)
        ui = None
        if use_sheet:
            import uuid
            ui = {
                "type": "workout_card",
                "title": "今日训练计划（快速模式）",
                "targetMuscles": [],
                "exercises": [{"name": e.get("name",""), "sets": e.get("sets",3), "reps": e.get("reps","10"), "weight": e.get("weight",""), "notes": e.get("notes","")} for e in exercises],
                "disclaimer": f"安全评分: {safety_score}/100。{disclaimer}",
            }
            ui["plan_id"] = str(uuid.uuid4())

        span.set_output({
            "exercises_count": len(exercises),
            "exercise_names": [e.get("name") for e in exercises],
            "duration_minutes": result.get("duration_minutes", 40),
            "estimated_rpe": result.get("estimated_rpe", 5),
            "safety_score": safety_score,
            "final_response_preview": final_response[:100],
            "has_ui_card": ui is not None,
        })

    return {
        "execution_results": {"exercises": exercises, "duration_minutes": result.get("duration_minutes", 40), "estimated_rpe": result.get("estimated_rpe", 5)},
        "final_response": final_response,
        "ui_components": ui,
        "route": "end",
    }


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?# 5. Executor (浠呰缁嗘ā寮?
async def executor_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    db = config["configurable"]["db"]
    user_id = state["user_id"]
    user_profile = state.get("user_profile", {})
    plan_steps = state.get("plan_steps", [])
    error_count = state.get("error_count", 0)
    corrector_feedback = state.get("corrector_feedback", "")
    history = state.get("conversation_history", [])
    history_text = _format_history(history)
    recent_events = state.get("recent_events", [])
    trace = get_trace_from_config(config)

    pr_weights = {}
    for mt in ["bench_press", "squat", "deadlift"]:
        stmt = select(UserMetrics).where(UserMetrics.user_id == user_id, UserMetrics.metric_type == mt).order_by(desc(UserMetrics.recorded_at)).limit(1)
        r = await db.execute(stmt)
        latest = r.scalars().first()
        if latest:
            pr_weights[mt] = float(latest.value)
    pr_text = ", ".join(f"{k}: {v}kg" for k, v in pr_weights.items()) if pr_weights else "暂无 PR 记录"

    sys = EXECUTOR_CORRECTION_SYSTEM if error_count > 0 else EXECUTOR_SYSTEM
    user_msg = _build_prompt_context(
        agent_instruction=f"请把训练策略细化为可执行动作清单。PR记录: {pr_text}",
        user_profile=user_profile,
        mem0_context=state.get("mem0_context", ""),
        recent_events=recent_events,
        history_text=history_text,
        current_plan_text=json.dumps(plan_steps, ensure_ascii=False),
        user_input=state.get("user_input", ""),
    )
    if error_count > 0:
        user_msg += f"\n第 {error_count + 1} 次修正。修正指令: {corrector_feedback}"

    with NodeSpan(
        trace, "executor",
        input_data={
            "plan_steps": plan_steps,
            "error_count": error_count,
            "is_correction_round": error_count > 0,
            "corrector_feedback": corrector_feedback,
            "pr_weights": pr_weights,
        },
        metadata={"node_order": 5, "mode": "detailed"},
    ) as span:
        result = await _safe_llm_structured(
            system_prompt=sys, user_prompt=user_msg, temperature=0.5,
            fallback={"exercises": [{"name": "动态拉伸", "sets": 3, "reps": "15", "weight": "0kg", "notes": "安全热身"}], "duration_minutes": 20, "estimated_rpe": 2},
            user_id=user_id,
            db=db,
            session_id=state.get("session_id"),
            langfuse_parent=span.observation,
        )

        exercises = _normalize_exercises(result.get("exercises", []))
        repaired = False
        if not exercises:
            repair_prompt = user_msg + (
                "\n\n[结构化修复要求]\n"
                "上一版返回缺少有效的 exercises 数组。"
                "请严格返回 4 到 6 个训练动作，每个动作必须包含"
                " name、sets、reps、weight、rest_seconds、notes。"
                "禁止返回空数组，禁止省略动作名称。"
            )
            repaired_result = await _safe_llm_structured(
                system_prompt=sys,
                user_prompt=repair_prompt,
                temperature=0.2,
                max_tokens=1536,
                fallback={"exercises": [{"name": "动态拉伸", "sets": 3, "reps": "15", "weight": "0kg", "notes": "安全热身"}], "duration_minutes": 20, "estimated_rpe": 2},
                user_id=user_id,
                db=db,
                session_id=state.get("session_id"),
                langfuse_parent=span.observation,
            )
            repaired_exercises = _normalize_exercises(repaired_result.get("exercises", []))
            if repaired_exercises:
                result = repaired_result
                exercises = repaired_exercises
                repaired = True

        duration = result.get("duration_minutes", 45)
        rpe = result.get("estimated_rpe", 7)

        # Tavily search (5s timeout, non-critical)
        tavily_results = []
        if settings.TAVILY_API_KEY and exercises:
            async def _search():
                res = []
                for ex in exercises[:2]:
                    try:
                        sr = await search_exercise_info(ex["name"])
                        if sr: res.append({"exercise": ex["name"], "results": sr})
                    except Exception: pass
                return res
            try:
                tavily_results = await asyncio.wait_for(_search(), timeout=5.0)
            except (asyncio.TimeoutError, Exception): pass

        span.set_output({
            "exercises_count": len(exercises),
            "exercise_names": [e.get("name") for e in exercises],
            "duration_minutes": duration,
            "estimated_rpe": rpe,
            "tavily_results_count": len(tavily_results),
            "repaired_empty_exercises": repaired,
        })

    return {
        "execution_results": {"exercises": exercises, "duration_minutes": duration, "estimated_rpe": rpe},
        "tavily_results": tavily_results,
    }


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?# 6. Evaluator (浠呰缁嗘ā寮?
async def evaluator_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    db = config["configurable"]["db"]
    user_id = state["user_id"]
    user_profile = state.get("user_profile", {})
    execution_results = state.get("execution_results", {})
    exercises = execution_results.get("exercises", [])
    profile_summary = _format_profile_for_prompt(user_profile)
    error_count = state.get("error_count", 0)
    trace = get_trace_from_config(config)

    acwr_result = await calculate_acwr(
        user_id,
        execution_results.get("duration_minutes", 45),
        execution_results.get("estimated_rpe", 7),
        db=db,
    )
    exercises_text = json.dumps(exercises, ensure_ascii=False, indent=2)

    with NodeSpan(
        trace, "evaluator",
        input_data={
            "exercises_count": len(exercises),
            "exercise_names": [e.get("name") for e in exercises],
            "duration_minutes": execution_results.get("duration_minutes", 45),
            "estimated_rpe": execution_results.get("estimated_rpe", 7),
            "acwr": acwr_result["acwr"],
            "acwr_risk": acwr_result["risk"],
            "retry_count": error_count,
        },
        metadata={"node_order": 6, "mode": "detailed"},
    ) as span:
        review = await _safe_llm_structured(
            system_prompt=EVALUATOR_SYSTEM,
            user_prompt=(
                f"用户画像: {profile_summary}\n"
                f"训练计划:\n{exercises_text}\n"
                f"ACWR: {acwr_result['acwr']}, 风险等级: {acwr_result['risk']}, "
                f"历史天数: {acwr_result.get('history_days', 0)}, "
                f"近28天训练次数: {acwr_result.get('training_sessions_28d', 0)}\n"
                f"当前重试次数: {error_count}"
            ),
            temperature=0.2, max_tokens=1536,
            fallback={"score": 85, "feedback": "自动审查通过", "risk": "low"},
            user_id=user_id,
            db=db,
            session_id=state.get("session_id"),
            langfuse_parent=span.observation,
        )

        score = review.get("score", 85)
        feedback = review.get("feedback", "审查通过")
        risk = review.get("risk", acwr_result["risk"])

        # Hard safety override
        acwr_override = False
        if acwr_result["risk"] == "high" and execution_results.get("estimated_rpe", 7) > 3:
            if score > 80:
                score = 60
                feedback += " 【ACWR安全覆盖】急慢性负荷比过高，已强制降级。"
                risk = "high"
                acwr_override = True

        # Prevent infinite loops
        force_pass = False
        if error_count >= MAX_CORRECTION_LOOPS:
            score = 85
            feedback += f" 【已达最大修正次数 {MAX_CORRECTION_LOOPS}，强制通过。】"
            risk = "low"
            force_pass = True

        route = "response_builder" if score >= 85 else "corrector"

        span.set_output({
            "score": score,
            "risk": risk,
            "route": route,
            "acwr_override_triggered": acwr_override,
            "force_pass": force_pass,
            "feedback_preview": feedback[:200],
        })

    return {
        "reflection_result": {"score": score, "feedback": feedback, "risk": risk, "acwr": acwr_result["acwr"]},
        "route": route,
    }


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?# 7. Corrector (浠呰缁嗘ā寮?
async def corrector_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    db = config["configurable"]["db"]
    user_id = state["user_id"]
    error_count = state.get("error_count", 0) + 1
    feedback = state.get("reflection_result", {}).get("feedback", "")
    exercises = state.get("execution_results", {}).get("exercises", [])
    trace = get_trace_from_config(config)

    with NodeSpan(
        trace, "corrector",
        input_data={
            "correction_round": error_count,
            "evaluator_feedback": feedback,
            "current_exercises": [e.get("name") for e in exercises],
        },
        metadata={"node_order": 7, "mode": "detailed"},
    ) as span:
        correction = await _safe_llm_structured(
            system_prompt=CORRECTOR_SYSTEM,
            user_prompt=f"评估反馈: {feedback}\n当前计划: {json.dumps(exercises, ensure_ascii=False)}",
            temperature=0.3, max_tokens=1024,
            fallback={"correction_summary": "降为更保守的主动恢复与拉伸训练", "specific_actions": [], "safety_override": True},
            user_id=user_id,
            db=db,
            session_id=state.get("session_id"),
            langfuse_parent=span.observation,
        )

        combined = f"【第 {error_count} 次修正】{correction.get('correction_summary', '')}"
        if correction.get("specific_actions"):
            combined += f"\n具体措施: {'; '.join(correction['specific_actions'])}"

        span.set_output({
            "correction_round": error_count,
            "correction_summary": correction.get("correction_summary", ""),
            "specific_actions": correction.get("specific_actions", []),
            "safety_override": correction.get("safety_override", False),
        })

    return {"error_count": error_count, "corrector_feedback": combined, "route": "executor"}


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?# 8. Response Builder (璇︾粏妯″紡 / 闈炶缁冩剰鍥剧殑閫氱敤鍥炲鑺傜偣)
async def response_builder_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    db = config["configurable"]["db"]
    user_id = state["user_id"]
    intent = state.get("intent", "chat")
    execution_results = state.get("execution_results", {}) or {}
    reflection = state.get("reflection_result", {})
    exercises = execution_results.get("exercises", [])
    if exercises is None:
        exercises = []
    print(f"[DEBUG response_builder] execution_results keys={list(execution_results.keys())}, exercises count={len(exercises)}, exercises={exercises[:2] if exercises else 'EMPTY'}")

    user_profile = state.get("user_profile", {})
    user_input = state.get("user_input", "")
    mem0_context = state.get("mem0_context", "")
    feedback = reflection.get("feedback", "")
    score = reflection.get("score", 85)
    history = state.get("conversation_history", [])
    history_text = _format_history(history)
    recent_events = state.get("recent_events", [])
    trace = get_trace_from_config(config)

    if intent == "training_plan":
        sys_prompt = RESPONSE_TRAINING_SYSTEM
        ctx = _build_prompt_context(
            agent_instruction=f"请向用户解释训练计划，并明确引用实际训练背景。审查结果: {feedback} (评分: {score})",
            user_profile=user_profile,
            mem0_context=mem0_context,
            recent_events=recent_events,
            history_text=history_text,
            current_plan_text=json.dumps([{'name': e['name'], 'sets': e.get('sets'), 'reps': e.get('reps'), 'weight': e.get('weight')} for e in exercises], ensure_ascii=False) if exercises else '暂无训练动作',
            user_input=user_input,
        )
    elif intent == "diet_log":
        sys_prompt = RESPONSE_DIET_SYSTEM
        ctx = _build_prompt_context(
            agent_instruction="请确认本次饮食记录，并给出简明专业建议。",
            user_profile=user_profile,
            mem0_context=mem0_context,
            recent_events=recent_events,
            history_text=history_text,
            user_input=user_input,
        )
    elif intent == "profile_update":
        sys_prompt = RESPONSE_PROFILE_SYSTEM
        ctx = _build_prompt_context(
            agent_instruction="请确认本次身体数据或画像更新，并说明系统已记住。",
            user_profile=user_profile,
            mem0_context=mem0_context,
            recent_events=recent_events,
            history_text=history_text,
            user_input=user_input,
        )
    else:
        sys_prompt = RESPONSE_CHAT_SYSTEM
        ctx = _build_prompt_context(
            agent_instruction="请优先根据近期训练事实回答用户问题，特别注意今天/昨天这类相对日期要映射到真实日期后再作答。",
            user_profile=user_profile,
            mem0_context=mem0_context,
            recent_events=recent_events,
            history_text=history_text,
            user_input=user_input,
        )

    with NodeSpan(
        trace, "response_builder",
        input_data={
            "intent": intent,
            "user_input": user_input,
            "exercises_count": len(exercises),
            "reflection_score": score,
            "use_training_sheet": state.get("use_training_sheet", False),
        },
        metadata={"node_order": 8},
    ) as span:
        resp = await _safe_llm_structured(
            system_prompt=sys_prompt, user_prompt=ctx, temperature=0.7, max_tokens=512,
            fallback={"final_response": "已为您准备好。"},
            user_id=user_id, db=db, session_id=state.get("session_id"),
            langfuse_parent=span.observation,
        )
        final_response = resp.get("final_response", "已为您准备好。")

        use_sheet = state.get("use_training_sheet", False)
        ui = None
        if use_sheet and intent == "training_plan":
            if not exercises:
                exercises = [{"name": "全身关节活动与动态拉伸", "sets": 3, "reps": "12", "weight": "自重", "notes": "安全热身，唤醒全身状态"}]
            import uuid
            ui = {
                "type": "workout_card",
                "title": "今日训练计划（详细审查模式）",
                "targetMuscles": [],
                "exercises": [{"name": e.get("name",""), "sets": e.get("sets",3), "reps": e.get("reps","10"), "weight": e.get("weight",""), "notes": e.get("notes","")} for e in exercises],
                "disclaimer": f"安全评分: {score}/100。如有疼痛请立即停止。",
            }
            ui["plan_id"] = str(uuid.uuid4())
        elif intent == "diet_log":
            ui = state.get("ui_components")

        span.set_output({
            "intent": intent,
            "final_response_preview": final_response[:200],
            "final_response_len": len(final_response),
            "has_ui_card": ui is not None,
        })

    return {"final_response": final_response, "ui_components": ui, "route": "end"}


# Build the StateGraph
workflow = StateGraph(AgentState)

workflow.add_node("intent_classifier", intent_classifier_node)
workflow.add_node("profile_retrieval", profile_retrieval_node)
workflow.add_node("planner", planner_node)
workflow.add_node("quick_combined", quick_combined_node)
workflow.add_node("executor", executor_node)
workflow.add_node("evaluator", evaluator_node)
workflow.add_node("corrector", corrector_node)
workflow.add_node("response_builder", response_builder_node)

workflow.set_entry_point("intent_classifier")


def route_intent(state: AgentState) -> str:
    # 鎵€鏈夋剰鍥鹃兘鍏堣蛋 profile_retrieval锛岀‘淇?AI 鍥炲鏃惰兘璇诲彇鍒拌缁冨巻鍙层€佽繎鏈熶簨浠剁瓑鏁版嵁
    # 锛堜箣鍓?chat 鎰忓浘鐩存帴璺冲埌 response_builder锛屽鑷?AI 鐪嬩笉鍒拌缁冨畬鎴愯褰曪級
    return "profile_retrieval"


workflow.add_conditional_edges("intent_classifier", route_intent, {
    "profile_retrieval": "profile_retrieval",
})

def route_after_profile(state: AgentState) -> str:
    """profile_retrieval 瀹屾垚鍚庯紝鏍规嵁鎰忓浘鍐冲畾涓嬩竴涓妭鐐广€?    - training_plan 鈫?planner锛堢敓鎴愯缁冭鍒掓祦绋嬶級
    - 鍏朵粬鎰忓浘锛坈hat/diet_log/profile_update锛夆啋 response_builder锛堢洿鎺ョ敓鎴愬洖澶嶏級
    """
    if state.get("intent") == "training_plan":
        return "planner"
    return "response_builder"


workflow.add_conditional_edges("profile_retrieval", route_after_profile, {
    "planner": "planner",
    "response_builder": "response_builder",
})


def route_mode(state: AgentState) -> str:
    mode = state.get("mode", "detailed")
    if mode == "quick":
        return "quick_combined"
    return "executor"


workflow.add_conditional_edges("planner", route_mode, {
    "quick_combined": "quick_combined",
    "executor": "executor",
})

workflow.add_edge("quick_combined", END)

# Detailed mode edges
workflow.add_edge("executor", "evaluator")


def route_evaluation(state: AgentState) -> str:
    return state["route"]


workflow.add_conditional_edges("evaluator", route_evaluation, {
    "corrector": "corrector",
    "response_builder": "response_builder",
})
workflow.add_edge("corrector", "executor")
workflow.add_edge("response_builder", END)

app_workflow = workflow.compile()


