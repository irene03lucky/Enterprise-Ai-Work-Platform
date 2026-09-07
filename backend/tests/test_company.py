"""Company CRUD 测试。"""

COMPANY_PAYLOAD = {
    "name": "测试企业",
    "description": "用于测试",
    "industry": "互联网",
}


def test_create_company(client, auth_headers):
    resp = client.post("/api/v1/companies", json=COMPANY_PAYLOAD, headers=auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "测试企业"
    assert body["owner_id"] is not None


def test_create_company_requires_auth(client):
    assert client.post("/api/v1/companies", json=COMPANY_PAYLOAD).status_code == 401


def test_list_my_companies(client, auth_headers):
    client.post("/api/v1/companies", json=COMPANY_PAYLOAD, headers=auth_headers)
    resp = client.get("/api/v1/companies", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_create_company_makes_owner_employee(client, auth_headers):
    """创建者自动成为企业员工。"""
    resp = client.post("/api/v1/companies", json=COMPANY_PAYLOAD, headers=auth_headers)
    company_id = resp.json()["id"]

    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    assert len(me["companies"]) == 1
    assert me["companies"][0]["id"] == company_id


def test_get_company(client, auth_headers):
    company_id = client.post(
        "/api/v1/companies", json=COMPANY_PAYLOAD, headers=auth_headers
    ).json()["id"]
    resp = client.get(f"/api/v1/companies/{company_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "测试企业"


def test_update_company(client, auth_headers):
    company_id = client.post(
        "/api/v1/companies", json=COMPANY_PAYLOAD, headers=auth_headers
    ).json()["id"]
    resp = client.patch(
        f"/api/v1/companies/{company_id}",
        json={"name": "新名字", "industry": "金融"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "新名字"
    assert resp.json()["industry"] == "金融"


def test_delete_company(client, auth_headers):
    company_id = client.post(
        "/api/v1/companies", json=COMPANY_PAYLOAD, headers=auth_headers
    ).json()["id"]
    assert (
        client.delete(f"/api/v1/companies/{company_id}", headers=auth_headers).status_code
        == 204
    )
    assert (
        client.get(f"/api/v1/companies/{company_id}", headers=auth_headers).status_code
        == 404
    )


def test_company_access_denied_for_outsider(client, auth_headers):
    """非成员无法访问企业。"""
    company_id = client.post(
        "/api/v1/companies", json=COMPANY_PAYLOAD, headers=auth_headers
    ).json()["id"]

    client.post(
        "/api/v1/auth/register",
        json={"name": "路人", "email": "outsider@test.dev", "password": "pass1234"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": "outsider@test.dev", "password": "pass1234"}
    ).json()["access_token"]

    resp = client.get(
        f"/api/v1/companies/{company_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403
