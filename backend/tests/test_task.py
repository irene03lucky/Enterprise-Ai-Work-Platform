"""Task 测试：创建、状态流转、我的任务、AI 提案确认创建。"""

from tests.test_room import _create_company, _create_room


def _employee_id(client, headers, company_id: str, email: str = "admin@test.dev"):
    employees = client.get(
        f"/api/v1/companies/{company_id}/employees", headers=headers
    ).json()
    return next(e["id"] for e in employees if e["user_email"] == email)


def test_create_and_list_tasks(client, auth_headers):
    company_id = _create_company(client, auth_headers)
    room_id = _create_room(client, auth_headers, company_id)
    emp_id = _employee_id(client, auth_headers, company_id)

    resp = client.post(
        f"/api/v1/companies/{company_id}/rooms/{room_id}/tasks",
        json={
            "title": "完成首页高保真设计稿",
            "description": "基于新视觉规范输出",
            "assignee_employee_id": emp_id,
            "due_date": "2026-12-31",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    task = resp.json()
    assert task["status"] == "TODO"
    assert task["source"] == "MANUAL"
    assert task["assignee_name"] == "测试管理员"
    assert task["creator_name"] == "测试管理员"

    tasks = client.get(
        f"/api/v1/companies/{company_id}/rooms/{room_id}/tasks", headers=auth_headers
    ).json()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "完成首页高保真设计稿"


def test_task_status_flow_sets_completed_at(client, auth_headers):
    """TODO → IN_PROGRESS → DONE：DONE 时写入完成时间，回退时清空。"""
    company_id = _create_company(client, auth_headers)
    room_id = _create_room(client, auth_headers, company_id)
    task_id = client.post(
        f"/api/v1/companies/{company_id}/rooms/{room_id}/tasks",
        json={"title": "联调测试"},
        headers=auth_headers,
    ).json()["id"]
    base = f"/api/v1/companies/{company_id}/rooms/{room_id}/tasks/{task_id}"

    resp = client.patch(base, json={"status": "IN_PROGRESS"}, headers=auth_headers)
    assert resp.json()["status"] == "IN_PROGRESS"
    assert resp.json()["completed_at"] is None

    resp = client.patch(base, json={"status": "DONE"}, headers=auth_headers)
    assert resp.json()["status"] == "DONE"
    assert resp.json()["completed_at"] is not None

    resp = client.patch(base, json={"status": "TODO"}, headers=auth_headers)
    assert resp.json()["completed_at"] is None


def test_my_tasks_scope(client, auth_headers):
    company_id = _create_company(client, auth_headers)
    room_id = _create_room(client, auth_headers, company_id)
    emp_id = _employee_id(client, auth_headers, company_id)

    client.post(
        f"/api/v1/companies/{company_id}/rooms/{room_id}/tasks",
        json={"title": "我的任务", "assignee_employee_id": emp_id},
        headers=auth_headers,
    )
    client.post(
        f"/api/v1/companies/{company_id}/rooms/{room_id}/tasks",
        json={"title": "别人的任务"},
        headers=auth_headers,
    )

    mine = client.get(
        f"/api/v1/companies/{company_id}/tasks?scope=my", headers=auth_headers
    ).json()
    assert [t["title"] for t in mine] == ["我的任务"]

    # 已完成任务不出现在「我的任务」默认视图
    task_id = mine[0]["id"]
    client.patch(
        f"/api/v1/companies/{company_id}/rooms/{room_id}/tasks/{task_id}",
        json={"status": "DONE"},
        headers=auth_headers,
    )
    mine = client.get(
        f"/api/v1/companies/{company_id}/tasks?scope=my", headers=auth_headers
    ).json()
    assert mine == []
    done = client.get(
        f"/api/v1/companies/{company_id}/tasks?scope=done", headers=auth_headers
    ).json()
    assert [t["title"] for t in done] == ["我的任务"]


def test_create_from_ai_proposal_keeps_source(client, auth_headers):
    """AI 提案确认后创建任务：保留来源与原文摘录，按姓名解析负责人。"""
    company_id = _create_company(client, auth_headers)
    room_id = _create_room(client, auth_headers, company_id)
    emp_id = client.post(
        f"/api/v1/companies/{company_id}/employees/with-user",
        json={"name": "张三", "email": "zhangsan@test.dev", "password": "pass1234"},
        headers=auth_headers,
    ).json()["id"]

    resp = client.post(
        f"/api/v1/companies/{company_id}/rooms/{room_id}/tasks/from-proposal",
        json={
            "proposals": [
                {
                    "title": "李四周五前完成测试",
                    "description": "覆盖核心流程",
                    "assignee_name": "张三",
                    "due_date": "2026-09-11",
                    "source": "CHAT",
                    "source_quote": "让李四周五前完成测试",
                }
            ]
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    task = resp.json()[0]
    assert task["title"] == "李四周五前完成测试"
    assert task["source"] == "CHAT"
    assert task["source_quote"] == "让李四周五前完成测试"
    assert task["assignee_employee_id"] == emp_id
    assert task["status"] == "TODO"


def test_delete_task(client, auth_headers):
    company_id = _create_company(client, auth_headers)
    room_id = _create_room(client, auth_headers, company_id)
    task_id = client.post(
        f"/api/v1/companies/{company_id}/rooms/{room_id}/tasks",
        json={"title": "待删除"},
        headers=auth_headers,
    ).json()["id"]
    assert (
        client.delete(
            f"/api/v1/companies/{company_id}/rooms/{room_id}/tasks/{task_id}",
            headers=auth_headers,
        ).status_code
        == 204
    )
    assert (
        client.get(
            f"/api/v1/companies/{company_id}/rooms/{room_id}/tasks", headers=auth_headers
        ).json()
        == []
    )


def test_room_open_task_count(client, auth_headers):
    """房间列表返回未完成任务数。"""
    company_id = _create_company(client, auth_headers)
    room_id = _create_room(client, auth_headers, company_id)
    for title in ("A", "B"):
        client.post(
            f"/api/v1/companies/{company_id}/rooms/{room_id}/tasks",
            json={"title": title},
            headers=auth_headers,
        )
    room = client.get(
        f"/api/v1/companies/{company_id}/rooms/{room_id}", headers=auth_headers
    ).json()
    assert room["open_task_count"] == 2
