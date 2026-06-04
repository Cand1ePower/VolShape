from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, text
from app.core.config import settings

import os

db_url = settings.DATABASE_URL
# 如果处于测试环境，强制使用 SQLite 内存数据库以实现 100% 本地环境健壮性
if os.getenv("TESTING") == "1":
    db_url = "sqlite+aiosqlite:///:memory:"

# 创建异步数据库引擎
engine = create_async_engine(
    db_url,
    echo=True if settings.ENV == "development" else False,
    future=True
)

# 创建异步 Session 工厂
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 依赖注入：获取数据库连接 Session
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
            
async def init_db():
    """初始化数据库表（开发环境下可以直接调用，生产环境下推荐使用 Alembic）"""
    global engine, AsyncSessionLocal
    from app.database.models import Base
    
    # 仅在非测试环境且使用 PostgreSQL 时尝试连接探测
    if os.getenv("TESTING") != "1" and "postgresql" in str(engine.url).lower():
        try:
            # 尝试轻量级查询以探测 PostgreSQL 可用性
            async with engine.connect() as conn:
                await conn.execute(select(1))
            print("Successfully connected to PostgreSQL database!")
        except Exception as e:
            print(f"\n[WARNING] PostgreSQL database port unavailable ({e}).")
            print("Fallback to local SQLite file database: sqlite+aiosqlite:///volshape_local.db\n")
            
            sqlite_url = "sqlite+aiosqlite:///volshape_local.db"
            engine = create_async_engine(
                sqlite_url,
                echo=True if settings.ENV == "development" else False,
                future=True
            )
            # 动态调整 Session 绑定
            AsyncSessionLocal.configure(bind=engine)
            
    async with engine.begin() as conn:
        # 如果需要重新建表，可以先 drop_all
        # await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_schema_compatibility(conn)


async def _ensure_schema_compatibility(conn) -> None:
    dialect = conn.dialect.name.lower()
    if "sqlite" in dialect:
        columns = await conn.execute(text("PRAGMA table_info(conversation_sessions)"))
        column_names = {row[1] for row in columns.fetchall()}
        if "pinned_at" not in column_names:
            await conn.execute(text("ALTER TABLE conversation_sessions ADD COLUMN pinned_at DATETIME"))

        profile_columns = await conn.execute(text("PRAGMA table_info(user_profile)"))
        profile_column_names = {row[1] for row in profile_columns.fetchall()}
        if "dynamic_attributes" not in profile_column_names:
            await conn.execute(
                text("ALTER TABLE user_profile ADD COLUMN dynamic_attributes JSON DEFAULT '{}' NOT NULL")
            )
    elif "postgresql" in dialect:
        await conn.execute(
            text(
                "ALTER TABLE conversation_sessions "
                "ADD COLUMN IF NOT EXISTS pinned_at TIMESTAMP WITH TIME ZONE"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE user_profile "
                "ADD COLUMN IF NOT EXISTS dynamic_attributes JSONB DEFAULT '{}'::jsonb NOT NULL"
            )
        )
