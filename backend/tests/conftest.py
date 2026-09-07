"""测试夹具：使用独立 PostgreSQL 测试库。

环境变量 TEST_DATABASE_URI（默认 localhost:5433/eai_test，
与 docker-compose 暴露的 db 端口一致）。
"""

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# 测试隔离：必须在导入 app 之前设置（settings 在导入期固化）
os.environ.setdefault("CHROMA_DIR", "/tmp/eai_test_chroma")
os.environ.setdefault("UPLOAD_DIR", "/tmp/eai_test_uploads")

# 启用 anyio 的 pytest 插件（异步 Agent 测试需要）
pytest_plugins = ["anyio"]

import app.core.database as database_module
from app.core.database import Base, get_db

TEST_DATABASE_URI = os.environ.get(
    "TEST_DATABASE_URI",
    "postgresql://eai:eai_dev_password@localhost:5433/eai_test",
)

test_engine = create_engine(TEST_DATABASE_URI, pool_pre_ping=True)
TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

# 替换应用使用的引擎/会话工厂。
# 注意：必须在 import app.main 之前执行——services 模块在导入期
# 通过 `from app.core.database import SessionLocal` 绑定引用，
# 晚于本替换执行的话会指向生产库。
database_module.engine = test_engine
database_module.SessionLocal = TestSessionLocal

# 禁用 startup seed（先改配置，再导入 app 触发 startup 事件注册）
database_module.settings.SEED_ON_STARTUP = False

from app.main import app  # noqa: E402


def override_get_db():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    # 确保测试库存在
    admin_engine = create_engine(
        TEST_DATABASE_URI.rsplit("/", 1)[0] + "/postgres", pool_pre_ping=True, isolation_level="AUTOCOMMIT"
    )
    with admin_engine.connect() as conn:
        db_name = TEST_DATABASE_URI.rsplit("/", 1)[1]
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin_engine.dispose()

    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers(client: TestClient) -> dict[str, str]:
    """注册用户并登录，返回认证头。"""
    client.post(
        "/api/v1/auth/register",
        json={"name": "测试管理员", "email": "admin@test.dev", "password": "test1234"},
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.dev", "password": "test1234"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
