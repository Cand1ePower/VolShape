import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

class Settings:
    ENV: str = os.getenv("ENV", "development")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:localpassword123@localhost:5432/volshape")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "volshape-development-secret-key-32-chars-long!")

    # DeepSeek LLM API (via OpenAI SDK)
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    LLM_LIGHT_MODEL: str = os.getenv("LLM_LIGHT_MODEL", "deepseek-chat")
    LLM_HEAVY_MODEL: str = os.getenv("LLM_HEAVY_MODEL", "deepseek-chat")

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



