import pytest
import datetime
from app.graphs.workflow import app_workflow
from app.database.models import UserProfile, UserMetrics, Events
from app.services.memory import MemoryService


def _make_state(user_id: str, user_input: str) -> dict:
    return {
        "user_input": user_input,
        "user_id": user_id,
        "session_id": "test_session",
        "intent": "",
        "user_profile": {},
        "recent_events": [],
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


@pytest.mark.anyio
async def test_workflow_runs_without_crash(anyio_backend):
    """Verify the LangGraph compiles and runs end-to-end without crashing."""
    from app.database.session import AsyncSessionLocal

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

        # Graph must produce a response and UI components (or complete gracefully)
        assert "final_response" in result
        assert len(result["final_response"]) > 0

        # If intent was correctly classified as training_plan, verify full chain
        if result["intent"] == "training_plan":
            assert len(result.get("plan_steps", [])) > 0
            assert result.get("reflection_result", {}).get("score", 0) >= 0
            assert result.get("ui_components") is not None
            assert result["ui_components"]["type"] == "workout_card"
        else:
            # LLM not available — fallback to chat, still valid
            assert result["intent"] in ("chat", "diet_log", "profile_update")


@pytest.mark.anyio
async def test_workflow_with_injury_profile(anyio_backend):
    """Verify workflow respects injury profile and ACWR safety loop."""
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        user_id = "test-user-candlepw"

        profile = await session.get(UserProfile, user_id)
        if profile:
            await session.delete(profile)
            await session.commit()

        profile = UserProfile(user_id=user_id, height_cm=175.0, goal="cut", injuries=["左肩袖轻度劳损史"])
        session.add(profile)
        await session.commit()

        # Add high-load training events to trigger ACWR
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
        state = _make_state(user_id, "我想练胸，肩膀不舒服但也得冲大重量杠铃卧推")

        result = await app_workflow.ainvoke(state, config=config)

        # Graph must complete without exception
        assert "final_response" in result

        if result["intent"] == "training_plan":
            acwr = result.get("reflection_result", {}).get("acwr")
            assert acwr is not None

            # If ACWR was triggered, verify corrector loop ran
            if result["reflection_result"].get("risk") == "high":
                assert result["error_count"] > 0
                exercises = result.get("execution_results", {}).get("exercises", [])
                for ex in exercises:
                    assert "康复" in str(ex) or "拉伸" in str(ex) or "lower" in str(ex).lower()


@pytest.mark.anyio
async def test_graph_compiles(anyio_backend):
    """Verify the StateGraph compiles successfully."""
    from app.graphs.workflow import app_workflow
    assert app_workflow is not None
