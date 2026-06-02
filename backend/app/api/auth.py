import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    hash_token,
    issue_session,
    verify_password,
)
from app.database.models import AppUser, AuthSession
from app.database.session import get_db
from app.services.quota import QuotaService

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    username: str | None = Field(default=None, max_length=80)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.lower().strip()
        if "@" not in value or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("邮箱格式不正确")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.lower().strip()
        if "@" not in value or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("邮箱格式不正确")
        return value


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/register")
async def register(request: RegisterRequest, http_request: Request, db: AsyncSession = Depends(get_db)):
    email = request.email.lower().strip()
    existing = await db.execute(select(AppUser).where(AppUser.email == email))
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="该邮箱已注册")

    user = AppUser(
        id=str(uuid.uuid4()),
        email=email,
        username=request.username or email.split("@")[0],
        password_hash=hash_password(request.password),
        status="active",
        role="user",
        email_verified_at=datetime.datetime.utcnow(),
    )
    db.add(user)
    await db.flush()
    return await issue_session(user, db, http_request)


@router.post("/login")
async def login(request: LoginRequest, http_request: Request, db: AsyncSession = Depends(get_db)):
    email = request.email.lower().strip()
    result = await db.execute(select(AppUser).where(AppUser.email == email))
    user = result.scalars().first()
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")
    return await issue_session(user, db, http_request)


@router.post("/refresh")
async def refresh(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hash_token(request.refresh_token)
    result = await db.execute(select(AuthSession).where(AuthSession.refresh_token_hash == token_hash))
    session = result.scalars().first()
    if not session or session.revoked_at or session.expires_at < datetime.datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新凭证无效或已过期")
    user = await db.get(AppUser, session.user_id)
    if not user or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不存在或已被禁用")
    return {
        "access_token": create_access_token(user.id, user.role),
        "token_type": "bearer",
        "expires_in": 15 * 60,
        "user": {"id": user.id, "email": user.email, "username": user.username, "role": user.role, "status": user.status},
    }


@router.post("/logout")
async def logout(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hash_token(request.refresh_token)
    result = await db.execute(select(AuthSession).where(AuthSession.refresh_token_hash == token_hash))
    session = result.scalars().first()
    if session:
        session.revoked_at = datetime.datetime.utcnow()
        await db.commit()
    return {"status": "ok"}


@router.get("/me")
async def me(user: AppUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    quota = await QuotaService.quota_status(user.id, db)
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "role": user.role,
            "status": user.status,
        },
        "quota": quota,
    }
