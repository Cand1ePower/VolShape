import datetime
import os
import uuid
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.time import utc_now
from app.database.models import NewApiToken, Subscription, UserQuotaPolicy
from app.services.crypto import decrypt_secret, encrypt_secret
from app.services.errors import NewApiProvisionError


def _policy_models() -> list[str]:
    models = [
        settings.LLM_LIGHT_MODEL,
        settings.LLM_HEAVY_MODEL,
        settings.LLM_VISION_MODEL,
        "deepseek-v4-flash",
        "deepseek-chat",
    ]
    unique: list[str] = []
    for model in models:
        if model and model not in unique:
            unique.append(model)
    return unique


DEFAULT_POLICIES = {
    "free": {
        "daily_messages": 10,
        "monthly_quota_units": 50_000,
        "allowed_models": _policy_models(),
        "max_context_tokens": 16_000,
        "max_output_tokens": 2048,
        "features": {"quick": True, "detailed": False, "training_sheet": True},
    },
    "pro": {
        "daily_messages": 100,
        "monthly_quota_units": 1_000_000,
        "allowed_models": _policy_models(),
        "max_context_tokens": 64_000,
        "max_output_tokens": 4096,
        "features": {"quick": True, "detailed": True, "training_sheet": True},
    },
    "premium": {
        "daily_messages": 500,
        "monthly_quota_units": 5_000_000,
        "allowed_models": _policy_models(),
        "max_context_tokens": 128_000,
        "max_output_tokens": 8192,
        "features": {"quick": True, "detailed": True, "training_sheet": True, "weekly_report": True},
    },
}


def group_for_tier(tier: str) -> str:
    if tier == "premium":
        return settings.NEWAPI_DEFAULT_PREMIUM_GROUP
    if tier == "pro":
        return settings.NEWAPI_DEFAULT_PRO_GROUP
    return settings.NEWAPI_DEFAULT_FREE_GROUP


async def ensure_quota_policies(db: AsyncSession) -> None:
    for tier, spec in DEFAULT_POLICIES.items():
        result = await db.execute(select(UserQuotaPolicy).where(UserQuotaPolicy.tier == tier))
        if result.scalars().first():
            continue
        db.add(UserQuotaPolicy(id=str(uuid.uuid4()), tier=tier, **spec))
    await db.commit()


async def get_user_tier(user_id: str, db: AsyncSession) -> str:
    result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    sub = result.scalars().first()
    if not sub or sub.status not in ("trialing", "active"):
        return "free"
    if sub.current_period_end and sub.current_period_end < utc_now():
        sub.status = "expired"
        sub.updated_at = utc_now()
        await db.commit()
        return "free"
    return sub.tier or "free"


async def get_policy_for_user(user_id: str, db: AsyncSession) -> UserQuotaPolicy:
    await ensure_quota_policies(db)
    tier = await get_user_tier(user_id, db)
    result = await db.execute(select(UserQuotaPolicy).where(UserQuotaPolicy.tier == tier))
    policy = result.scalars().first()
    if policy:
        return policy
    result = await db.execute(select(UserQuotaPolicy).where(UserQuotaPolicy.tier == "free"))
    return result.scalars().one()


class NewApiService:
    @staticmethod
    def enabled() -> bool:
        return bool(settings.NEWAPI_BASE_URL) and os.getenv("TESTING") != "1"

    @staticmethod
    async def query_token_usage(api_key: str) -> dict:
        if not settings.NEWAPI_BASE_URL:
            return {}
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(
                f"{settings.NEWAPI_BASE_URL.rstrip('/')}/api/usage/token/",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            payload = resp.json()
            return payload.get("data", payload)

    @staticmethod
    async def _fetch_token_key(client: httpx.AsyncClient, headers: dict, token_id: str) -> Optional[str]:
        resp = await client.post(
            f"{settings.NEWAPI_BASE_URL.rstrip('/')}/api/token/{token_id}/key",
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json().get("data") or {}
        raw_key = data.get("key")
        if not raw_key:
            return None
        return raw_key if raw_key.startswith("sk-") else f"sk-{raw_key}"

    @staticmethod
    async def _find_token_id_by_name(client: httpx.AsyncClient, headers: dict, token_name: str) -> Optional[str]:
        resp = await client.get(
            f"{settings.NEWAPI_BASE_URL.rstrip('/')}/api/token/?p=0&page_size=100",
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json().get("data") or {}
        items = data.get("items") if isinstance(data, dict) else data
        if not isinstance(items, list):
            return None

        matches = [item for item in items if item.get("name") == token_name and item.get("id") is not None]
        if not matches:
            return None
        matches.sort(key=lambda item: int(item.get("id") or 0), reverse=True)
        return str(matches[0]["id"])

    @staticmethod
    async def _create_token_with_management_api(user_id: str, tier: str, policy: UserQuotaPolicy) -> Optional[tuple[str, Optional[str]]]:
        if os.getenv("TESTING") == "1":
            return None
        if not (settings.NEWAPI_BASE_URL and settings.NEWAPI_SYSTEM_TOKEN and settings.NEWAPI_AUTO_PROVISION_TOKENS):
            return None

        model_limits = policy.allowed_models or []
        token_name = f"volshape-{tier}-{user_id[:18]}"
        body = {
            "name": token_name,
            "expired_time": -1,
            "remain_quota": int(policy.monthly_quota_units),
            "unlimited_quota": False,
            "model_limits_enabled": bool(model_limits),
            "model_limits": ",".join(model_limits),
            "allow_ips": settings.NEWAPI_SERVER_ALLOW_IPS,
            "group": group_for_tier(tier),
        }

        headers = {
            "Authorization": f"Bearer {settings.NEWAPI_SYSTEM_TOKEN}",
            "Content-Type": "application/json",
        }
        if settings.NEWAPI_ADMIN_USER_ID:
            headers["New-Api-User"] = settings.NEWAPI_ADMIN_USER_ID

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{settings.NEWAPI_BASE_URL.rstrip('/')}/api/token/", headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json().get("data") or resp.json()

        key = data.get("key") or data.get("token")
        token_id = str(data.get("id")) if data.get("id") is not None else None
        if key and not key.startswith("sk-"):
            key = f"sk-{key}"

        if not token_id:
            async with httpx.AsyncClient(timeout=15.0) as client:
                token_id = await NewApiService._find_token_id_by_name(client, headers, token_name)
        if token_id and not key:
            async with httpx.AsyncClient(timeout=15.0) as client:
                key = await NewApiService._fetch_token_key(client, headers, token_id)

        if key:
            return key, token_id
        return None

    @staticmethod
    async def ensure_user_token(user_id: str, db: AsyncSession) -> NewApiToken:
        result = await db.execute(
            select(NewApiToken).where(NewApiToken.user_id == user_id, NewApiToken.status == "active").order_by(NewApiToken.created_at.desc())
        )
        existing = result.scalars().first()
        if existing:
            return existing

        reusable_result = await db.execute(
            select(NewApiToken)
            .where(NewApiToken.user_id == user_id, NewApiToken.status == "rotated")
            .order_by(NewApiToken.created_at.desc())
        )
        reusable = reusable_result.scalars().first()

        policy = await get_policy_for_user(user_id, db)
        tier = await get_user_tier(user_id, db)
        provisioned = None
        try:
            provisioned = await NewApiService._create_token_with_management_api(user_id, tier, policy)
        except Exception as e:
            print(f"[NewAPI Provision Error] {e}")

        if provisioned:
            api_key, newapi_token_id = provisioned
        elif reusable and settings.ENV == "development":
            reusable.status = "active"
            reusable.group_name = group_for_tier(tier)
            reusable.model_limits = policy.allowed_models or []
            reusable.quota_granted = int(policy.monthly_quota_units)
            reusable.quota_available_cache = max(int(reusable.quota_available_cache or 0), int(policy.monthly_quota_units))
            reusable.updated_at = utc_now()
            await db.commit()
            return reusable
        elif settings.NEWAPI_SHARED_TOKEN and settings.ENV == "development":
            api_key, newapi_token_id = settings.NEWAPI_SHARED_TOKEN, None
        else:
            raise NewApiProvisionError(
                "New API 用户令牌创建失败，且未配置可用于开发的 NEWAPI_SHARED_TOKEN。",
                details={"tier": tier, "group": group_for_tier(tier)},
            )

        token = NewApiToken(
            id=str(uuid.uuid4()),
            user_id=user_id,
            newapi_token_id=newapi_token_id,
            token_ciphertext=encrypt_secret(api_key),
            token_name=f"volshape-{tier}-{user_id[:18]}",
            group_name=group_for_tier(tier),
            model_limits=policy.allowed_models or [],
            quota_granted=int(policy.monthly_quota_units),
            quota_available_cache=int(policy.monthly_quota_units),
            expires_at=None,
            status="active",
        )
        db.add(token)
        await db.commit()
        return token

    @staticmethod
    async def get_api_key_for_user(user_id: str, db: AsyncSession) -> tuple[str, NewApiToken]:
        token = await NewApiService.ensure_user_token(user_id, db)
        return decrypt_secret(token.token_ciphertext), token

    @staticmethod
    async def sync_token_usage(user_id: str, db: AsyncSession) -> dict:
        api_key, token = await NewApiService.get_api_key_for_user(user_id, db)
        usage = await NewApiService.query_token_usage(api_key)
        available = usage.get("total_available")
        granted = usage.get("total_granted")
        if isinstance(available, int):
            token.quota_available_cache = available
        if isinstance(granted, int):
            token.quota_granted = granted
        token.updated_at = utc_now()
        await db.commit()
        return usage
