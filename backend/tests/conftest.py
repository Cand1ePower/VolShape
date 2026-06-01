import os
import pytest
import asyncio

# 必须在任何 app 模块导入前，将环境变量 TESTING 设为 1
os.environ["TESTING"] = "1"

from app.database.session import engine
from app.database.models import Base

# 关闭 SQLAlchemy SQL 语句打印以保持测试输出简洁
engine.echo = False

@pytest.fixture(scope="session", autouse=True)
async def init_test_database():
    """
    自动在测试启动时，于内存 SQLite 数据库中创建所有 7 张核心数据表。
    测试结束时自动清理，保证单测环境的完全纯净和零依赖性。
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        
@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
