"""Knowledge Agent 端到端测试：上传 → 向量化 → 提问 → 带来源回答。"""

import json
import time

import httpx
import pytest

from tests.test_knowledge import _ollama_ready

AI_MODELS = ("bge-m3", "qwen2.5:1.5b")

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def seeded_company():
    """每个测试独立准备：企业 + 知识空间 + 差旅制度文档（等待向量化完成）。"""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        # 禁用启动 seed 时 app 已被 conftest 处理；此处直接注册管理员
        reg = c.post(
            "/api/v1/auth/register",
            json={"name": "测试管理员", "email": "admin@test.dev", "password": "test1234"},
        )
        assert reg.status_code in (201, 409), reg.text
        login = c.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.dev", "password": "test1234"},
        )
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        company_id = c.post(
            "/api/v1/companies", json={"name": "AI测试企业"}, headers=headers
        ).json()["id"]
        space_id = c.post(
            f"/api/v1/companies/{company_id}/knowledge/spaces",
            json={"name": "制度规范"},
            headers=headers,
        ).json()["id"]

        doc_content = (
            "# 员工差旅管理制度\n\n"
            "## 住宿标准\n"
            "国内出差：一线城市住宿标准为每人每晚 600 元，其他城市为每人每晚 450 元。\n"
            "机票默认经济舱，8 小时以上长途可申请商务舱。\n"
            "出差期间每日餐补 150 元，无需发票。\n"
        ) * 10
        doc_id = c.post(
            f"/api/v1/companies/{company_id}/knowledge/spaces/{space_id}/documents",
            headers=headers,
            files={"file": ("差旅制度.md", doc_content.encode("utf-8"), "text/markdown")},
        ).json()["id"]

        # 等待向量化完成（模型就绪时）
        if _ollama_ready(("bge-m3",)):
            for _ in range(120):
                docs = c.get(
                    f"/api/v1/companies/{company_id}/knowledge/spaces/{space_id}/documents",
                    headers=headers,
                ).json()
                doc = next(d for d in docs if d["id"] == doc_id)
                if doc["status"] in {"READY", "FAILED"}:
                    break
                time.sleep(1)
            assert doc["status"] == "READY", doc.get("error_message")

        yield company_id, token


def test_health_ai(client):
    resp = client.get("/api/v1/health/ai")
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] in {"ollama", "openai-compatible"}
    assert "llm_ready" in body and "embedding_ready" in body


@pytest.mark.skipif(
    not _ollama_ready(AI_MODELS),
    reason="Ollama 或所需模型（bge-m3 / qwen2.5:1.5b）不可用",
)
async def test_agent_answers_with_sources(seeded_company):
    """验收：Agent 检索知识库 → 生成回答 → 返回来源文档。"""
    company_id, token = seeded_company

    transport = httpx.ASGITransport(app=_get_app())
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=300
    ) as ac:
        async with ac.stream(
            "POST",
            f"/api/v1/companies/{company_id}/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "公司差旅的住宿标准是什么？", "history": []},
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")

            tokens: list[str] = []
            sources: list[dict] = []
            event_types: list[str] = []
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])
                event_types.append(event["type"])
                if event["type"] == "token":
                    tokens.append(event["content"])
                elif event["type"] == "sources":
                    sources = event["sources"]

            assert "done" in event_types
            answer = "".join(tokens)
            assert len(answer) > 10
            # 回答应基于检索到的差旅制度（一线城市 600 元）
            assert "600" in answer
            assert sources, "应返回引用来源文档"
            assert any("差旅" in s["name"] for s in sources)


def _get_app():
    from app.main import app

    return app


@pytest.mark.skipif(
    not _ollama_ready(AI_MODELS),
    reason="Ollama 或所需模型（bge-m3 / qwen2.5:1.5b）不可用",
)
async def test_agent_multi_turn(seeded_company):
    """验收：多轮对话上下文。第二轮用代词指代，Agent 应能理解。"""
    company_id, token = seeded_company

    transport = httpx.ASGITransport(app=_get_app())
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=300
    ) as ac:
        async with ac.stream(
            "POST",
            f"/api/v1/companies/{company_id}/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "message": "那餐补是多少？",
                "history": [
                    {"role": "user", "content": "公司差旅的住宿标准是什么？"},
                    {"role": "assistant", "content": "一线城市每晚 600 元，其他城市 450 元。"},
                ],
            },
        ) as resp:
            assert resp.status_code == 200
            tokens = []
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])
                if event["type"] == "token":
                    tokens.append(event["content"])
            answer = "".join(tokens)
            assert "150" in answer  # 餐补 150 元
