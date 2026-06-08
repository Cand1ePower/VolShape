import os

from dotenv import dotenv_values, load_dotenv

# Load .env. Normal settings keep environment-variable priority to avoid
# breaking deployments and test overrides.
load_dotenv()
_DOTENV_VALUES = dotenv_values()


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _newapi_env(name: str, default: str = "") -> str:
    if _env("ENV", "development") != "production" and name in _DOTENV_VALUES:
        return str(_DOTENV_VALUES.get(name) or default).strip()
    return _env(name, default)


class Settings:
    ENV: str = _env("ENV", "development")
    SQL_ECHO: bool = _env("SQL_ECHO", "0") == "1"
    DATABASE_URL: str = _env("DATABASE_URL", "postgresql+asyncpg://postgres:localpassword123@localhost:5432/volshape")
    REDIS_URL: str = _env("REDIS_URL", "redis://localhost:6379/0")
    CORS_ORIGINS: str = _env(
        "CORS_ORIGINS",
        "http://localhost:8081,http://127.0.0.1:8081,http://localhost:19006,http://127.0.0.1:19006",
    )
    SUPABASE_JWT_SECRET: str = _env("SUPABASE_JWT_SECRET", "volshape-development-secret-key-32-chars-long!")
    AUTH_JWT_SECRET: str = _env("AUTH_JWT_SECRET", SUPABASE_JWT_SECRET)
    AUTH_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    AUTH_REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("AUTH_REFRESH_TOKEN_EXPIRE_DAYS", "30"))
    TOKEN_ENCRYPTION_SECRET: str = _env("TOKEN_ENCRYPTION_SECRET", AUTH_JWT_SECRET)

    # DeepSeek LLM API (via OpenAI SDK)
    DEEPSEEK_API_KEY: str = _env("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    LLM_LIGHT_MODEL: str = _env("LLM_LIGHT_MODEL", "deepseek-chat")
    LLM_HEAVY_MODEL: str = _env("LLM_HEAVY_MODEL", "deepseek-chat")
    LLM_VISION_MODEL: str = _env("LLM_VISION_MODEL", LLM_HEAVY_MODEL or "deepseek-chat")
    VISION_API_KEY: str = _env("VISION_API_KEY", "")
    VISION_BASE_URL: str = _env("VISION_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

    # New API gateway. When enabled, VolShape provisions one managed New API token
    # per user and routes model calls through the gateway.
    NEWAPI_BASE_URL: str = _newapi_env("NEWAPI_BASE_URL", "")
    NEWAPI_ACCESS_TOKEN: str = _newapi_env("NEWAPI_ACCESS_TOKEN", _newapi_env("NEWAPI_SYSTEM_TOKEN", ""))
    NEWAPI_USER_ID: str = _newapi_env("NEWAPI_USER_ID", _newapi_env("NEWAPI_ADMIN_USER_ID", ""))
    NEWAPI_SYSTEM_TOKEN: str = NEWAPI_ACCESS_TOKEN
    NEWAPI_ADMIN_USER_ID: str = NEWAPI_USER_ID
    NEWAPI_SHARED_TOKEN: str = _newapi_env("NEWAPI_SHARED_TOKEN", "")
    NEWAPI_DEFAULT_FREE_GROUP: str = _newapi_env("NEWAPI_DEFAULT_FREE_GROUP", "free")
    NEWAPI_DEFAULT_PRO_GROUP: str = _newapi_env("NEWAPI_DEFAULT_PRO_GROUP", "pro")
    NEWAPI_DEFAULT_PREMIUM_GROUP: str = _newapi_env("NEWAPI_DEFAULT_PREMIUM_GROUP", "premium")
    NEWAPI_SERVER_ALLOW_IPS: str = _newapi_env("NEWAPI_SERVER_ALLOW_IPS", "")
    NEWAPI_AUTO_PROVISION_TOKENS: bool = _newapi_env("NEWAPI_AUTO_PROVISION_TOKENS", "1") == "1"

    # Embedding API (For mem0)
    EMBEDDING_API_KEY: str = _env("EMBEDDING_API_KEY", "")
    EMBEDDING_BASE_URL: str = _env("EMBEDDING_BASE_URL", "")
    EMBEDDING_MODEL: str = _env("EMBEDDING_MODEL", "")
    EMBEDDING_DIMS: int = int(os.getenv("EMBEDDING_DIMS", "768"))

    # FatSecret nutrition API
    FATSECRET_AUTH_MODE: str = _env("FATSECRET_AUTH_MODE", "auto")
    FATSECRET_CONSUMER_KEY: str = _env("FATSECRET_CONSUMER_KEY", "")
    FATSECRET_CONSUMER_SECRET: str = _env("FATSECRET_CONSUMER_SECRET", "")
    FATSECRET_CLIENT_ID: str = _env("FATSECRET_CLIENT_ID", "")
    FATSECRET_CLIENT_SECRET: str = _env("FATSECRET_CLIENT_SECRET", "")
    FATSECRET_TOKEN_URL: str = _env("FATSECRET_TOKEN_URL", "https://oauth.fatsecret.com/connect/token")
    FATSECRET_API_BASE_URL: str = _env("FATSECRET_API_BASE_URL", "https://platform.fatsecret.com/rest/server.api")
    MAX_IMAGE_UPLOAD_MB: int = int(os.getenv("MAX_IMAGE_UPLOAD_MB", "10"))
    MAX_VIDEO_UPLOAD_MB: int = int(os.getenv("MAX_VIDEO_UPLOAD_MB", "50"))

    # Tavily Web Search
    TAVILY_API_KEY: str = _env("TAVILY_API_KEY", "")

    # Langfuse observability.
    LANGFUSE_PUBLIC_KEY: str = _env("LANGFUSE_PUBLIC_KEY", "pk-lf-default-mock-key")
    LANGFUSE_SECRET_KEY: str = _env("LANGFUSE_SECRET_KEY", "sk-lf-default-mock-key")
    LANGFUSE_HOST: str = _env("LANGFUSE_HOST", "https://cloud.langfuse.com")


settings = Settings()
