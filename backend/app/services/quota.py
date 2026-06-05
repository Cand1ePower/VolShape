import datetime
import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.database.models import LLMRequest, NewApiToken, Subscription, UserUsageDaily
from app.services.newapi import get_policy_for_user


async def _today_usage(user_id: str, db: AsyncSession) -> UserUsageDaily:
    today = datetime.date.today()
    result = await db.execute(select(UserUsageDaily).where(UserUsageDaily.user_id == user_id, UserUsageDaily.date == today))
    usage = result.scalars().first()
    if usage:
        return usage
    usage = UserUsageDaily(id=str(uuid.uuid4()), user_id=user_id, date=today)
    db.add(usage)
    await db.flush()
    return usage


async def monthly_quota_used(user_id: str, db: AsyncSession) -> int:
    today = datetime.date.today()
    result = await db.execute(
        select(func.coalesce(func.sum(UserUsageDaily.quota_used), 0)).where(
            UserUsageDaily.user_id == user_id,
            extract("year", UserUsageDaily.date) == today.year,
            extract("month", UserUsageDaily.date) == today.month,
        )
    )
    return int(result.scalar() or 0)


class QuotaService:
    @staticmethod
    async def assert_can_chat(user_id: str, db: AsyncSession, mode: str = "quick", estimated_quota: int = 1000) -> None:
        policy = await get_policy_for_user(user_id, db)
        usage = await _today_usage(user_id, db)
        month_used = await monthly_quota_used(user_id, db)

        if usage.message_count >= int(policy.daily_messages):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="今日 AI 对话次数已用完，请升级套餐或明天再试。",
            )

        if month_used + estimated_quota > int(policy.monthly_quota_units):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="本月模型额度不足，请升级套餐或充值。",
            )

        features = policy.features or {}
        if mode == "detailed" and not features.get("detailed", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="专家模式需要 Pro 或更高套餐。",
            )

    @staticmethod
    async def increment_message(user_id: str, db: AsyncSession) -> None:
        usage = await _today_usage(user_id, db)
        usage.message_count += 1
        usage.updated_at = utc_now()
        await db.commit()

    @staticmethod
    async def record_llm_request(
        user_id: str,
        db: AsyncSession,
        model: str,
        newapi_token: Optional[NewApiToken] = None,
        session_id: Optional[str] = None,
        status_value: str = "success",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        quota_used: Optional[int] = None,
        latency_ms: int = 0,
        error_code: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        quota = quota_used if quota_used is not None else prompt_tokens + completion_tokens
        db.add(
            LLMRequest(
                id=str(uuid.uuid4()),
                user_id=user_id,
                session_id=session_id,
                provider="newapi",
                newapi_token_id=newapi_token.id if newapi_token else None,
                model=model,
                status=status_value,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                quota_used=quota,
                latency_ms=latency_ms,
                error_code=error_code,
                request_id=request_id,
            )
        )
        usage = await _today_usage(user_id, db)
        usage.prompt_tokens += int(prompt_tokens or 0)
        usage.completion_tokens += int(completion_tokens or 0)
        usage.quota_used += int(quota or 0)
        usage.updated_at = utc_now()
        await db.commit()

    @staticmethod
    async def quota_status(user_id: str, db: AsyncSession) -> dict:
        policy = await get_policy_for_user(user_id, db)
        usage = await _today_usage(user_id, db)
        month_used = await monthly_quota_used(user_id, db)
        sub_result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
        subscription = sub_result.scalars().first()
        return {
            "tier": policy.tier,
            "subscription_status": subscription.status if subscription else "free",
            "subscription_provider": subscription.provider if subscription else "manual",
            "current_period_start": subscription.current_period_start.isoformat() if subscription and subscription.current_period_start else None,
            "current_period_end": subscription.current_period_end.isoformat() if subscription and subscription.current_period_end else None,
            "daily_messages": int(policy.daily_messages),
            "daily_messages_used": int(usage.message_count),
            "daily_messages_remaining": max(0, int(policy.daily_messages) - int(usage.message_count)),
            "monthly_quota_units": int(policy.monthly_quota_units),
            "monthly_quota_used": int(month_used),
            "monthly_quota_remaining": max(0, int(policy.monthly_quota_units) - int(month_used)),
            "allowed_models": policy.allowed_models or [],
            "features": policy.features or {},
        }
