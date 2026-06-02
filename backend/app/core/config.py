import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

class Settings:
    ENV: str = os.getenv("ENV", "development")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:localpassword123@localhost:5432/volshape")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "volshape-development-secret-key-32-chars-long!")
    AUTH_JWT_SECRET: str = os.getenv("AUTH_JWT_SECRET", SUPABASE_JWT_SECRET)
    AUTH_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    AUTH_REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("AUTH_REFRESH_TOKEN_EXPIRE_DAYS", "30"))
    TOKEN_ENCRYPTION_SECRET: str = os.getenv("TOKEN_ENCRYPTION_SECRET", AUTH_JWT_SECRET)

    # DeepSeek LLM API (via OpenAI SDK)
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    LLM_LIGHT_MODEL: str = os.getenv("LLM_LIGHT_MODEL", "deepseek-chat")
    LLM_HEAVY_MODEL: str = os.getenv("LLM_HEAVY_MODEL", "deepseek-chat")

    # New API gateway. When enabled, VolShape provisions one managed New API token
    # per user and routes model calls through the gateway.
    NEWAPI_BASE_URL: str = os.getenv("NEWAPI_BASE_URL", "")
    NEWAPI_ACCESS_TOKEN: str = os.getenv("NEWAPI_ACCESS_TOKEN", os.getenv("NEWAPI_SYSTEM_TOKEN", ""))
    NEWAPI_USER_ID: str = os.getenv("NEWAPI_USER_ID", os.getenv("NEWAPI_ADMIN_USER_ID", ""))
    NEWAPI_SYSTEM_TOKEN: str = NEWAPI_ACCESS_TOKEN
    NEWAPI_ADMIN_USER_ID: str = NEWAPI_USER_ID
    NEWAPI_SHARED_TOKEN: str = os.getenv("NEWAPI_SHARED_TOKEN", "")
    NEWAPI_DEFAULT_FREE_GROUP: str = os.getenv("NEWAPI_DEFAULT_FREE_GROUP", "free")
    NEWAPI_DEFAULT_PRO_GROUP: str = os.getenv("NEWAPI_DEFAULT_PRO_GROUP", "pro")
    NEWAPI_DEFAULT_PREMIUM_GROUP: str = os.getenv("NEWAPI_DEFAULT_PREMIUM_GROUP", "premium")
    NEWAPI_SERVER_ALLOW_IPS: str = os.getenv("NEWAPI_SERVER_ALLOW_IPS", "")
    NEWAPI_AUTO_PROVISION_TOKENS: bool = os.getenv("NEWAPI_AUTO_PROVISION_TOKENS", "1") == "1"

    # Embedding API (For mem0)
    EMBEDDING_API_KEY: str = os.getenv("EMBEDDING_API_KEY", "")
    EMBEDDING_BASE_URL: str = os.getenv("EMBEDDING_BASE_URL", "")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "")
    EMBEDDING_DIMS: int = int(os.getenv("EMBEDDING_DIMS", "768"))


    # Tavily Web Search
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

    # Langfuse 可观测性监控凭证 (Observability & Observability Metrics)
    LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "pk-lf-default-mock-key")
    LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "sk-lf-default-mock-key")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

settings = Settings()
