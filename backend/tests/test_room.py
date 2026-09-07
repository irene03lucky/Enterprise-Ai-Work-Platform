"""Project Room + Work Event 测试：CRUD、成员、关联文档、Timeline、房间问答。"""

import json
import time

import pytest

from tests.test_knowledge import _ollama_ready

AI_MODELS = ("bge-m3", "qwen2.5:1.5b")


def _create_company(client, headers) -> str:
    return client.post(
        "/api/v1/companies", json={"name": "测试企业"}, headers=headers
    ).json()["id"]


def _create_room(client, headers, company_id: str, name: str = "测试项目") -> str:
    resp = client.post(
        f"/api/v1/companies/{company_id}/rooms",
        json={"name": name, "description": "测试房间", "status": "ACTIVE"},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_create_and_list_rooms(client, auth_headers):
    company_id = _create_company(client, auth_headers)
    _create_room(client, auth_headers, company_id, "项目A")
    _create_room(client, auth_headers, company_id, "项目B")

    resp = client.get(f"/api/v1/companies/{company_id}/rooms", headers=auth_headers)
    assert resp.status_code == 200
    names = {r["name"] for r in resp.json()}
    assert names == {"项目A", "项目B"}


def test_creator_auto_member(client, auth_headers):
    """创建者自动成为 OWNER 成员。"""
    company_id = _create_company(client, auth_headers)
    room_id = _create_room(client, auth_headers, company_id)
    members = client.get(
        f"/api/v1/companies/{company_id}/rooms/{room_id}/members", headers=auth_headers
    ).json()
    assert len(members) == 1
    assert members[0]["role"] == "OWNER"
    assert members[0]["user_email"] == "admin@test.dev"


def test_add_remove_member(client, auth_headers):
    company_id = _create_company(client, auth_headers)
    room_id = _create_room(client, auth_headers, company_id)
    emp_id = client.post(
        f"/api/v1/companies/{company_id}/employees/with-user",
        json={"name": "张三", "email": "zhangsan@test.dev", "password": "pass1234"},
        headers=auth_headers,
    ).json()["id"]

    resp = client.post(
        f"/api/v1/companies/{company_id}/rooms/{room_id}/members",
        json={"employee_id": emp_id},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["user_name"] == "张三"

    # 重复添加幂等
    assert (
        client.post(
            f"/api/v1/companies/{company_id}/rooms/{room_id}/members",
            json={"employee_id": emp_id},
            headers=auth_headers,
        ).status_code
        == 201
    )
    members = client.get(
        f"/api/v1/companies/{company_id}/rooms/{room_id}/members", headers=auth_headers
    ).json()
    assert len(members) == 2

    assert (
        client.delete(
            f"/api/v1/companies/{company_id}/rooms/{room_id}/members/{emp_id}",
            headers=auth_headers,
        ).status_code
        == 204
    )
    members = client.get(
        f"/api/v1/companies/{company_id}/rooms/{room_id}/members", headers=auth_headers
    ).json()
    assert len(members) == 1


def test_link_knowledge_document(client, auth_headers):
    """房间关联 Knowledge 文档（复用知识资产，不新建文档体系）。"""
    company_id = _create_company(client, auth_headers)
    space_id = client.post(
        f"/api/v1/companies/{company_id}/knowledge/spaces",
        json={"name": "产品业务"},
        headers=auth_headers,
    ).json()["id"]
    doc_id = client.post(
        f"/api/v1/companies/{company_id}/knowledge/spaces/{space_id}/documents",
        headers=auth_headers,
        files={"file": ("产品介绍.md", "# 产品\n核心模块介绍。".encode("utf-8"), "text/markdown")},
    ).json()["id"]
    time.sleep(0.5)

    room_id = _create_room(client, auth_headers, company_id)
    resp = client.post(
        f"/api/v1/companies/{company_id}/rooms/{room_id}/documents",
        json={"document_id": doc_id},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["document_name"] == "产品介绍.md"

    docs = client.get(
        f"/api/v1/companies/{company_id}/rooms/{room_id}/documents", headers=auth_headers
    ).json()
    assert len(docs) == 1


def test_work_event_timeline(client, auth_headers):
    """新增 Work Event → Timeline 倒序展示。"""
    company_id = _create_company(client, auth_headers)
    room_id = _create_room(client, auth_headers, company_id)

    events_payload = [
        ("meeting", "项目启动会：确认范围。"),
        ("decision", "决策：采用新视觉规范。"),
        ("customer_feedback", "今天与客户沟通，对方希望增加数字人导览，预算控制在50万元以内。"),
    ]
    for etype, content in events_payload:
        resp = client.post(
            f"/api/v1/companies/{company_id}/rooms/{room_id}/events",
            json={"type": etype, "content": content},
            headers=auth_headers,
        )
        assert resp.status_code == 201

    timeline = client.get(
        f"/api/v1/companies/{company_id}/rooms/{room_id}/events", headers=auth_headers
    ).json()
    assert len(timeline) == 3
    # 倒序（最新在前）
    assert timeline[0]["type"] == "customer_feedback"
    assert "数字人导览" in timeline[0]["content"]
    assert timeline[0]["author_name"] == "测试管理员"

    # 房间计数
    room = client.get(
        f"/api/v1/companies/{company_id}/rooms/{room_id}", headers=auth_headers
    ).json()
    assert room["event_count"] == 3


def test_delete_room_cascades(client, auth_headers):
    company_id = _create_company(client, auth_headers)
    room_id = _create_room(client, auth_headers, company_id)
    client.post(
        f"/api/v1/companies/{company_id}/rooms/{room_id}/events",
        json={"type": "work_log", "content": "记录"},
        headers=auth_headers,
    )
    assert (
        client.delete(
            f"/api/v1/companies/{company_id}/rooms/{room_id}", headers=auth_headers
        ).status_code
        == 204
    )
    assert (
        client.get(f"/api/v1/companies/{company_id}/rooms", headers=auth_headers).json()
        == []
    )


@pytest.mark.skipif(
    not _ollama_ready(AI_MODELS),
    reason="Ollama 或所需模型不可用",
)
def test_room_chat_with_context(client, auth_headers):
    """验收：房间问答自动携带项目上下文（客户 50 万预算事件）。"""
    company_id = _create_company(client, auth_headers)
    room_id = _create_room(client, auth_headers, company_id, "品牌官网升级项目")
    client.post(
        f"/api/v1/companies/{company_id}/rooms/{room_id}/events",
        json={"type": "customer_feedback", "content": "今天与客户沟通，对方希望增加数字人导览，预算控制在50万元以内。"},
        headers=auth_headers,
    )
    client.post(
        f"/api/v1/companies/{company_id}/rooms/{room_id}/events",
        json={"type": "meeting", "content": "项目启动会：确认官网升级范围，目标下季度上线。"},
        headers=auth_headers,
    )

    with client.stream(
        "POST",
        f"/api/v1/companies/{company_id}/rooms/{room_id}/chat",
        headers={**auth_headers, "Content-Type": "application/json"},
        json={"message": "当前项目情况如何？客户有什么要求？", "history": []},
    ) as resp:
        assert resp.status_code == 200
        tokens = []
        for line in resp.iter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            if event["type"] == "token":
                tokens.append(event["content"])
        answer = "".join(tokens)
        # AI 应能引用事件中的客户要求（预算 50 万）
        assert "50万" in answer or "50 万" in answer, answer
        assert "数字人导览" in answer, answer
