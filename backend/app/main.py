from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.chat import router as chat_router
from app.api.auth import router as auth_router
from app.api.diet import router as diet_router
from app.api.payment import router as payment_router
from app.api.workout import router as workout_router
from app.database.session import init_db
from app.services.newapi import ensure_quota_policies
from app.database.session import AsyncSessionLocal
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时逻辑：尝试初始化数据库表（如果本地 Docker 容器已启动且可用）
    try:
        await init_db()
        async with AsyncSessionLocal() as session:
            await ensure_quota_policies(session)
        print("数据库表结构初始化成功！")
    except Exception as e:
        print(f"数据库表结构初始化失败（可能数据库容器未启动，请运行 docker-compose up -d）: {e}")
    yield
    # 关闭时逻辑

app = FastAPI(
    title="VolShape Backend Gateway",
    description="VolShape 智能健身助手 FastAPI 后端骨架",
    version="1.0.0",
    lifespan=lifespan
)

# 允许跨域（本地 RN 与 Expo 开发需要）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(diet_router, prefix="/api/diet", tags=["diet"])
app.include_router(payment_router, prefix="/api/payment", tags=["payment"])
app.include_router(workout_router, prefix="/api/workout", tags=["workout"])

@app.get("/")
async def read_root():
    return {
        "status": "online",
        "app": "VolShape Backend Service",
        "version": "1.0.0"
    }
