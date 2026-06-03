import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.database.models import NewApiToken, WeeklySummary
from app.services.crypto import encrypt_secret
from app.services.newapi import NewApiService
from app.services.weekly_report import WeeklyReportGenerator
import datetime
import uuid

client = TestClient(app)

@pytest.mark.anyio
async def test_payment_quota_for_regular_and_vip():
    """
    测试非会员与 VIP 会员的咨询配额校验逻辑
    """
    # 1. 校验非会员配额详情
    response_free = client.get(
        "/api/payment/quota",
        headers={"Authorization": "Bearer test-user-candlepw"}
    )
    assert response_free.status_code == 200
    json_free = response_free.json()
    assert json_free["is_vip"] is False
    assert json_free["quota_limit"] == 10
    
    # 2. 校验带 vip 标识的尊贵会员配额详情
    response_vip = client.get(
        "/api/payment/quota",
        headers={"Authorization": "Bearer test-user-vip-candlepw"}
    )
    assert response_vip.status_code == 200
    json_vip = response_vip.json()
    assert json_vip["is_vip"] is True
    assert json_vip["quota_limit"] == "unlimited"


@pytest.mark.anyio
async def test_payment_checkout_session():
    """
    测试开发期订阅按钮直接切换套餐
    """
    user_id = f"test-user-checkout-{datetime.datetime.utcnow().timestamp()}"
    response = client.post(
        "/api/payment/checkout?plan_id=monthly_vip",
        headers={"Authorization": f"Bearer {user_id}"}
    )
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["plan_id"] == "monthly_vip"
    assert json_data["tier"] == "pro"
    assert json_data["status"] == "active"
    assert json_data["quota"]["features"]["detailed"] is True


@pytest.mark.anyio
async def test_subscription_switch_unlocks_expert_mode():
    """
    免费账号不能使用专家模式，切换 Pro 后立即解锁。
    """
    user_id = f"test-user-subscription-{datetime.datetime.utcnow().timestamp()}"
    headers = {"Authorization": f"Bearer {user_id}"}

    free_quota = client.get("/api/payment/quota", headers=headers)
    assert free_quota.status_code == 200
    assert free_quota.json()["quota"]["tier"] == "free"
    assert free_quota.json()["quota"]["features"]["detailed"] is False

    locked = client.post(
        "/api/chat/stream",
        headers=headers,
        json={"user_input": "帮我制定一个计划", "mode": "detailed"},
    )
    assert locked.status_code == 403
    assert locked.json()["detail"] == "专家模式需要 Pro 或更高套餐。"

    switched = client.post("/api/payment/checkout?plan_id=monthly_vip", headers=headers)
    assert switched.status_code == 200
    assert switched.json()["quota"]["tier"] == "pro"
    assert switched.json()["quota"]["features"]["detailed"] is True
    assert switched.json()["current_period_end"] is not None


@pytest.mark.anyio
async def test_checkout_keeps_existing_newapi_token_active():
    """
    切换套餐不应同步废弃已有 New API token，否则管理接口异常时会导致模型不可用。
    """
    from app.database.session import AsyncSessionLocal

    registered = client.post(
        "/api/auth/register",
        json={
            "email": f"token-keep-{uuid.uuid4().hex}@volshape.local",
            "password": "password123",
            "username": "token keep",
        },
    )
    assert registered.status_code == 200
    payload = registered.json()
    user_id = payload["user"]["id"]
    headers = {"Authorization": f"Bearer {payload['access_token']}"}

    token_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as session:
        session.add(NewApiToken(
            id=token_id,
            user_id=user_id,
            token_ciphertext=encrypt_secret("sk-test-existing-token"),
            token_name="existing-token",
            group_name="default",
            model_limits=[],
            quota_granted=50000,
            quota_available_cache=50000,
            status="active",
        ))
        await session.commit()

    switched = client.post("/api/payment/checkout?plan_id=monthly_vip", headers=headers)
    assert switched.status_code == 200

    async with AsyncSessionLocal() as session:
        token = await session.get(NewApiToken, token_id)
        assert token is not None
        assert token.status == "active"


@pytest.mark.anyio
async def test_trial_pro_can_only_be_claimed_once():
    registered = client.post(
        "/api/auth/register",
        json={
            "email": f"trial-{uuid.uuid4().hex}@volshape.local",
            "password": "password123",
            "username": "trial",
        },
    )
    assert registered.status_code == 200
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

    first = client.post("/api/payment/checkout?plan_id=trial_pro", headers=headers)
    assert first.status_code == 200
    assert first.json()["tier"] == "pro"
    assert first.json()["status"] == "trialing"
    assert first.json()["current_period_end"] is not None

    second = client.post("/api/payment/checkout?plan_id=trial_pro", headers=headers)
    assert second.status_code == 409


@pytest.mark.anyio
async def test_expired_subscription_falls_back_to_free():
    from app.database.models import Subscription
    from app.database.session import AsyncSessionLocal
    from app.services.newapi import get_user_tier

    registered = client.post(
        "/api/auth/register",
        json={
            "email": f"expired-sub-{uuid.uuid4().hex}@volshape.local",
            "password": "password123",
            "username": "expired-sub",
        },
    )
    assert registered.status_code == 200
    user_id = registered.json()["user"]["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        sub = result.scalars().first()
        sub.tier = "pro"
        sub.status = "active"
        sub.current_period_end = datetime.datetime.utcnow() - datetime.timedelta(days=1)
        await session.commit()

        assert await get_user_tier(user_id, session) == "free"


@pytest.mark.anyio
async def test_reuses_rotated_newapi_token_in_development():
    """
    修复上一版订阅切换误把 token 标记为 rotated 后，本地开发环境可自动恢复。
    """
    from app.database.session import AsyncSessionLocal

    registered = client.post(
        "/api/auth/register",
        json={
            "email": f"token-reuse-{uuid.uuid4().hex}@volshape.local",
            "password": "password123",
            "username": "token reuse",
        },
    )
    assert registered.status_code == 200
    payload = registered.json()
    user_id = payload["user"]["id"]
    headers = {"Authorization": f"Bearer {payload['access_token']}"}
    assert client.post("/api/payment/checkout?plan_id=monthly_vip", headers=headers).status_code == 200

    token_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as session:
        session.add(NewApiToken(
            id=token_id,
            user_id=user_id,
            token_ciphertext=encrypt_secret("sk-test-rotated-token"),
            token_name="rotated-token",
            group_name="default",
            model_limits=[],
            quota_granted=50000,
            quota_available_cache=50000,
            status="rotated",
        ))
        await session.commit()

        token = await NewApiService.ensure_user_token(user_id, session)
        assert token.id == token_id
        assert token.status == "active"
        assert token.group_name == "default"


@pytest.mark.anyio
async def test_weekly_report_html_generation(anyio_backend):
    """
    测试周报系统的 HTML 生成质量与留存样式提取
    """
    from app.database.session import AsyncSessionLocal
    
    user_id = "test-user-payment-report"
    
    # 1. 模拟在 PostgreSQL 写入一条周报汇总记录 (weekly_summaries)
    weekly_summary = WeeklySummary(
        id="mock-report-uuid-009",
        user_id=user_id,
        week_start=datetime.date.today() - datetime.timedelta(days=7),
        summary_text="本周训练打卡极好，肩膀完全康复。",
        metrics_snapshot={"weight": 64.0, "body_fat": 17.0}
    )
    
    async with AsyncSessionLocal() as session:
        # 清理老测试数据
        existing = await session.get(WeeklySummary, "mock-report-uuid-009")
        if existing:
            await session.delete(existing)
            await session.commit()
            
        session.add(weekly_summary)
        await session.commit()

        # 2. 触发 HTML 模板渲染
        html = await WeeklyReportGenerator.get_latest_report_html(user_id, session)
        
        # 3. 校验 HTML 内容与美学卡片元素
        assert html is not None
        assert "<!DOCTYPE html>" in html
        assert "VolShape 个人体征周报" in html
        assert "64" in html and "kg" in html
        assert "17" in html and "%" in html
        assert "本周训练打卡极好" in html
