"""
设备模板 API 集成测试
"""

import pytest
from app.models.gateway import DeviceTemplate

URL = "/api/v1/device-templates"


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


async def _create_template(async_db, **overrides):
    """在数据库中直接创建一条模板记录"""
    defaults = {
        "name": "测试模板",
        "manufacturer": "华为",
        "model": "UPS-5000",
        "protocol_type": "Modbus",
        "description": "测试用模板",
        "point_config": [{"name": "voltage", "unit": "V", "type": "AI"}],
    }
    defaults.update(overrides)
    t = DeviceTemplate(**defaults)
    async_db.add(t)
    await async_db.commit()
    await async_db.refresh(t)
    return t


# ==================== 列表 ====================


@pytest.mark.asyncio
async def test_list_templates_empty(client, async_db, viewer_token):
    """空列表应返回 0 条"""
    resp = await client.get(URL, headers=auth_headers(viewer_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


@pytest.mark.asyncio
async def test_list_templates_with_data(client, async_db, viewer_token):
    """列表包含已有模板"""
    await _create_template(async_db)
    await _create_template(async_db, name="模板2", manufacturer="施耐德")

    resp = await client.get(URL, headers=auth_headers(viewer_token))
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


@pytest.mark.asyncio
async def test_list_templates_filter_manufacturer(client, async_db, viewer_token):
    """按厂商过滤"""
    await _create_template(async_db, manufacturer="华为")
    await _create_template(async_db, manufacturer="施耐德")

    resp = await client.get(URL, params={"manufacturer": "华为"}, headers=auth_headers(viewer_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["manufacturer"] == "华为"


@pytest.mark.asyncio
async def test_list_templates_keyword(client, async_db, viewer_token):
    """关键词搜索（匹配 name / manufacturer / model）"""
    await _create_template(async_db, name="精密空调模板", manufacturer="华为")
    await _create_template(async_db, name="UPS模板", manufacturer="施耐德")

    resp = await client.get(URL, params={"keyword": "空调"}, headers=auth_headers(viewer_token))
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_list_templates_pagination(client, async_db, viewer_token):
    """分页参数生效"""
    for i in range(5):
        await _create_template(async_db, name=f"模板{i}")

    resp = await client.get(URL, params={"page": 2, "page_size": 2}, headers=auth_headers(viewer_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["page"] == 2


# ==================== 创建 ====================


@pytest.mark.asyncio
async def test_create_template(client, async_db, operator_token):
    """operator 可以创建模板"""
    payload = {
        "name": "新模板",
        "manufacturer": "华为",
        "model": "UPS-5000",
        "protocol_type": "Modbus",
        "description": "通过 API 创建",
        "point_config": [{"name": "current", "unit": "A", "type": "AI"}],
    }
    resp = await client.post(URL, json=payload, headers=auth_headers(operator_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "新模板"
    assert body["id"] is not None


@pytest.mark.asyncio
async def test_create_template_viewer_forbidden(client, async_db, viewer_token):
    """viewer 不能创建模板"""
    payload = {
        "name": "X",
        "manufacturer": "X",
        "model": "X",
        "protocol_type": "Modbus",
        "point_config": [],
    }
    resp = await client.post(URL, json=payload, headers=auth_headers(viewer_token))
    assert resp.status_code == 403


# ==================== 详情 ====================


@pytest.mark.asyncio
async def test_get_template(client, async_db, viewer_token):
    """获取单个模板详情"""
    t = await _create_template(async_db)
    resp = await client.get(f"{URL}/{t.id}", headers=auth_headers(viewer_token))
    assert resp.status_code == 200
    assert resp.json()["id"] == t.id
    assert resp.json()["manufacturer"] == "华为"


@pytest.mark.asyncio
async def test_get_template_not_found(client, async_db, viewer_token):
    """获取不存在的模板返回 404"""
    resp = await client.get(f"{URL}/99999", headers=auth_headers(viewer_token))
    assert resp.status_code == 404


# ==================== 更新 ====================


@pytest.mark.asyncio
async def test_update_template(client, async_db, operator_token):
    """operator 可以更新模板"""
    t = await _create_template(async_db)
    resp = await client.put(
        f"{URL}/{t.id}",
        json={"name": "更新后名称"},
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "更新后名称"


@pytest.mark.asyncio
async def test_update_template_not_found(client, async_db, operator_token):
    """更新不存在的模板返回 404"""
    resp = await client.put(
        f"{URL}/99999",
        json={"name": "X"},
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 404


# ==================== 删除 ====================


@pytest.mark.asyncio
async def test_delete_template(client, async_db, admin_token):
    """admin 可以删除模板"""
    t = await _create_template(async_db)
    resp = await client.delete(f"{URL}/{t.id}", headers=auth_headers(admin_token))
    assert resp.status_code == 200

    # 确认已删除
    resp2 = await client.get(f"{URL}/{t.id}", headers=auth_headers(admin_token))
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_delete_template_operator_forbidden(client, async_db, operator_token):
    """operator 不能删除模板"""
    t = await _create_template(async_db)
    resp = await client.delete(f"{URL}/{t.id}", headers=auth_headers(operator_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_template_not_found(client, async_db, admin_token):
    """删除不存在的模板返回 404"""
    resp = await client.delete(f"{URL}/99999", headers=auth_headers(admin_token))
    assert resp.status_code == 404


# ==================== 从模板创建数据源 ====================


@pytest.mark.asyncio
async def test_create_datasource_from_template(client, async_db, operator_token):
    """operator 从模板创建数据源"""
    t = await _create_template(async_db, point_config=[
        {"address": "40001", "data_type": "uint16", "scale": 0.1, "offset": 0},
    ])
    payload = {
        "name": "数据源-来自模板",
        "protocol_type": "Modbus",
        "connection_config": {"host": "192.168.1.100", "port": 502},
    }
    resp = await client.post(
        f"{URL}/{t.id}/create-datasource",
        json=payload,
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "数据源-来自模板"
    assert body["id"] is not None


@pytest.mark.asyncio
async def test_create_datasource_template_not_found(client, async_db, operator_token):
    """从不存在的模板创建数据源返回 404"""
    payload = {
        "name": "X",
        "protocol_type": "Modbus",
        "connection_config": {"host": "127.0.0.1", "port": 502},
    }
    resp = await client.post(
        f"{URL}/99999/create-datasource",
        json=payload,
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 404
