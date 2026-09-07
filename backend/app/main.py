"""EAI Backend 入口。"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import Base

app = FastAPI(
    title="EAI Backend",
    description="Enterprise AI Work Platform - API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health", tags=["health"])
def root_health():
    """根路径健康检查（供容器 / 负载均衡探活使用）。"""
    return {"status": "ok", "service": "eai-backend"}


@app.on_event("startup")
def on_startup() -> None:
    # 建表（未来引入 Alembic 迁移后移除）
    # 注意：这里在运行时解析 engine，以便测试环境替换连接
    from app.core.database import engine

    Base.metadata.create_all(bind=engine)

    if settings.SEED_ON_STARTUP:
        from app.seed import run_seed

        run_seed()
