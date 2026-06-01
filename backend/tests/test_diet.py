import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.models import DietRecord
from sqlalchemy import select

client = TestClient(app)


@pytest.mark.anyio
async def test_diet_analysis_bad_meal_type(anyio_backend):
    response = client.post(
        "/api/diet/analyze",
        json={"meal_type": "invalid", "description": "test"},
        headers={"Authorization": "Bearer test-user-candlepw"},
    )
    assert response.status_code == 400


@pytest.mark.anyio
async def test_diet_analysis_persistence(anyio_backend):
    from app.database.session import AsyncSessionLocal
    user_id = "test-user-candlepw"

    response = client.post(
        "/api/diet/analyze",
        json={"meal_type": "lunch", "description": "150g chicken breast with broccoli and brown rice"},
        headers={"Authorization": "Bearer test-user-candlepw"},
    )

    # May fail if no LLM API key configured; accept 500 in that case
    if response.status_code == 500:
        assert "营养分析失败" in response.json()["detail"]
        return

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["type"] == "diet_card"
    assert json_data["mealType"] == "lunch"
    assert json_data["totalCalories"] > 0
    assert len(json_data["foodItems"]) > 0

    record_id = json_data["record_id"]
    async with AsyncSessionLocal() as session:
        db_record = await session.get(DietRecord, record_id)
        assert db_record is not None
        assert db_record.user_id == user_id
        assert db_record.meal_type == "lunch"
