import datetime

import pytest

from app.database.models import Events, UserProfile
from app.graphs.workflow import app_workflow, _format_recent_training_context
from app.services.memory import MemoryService


def _make_state(user_id: str, user_input: str) -> dict:
    return {
        "user_input": user_input,
        "user_id": user_id,
        "session_id": "test_session",
        "mode": "quick",
        "use_training_sheet": True,
        "intent": "",
        "user_profile": {},
        "mem0_context": "",
        "recent_events": [],
        "conversation_history": [],
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


async def _fake_llm_call_structured(system_prompt, user_prompt, **kwargs):
    if "用户输入" in user_prompt:
        return {"intent": "training_plan"}
    if ("训练策略" in user_prompt or "当前提取/生成的训练计划" in user_prompt) and "PR记录" in user_prompt:
        return {
            "exercises": [
                {"name": "哑铃卧推", "sets": 3, "reps": "10", "weight": "适中", "notes": "控制节奏"},
                {"name": "坐姿推肩", "sets": 3, "reps": "10", "weight": "轻中等", "notes": "避免耸肩"},
            ],
            "duration_minutes": 35,
            "estimated_rpe": 6,
            "safety_score": 90,
            "final_response": "已生成训练计划。",
            "disclaimer": "如有疼痛请立即停止。",
        }
    if "评估反馈" in user_prompt:
        return {
            "correction_summary": "转为肩部友好的主动恢复训练",
            "specific_actions": [],
            "safety_override": True,
        }
    if "训练计划" in user_prompt or "ACWR" in user_prompt:
        return {"score": 90, "feedback": "自动审查通过", "risk": "low"}
    return {"plan_steps": ["热身", "主训练", "整理放松"]}


async def _noop_memory_extraction(*args, **kwargs):
    return []


@pytest.mark.anyio
async def test_workflow_runs_without_crash(monkeypatch, anyio_backend):
    from app.database.session import AsyncSessionLocal

    monkeypatch.setattr("app.graphs.workflow.llm_call_structured", _fake_llm_call_structured)
    monkeypatch.setattr(MemoryService, "extract_and_sync_memory", _noop_memory_extraction)

    async with AsyncSessionLocal() as session:
        user_id = "test-user-candlepw"

        profile = await session.get(UserProfile, user_id)
        if profile:
            await session.delete(profile)
            await session.commit()

        profile = UserProfile(user_id=user_id, height_cm=175.0, goal="cut", training_years=2)
        session.add(profile)
        await session.commit()

        config = {"configurable": {"db": session}}
        state = _make_state(user_id, "今天想安排一次胸肩训练")

        result = await app_workflow.ainvoke(state, config=config)

        assert "final_response" in result
        assert len(result["final_response"]) > 0

        if result["intent"] == "training_plan":
            assert len(result.get("plan_steps", [])) > 0
            assert result.get("reflection_result", {}).get("score", 0) >= 0
            assert result.get("ui_components") is not None
            assert result["ui_components"]["type"] == "workout_card"
        else:
            assert result["intent"] in ("chat", "diet_log", "profile_update")


@pytest.mark.anyio
async def test_workflow_with_injury_profile(monkeypatch, anyio_backend):
    from app.database.session import AsyncSessionLocal

    monkeypatch.setattr("app.graphs.workflow.llm_call_structured", _fake_llm_call_structured)
    monkeypatch.setattr(MemoryService, "extract_and_sync_memory", _noop_memory_extraction)

    async with AsyncSessionLocal() as session:
        user_id = "test-user-candlepw"

        profile = await session.get(UserProfile, user_id)
        if profile:
            await session.delete(profile)
            await session.commit()

        profile = UserProfile(user_id=user_id, height_cm=175.0, goal="cut", injuries=["左肩袖轻度劳损史"])
        session.add(profile)
        await session.commit()

        for i in range(5):
            event = Events(
                user_id=user_id,
                event_type="training",
                payload={"duration_minutes": 90, "rpe": 9},
                event_date=datetime.date.today() - datetime.timedelta(days=i),
            )
            session.add(event)
        await session.commit()

        config = {"configurable": {"db": session}}
        state = _make_state(user_id, "我想练胸，但肩膀不舒服还想冲大重量杠铃卧推")
        state["mode"] = "detailed"
        state["use_training_sheet"] = False

        result = await app_workflow.ainvoke(state, config=config)

        assert "final_response" in result

        if result["intent"] == "training_plan":
            risk = result.get("reflection_result", {}).get("risk")
            assert risk in {"low", "moderate", "high", "safe", "insufficient_history"}


@pytest.mark.anyio
async def test_graph_compiles(anyio_backend):
    assert app_workflow is not None


@pytest.mark.anyio
async def test_recent_training_context_includes_actual_sets(anyio_backend):
    profile = {
        "recent_plans": [
            {
                "target_date": "2026-06-02",
                "status": "completed",
                "plan_json": {
                    "title": "Yesterday workout",
                    "exercises": [
                        {"name": "杠铃深蹲", "sets": 3},
                        {"name": "引体向上", "sets": 3},
                    ],
                },
                "completion_data": {
                    "completed_sets": 5,
                    "total_sets": 6,
                    "completed_keys": ["0-0", "0-1", "0-2", "1-0", "1-1"],
                },
            }
        ]
    }
    recent_events = [
        {
            "type": "training",
            "date": "2026-06-02",
            "payload": {"completed_sets": 5, "total_sets": 6, "completion_rate": 0.83},
        }
    ]

    context = _format_recent_training_context(profile, recent_events)

    assert "2026-06-02" in context
    assert "杠铃深蹲(计划3组, 实际3组)" in context
    assert "引体向上(计划3组, 实际2组)" in context
    assert "实际完成 5/6 组" in context


@pytest.mark.anyio
async def test_detailed_executor_retries_when_exercises_empty(monkeypatch, anyio_backend):
    from app.database.session import AsyncSessionLocal

    call_state = {"executor_calls": 0}

    async def fake_llm(system_prompt, user_prompt, **kwargs):
        if "用户输入" in user_prompt:
            return {"intent": "training_plan"}
        if "结构化修复要求" in user_prompt:
            call_state["executor_calls"] += 1
            return {
                "exercises": [
                    {"name": "平板哑铃卧推", "sets": 4, "reps": "12", "weight": "12kg", "rest_seconds": 60, "notes": "控制离心"},
                    {"name": "上斜哑铃飞鸟", "sets": 3, "reps": "15", "weight": "8kg", "rest_seconds": 60, "notes": "肩胛后收"},
                    {"name": "器械夹胸", "sets": 3, "reps": "15", "weight": "适中", "rest_seconds": 45, "notes": "顶峰收缩"},
                    {"name": "俯卧撑", "sets": 2, "reps": "力竭", "weight": "自重", "rest_seconds": 45, "notes": "收尾充血"},
                ],
                "duration_minutes": 40,
                "estimated_rpe": 6,
            }
        if "请把训练策略细化为可执行动作清单" in user_prompt:
            call_state["executor_calls"] += 1
            return {"exercises": [], "duration_minutes": 40, "estimated_rpe": 6}
        if "ACWR" in user_prompt or "训练计划" in user_prompt:
            return {"score": 90, "feedback": "自动审查通过", "risk": "low"}
        return {"plan_steps": ["热身", "胸部主训练", "整理放松"], "final_response": "已为您准备好。"}

    monkeypatch.setattr("app.graphs.workflow.llm_call_structured", fake_llm)
    monkeypatch.setattr(MemoryService, "extract_and_sync_memory", _noop_memory_extraction)

    async with AsyncSessionLocal() as session:
        user_id = "test-user-executor-repair"
        profile = await session.get(UserProfile, user_id)
        if profile:
            await session.delete(profile)
            await session.commit()

        profile = UserProfile(user_id=user_id, height_cm=175.0, goal="cut", training_years=2)
        session.add(profile)
        await session.commit()

        config = {"configurable": {"db": session}}
        state = _make_state(user_id, "给我一个胸部训练计划")
        state["mode"] = "detailed"

        result = await app_workflow.ainvoke(state, config=config)

        assert result["ui_components"] is not None
        assert result["ui_components"]["type"] == "workout_card"
        assert len(result["ui_components"]["exercises"]) >= 4
        assert result["ui_components"]["exercises"][0]["name"] == "平板哑铃卧推"
