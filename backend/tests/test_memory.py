import datetime

import pytest
from sqlalchemy import select

from app.database.models import Events, UserMetrics, UserProfile
from app.services.memory import MemoryService, should_capture_long_term_memory


@pytest.mark.anyio
async def test_should_capture_long_term_memory_filters_trivial_chat(anyio_backend):
    assert should_capture_long_term_memory("今天不是3号吗") is False
    assert should_capture_long_term_memory("谢谢") is False


@pytest.mark.anyio
async def test_should_capture_long_term_memory_keeps_meaningful_state(anyio_backend):
    assert should_capture_long_term_memory("我今天感冒了，而且特别累") is True
    assert should_capture_long_term_memory("我昨天练了卧推5组，每组8次") is True


@pytest.mark.anyio
async def test_extract_dynamic_state_updates_profile_and_recent_events(anyio_backend, monkeypatch):
    from app.database.session import AsyncSessionLocal

    async def fake_extract(user_input: str, user_id: str, db):
        return [
            {
                "type": "state",
                "key": "current_illness",
                "value": "感冒",
                "confidence": 0.96,
                "reason": "User explicitly said they caught a cold.",
            }
        ]

    monkeypatch.setattr("app.services.memory._llm_extract_memory", fake_extract)

    async with AsyncSessionLocal() as session:
        user_id = "test-dynamic-state-user"
        changes = await MemoryService.extract_and_sync_memory("我刚刚感冒了", user_id, session)

        assert len(changes) == 1
        assert changes[0]["key"] == "current_illness"
        assert changes[0]["layer"] == 2

        profile = await session.get(UserProfile, user_id)
        assert profile is not None
        assert profile.dynamic_attributes["current_illness"]["value"] == "感冒"
        assert profile.dynamic_attributes["current_illness"]["type"] == "state"

        events = (
            await session.execute(select(Events).where(Events.user_id == user_id).order_by(Events.recorded_at.desc()))
        ).scalars().all()
        assert len(events) == 1
        assert events[0].event_type == "current_illness"
        assert events[0].payload["value"] == "感冒"

        aggregated = await MemoryService.retrieve_aggregated_profile(user_id, session)
        assert aggregated["dynamic_attributes"]["current_illness"]["value"] == "感冒"


@pytest.mark.anyio
async def test_extract_arbitrary_metric_persists_to_layer2(anyio_backend, monkeypatch):
    from app.database.session import AsyncSessionLocal

    async def fake_extract(user_input: str, user_id: str, db):
        return [{"type": "metric", "key": "resting_heart_rate", "value": 58, "unit": "bpm"}]

    monkeypatch.setattr("app.services.memory._llm_extract_memory", fake_extract)

    async with AsyncSessionLocal() as session:
        user_id = "test-arbitrary-metric-user"
        changes = await MemoryService.extract_and_sync_memory("我静息心率 58", user_id, session)

        assert len(changes) == 1
        assert changes[0]["key"] == "resting_heart_rate"
        assert changes[0]["new"] == 58.0

        metrics = (
            await session.execute(
                select(UserMetrics).where(
                    UserMetrics.user_id == user_id,
                    UserMetrics.metric_type == "resting_heart_rate",
                )
            )
        ).scalars().all()
        assert len(metrics) == 1
        assert float(metrics[0].value) == 58.0
        assert metrics[0].unit == "bpm"

        aggregated = await MemoryService.retrieve_aggregated_profile(user_id, session)
        assert aggregated["metrics"]["resting_heart_rate"]["value"] == 58.0


@pytest.mark.anyio
async def test_injury_recovery_add_and_remove(anyio_backend, monkeypatch):
    from app.database.session import AsyncSessionLocal

    responses = [
        [{"type": "injury", "key": "wrist_injury", "value": "TFCC不适", "action": "add"}],
        [{"type": "injury", "key": "wrist_injury", "value": "TFCC不适", "action": "remove"}],
    ]

    async def fake_extract(user_input: str, user_id: str, db):
        return responses.pop(0)

    monkeypatch.setattr("app.services.memory._llm_extract_memory", fake_extract)

    async with AsyncSessionLocal() as session:
        user_id = "test-injury-recovery-user"
        changes_add = await MemoryService.extract_and_sync_memory("我手腕 TFCC 不舒服", user_id, session)
        assert changes_add[0]["key"] == "injuries"

        aggregated = await MemoryService.retrieve_aggregated_profile(user_id, session)
        assert "TFCC不适" in aggregated["injuries"]

        changes_remove = await MemoryService.extract_and_sync_memory("我的 TFCC 已经恢复了", user_id, session)
        assert changes_remove[0]["key"] == "injuries"

        aggregated = await MemoryService.retrieve_aggregated_profile(user_id, session)
        assert "TFCC不适" not in aggregated["injuries"]


@pytest.mark.anyio
async def test_profile_core_still_writes_fixed_columns(anyio_backend, monkeypatch):
    from app.database.session import AsyncSessionLocal

    async def fake_extract(user_input: str, user_id: str, db):
        return [
            {"type": "profile_core", "key": "height_cm", "value": 175},
            {"type": "metric", "key": "weight", "value": 64, "unit": "kg"},
        ]

    monkeypatch.setattr("app.services.memory._llm_extract_memory", fake_extract)

    async with AsyncSessionLocal() as session:
        user_id = "test-profile-core-user"
        changes = await MemoryService.extract_and_sync_memory("我175cm，64kg", user_id, session)

        assert {change["key"] for change in changes} == {"height_cm", "weight"}

        profile = await session.get(UserProfile, user_id)
        assert float(profile.height_cm) == 175.0

        aggregated = await MemoryService.retrieve_aggregated_profile(user_id, session)
        assert aggregated["height_cm"] == 175.0
        assert aggregated["metrics"]["weight"]["value"] == 64.0
