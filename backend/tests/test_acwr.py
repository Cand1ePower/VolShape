import datetime

import pytest

from app.database.models import Events
from app.database.session import AsyncSessionLocal
from app.graphs.acwr import calculate_acwr


@pytest.mark.anyio
async def test_acwr_returns_insufficient_history_for_sparse_users():
    async with AsyncSessionLocal() as session:
        user_id = "acwr-sparse-user"
        result = await calculate_acwr(user_id=user_id, new_session_duration=45, new_session_rpe=7, db=session)

    assert result["acwr"] is None
    assert result["risk"] == "insufficient_history"
    assert result["training_sessions_28d"] == 0


@pytest.mark.anyio
async def test_acwr_returns_ratio_when_history_is_sufficient():
    async with AsyncSessionLocal() as session:
        user_id = "acwr-history-user"
        for days_ago in (3, 8, 15, 22):
            session.add(
                Events(
                    user_id=user_id,
                    event_type="training",
                    payload={"duration_minutes": 60, "rpe": 8},
                    event_date=datetime.date.today() - datetime.timedelta(days=days_ago),
                )
            )
        await session.commit()

        result = await calculate_acwr(user_id=user_id, new_session_duration=45, new_session_rpe=7, db=session)

    assert isinstance(result["acwr"], float)
    assert result["risk"] in {"safe", "moderate", "high"}
    assert result["history_days"] >= 14
    assert result["training_sessions_28d"] == 4
