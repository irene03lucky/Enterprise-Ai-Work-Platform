"""Employee CRUD 与组织树测试。"""

NEW_EMPLOYEE_PAYLOAD = {
    "name": "张三",
    "email": "zhangsan@test.dev",
    "password": "pass1234",
    "position": "市场总监",
}


def _create_company(client, headers) -> str:
    return client.post(
        "/api/v1/companies", json={"name": "测试企业"}, headers=headers
    ).json()["id"]


def _create_department(client, headers, company_id: str, name: str = "市场部") -> str:
    return client.post(
        f"/api/v1/companies/{company_id}/departments",
        json={"name": name},
        headers=headers,
    ).json()["id"]


def test_create_employee_with_user(client, auth_headers):
    company_id = _create_company(client, auth_headers)
    dept_id = _create_department(client, auth_headers, company_id)

    resp = client.post(
        f"/api/v1/companies/{company_id}/employees/with-user",
        json={**NEW_EMPLOYEE_PAYLOAD, "department_id": dept_id},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user_name"] == "张三"
    assert body["department_id"] == dept_id
    assert body["status"] == "ACTIVE"


def test_create_employee_duplicate_email(client, auth_headers):
    company_id = _create_company(client, auth_headers)
    url = f"/api/v1/companies/{company_id}/employees/with-user"
    first = client.post(url, json=NEW_EMPLOYEE_PAYLOAD, headers=auth_headers)
    assert first.status_code == 201
    assert client.post(url, json=NEW_EMPLOYEE_PAYLOAD, headers=auth_headers).status_code == 400


def test_list_employees(client, auth_headers):
    company_id = _create_company(client, auth_headers)
    url = f"/api/v1/companies/{company_id}/employees"
    client.post(
        f"{url}/with-user", json=NEW_EMPLOYEE_PAYLOAD, headers=auth_headers
    )
    resp = client.get(url, headers=auth_headers)
    assert resp.status_code == 200
    # 创建者 + 新员工 = 2
    assert len(resp.json()) == 2


def test_update_employee(client, auth_headers):
    company_id = _create_company(client, auth_headers)
    dept_a = _create_department(client, auth_headers, company_id, "市场部")
    dept_b = _create_department(client, auth_headers, company_id, "项目部")

    emp_id = client.post(
        f"/api/v1/companies/{company_id}/employees/with-user",
        json={**NEW_EMPLOYEE_PAYLOAD, "department_id": dept_a},
        headers=auth_headers,
    ).json()["id"]

    resp = client.patch(
        f"/api/v1/companies/{company_id}/employees/{emp_id}",
        json={"department_id": dept_b, "position": "项目负责人", "status": "BUSINESS_TRIP"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["department_id"] == dept_b
    assert resp.json()["position"] == "项目负责人"
    assert resp.json()["status"] == "BUSINESS_TRIP"


def test_delete_employee(client, auth_headers):
    company_id = _create_company(client, auth_headers)
    emp_id = client.post(
        f"/api/v1/companies/{company_id}/employees/with-user",
        json=NEW_EMPLOYEE_PAYLOAD,
        headers=auth_headers,
    ).json()["id"]
    assert (
        client.delete(
            f"/api/v1/companies/{company_id}/employees/{emp_id}", headers=auth_headers
        ).status_code
        == 204
    )
    assert (
        client.get(
            f"/api/v1/companies/{company_id}/employees/{emp_id}", headers=auth_headers
        ).status_code
        == 404
    )


def test_employee_login_and_see_company(client, auth_headers):
    """验收场景：员工登录后能看到自己的企业空间。"""
    company_id = _create_company(client, auth_headers)
    client.post(
        f"/api/v1/companies/{company_id}/employees/with-user",
        json=NEW_EMPLOYEE_PAYLOAD,
        headers=auth_headers,
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "zhangsan@test.dev", "password": "pass1234"},
    ).json()["access_token"]
    me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    ).json()
    assert len(me["companies"]) == 1
    assert me["companies"][0]["name"] == "测试企业"


def test_organization_tree(client, auth_headers):
    """验收场景：组织树展示 公司 -> 部门(嵌套) -> 员工。"""
    company_id = _create_company(client, auth_headers)
    market = _create_department(client, auth_headers, company_id, "市场部")
    client.post(
        f"/api/v1/companies/{company_id}/departments",
        json={"name": "品牌组", "parent_id": market},
        headers=auth_headers,
    )
    finance = _create_department(client, auth_headers, company_id, "财务部")
    client.post(
        f"/api/v1/companies/{company_id}/employees/with-user",
        json={**NEW_EMPLOYEE_PAYLOAD, "department_id": market},
        headers=auth_headers,
    )

    resp = client.get(
        f"/api/v1/companies/{company_id}/organization/tree", headers=auth_headers
    )
    assert resp.status_code == 200
    company = resp.json()["company"]
    assert company["name"] == "测试企业"

    dept_names = {d["name"]: d for d in company["departments"]}
    assert set(dept_names) == {"市场部", "财务部"}
    assert len(dept_names["市场部"]["children"]) == 1
    assert dept_names["市场部"]["children"][0]["name"] == "品牌组"
    assert dept_names["市场部"]["employees"][0]["user_name"] == "张三"
    assert dept_names["财务部"]["employees"] == []
    # 企业创建者（未分配部门）应出现在 unassigned_employees
    assert [e["user_name"] for e in company["unassigned_employees"]] == ["测试管理员"]
    assert finance  # created for tree shape
