"""
BACnet MS/TP 网关数据源 API 测试
Story 35.1: DeviceTemplate extra_config + DataSource parent_datasource_id + 批量创建
"""

import pytest
from app.models.gateway import DeviceTemplate, DataSource, DataSourcePoint

URL = "/api/v1/device-templates"


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ==================== 辅助函数 ====================

SAMPLE_EXTRA_CONFIG = {
    "gateway_type": "bacnet_mstp_to_ip",
    "gateway_device_instance": 100,
    "mstp_config": {"network_number": 1, "mac_range": [1, 127], "baud_rate": 9600, "parity": "none"},
    "bbmd_config": {"enabled": False, "bdt_entries": []},
    "downstream_devices": [
        {"mac_address": 1, "device_instance": 201, "device_name": "大金VRV-B区-1", "model": "RXYQ16TAY1"},
        {"mac_address": 2, "device_instance": 202, "device_name": "大金VRV-B区-2", "model": "RXYQ16TAY1"},
    ],
}

SAMPLE_POINT_CONFIG = [
    {"address": "MI:1", "data_type": "uint16", "scale": 1.0, "offset": 0.0, "description": "运行模式"},
    {"address": "AV:1", "data_type": "float32", "scale": 1.0, "offset": 0.0, "description": "设定温度"},
]


async def _create_mstp_template(async_db, **overrides):
    """创建带 extra_config 的 MS/TP 网关模板"""
    defaults = {
        "name": "大金VRV转换网关(测试)",
        "manufacturer": "大金/Intesis",
        "model": "MAPS-VRV-BACNET",
        "protocol_type": "bacnet_ip",
        "description": "测试用 MS/TP 网关模板",
        "point_config": SAMPLE_POINT_CONFIG,
        "extra_config": SAMPLE_EXTRA_CONFIG,
    }
    defaults.update(overrides)
    t = DeviceTemplate(**defaults)
    async_db.add(t)
    await async_db.commit()
    await async_db.refresh(t)
    return t


# ==================== Task 6.1: 模型字段存在性测试 ====================


@pytest.mark.asyncio
async def test_device_template_extra_config_field(async_db):
    """DeviceTemplate 模型支持 extra_config 字段"""
    t = await _create_mstp_template(async_db)
    assert t.extra_config is not None
    assert t.extra_config["gateway_type"] == "bacnet_mstp_to_ip"


@pytest.mark.asyncio
async def test_datasource_parent_datasource_id_field(async_db):
    """DataSource 模型支持 parent_datasource_id 字段"""
    parent = DataSource(
        name="网关DS", protocol_type="bacnet_ip",
        connection_config={"host": "10.0.0.1", "port": 47808},
    )
    async_db.add(parent)
    await async_db.flush()

    child = DataSource(
        name="子设备DS", protocol_type="bacnet_ip",
        connection_config={"host": "10.0.0.1", "port": 47808},
        parent_datasource_id=parent.id,
    )
    async_db.add(child)
    await async_db.commit()
    await async_db.refresh(child)
    assert child.parent_datasource_id == parent.id


# ==================== Task 6.2: Schema 验证测试 ====================


def test_mstp_gateway_extra_config_valid():
    """MstpGatewayExtraConfig 正常验证通过"""
    from app.schemas.gateway import MstpGatewayExtraConfig
    cfg = MstpGatewayExtraConfig(**SAMPLE_EXTRA_CONFIG)
    assert cfg.gateway_type == "bacnet_mstp_to_ip"
    assert len(cfg.downstream_devices) == 2


def test_mstp_baud_rate_invalid():
    """baud_rate 不在允许列表时返回验证错误"""
    from app.schemas.gateway import MstpGatewayExtraConfig
    bad = {**SAMPLE_EXTRA_CONFIG, "mstp_config": {**SAMPLE_EXTRA_CONFIG["mstp_config"], "baud_rate": 4800}}
    with pytest.raises(Exception):
        MstpGatewayExtraConfig(**bad)


def test_mstp_mac_address_out_of_range():
    """mac_address=0 和 mac_address=128 应校验失败 (Task 6.9)"""
    from app.schemas.gateway import MstpDownstreamDevice
    with pytest.raises(Exception):
        MstpDownstreamDevice(mac_address=0, device_instance=100, device_name="test")
    with pytest.raises(Exception):
        MstpDownstreamDevice(mac_address=128, device_instance=100, device_name="test")


def test_mstp_device_instance_out_of_range():
    """device_instance 负数和 4194303 应校验失败 (Task 6.9)"""
    from app.schemas.gateway import MstpDownstreamDevice
    with pytest.raises(Exception):
        MstpDownstreamDevice(mac_address=1, device_instance=-1, device_name="test")
    with pytest.raises(Exception):
        MstpDownstreamDevice(mac_address=1, device_instance=4194303, device_name="test")


def test_mstp_duplicate_mac_address():
    """downstream_devices 内 mac_address 重复应验证失败 (Task 6.14)"""
    from app.schemas.gateway import MstpGatewayExtraConfig
    bad = {
        **SAMPLE_EXTRA_CONFIG,
        "downstream_devices": [
            {"mac_address": 1, "device_instance": 201, "device_name": "A"},
            {"mac_address": 1, "device_instance": 202, "device_name": "B"},
        ],
    }
    with pytest.raises(Exception, match="mac_address"):
        MstpGatewayExtraConfig(**bad)


def test_mstp_duplicate_device_instance():
    """downstream_devices 内 device_instance 重复应验证失败"""
    from app.schemas.gateway import MstpGatewayExtraConfig
    bad = {
        **SAMPLE_EXTRA_CONFIG,
        "downstream_devices": [
            {"mac_address": 1, "device_instance": 201, "device_name": "A"},
            {"mac_address": 2, "device_instance": 201, "device_name": "B"},
        ],
    }
    with pytest.raises(Exception, match="device_instance"):
        MstpGatewayExtraConfig(**bad)


def test_gateway_ip_invalid():
    """gateway_ip 非法格式应返回验证错误 (Task 6.13)"""
    from app.schemas.gateway import CreateMstpDatasourcesRequest
    with pytest.raises(Exception):
        CreateMstpDatasourcesRequest(gateway_ip="abc")
    with pytest.raises(Exception):
        CreateMstpDatasourcesRequest(gateway_ip="")


def test_gateway_ip_reject_special_addresses():
    """gateway_ip 不能是 0.0.0.0 / 255.255.255.255 / 多播"""
    from app.schemas.gateway import CreateMstpDatasourcesRequest
    with pytest.raises(Exception):
        CreateMstpDatasourcesRequest(gateway_ip="0.0.0.0")
    with pytest.raises(Exception):
        CreateMstpDatasourcesRequest(gateway_ip="255.255.255.255")
    with pytest.raises(Exception):
        CreateMstpDatasourcesRequest(gateway_ip="224.0.0.1")


def test_gateway_device_instance_out_of_range():
    """gateway_device_instance 越界应校验失败 (P7)"""
    from app.schemas.gateway import MstpGatewayExtraConfig
    bad_neg = {**SAMPLE_EXTRA_CONFIG, "gateway_device_instance": -1}
    with pytest.raises(Exception):
        MstpGatewayExtraConfig(**bad_neg)
    bad_high = {**SAMPLE_EXTRA_CONFIG, "gateway_device_instance": 4194303}
    with pytest.raises(Exception):
        MstpGatewayExtraConfig(**bad_high)


def test_mstp_config_mac_range_validation():
    """mac_range 必须是两个有序元素，范围 1-127"""
    from app.schemas.gateway import MstpConfig
    with pytest.raises(Exception):
        MstpConfig(mac_range=[])
    with pytest.raises(Exception):
        MstpConfig(mac_range=[1])
    with pytest.raises(Exception):
        MstpConfig(mac_range=[127, 1])
    with pytest.raises(Exception):
        MstpConfig(mac_range=[0, 127])


def test_mstp_config_parity_invalid():
    """parity 不在 none/even/odd 时应校验失败"""
    from app.schemas.gateway import MstpConfig
    with pytest.raises(Exception):
        MstpConfig(parity="garbage")


# ==================== Task 6.3: API — 创建/更新/查询带 extra_config 的模板 ====================


@pytest.mark.asyncio
async def test_create_template_with_extra_config(client, async_db, operator_token):
    """创建模板带 extra_config 成功"""
    payload = {
        "name": "网关模板API",
        "manufacturer": "大金",
        "model": "VRV-GW",
        "protocol_type": "bacnet_ip",
        "point_config": SAMPLE_POINT_CONFIG,
        "extra_config": SAMPLE_EXTRA_CONFIG,
    }
    resp = await client.post(URL, json=payload, headers=auth_headers(operator_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["extra_config"]["gateway_type"] == "bacnet_mstp_to_ip"
    assert "mstp_config" in body["extra_config"]
    assert "downstream_devices" in body["extra_config"]


@pytest.mark.asyncio
async def test_update_template_extra_config(client, async_db, operator_token):
    """更新模板 extra_config"""
    t = await _create_mstp_template(async_db)
    new_extra = {**SAMPLE_EXTRA_CONFIG, "gateway_device_instance": 200}
    resp = await client.put(
        f"{URL}/{t.id}",
        json={"extra_config": new_extra},
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 200
    assert resp.json()["extra_config"]["gateway_device_instance"] == 200


@pytest.mark.asyncio
async def test_create_template_invalid_extra_config_baud_rate(client, async_db, operator_token):
    """创建模板时 extra_config baud_rate 无效返回 422"""
    bad_extra = {**SAMPLE_EXTRA_CONFIG, "mstp_config": {**SAMPLE_EXTRA_CONFIG["mstp_config"], "baud_rate": 4800}}
    payload = {
        "name": "Bad",
        "manufacturer": "X",
        "model": "X",
        "protocol_type": "bacnet_ip",
        "point_config": [],
        "extra_config": bad_extra,
    }
    resp = await client.post(URL, json=payload, headers=auth_headers(operator_token))
    assert resp.status_code == 422


# ==================== Task 6.4: API — create-mstp-datasources 完整流程 ====================


@pytest.mark.asyncio
async def test_create_mstp_datasources_full_flow(client, async_db, operator_token):
    """批量创建 MS/TP 数据源完整流程：网关+子设备+点位"""
    t = await _create_mstp_template(async_db)
    payload = {"gateway_ip": "192.168.1.100", "port": 47808}
    resp = await client.post(
        f"{URL}/{t.id}/create-mstp-datasources",
        json=payload,
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 200
    body = resp.json()

    # 网关 DataSource
    gw = body["gateway"]
    assert "网关" in gw["name"]
    assert "192.168.1.100" in gw["name"]
    assert gw["connection_config"]["is_mstp_gateway"] is True
    assert gw["connection_config"]["device_id"] == 100
    assert gw["is_enabled"] is False
    assert gw["collection_interval"] == 5  # 网关不采集，使用默认值

    # 子设备 DataSource
    assert body["total_devices"] == 2
    assert len(body["devices"]) == 2
    for dev in body["devices"]:
        assert dev["parent_datasource_id"] == gw["id"]
        assert dev["is_enabled"] is True
        assert dev["collection_interval"] == 10


@pytest.mark.asyncio
async def test_create_mstp_datasources_response_format(client, async_db, operator_token):
    """响应包含网关和所有子 DataSource 列表 (Task 6.10)"""
    t = await _create_mstp_template(async_db)
    resp = await client.post(
        f"{URL}/{t.id}/create-mstp-datasources",
        json={"gateway_ip": "10.0.0.1"},
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "gateway" in body
    assert "devices" in body
    assert "total_devices" in body
    assert body["total_devices"] == len(body["devices"])


@pytest.mark.asyncio
async def test_create_mstp_datasources_child_names(client, async_db, operator_token):
    """子设备 DataSource 的 name 使用 device_name (Task 6.15)"""
    t = await _create_mstp_template(async_db)
    resp = await client.post(
        f"{URL}/{t.id}/create-mstp-datasources",
        json={"gateway_ip": "10.0.0.1"},
        headers=auth_headers(operator_token),
    )
    body = resp.json()
    names = [d["name"] for d in body["devices"]]
    assert "大金VRV-B区-1" in names
    assert "大金VRV-B区-2" in names


# ==================== Task 6.5: API — 错误场景 ====================


@pytest.mark.asyncio
async def test_create_mstp_datasources_template_not_found(client, async_db, operator_token):
    """模板不存在返回 404"""
    resp = await client.post(
        f"{URL}/99999/create-mstp-datasources",
        json={"gateway_ip": "10.0.0.1"},
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_mstp_datasources_no_extra_config(client, async_db, operator_token):
    """模板无 extra_config 返回 422"""
    t = await _create_mstp_template(async_db, extra_config=None)
    resp = await client.post(
        f"{URL}/{t.id}/create-mstp-datasources",
        json={"gateway_ip": "10.0.0.1"},
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_mstp_datasources_wrong_gateway_type(client, async_db, operator_token):
    """gateway_type 不匹配返回 422"""
    t = await _create_mstp_template(async_db, extra_config={"gateway_type": "other", "foo": "bar"})
    resp = await client.post(
        f"{URL}/{t.id}/create-mstp-datasources",
        json={"gateway_ip": "10.0.0.1"},
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_mstp_datasources_empty_downstream(client, async_db, operator_token):
    """downstream_devices 为空返回 422"""
    empty_extra = {**SAMPLE_EXTRA_CONFIG, "downstream_devices": []}
    t = await _create_mstp_template(async_db, extra_config=empty_extra)
    resp = await client.post(
        f"{URL}/{t.id}/create-mstp-datasources",
        json={"gateway_ip": "10.0.0.1"},
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 422


# ==================== Task 6.6: DataSourceResponse 包含 parent_datasource_id ====================


@pytest.mark.asyncio
async def test_datasource_response_includes_parent_id(client, async_db, operator_token):
    """DataSourceResponse 包含 parent_datasource_id 字段"""
    t = await _create_mstp_template(async_db)
    resp = await client.post(
        f"{URL}/{t.id}/create-mstp-datasources",
        json={"gateway_ip": "10.0.0.2"},
        headers=auth_headers(operator_token),
    )
    body = resp.json()
    # 网关自身无父
    assert body["gateway"]["parent_datasource_id"] is None
    # 子设备有父
    for dev in body["devices"]:
        assert dev["parent_datasource_id"] is not None


# ==================== Task 6.8: 权限测试 ====================


@pytest.mark.asyncio
async def test_create_mstp_datasources_viewer_forbidden(client, async_db, viewer_token):
    """viewer 无法创建 MS/TP 数据源"""
    t = await _create_mstp_template(async_db)
    resp = await client.post(
        f"{URL}/{t.id}/create-mstp-datasources",
        json={"gateway_ip": "10.0.0.1"},
        headers=auth_headers(viewer_token),
    )
    assert resp.status_code == 403


# ==================== Task 6.7: 事务回滚测试 ====================


@pytest.mark.asyncio
async def test_create_mstp_datasources_no_residual_on_error(client, async_db, operator_token):
    """错误场景不应留下残留数据（事务原子性）"""
    from sqlalchemy import select, func
    from app.models.gateway import DataSource

    # 先统计现有 DataSource 数量
    count_before = (await async_db.execute(select(func.count()).select_from(DataSource))).scalar()

    # 尝试用不存在的模板创建（应 404，无残留）
    resp = await client.post(
        f"{URL}/99999/create-mstp-datasources",
        json={"gateway_ip": "10.0.0.99"},
        headers=auth_headers(operator_token),
    )
    assert resp.status_code == 404

    count_after = (await async_db.execute(select(func.count()).select_from(DataSource))).scalar()
    assert count_after == count_before, "404 不应创建任何 DataSource"


# ==================== Task 6.11: 回归测试 ====================


@pytest.mark.asyncio
async def test_create_template_without_extra_config(client, async_db, operator_token):
    """不传 extra_config 的模板仍正常创建（回归）"""
    payload = {
        "name": "普通模板",
        "manufacturer": "华为",
        "model": "UPS-5000",
        "protocol_type": "Modbus",
        "point_config": [{"address": "40001", "data_type": "uint16"}],
    }
    resp = await client.post(URL, json=payload, headers=auth_headers(operator_token))
    assert resp.status_code == 200
    assert resp.json()["extra_config"] is None


# ==================== Task 6.12: extra_config 透传模式 ====================


@pytest.mark.asyncio
async def test_extra_config_passthrough(client, async_db, operator_token):
    """extra_config 不含 gateway_type 时原样保存（透传模式）"""
    custom_extra = {"custom_key": "custom_value", "nested": {"a": 1}}
    payload = {
        "name": "自定义模板",
        "manufacturer": "X",
        "model": "X",
        "protocol_type": "custom",
        "point_config": [],
        "extra_config": custom_extra,
    }
    resp = await client.post(URL, json=payload, headers=auth_headers(operator_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["extra_config"]["custom_key"] == "custom_value"
    assert body["extra_config"]["nested"]["a"] == 1
