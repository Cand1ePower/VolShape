import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import desc, select

from app.database.models import Events
from app.database.session import AsyncSessionLocal
from app.main import app
from app.api.workout import summarize_completion

client = TestClient(app)


def test_summarize_completion_supports_nested_progress_shape():
    plan_json = {
        "exercises": [
            {"name": "A", "sets": 3},
            {"name": "B", "sets": 2},
        ]
    }
    completion = {
        "0": {"0": True, "1": True, "2": False},
        "1": {"0": True, "1": False},
    }

    summary = summarize_completion(plan_json, completion)

    assert summary["total_sets"] == 5
    assert summary["completed_sets"] == 3
    assert summary["completed_keys"] == []
    assert summary["completion_rate"] == 0.6


@pytest.mark.anyio
async def test_complete_workout_records_partial_completed_sets():
    registered = client.post(
        "/api/auth/register",
        json={
            "email": f"workout-{uuid.uuid4().hex}@volshape.local",
            "password": "password123",
            "username": "workout",
        },
    )
    assert registered.status_code == 200
    token = registered.json()["access_token"]
    user_id = registered.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    plan_id = str(uuid.uuid4())
    plan_json = {
        "title": "Partial completion plan",
        "duration_minutes": 70,
        "estimated_rpe": 8,
        "exercises": [
            {"name": "A", "sets": 5, "reps": "10"},
            {"name": "B", "sets": 5, "reps": "10"},
            {"name": "C", "sets": 4, "reps": "10"},
            {"name": "D", "sets": 4, "reps": "10"},
            {"name": "E", "sets": 4, "reps": "10"},
        ],
    }
    assert client.post("/api/workout/apply", headers=headers, json={"plan_id": plan_id, "plan_json": plan_json}).status_code == 200

    completed_keys = [f"{i // 4}-{i % 4}" for i in range(12)]
    complete = client.post(
        "/api/workout/complete",
        headers=headers,
        json={
            "plan_id": plan_id,
            "completion_data": {
                "completed_sets": 12,
                "total_sets": 22,
                "completed_keys": completed_keys,
            },
        },
    )
    assert complete.status_code == 200
    assert complete.json()["completion"]["completed_sets"] == 12
    assert complete.json()["completion"]["total_sets"] == 22

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Events)
            .where(Events.user_id == user_id, Events.event_type == "training")
            .order_by(desc(Events.recorded_at))
            .limit(1)
        )
        event = result.scalars().first()
        assert event.payload["completed_sets"] == 12
        assert event.payload["total_sets"] == 22
        assert event.payload["completion_rate"] == 0.55
        assert event.payload["exercise_completion"][0]["name"] == "A"
        assert event.payload["exercise_completion"][0]["planned_sets"] == 5
        assert event.payload["exercise_completion"][0]["completed_sets"] == 4
        assert event.payload["exercise_completion"][2]["name"] == "C"
        assert event.payload["exercise_completion"][2]["completed_sets"] == 4
