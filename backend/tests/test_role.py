"""Role 基础测试。"""


def _setup(client, headers):
    company_id = client.post(
        "/api/v1/companies", json={"name": "测试企业"}, headers=headers
    ).json()["id"]
    role_id = client.post(
        f"/api/v1/companies/{company_id}/roles",
        json={"name": "管理员", "description": "企业管理者"},
        headers=headers,
    ).json()["id"]
    return company_id, role_id


def test_create_and_list_roles(client, auth_headers):
    company_id, _ = _setup(client, auth_headers)
    resp = client.get(
        f"/api/v1/companies/{company_id}/roles", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "管理员"


def test_assign_role(client, auth_headers):
    company_id, role_id = _setup(client, auth_headers)
    user_id = client.post(
        f"/api/v1/companies/{company_id}/employees/with-user",
        json={"name": "张三", "email": "zhangsan@test.dev", "password": "pass1234"},
        headers=auth_headers,
    ).json()["user_id"]

    resp = client.post(
        f"/api/v1/companies/{company_id}/roles/assign",
        json={"user_id": user_id, "role_id": role_id},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    # 重复授权幂等
    assert (
        client.post(
            f"/api/v1/companies/{company_id}/roles/assign",
            json={"user_id": user_id, "role_id": role_id},
            headers=auth_headers,
        ).status_code
        == 200
    )

    listing = client.get(
        f"/api/v1/companies/{company_id}/roles/users/{user_id}",
        headers=auth_headers,
    )
    assert len(listing.json()) == 1


def test_delete_role(client, auth_headers):
    company_id, role_id = _setup(client, auth_headers)
    assert (
        client.delete(
            f"/api/v1/companies/{company_id}/roles/{role_id}", headers=auth_headers
        ).status_code
        == 204
    )
    assert (
        client.get(f"/api/v1/companies/{company_id}/roles", headers=auth_headers).json()
        == []
    )
