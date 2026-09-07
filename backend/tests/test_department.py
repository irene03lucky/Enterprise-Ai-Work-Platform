"""Department CRUD 测试（树状结构）。"""


def _create_company(client, headers) -> str:
    return client.post(
        "/api/v1/companies", json={"name": "测试企业"}, headers=headers
    ).json()["id"]


def _base(company_id: str) -> str:
    return f"/api/v1/companies/{company_id}/departments"


def test_create_department(client, auth_headers):
    company_id = _create_company(client, auth_headers)
    resp = client.post(
        _base(company_id), json={"name": "市场部"}, headers=auth_headers
    )
    assert resp.status_code == 201
    assert resp.json()["parent_id"] is None


def test_create_child_department(client, auth_headers):
    company_id = _create_company(client, auth_headers)
    parent_id = client.post(
        _base(company_id), json={"name": "市场部"}, headers=auth_headers
    ).json()["id"]
    resp = client.post(
        _base(company_id),
        json={"name": "品牌组", "parent_id": parent_id},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["parent_id"] == parent_id


def test_list_departments(client, auth_headers):
    company_id = _create_company(client, auth_headers)
    for name in ["市场部", "项目部", "财务部"]:
        client.post(_base(company_id), json={"name": name}, headers=auth_headers)
    resp = client.get(_base(company_id), headers=auth_headers)
    assert resp.status_code == 200
    assert {d["name"] for d in resp.json()} == {"市场部", "项目部", "财务部"}


def test_update_department(client, auth_headers):
    company_id = _create_company(client, auth_headers)
    dept_id = client.post(
        _base(company_id), json={"name": "市场部"}, headers=auth_headers
    ).json()["id"]
    resp = client.patch(
        f"{_base(company_id)}/{dept_id}",
        json={"name": "增长部"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "增长部"


def test_delete_department_cascades(client, auth_headers):
    """删除父部门应级联删除子部门。"""
    company_id = _create_company(client, auth_headers)
    parent_id = client.post(
        _base(company_id), json={"name": "市场部"}, headers=auth_headers
    ).json()["id"]
    child_id = client.post(
        _base(company_id), json={"name": "品牌组", "parent_id": parent_id}, headers=auth_headers
    ).json()["id"]

    assert (
        client.delete(f"{_base(company_id)}/{parent_id}", headers=auth_headers).status_code
        == 204
    )
    assert (
        client.get(f"{_base(company_id)}/{child_id}", headers=auth_headers).status_code
        == 404
    )


def test_reject_parent_from_other_company(client, auth_headers):
    """父部门不能属于其他企业。"""
    company_a = _create_company(client, auth_headers)
    company_b = client.post(
        "/api/v1/companies", json={"name": "企业B"}, headers=auth_headers
    ).json()["id"]
    foreign_parent = client.post(
        _base(company_b), json={"name": "B的部门"}, headers=auth_headers
    ).json()["id"]

    resp = client.post(
        _base(company_a),
        json={"name": "A的部门", "parent_id": foreign_parent},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_reject_moving_under_descendant(client, auth_headers):
    """不能把部门移动到自己的子孙节点下。"""
    company_id = _create_company(client, auth_headers)
    root_id = client.post(
        _base(company_id), json={"name": "市场部"}, headers=auth_headers
    ).json()["id"]
    child_id = client.post(
        _base(company_id), json={"name": "品牌组", "parent_id": root_id}, headers=auth_headers
    ).json()["id"]

    resp = client.patch(
        f"{_base(company_id)}/{root_id}",
        json={"parent_id": child_id},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_departments_require_auth(client, auth_headers):
    company_id = _create_company(client, auth_headers)
    assert client.get(_base(company_id)).status_code == 401
