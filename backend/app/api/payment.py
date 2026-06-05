import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.core.time import utc_now
from app.database.models import AuditLog, Subscription
from app.database.session import get_db
from app.services.newapi import NewApiService
from app.services.quota import QuotaService

router = APIRouter()

PLAN_TO_TIER = {
    "free": "free",
    "trial_pro": "pro",
    "monthly_vip": "pro",
    "annual_vip": "premium",
}

PLAN_DURATIONS = {
    "trial_pro": datetime.timedelta(days=7),
    "monthly_vip": datetime.timedelta(days=30),
    "annual_vip": datetime.timedelta(days=365),
}


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
    db: AsyncSession = Depends(get_db),
):
    tier = PLAN_TO_TIER.get(plan_id)
    if not tier:
        raise HTTPException(status_code=400, detail="无效的产品套餐订阅计划ID")

    if plan_id == "trial_pro":
        trial_result = await db.execute(
            select(AuditLog).where(
                AuditLog.actor_user_id == user_id,
                AuditLog.action == "subscription.trial_started",
            )
        )
        if trial_result.scalars().first():
            raise HTTPException(status_code=409, detail="7 天 Pro 试用已领取过")

    result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    subscription = result.scalars().first()
    now = utc_now()
    period_end = now + PLAN_DURATIONS[plan_id] if plan_id in PLAN_DURATIONS else None
    status_value = "trialing" if plan_id == "trial_pro" else "active"
    provider = "trial" if plan_id == "trial_pro" else "manual"

    if subscription:
        subscription.tier = tier
        subscription.status = status_value
        subscription.provider = provider
        subscription.current_period_start = now
        subscription.current_period_end = period_end
        subscription.cancel_at_period_end = False
        subscription.updated_at = now
    else:
        subscription = Subscription(
            id=str(uuid.uuid4()),
            user_id=user_id,
            tier=tier,
            status=status_value,
            provider=provider,
            current_period_start=now,
            current_period_end=period_end,
            cancel_at_period_end=False,
        )
        db.add(subscription)

    if plan_id == "trial_pro":
        db.add(
            AuditLog(
                id=str(uuid.uuid4()),
                actor_user_id=user_id,
                action="subscription.trial_started",
                resource_type="subscription",
                resource_id=subscription.id,
                metadata_json={"tier": tier, "days": 7},
            )
        )

    await db.commit()
    status_payload = await QuotaService.quota_status(user_id, db)

    return {
        "plan_id": plan_id,
        "tier": tier,
        "status": status_value,
        "current_period_end": period_end.isoformat() if period_end else None,
        "quota": status_payload,
        "message": "套餐已切换。",
    }
