"""
设备模板 API 集成测试
"""

import pytest
from sqlalchemy import select

from app.models.asset import Asset, Cabinet
from app.models.energy import DeviceShiftConfig, LoadRegulationConfig, PowerDevice
from app.models.gateway import DataSourcePoint, DeviceTemplate
from app.models.point import Point

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


# ==================== 内置协议模板 ====================


@pytest.mark.asyncio
async def test_list_builtin_templates(client, async_db, viewer_token):
    """viewer 可以查看内置协议模板"""
    resp = await client.get(f"{URL}/builtins", headers=auth_headers(viewer_token))
    assert resp.status_code == 200
    body = resp.json()
    keys = {item["key"] for item in body}
    assert "huawei-ups5000-modbus" in keys
    assert "huawei-fusioncol5000a-modbus-rtu" in keys
    ups = next(item for item in body if item["key"] == "huawei-ups5000-modbus")
    assert ups["protocol_type"] == "modbus_tcp"
    assert ups["point_count"] == len(ups["point_config"])
    assert any(p["address"] == "HR:40300.0" for p in ups["point_config"])


@pytest.mark.asyncio
async def test_install_builtin_template_idempotent(client, async_db, operator_token):
    """operator 安装内置模板，重复安装更新同一条记录"""
    url = f"{URL}/builtins/huawei-ups5000-modbus/install"
    resp1 = await client.post(url, headers=auth_headers(operator_token))
    assert resp1.status_code == 200
    body1 = resp1.json()
    assert body1["model"] == "UPS5000"
    assert body1["extra_config"]["builtin_template_key"] == "huawei-ups5000-modbus"
    assert any(p["address"] == "HR:40131.7-9" for p in body1["point_config"])

    resp2 = await client.post(url, headers=auth_headers(operator_token))
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["id"] == body1["id"]

    result = await async_db.execute(select(DeviceTemplate).where(DeviceTemplate.model == "UPS5000"))
    assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_install_builtin_template_viewer_forbidden(client, async_db, viewer_token):
    """viewer 不能安装内置模板"""
    resp = await client.post(f"{URL}/builtins/huawei-ups5000-modbus/install", headers=auth_headers(viewer_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_install_builtin_template_not_found(client, async_db, operator_token):
    """未知内置模板 key 返回 404"""
    resp = await client.post(f"{URL}/builtins/missing/install", headers=auth_headers(operator_token))
    assert resp.status_code == 404


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
async def test_create_datasource_from_installed_builtin_template(client, async_db, operator_token):
    """从安装后的 UPS5000 内置模板创建数据源时填充 PDF 协议点位"""
    install_resp = await client.post(
        f"{URL}/builtins/huawei-ups5000-modbus/install",
        headers=auth_headers(operator_token),
    )
    assert install_resp.status_code == 200
    template_id = install_resp.json()["id"]

    payload = {
        "name": "UPS5000-试点",
        "protocol_type": "modbus_tcp",
        "connection_config": {
            "host": "192.168.1.100",
            "port": 502,
            "device_id": 1,
            "device_code": "UPS5000-A01",
            "device_name": "UPS5000 A01",
            "rated_power": 200,
            "rated_voltage": 380,
            "rated_current": 300,
            "area_code": "A2",
        },
    }
    resp = await client.post(
        f"{URL}/{template_id}/create-datasource",
        json=payload,
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 200
    datasource_id = resp.json()["id"]

    result = await async_db.execute(
        select(DataSourcePoint).where(DataSourcePoint.datasource_id == datasource_id)
    )
    points = result.scalars().all()
    addresses = {p.address for p in points}
    assert "HR:40001" in addresses
    assert "HR:40131.7-9" in addresses
    assert "HR:40300.0" in addresses
    assert len(points) == len(install_resp.json()["point_config"])
    assert all(p.point_id is not None for p in points)

    point_ids = [p.point_id for p in points]
    point_result = await async_db.execute(select(Point).where(Point.id.in_(point_ids)))
    business_points = point_result.scalars().all()
    points_by_code = {p.point_code: p for p in business_points}
    point_codes = set(points_by_code)
    assert f"ds{datasource_id}_input_voltage_a" in point_codes
    assert all(p.device_type == "UPS" for p in business_points)

    device_result = await async_db.execute(select(PowerDevice).where(PowerDevice.device_code == "UPS5000-A01"))
    device = device_result.scalar_one()
    assert device.device_name == "UPS5000 A01"
    assert device.device_type == "UPS"
    assert device.rated_power == 200
    assert device.area_code == "A2"
    assert device.power_point_id == points_by_code[f"ds{datasource_id}_output_active_power_a"].id
    assert device.voltage_point_id == points_by_code[f"ds{datasource_id}_output_voltage_a"].id
    assert device.current_point_id == points_by_code[f"ds{datasource_id}_output_current_a"].id
    assert all(p.energy_device_id == device.id for p in business_points)

    reg_result = await async_db.execute(
        select(LoadRegulationConfig).where(LoadRegulationConfig.device_id == device.id)
    )
    regulation_config = reg_result.scalar_one()
    assert regulation_config.regulation_type == "mode"


@pytest.mark.asyncio
async def test_create_datasource_from_fusioncol_template_creates_ac_power_device(client, async_db, operator_token):
    """从 FusionCol5000-A 模板创建数据源时生成 AC 用电设备和调节配置"""
    cabinet = Cabinet(cabinet_code="CAB-A01", cabinet_name="A01机柜", total_u=42)
    async_db.add(cabinet)
    await async_db.commit()

    install_resp = await client.post(
        f"{URL}/builtins/huawei-fusioncol5000a-modbus-rtu/install",
        headers=auth_headers(operator_token),
    )
    assert install_resp.status_code == 200
    template_id = install_resp.json()["id"]

    payload = {
        "name": "FusionCol5000-A-01",
        "protocol_type": "modbus_rtu",
        "connection_config": {
            "port": "COM3",
            "baudrate": 9600,
            "device_id": 1,
            "device_code": "FCOL-A01",
            "device_name": "FusionCol A01",
            "rated_power": 35,
            "area_code": "B1",
            "load_subtype": "row_ac",
            "controllable_params": ["temperature_setpoint", "indoor_fan_output", "cooling_output"],
            "asset_code": "ASSET-FCOL-A01",
            "cabinet_code": "CAB-A01",
            "u_position": 38,
            "u_height": 4,
        },
    }
    resp = await client.post(
        f"{URL}/{template_id}/create-datasource",
        json=payload,
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 200
    datasource_id = resp.json()["id"]

    ds_points_result = await async_db.execute(
        select(DataSourcePoint).where(DataSourcePoint.datasource_id == datasource_id)
    )
    ds_points = ds_points_result.scalars().all()
    assert len(ds_points) == len(install_resp.json()["point_config"])
    assert all(p.point_id is not None for p in ds_points)

    point_result = await async_db.execute(select(Point).where(Point.id.in_([p.point_id for p in ds_points])))
    business_points = point_result.scalars().all()
    points_by_code = {p.point_code: p for p in business_points}

    device_result = await async_db.execute(select(PowerDevice).where(PowerDevice.device_code == "FCOL-A01"))
    device = device_result.scalar_one()
    assert device.device_name == "FusionCol A01"
    assert device.device_type == "AC"
    assert device.area_code == "B1"
    assert device.rated_power == 35
    assert device.load_subtype == "row_ac"
    assert "indoor_fan_output" in device.controllable_params
    assert device.voltage_point_id == points_by_code[f"ds{datasource_id}_ab_line_voltage"].id
    assert device.power_point_id is None
    assert all(p.energy_device_id == device.id for p in business_points)

    reg_result = await async_db.execute(
        select(LoadRegulationConfig).where(LoadRegulationConfig.device_id == device.id)
    )
    regulation_config = reg_result.scalar_one()
    assert regulation_config.regulation_type == "temperature"
    assert regulation_config.base_power == 35

    shift_result = await async_db.execute(select(DeviceShiftConfig).where(DeviceShiftConfig.device_id == device.id))
    shift_config = shift_result.scalar_one()
    assert shift_config.is_shiftable is True
    assert shift_config.shiftable_power_ratio != 0.30

    asset_result = await async_db.execute(select(Asset).where(Asset.asset_code == "ASSET-FCOL-A01"))
    asset = asset_result.scalar_one()
    assert asset.cabinet_id == cabinet.id
    assert asset.u_position == 38
    assert asset.u_height == 4


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
