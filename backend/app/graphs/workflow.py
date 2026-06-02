import json
import asyncio
import datetime
from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from app.graphs.state import AgentState
from app.graphs.acwr import calculate_acwr
from app.services.memory import MemoryService
from app.services.llm_client import llm_call_structured
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

MAX_CORRECTION_LOOPS = 3


def _format_profile_for_prompt(profile: dict, mem0_context: str = "") -> str:
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
        parts.append(f"⚠️ 伤病/限制: {', '.join(profile['injuries'])}")
    if profile.get("medical_conditions"):
        parts.append(f"医疗状况: {', '.join(profile['medical_conditions'])}")
        
    metrics = profile.get("metrics", {})
    if isinstance(metrics, dict):
        for key, val in metrics.items():
            if isinstance(val, dict):
                parts.append(f"{key}: {val.get('value', '')}{val.get('unit', '')}")
                
    # Add recent events summary (no training plans here, only somatic metrics/notes)
    recent = profile.get("_recent_events", [])
    if recent:
        diet_count = sum(1 for e in recent if e.get("type") == "diet")
        if diet_count:
            parts.append(f"近期饮食记录: {diet_count} 条")
            
    # 🌟 主动拉取该用户近5天训练计划物理数据库并注入大模型上下文
    recent_plans = profile.get("recent_plans", [])
    if recent_plans:
        plan_summaries = []
        for p in recent_plans:
            plan_json = p.get("plan_json", {})
            title = plan_json.get("title", "今日训练")
            status_label = "【已完成】" if p.get("status") == "completed" else "【未完成(应用进行中)】"
            exercises = plan_json.get("exercises", [])
            ex_details = [f"{e.get('name')}({e.get('sets')}组)" for e in exercises if e.get("name")]
            plan_summaries.append(f"- 日期: {p.get('target_date')} | 计划: {title} | 状态: {status_label} | 包含动作: {', '.join(ex_details)}")
        parts.append("\n[用户近5天在独立数据库中应用并使用的训练计划数据(专表专用)]:\n" + "\n".join(plan_summaries) + "\n[近5天计划背景结束]\n")

    if mem0_context:
        parts.append("\n[Mem0 高级记忆系统提取的用户特征与上下文]:\n" + mem0_context + "\n[Mem0记忆结束]\n")

    return "; ".join(parts) if parts else "新用户，无历史数据"


async def _save_training_plan(user_id: str, plan_json: dict, db: AsyncSession) -> str:
    from app.database.models import TrainingPlan
    import datetime
    import uuid
    plan_id = str(uuid.uuid4())
    plan_json["plan_id"] = plan_id  # 将物理 UUID 回填至 plan_json，使前端卡片渲染时能获取 plan_id
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
        # 如果是 AI，且携带了卡片信息，我们将卡片里具体的动作和标题回填到对话历史中，让 AI 可以深刻感知
        custom_card = msg.get("customCard")
        card_info = ""
        if custom_card and custom_card.get("type") == "workout_card":
            ex_names = [e.get("name") for e in custom_card.get("exercises", []) if e.get("name")]
            card_info = f"【系统生成的卡片: {custom_card.get('title')}，包含动作: {', '.join(ex_names)}】"
            
        parts.append(f"{role}: {content}{card_info}")
        
    return "\n[历史对话上下文]\n" + "\n".join(parts) + "\n[历史对话上下文结束]\n"


async def _safe_llm_structured(system_prompt: str, user_prompt: str, temperature: float,
                               fallback: dict, max_tokens: int = 1024) -> dict:
    try:
        return await llm_call_structured(
            system_prompt=system_prompt, user_prompt=user_prompt,
            temperature=temperature, max_tokens=max_tokens,
        )
    except Exception as e:
        print(f"[LLM Fallback] {e}")
        return fallback


# ═══════════════════════════════════════════════════════════════
# 1. Intent Classifier
# ═══════════════════════════════════════════════════════════════
async def intent_classifier_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    db = config["configurable"]["db"]
    user_id = state["user_id"]
    user_input = state["user_input"]

    await MemoryService.extract_and_sync_memory(user_input, user_id, db)

    result = await _safe_llm_structured(
        system_prompt=INTENT_CLASSIFIER_SYSTEM,
        user_prompt=f"用户输入: {user_input}",
        temperature=0.0,
        max_tokens=128,
        fallback={"intent": "chat"},
    )
    intent = result.get("intent", "chat")
    if intent not in ("training_plan", "diet_log", "profile_update", "chat"):
        intent = "chat"
    return {"intent": intent, "route": intent}


# ═══════════════════════════════════════════════════════════════
# 2. Profile Retrieval
# ═══════════════════════════════════════════════════════════════
async def profile_retrieval_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    db = config["configurable"]["db"]
    user_id = state["user_id"]
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
            "plan_json": p.plan_json
        }
        for p in plan_result.scalars().all()
    ]
    profile["recent_plans"] = recent_plans

    return {"user_profile": profile, "recent_events": recent}


# ═══════════════════════════════════════════════════════════════
# 3. Planner
# ═══════════════════════════════════════════════════════════════
async def planner_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    user_profile = state.get("user_profile", {})
    user_input = state.get("user_input", "")
    mem0_context = state.get("mem0_context", "")
    profile_summary = _format_profile_for_prompt(user_profile, mem0_context)
    history = state.get("conversation_history", [])
    history_text = _format_history(history)

    result = await _safe_llm_structured(
        system_prompt=PLANNER_SYSTEM,
        user_prompt=f"用户画像: {profile_summary}\n{history_text}\n用户需求: {user_input}",
        temperature=0.4,
        fallback={"plan_steps": [
            "Step 1: 全身关节热身与动态拉伸 (5-10分钟)",
            "Step 2: 主要复合动作训练",
            "Step 3: 辅助孤立动作训练",
            "Step 4: 整理拉伸与泡沫轴放松 (5分钟)",
        ]},
    )
    return {"plan_steps": result.get("plan_steps", [])}


# ═══════════════════════════════════════════════════════════════
# 4. Quick Combined (快速模式)
# ═══════════════════════════════════════════════════════════════
async def quick_combined_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    db = config["configurable"]["db"]
    user_id = state["user_id"]
    user_profile = state.get("user_profile", {})
    plan_steps = state.get("plan_steps", [])
    user_input = state.get("user_input", "")
    mem0_context = state.get("mem0_context", "")
    profile_summary = _format_profile_for_prompt(user_profile, mem0_context)
    history = state.get("conversation_history", [])
    history_text = _format_history(history)

    pr_weights = {}
    for mt in ["bench_press", "squat", "deadlift"]:
        stmt = select(UserMetrics).where(UserMetrics.user_id == user_id, UserMetrics.metric_type == mt).order_by(desc(UserMetrics.recorded_at)).limit(1)
        r = await db.execute(stmt)
        latest = r.scalars().first()
        if latest:
            pr_weights[mt] = float(latest.value)
    pr_text = ", ".join(f"{k}: {v}kg" for k, v in pr_weights.items()) if pr_weights else "无历史记录"

    result = await _safe_llm_structured(
        system_prompt=QUICK_COMBINED_SYSTEM,
        user_prompt=f"用户画像: {profile_summary}\nPR记录: {pr_text}\n{history_text}\n训练策略: {json.dumps(plan_steps, ensure_ascii=False)}\n用户需求: {user_input}",
        temperature=0.5,
        max_tokens=2048,
        fallback={
            "exercises": [{"name": "动态拉伸", "sets": 3, "reps": "15", "weight": "0kg", "notes": "热身"}],
            "duration_minutes": 30, "estimated_rpe": 3, "safety_score": 85,
            "final_response": "已为您生成快速训练计划，请查看下方卡片。",
            "disclaimer": "如有疼痛请立即停止",
        },
    )

    exercises = result.get("exercises", [])
    final_response = result.get("final_response", "已为您准备好训练计划！")
    disclaimer = result.get("disclaimer", "如有疼痛请立即停止")

    import uuid
    ui = {
        "type": "workout_card",
        "title": "今日训练计划（快速模式）",
        "targetMuscles": [],
        "exercises": [{"name": e.get("name",""), "sets": e.get("sets",3), "reps": e.get("reps","10"), "weight": e.get("weight",""), "notes": e.get("notes","")} for e in exercises],
        "disclaimer": f"安全评分: {result.get('safety_score', 85)}/100。{disclaimer}",
    }
    ui["plan_id"] = str(uuid.uuid4()) # 🌟 仅在 UI 中携带临时 plan_id，数据库无物理写入

    return {"execution_results": {"exercises": exercises, "duration_minutes": result.get("duration_minutes", 40), "estimated_rpe": result.get("estimated_rpe", 5)}, "final_response": final_response, "ui_components": ui, "route": "end"}


# ═══════════════════════════════════════════════════════════════
# 5. Executor (仅详细模式)
# ═══════════════════════════════════════════════════════════════
async def executor_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    db = config["configurable"]["db"]
    user_id = state["user_id"]
    user_profile = state.get("user_profile", {})
    plan_steps = state.get("plan_steps", [])
    error_count = state.get("error_count", 0)
    corrector_feedback = state.get("corrector_feedback", "")
    profile_summary = _format_profile_for_prompt(user_profile)
    history = state.get("conversation_history", [])
    history_text = _format_history(history)

    pr_weights = {}
    for mt in ["bench_press", "squat", "deadlift"]:
        stmt = select(UserMetrics).where(UserMetrics.user_id == user_id, UserMetrics.metric_type == mt).order_by(desc(UserMetrics.recorded_at)).limit(1)
        r = await db.execute(stmt)
        latest = r.scalars().first()
        if latest:
            pr_weights[mt] = float(latest.value)
    pr_text = ", ".join(f"{k}: {v}kg" for k, v in pr_weights.items()) if pr_weights else "无历史记录"

    sys = EXECUTOR_CORRECTION_SYSTEM if error_count > 0 else EXECUTOR_SYSTEM
    user_msg = f"用户画像: {profile_summary}\nPR记录: {pr_text}\n{history_text}\n训练策略: {json.dumps(plan_steps, ensure_ascii=False)}"
    if error_count > 0:
        user_msg += f"\n⚠️ 第 {error_count + 1} 次修正。修正指令: {corrector_feedback}"

    result = await _safe_llm_structured(
        system_prompt=sys, user_prompt=user_msg, temperature=0.5,
        fallback={"exercises": [{"name": "动态拉伸", "sets": 3, "reps": "15", "weight": "0kg", "notes": "安全热身"}], "duration_minutes": 20, "estimated_rpe": 2},
    )

    exercises = result.get("exercises", [])
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

    return {
        "execution_results": {"exercises": exercises, "duration_minutes": duration, "estimated_rpe": rpe},
        "tavily_results": tavily_results,
    }


# ═══════════════════════════════════════════════════════════════
# 6. Evaluator (仅详细模式)
# ═══════════════════════════════════════════════════════════════
async def evaluator_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    db = config["configurable"]["db"]
    user_id = state["user_id"]
    user_profile = state.get("user_profile", {})
    execution_results = state.get("execution_results", {})
    exercises = execution_results.get("exercises", [])
    profile_summary = _format_profile_for_prompt(user_profile)
    error_count = state.get("error_count", 0)

    acwr_result = await calculate_acwr(user_id, execution_results.get("duration_minutes", 45), execution_results.get("estimated_rpe", 7), db=db)
    exercises_text = json.dumps(exercises, ensure_ascii=False, indent=2)

    review = await _safe_llm_structured(
        system_prompt=EVALUATOR_SYSTEM,
        user_prompt=f"用户画像: {profile_summary}\n训练计划:\n{exercises_text}\nACWR: {acwr_result['acwr']}, 风险等级: {acwr_result['risk']}\n当前重试次数: {error_count}",
        temperature=0.2, max_tokens=1536,
        fallback={"score": 85, "feedback": "自动审查通过", "risk": "low"},
    )

    score = review.get("score", 85)
    feedback = review.get("feedback", "审查通过")
    risk = review.get("risk", acwr_result["risk"])

    # Hard safety override
    if acwr_result["risk"] == "high" and execution_results.get("estimated_rpe", 7) > 3:
        if score > 80:
            score = 60; feedback += " 【ACWR 安全覆盖】急慢性负荷比过高，强制降级。"; risk = "high"

    # Prevent infinite loops
    if error_count >= MAX_CORRECTION_LOOPS:
        score = 85; feedback += f" 【已达最大修正次数 {MAX_CORRECTION_LOOPS}，强制通过】"; risk = "low"

    route = "response_builder" if score >= 85 else "corrector"
    return {"reflection_result": {"score": score, "feedback": feedback, "risk": risk, "acwr": acwr_result["acwr"]}, "route": route}


# ═══════════════════════════════════════════════════════════════
# 7. Corrector (仅详细模式)
# ═══════════════════════════════════════════════════════════════
async def corrector_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    error_count = state.get("error_count", 0) + 1
    feedback = state.get("reflection_result", {}).get("feedback", "")
    exercises = state.get("execution_results", {}).get("exercises", [])

    correction = await _safe_llm_structured(
        system_prompt=CORRECTOR_SYSTEM,
        user_prompt=f"评估反馈: {feedback}\n当前计划: {json.dumps(exercises, ensure_ascii=False)}",
        temperature=0.3, max_tokens=1024,
        fallback={"correction_summary": "降为主动恢复拉伸日", "specific_actions": [], "safety_override": True},
    )

    combined = f"【第{error_count}次修正】{correction.get('correction_summary', '')}"
    if correction.get("specific_actions"):
        combined += f"\n具体措施: {'; '.join(correction['specific_actions'])}"
    return {"error_count": error_count, "corrector_feedback": combined, "route": "executor"}


# ═══════════════════════════════════════════════════════════════
# 8. Response Builder (仅详细模式)
# ═══════════════════════════════════════════════════════════════
async def response_builder_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    intent = state.get("intent", "chat")
    execution_results = state.get("execution_results", {}) or {}
    reflection = state.get("reflection_result", {})
    exercises = execution_results.get("exercises", [])
    if exercises is None:
        exercises = []
        
    user_profile = state.get("user_profile", {})
    user_input = state.get("user_input", "")
    mem0_context = state.get("mem0_context", "")
    profile_summary = _format_profile_for_prompt(user_profile, mem0_context)
    feedback = reflection.get("feedback", "")
    score = reflection.get("score", 85)
    history = state.get("conversation_history", [])
    history_text = _format_history(history)

    if intent == "training_plan":
        sys, ctx = RESPONSE_TRAINING_SYSTEM, f"用户需求: {user_input}\n画像: {profile_summary}\n{history_text}\n训练计划: {json.dumps([{'name': e['name'], 'sets': e.get('sets'), 'reps': e.get('reps'), 'weight': e.get('weight')} for e in exercises], ensure_ascii=False) if exercises else '无'}\n审查: {feedback} (评分: {score})"
    elif intent == "diet_log":
        sys, ctx = RESPONSE_DIET_SYSTEM, f"用户输入: {user_input}\n画像: {profile_summary}\n{history_text}"
    elif intent == "profile_update":
        sys, ctx = RESPONSE_PROFILE_SYSTEM, f"用户输入: {user_input}\n画像: {profile_summary}\n{history_text}"
    else:
        sys, ctx = RESPONSE_CHAT_SYSTEM, f"用户输入: {user_input}\n画像: {profile_summary}\n{history_text}"

    resp = await _safe_llm_structured(system_prompt=sys, user_prompt=ctx, temperature=0.7, max_tokens=512, fallback={"final_response": "已为您准备好！"})
    final_response = resp.get("final_response", "已为您准备好！")

    ui = None
    if intent == "training_plan":
        if not exercises:
            exercises = [{"name": "全身关节活动与动态拉伸", "sets": 3, "reps": "12", "weight": "自重", "notes": "安全热身，唤醒全身体征"}]
            
        import uuid
        ui = {"type": "workout_card", "title": "今日训练计划（详细审查模式）", "targetMuscles": [],
              "exercises": [{"name": e.get("name",""), "sets": e.get("sets",3), "reps": e.get("reps","10"), "weight": e.get("weight",""), "notes": e.get("notes","")} for e in exercises],
              "disclaimer": f"安全评分: {score}/100。如有疼痛请立即停止。"}
        ui["plan_id"] = str(uuid.uuid4()) # 🌟 仅在 UI 中携带临时 plan_id，数据库无物理写入
    elif intent == "diet_log":
        ui = state.get("ui_components")
    return {"final_response": final_response, "ui_components": ui, "route": "end"}


# ═══════════════════════════════════════════════════════════════
# Build the StateGraph
# ═══════════════════════════════════════════════════════════════
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
    if state["route"] == "training_plan":
        return "profile_retrieval"
    return "response_builder"


workflow.add_conditional_edges("intent_classifier", route_intent, {
    "profile_retrieval": "profile_retrieval",
    "response_builder": "response_builder",
})

workflow.add_edge("profile_retrieval", "planner")


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
