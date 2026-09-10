"""数据库连接与会话管理（SQLAlchemy 2.0）。"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """全局 ORM 基类。"""


engine = create_engine(settings.sqlalchemy_database_uri, pool_pre_ping=True)

# expire_on_commit=False：避免 commit 后 ORM 对象属性过期，
# 否则流式响应（SSE）在会话关闭后再访问关系属性会抛 DetachedInstanceError。
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：请求级数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
