"""认证流程测试。"""


def test_register_and_login(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"name": "用户A", "email": "a@test.dev", "password": "pass1234"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "a@test.dev"
    assert "password" not in body and "password_hash" not in body

    resp = client.post(
        "/api/v1/auth/login", json={"email": "a@test.dev", "password": "pass1234"}
    )
    assert resp.status_code == 200
    assert resp.json()["token_type"] == "bearer"


def test_register_duplicate_email(client):
    payload = {"name": "用户B", "email": "b@test.dev", "password": "pass1234"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409


def test_login_wrong_password(client):
    client.post(
        "/api/v1/auth/register",
        json={"name": "用户C", "email": "c@test.dev", "password": "pass1234"},
    )
    resp = client.post(
        "/api/v1/auth/login", json={"email": "c@test.dev", "password": "wrong"}
    )
    assert resp.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me(client, auth_headers):
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == "admin@test.dev"
    assert body["companies"] == []


def test_me_includes_department_membership(client, auth_headers):
    """创建企业并分配部门后，/auth/me 应返回部门与职位信息。"""
    company_id = client.post(
        "/api/v1/companies", json={"name": "测试企业"}, headers=auth_headers
    ).json()["id"]
    dept_id = client.post(
        f"/api/v1/companies/{company_id}/departments",
        json={"name": "市场部"},
        headers=auth_headers,
    ).json()["id"]

    employees = client.get(
        f"/api/v1/companies/{company_id}/employees", headers=auth_headers
    ).json()
    my_employee = next(e for e in employees if e["user_email"] == "admin@test.dev")

    client.patch(
        f"/api/v1/companies/{company_id}/employees/{my_employee['id']}",
        json={"department_id": dept_id, "position": "负责人"},
        headers=auth_headers,
    )

    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    membership = me["companies"][0]
    assert membership["id"] == company_id
    assert membership["employee_id"] == my_employee["id"]
    assert membership["department_id"] == dept_id
    assert membership["department_name"] == "市场部"
    assert membership["position"] == "负责人"
    assert membership["status"] == "ACTIVE"
