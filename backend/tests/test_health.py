"""API 启动 / 数据库连接测试。"""


def test_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_db(client):
    resp = client.get("/api/v1/health/db")
    assert resp.status_code == 200
    assert resp.json()["database"] == "connected"


def test_openapi(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert "/api/v1/auth/login" in resp.json()["paths"]
