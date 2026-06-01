import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.models import WeeklySummary
from app.services.weekly_report import WeeklyReportGenerator
import datetime

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
    测试生成 Stripe 收银台订单
    """
    response = client.post(
        "/api/payment/checkout?plan_id=monthly_vip",
        headers={"Authorization": "Bearer test-user-candlepw"}
    )
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["plan_id"] == "monthly_vip"
    assert "stripe.com" in json_data["checkout_url"]
    assert json_data["status"] == "requires_payment"


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
