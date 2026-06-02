import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.database.models import UserProfile
from app.core.auth import get_current_user_id
from app.core.config import settings
from app.services.quota import QuotaService
from app.services.newapi import NewApiService

router = APIRouter()

@router.get("/quota")
async def get_quota_status(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    status_payload = await QuotaService.quota_status(user_id, db)
    newapi_usage = {}
    if NewApiService.enabled():
        try:
            newapi_usage = await NewApiService.sync_token_usage(user_id, db)
        except Exception as e:
            newapi_usage = {"sync_error": e.__class__.__name__}
    is_vip = status_payload["tier"] in ("pro", "premium") or "vip" in user_id.lower()
    return {
        "user_id": user_id,
        "is_vip": is_vip,
        "quota_limit": "unlimited" if is_vip else status_payload["daily_messages"],
        "quota_used": status_payload["daily_messages_used"],
        "subscription_tier": status_payload["tier"],
        "quota": status_payload,
        "newapi_usage": newapi_usage,
    }


@router.post("/checkout")
async def create_checkout_session(
    plan_id: str,
    user_id: str = Depends(get_current_user_id),
):
    if plan_id not in ["monthly_vip", "annual_vip"]:
        raise HTTPException(status_code=400, detail="无效的产品套餐订阅计划ID")

    mock_stripe_url = f"https://checkout.stripe.com/c/pay/cs_test_mock_{uuid.uuid4().hex}"

    return {
        "checkout_url": mock_stripe_url,
        "plan_id": plan_id,
        "status": "requires_payment",
        "message": "Stripe 收银台订单初始化成功，请前往支付。",
    }
