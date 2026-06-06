import base64
import datetime
import hashlib
import hmac
import os
import secrets
import uuid
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.time import utc_now
from app.database.models import AppUser, AuthSession, Subscription, UserProfile
from app.database.session import get_db

security = HTTPBearer()
ALGORITHM = "HS256"


def _utcnow() -> datetime.datetime:
    return utc_now()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return "pbkdf2_sha256$210000$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    try:
        scheme, iterations, salt_b64, digest_b64 = stored_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.AUTH_JWT_SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise JWTError("invalid token type")
        user_id = payload.get("sub")
        if not user_id:
            raise JWTError("missing subject")
        return user_id
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"无效或已过期的登录凭证: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def create_access_token(user_id: str, role: str = "user") -> str:
    expires = _utcnow() + datetime.timedelta(minutes=settings.AUTH_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "role": role, "type": "access", "exp": expires}
    return jwt.encode(payload, settings.AUTH_JWT_SECRET, algorithm=ALGORITHM)


def create_refresh_token() -> tuple[str, datetime.datetime]:
    token = secrets.token_urlsafe(48)
    expires = _utcnow() + datetime.timedelta(days=settings.AUTH_REFRESH_TOKEN_EXPIRE_DAYS)
    return token, expires


async def ensure_user_profile(user_id: str, db: AsyncSession) -> None:
    profile = await db.get(UserProfile, user_id)
    if not profile:
        db.add(UserProfile(user_id=user_id))


async def create_default_subscription(user_id: str, db: AsyncSession) -> None:
    existing = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    if existing.scalars().first():
        return
    now = _utcnow()
    db.add(
        Subscription(
            id=str(uuid.uuid4()),
            user_id=user_id,
            tier="free",
            status="active",
            provider="manual",
            current_period_start=now,
            current_period_end=now + datetime.timedelta(days=30),
        )
    )


async def issue_session(user: AppUser, db: AsyncSession, request: Optional[Request] = None) -> dict:
    refresh_token, refresh_expires = create_refresh_token()
    session = AuthSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        refresh_token_hash=hash_token(refresh_token),
        ip=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
        expires_at=refresh_expires,
    )
    user.last_login_at = _utcnow()
    db.add(session)
    await ensure_user_profile(user.id, db)
    await create_default_subscription(user.id, db)
    await db.commit()
    return {
        "access_token": create_access_token(user.id, user.role),
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.AUTH_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "role": user.role,
            "status": user.status,
        },
    }


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> AppUser:
    token = credentials.credentials

    if settings.ENV == "development" and token.startswith("test-user-"):
        email = f"{token}@dev.local"
        result = await db.execute(select(AppUser).where(AppUser.id == token))
        user = result.scalars().first()
        if not user:
            user = AppUser(id=token, email=email, username=token, role="user", status="active")
            db.add(user)
            await ensure_user_profile(user.id, db)
            await create_default_subscription(user.id, db)
            await db.commit()
        return user

    user_id = _decode_access_token(token)
    user = await db.get(AppUser, user_id)
    if not user or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不存在或已被禁用")
    return user


def get_current_user_id_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    return _decode_access_token(credentials.credentials)


async def get_current_user_id(user: AppUser = Depends(get_current_user)) -> str:
    return user.id


async def require_admin(user: AppUser = Depends(get_current_user)) -> AppUser:
    if user.role not in ("admin", "root"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user
