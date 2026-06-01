from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.core.config import settings

security = HTTPBearer()

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    FastAPI 依赖注入项：验证 JWT Token 并提取 user_id (Supabase 中的 UUID / sub)。
    支持在开发环境下通过 `test-user-xxx` 进行模拟登录。
    """
    token = credentials.credentials
    
    # 工业实践：本地开发环境下的测试后门，避免依赖线上网络或测试 Token 过期
    if settings.ENV == "development" and token.startswith("test-user-"):
        # 直接提取后半部分作为 user_id
        return token
        
    try:
        # 解码并校验 Supabase JWT
        # Supabase 的 JWT 默认使用 HS256 签名，Secret 在后台设置
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False}  # Supabase aud 通常为 "authenticated"
        )
        
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token 中缺少用户标识 (sub)",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user_id
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"无效的认证凭证或已过期: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
