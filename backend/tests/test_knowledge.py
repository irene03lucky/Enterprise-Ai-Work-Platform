"""Knowledge 模块测试：空间 CRUD、文档上传与状态流转。"""

import time


def _create_company(client, headers) -> str:
    return client.post(
        "/api/v1/companies", json={"name": "测试企业"}, headers=headers
    ).json()["id"]


def _create_space(client, headers, company_id: str, name: str = "制度规范") -> str:
    resp = client.post(
        f"/api/v1/companies/{company_id}/knowledge/spaces",
        json={"name": name, "description": "测试空间", "visibility": "COMPANY"},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _ollama_ready(models: tuple[str, ...]) -> bool:
    import json
    import urllib.request

    from app.core.config import settings

    try:
        with urllib.request.urlopen(
            f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=3
        ) as resp:
            installed = [
                m.get("model") or m.get("name", "")
                for m in json.loads(resp.read().decode()).get("models", [])
            ]
            return all(any(n.startswith(m) for n in installed) for m in models)
    except Exception:
        return False


def test_create_and_list_spaces(client, auth_headers):
    company_id = _create_company(client, auth_headers)
    _create_space(client, auth_headers, company_id, "公司知识")
    _create_space(client, auth_headers, company_id, "项目资料")

    resp = client.get(
        f"/api/v1/companies/{company_id}/knowledge/spaces", headers=auth_headers
    )
    assert resp.status_code == 200
    names = {s["name"] for s in resp.json()}
    assert names == {"公司知识", "项目资料"}


def test_update_space(client, auth_headers):
    company_id = _create_company(client, auth_headers)
    space_id = _create_space(client, auth_headers, company_id)

    resp = client.patch(
        f"/api/v1/companies/{company_id}/knowledge/spaces/{space_id}",
        json={"name": "新名称", "description": "新描述"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "新名称"


def test_delete_space(client, auth_headers):
    company_id = _create_company(client, auth_headers)
    space_id = _create_space(client, auth_headers, company_id)
    assert (
        client.delete(
            f"/api/v1/companies/{company_id}/knowledge/spaces/{space_id}",
            headers=auth_headers,
        ).status_code
        == 204
    )
    resp = client.get(
        f"/api/v1/companies/{company_id}/knowledge/spaces", headers=auth_headers
    )
    assert resp.json() == []


def test_spaces_require_auth(client, auth_headers):
    company_id = _create_company(client, auth_headers)
    assert (
        client.get(f"/api/v1/companies/{company_id}/knowledge/spaces").status_code
        == 401
    )


def test_upload_rejects_unsupported_type(client, auth_headers):
    company_id = _create_company(client, auth_headers)
    space_id = _create_space(client, auth_headers, company_id)
    resp = client.post(
        f"/api/v1/companies/{company_id}/knowledge/spaces/{space_id}/documents",
        headers=auth_headers,
        files={"file": ("photo.png", b"\x89PNG", "image/png")},
    )
    assert resp.status_code == 400


def test_upload_txt_document_pipeline(client, auth_headers):
    """上传 → 解析 → 分块 → 向量化 → 状态流转。

    Ollama 模型就绪时应到达 READY 且 chunk_count > 0；
    模型不可用时应明确转为 FAILED（而非卡在中间态）。
    """
    ai_ready = _ollama_ready(("bge-m3",))
    company_id = _create_company(client, auth_headers)
    space_id = _create_space(client, auth_headers, company_id)

    content = "公司差旅住宿标准：一线城市每晚 600 元。\n" * 30
    resp = client.post(
        f"/api/v1/companies/{company_id}/knowledge/spaces/{space_id}/documents",
        headers=auth_headers,
        files={"file": ("差旅制度.txt", content.encode("utf-8"), "text/plain")},
    )
    assert resp.status_code == 201
    doc_id = resp.json()["id"]
    assert resp.json()["name"] == "差旅制度.txt"

    # 轮询等待后台处理完成
    final_status = None
    for _ in range(120):
        docs = client.get(
            f"/api/v1/companies/{company_id}/knowledge/spaces/{space_id}/documents",
            headers=auth_headers,
        ).json()
        doc = next((d for d in docs if d["id"] == doc_id), None)
        assert doc is not None
        final_status = doc["status"]
        if final_status in {"READY", "FAILED"}:
            break
        time.sleep(1)

    if ai_ready:
        assert final_status == "READY"
        assert doc["chunk_count"] > 0
        assert doc["error_message"] is None
    else:
        assert final_status == "FAILED"
        assert doc["error_message"]


def test_delete_document(client, auth_headers):
    company_id = _create_company(client, auth_headers)
    space_id = _create_space(client, auth_headers, company_id)
    doc_id = client.post(
        f"/api/v1/companies/{company_id}/knowledge/spaces/{space_id}/documents",
        headers=auth_headers,
        files={"file": ("临时.txt", b"hello world", "text/plain")},
    ).json()["id"]
    time.sleep(0.5)  # 等待后台任务启动
    assert (
        client.delete(
            f"/api/v1/companies/{company_id}/knowledge/documents/{doc_id}",
            headers=auth_headers,
        ).status_code
        == 204
    )
    docs = client.get(
        f"/api/v1/companies/{company_id}/knowledge/spaces/{space_id}/documents",
        headers=auth_headers,
    ).json()
    assert docs == []
