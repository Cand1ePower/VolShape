from typing import AsyncGenerator
import os

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


db_url = settings.DATABASE_URL
if os.getenv("TESTING") == "1":
    db_url = "sqlite+aiosqlite:///:memory:"


def _build_engine(url: str):
    kwargs = {
        "echo": True if settings.ENV == "development" else False,
        "future": True,
    }
    if "postgresql" in url:
        kwargs.update(
            {
                "pool_pre_ping": True,
                "pool_recycle": 1800,
                "pool_size": 20,
                "max_overflow": 40,
                "pool_timeout": 30,
            }
        )
    return create_async_engine(url, **kwargs)


engine = _build_engine(db_url)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


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
    """Initialize tables in development; production should prefer Alembic."""
    global engine, AsyncSessionLocal
    from app.database.models import Base

    if os.getenv("TESTING") != "1" and "postgresql" in str(engine.url).lower():
        try:
            async with engine.connect() as conn:
                await conn.execute(select(1))
            print("Successfully connected to PostgreSQL database!")
        except Exception as e:
            print(f"\n[WARNING] PostgreSQL database port unavailable ({e}).")
            print("Fallback to local SQLite file database: sqlite+aiosqlite:///volshape_local.db\n")

            sqlite_url = "sqlite+aiosqlite:///volshape_local.db"
            engine = _build_engine(sqlite_url)
            AsyncSessionLocal.configure(bind=engine)

    async with engine.begin() as conn:
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
