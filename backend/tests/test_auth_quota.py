import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.services.quota import QuotaService


client = TestClient(app)


@pytest.mark.anyio
async def test_register_login_refresh_and_me(anyio_backend):
    email = "interview-auth-user@example.com"
    password = "StrongerPass123"

    register_resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "username": "interview"},
    )
    assert register_resp.status_code in (200, 409)

    login_resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200
    payload = login_resp.json()
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["user"]["email"] == email
    assert payload["quota"]["tier"] == "free"

    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {payload['access_token']}"})
    assert me_resp.status_code == 200
    me_payload = me_resp.json()
    assert me_payload["quota"]["tier"] == "free"
    assert me_payload["quota"]["daily_messages"] == 10

    refresh_resp = client.post("/api/auth/refresh", json={"refresh_token": payload["refresh_token"]})
    assert refresh_resp.status_code == 200
    assert refresh_resp.json()["access_token"]
    assert refresh_resp.json()["quota"]["tier"] == "free"


@pytest.mark.anyio
async def test_duplicate_register_returns_conflict(anyio_backend):
    body = {"email": "duplicate-user@example.com", "password": "StrongerPass123"}
    first = client.post("/api/auth/register", json=body)
    second = client.post("/api/auth/register", json=body)

    assert first.status_code in (200, 409)
    assert second.status_code == 409


@pytest.mark.anyio
async def test_free_user_cannot_use_detailed_mode(anyio_backend):
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        with pytest.raises(HTTPException) as exc:
            await QuotaService.assert_can_chat("test-user-free-detailed", session, mode="detailed")

    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_daily_message_limit_is_enforced(anyio_backend):
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        user_id = "test-user-daily-limit"
        for _ in range(10):
            await QuotaService.increment_message(user_id, session)

        with pytest.raises(HTTPException) as exc:
            await QuotaService.assert_can_chat(user_id, session, mode="quick")

    assert exc.value.status_code == 429
