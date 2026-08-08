"""
覆盖率测试 — datasources / demo / dispatch / floor_map / monitoring
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

from app.models.gateway import DataSource
from app.models.floor_map import FloorMap
from app.models.energy import (
    DispatchableDevice,
    StorageSystemConfig,
    PVSystemConfig,
    PricingConfig,
    RealtimeMonitoring,
)
from tests.conftest import auth_headers


# ==================== 辅助函数 ====================


async def _seed_datasource(db, **overrides) -> DataSource:
    defaults = dict(
        name="测试数据源",
        protocol_type="modbus_tcp",
        connection_config={"host": "127.0.0.1", "port": 502},
        status="connected",
        is_enabled=True,
    )
    defaults.update(overrides)
    obj = DataSource(**defaults)
    db.add(obj)
    await db.flush()
    return obj


async def _seed_floor_map(db, **overrides) -> FloorMap:
    defaults = dict(
        floor_code="F1",
        floor_name="一层",
        map_type="3d",
        map_data=json.dumps({"rooms": []}),
        is_default=True,
    )
    defaults.update(overrides)
    obj = FloorMap(**defaults)
    db.add(obj)
    await db.flush()
    return obj


async def _seed_dispatch_device(db, **overrides) -> DispatchableDevice:
    defaults = dict(
        name="测试设备",
        device_type="curtailable",
        rated_power=100,
        priority=5,
        is_active=True,
    )
    defaults.update(overrides)
    obj = DispatchableDevice(**defaults)
    db.add(obj)
    await db.flush()
    return obj


async def _seed_storage(db, **overrides) -> StorageSystemConfig:
    defaults = dict(
        name="测试储能",
        capacity=500,
        max_charge_power=125,
        max_discharge_power=125,
        is_active=True,
    )
    defaults.update(overrides)
    obj = StorageSystemConfig(**defaults)
    db.add(obj)
    await db.flush()
    return obj


async def _seed_pv(db, **overrides) -> PVSystemConfig:
    defaults = dict(
        name="测试光伏",
        rated_capacity=300,
        efficiency=0.85,
        is_active=True,
    )
    defaults.update(overrides)
    obj = PVSystemConfig(**defaults)
    db.add(obj)
    await db.flush()
    return obj


async def _seed_pricing(db) -> PricingConfig:
    from datetime import date as _date

    obj = PricingConfig(
        config_name="测试电价",
        is_enabled=True,
        declared_demand=1000,
        demand_price=38,
        effective_date=_date.today(),
    )
    db.add(obj)
    await db.flush()
    return obj


# ==================== DataSources ====================


class TestDataSources:
    """数据源管理 API"""

    async def test_list_datasources_empty(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/datasources", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    async def test_list_datasources_with_data(self, client, admin_user, async_db):
        _, token = admin_user
        await _seed_datasource(async_db)
        await _seed_datasource(async_db, name="第二数据源", protocol_type="snmp_v2c")
        resp = await client.get("/api/v1/datasources", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    async def test_list_datasources_filter_protocol(self, client, admin_user, async_db):
        _, token = admin_user
        await _seed_datasource(async_db)
        await _seed_datasource(async_db, name="SNMP源", protocol_type="snmp_v2c")
        resp = await client.get(
            "/api/v1/datasources",
            params={"protocol_type": "snmp_v2c"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    async def test_create_datasource(self, client, admin_user, async_db):
        _, token = admin_user
        payload = {
            "name": "新数据源",
            "protocol_type": "modbus_tcp",
            "connection_config": {"host": "10.0.0.1", "port": 502},
        }
        resp = await client.post(
            "/api/v1/datasources",
            json=payload,
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "新数据源"

    async def test_create_datasource_bad_protocol(self, client, admin_user, async_db):
        _, token = admin_user
        payload = {
            "name": "坏协议",
            "protocol_type": "unknown_proto",
            "connection_config": {},
        }
        resp = await client.post(
            "/api/v1/datasources",
            json=payload,
            headers=auth_headers(token),
        )
        assert resp.status_code == 400

    async def test_get_datasource_detail(self, client, admin_user, async_db):
        _, token = admin_user
        ds = await _seed_datasource(async_db)
        resp = await client.get(
            f"/api/v1/datasources/{ds.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == ds.id

    async def test_get_datasource_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get(
            "/api/v1/datasources/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_update_datasource(self, client, admin_user, async_db):
        _, token = admin_user
        ds = await _seed_datasource(async_db)
        resp = await client.put(
            f"/api/v1/datasources/{ds.id}",
            json={"name": "已更新"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "已更新"

    async def test_update_datasource_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.put(
            "/api/v1/datasources/99999",
            json={"name": "不存在"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_delete_datasource(self, client, admin_user, async_db):
        _, token = admin_user
        ds = await _seed_datasource(async_db)
        resp = await client.delete(
            f"/api/v1/datasources/{ds.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_delete_datasource_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.delete(
            "/api/v1/datasources/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_toggle_write_permission(self, client, admin_user, async_db):
        _, token = admin_user
        ds = await _seed_datasource(async_db, write_enabled=False)
        resp = await client.put(
            f"/api/v1/datasources/{ds.id}/write-permission",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["write_enabled"] is True

    async def test_communication_status(self, client, admin_user, async_db):
        _, token = admin_user
        await _seed_datasource(async_db)
        resp = await client.get(
            "/api/v1/datasources/communication-status",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ==================== Demo ====================


class TestDemo:
    """演示数据 API"""

    async def test_get_demo_status(self, client, admin_user, async_db):
        _, token = admin_user
        with patch(
            "app.demo.service.demo_data_service.check_demo_data_status",
            new_callable=AsyncMock,
            return_value={"loaded": False, "records": 0},
        ):
            resp = await client.get("/api/v1/demo/status", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    async def test_get_load_progress(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/demo/progress", headers=auth_headers(token))
        assert resp.status_code == 200
        assert "loading" in resp.json()["data"]

    async def test_load_demo_data(self, client, admin_user, async_db):
        _, token = admin_user
        with patch("app.demo.router.demo_data_service") as mock_svc:
            mock_svc.loading = False
            mock_svc.progress = 0
            mock_svc.progress_message = ""
            resp = await client.post(
                "/api/v1/demo/load",
                json={"days": 7},
                headers=auth_headers(token),
            )
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    async def test_load_demo_data_already_loading(self, client, admin_user, async_db):
        _, token = admin_user
        with patch("app.demo.router.demo_data_service") as mock_svc:
            mock_svc.loading = True
            mock_svc.progress = 50
            mock_svc.progress_message = "加载中"
            resp = await client.post(
                "/api/v1/demo/load",
                json={"days": 7},
                headers=auth_headers(token),
            )
        assert resp.status_code == 200
        assert resp.json()["code"] == 1

    async def test_unload_demo_data(self, client, admin_user, async_db):
        _, token = admin_user
        with patch("app.demo.router.demo_data_service") as mock_svc:
            mock_svc.unload_demo_data = AsyncMock(return_value={"success": True, "message": "已卸载"})
            resp = await client.post(
                "/api/v1/demo/unload",
                headers=auth_headers(token),
            )
        assert resp.status_code == 200

    async def test_refresh_dates(self, client, admin_user, async_db):
        _, token = admin_user
        with patch("app.demo.router.demo_data_service") as mock_svc:
            mock_svc.loading = False
            resp = await client.post(
                "/api/v1/demo/refresh-dates",
                headers=auth_headers(token),
            )
        assert resp.status_code == 200
        assert resp.json()["code"] == 0


# ==================== Dispatch ====================


class TestDispatchDevices:
    """可调度设备 API"""

    async def test_list_devices_empty(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/dispatch/devices", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_devices_with_data(self, client, admin_user, async_db):
        _, token = admin_user
        await _seed_dispatch_device(async_db)
        resp = await client.get("/api/v1/dispatch/devices", headers=auth_headers(token))
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_list_devices_filter_type(self, client, admin_user, async_db):
        _, token = admin_user
        await _seed_dispatch_device(async_db, device_type="shiftable")
        await _seed_dispatch_device(async_db, name="削减设备", device_type="curtailable")
        resp = await client.get(
            "/api/v1/dispatch/devices",
            params={"device_type": "shiftable"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_create_device(self, client, admin_user, async_db):
        _, token = admin_user
        payload = {
            "name": "新设备",
            "device_type": "curtailable",
            "rated_power": 200,
        }
        resp = await client.post(
            "/api/v1/dispatch/devices",
            json=payload,
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "新设备"

    async def test_get_device_detail(self, client, admin_user, async_db):
        _, token = admin_user
        dev = await _seed_dispatch_device(async_db)
        resp = await client.get(
            f"/api/v1/dispatch/devices/{dev.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == dev.id

    async def test_get_device_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get(
            "/api/v1/dispatch/devices/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_update_device(self, client, admin_user, async_db):
        _, token = admin_user
        dev = await _seed_dispatch_device(async_db)
        resp = await client.put(
            f"/api/v1/dispatch/devices/{dev.id}",
            json={"name": "已更新设备"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "已更新设备"

    async def test_delete_device(self, client, admin_user, async_db):
        _, token = admin_user
        dev = await _seed_dispatch_device(async_db)
        resp = await client.delete(
            f"/api/v1/dispatch/devices/{dev.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_delete_device_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.delete(
            "/api/v1/dispatch/devices/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_device_stats(self, client, admin_user, async_db):
        _, token = admin_user
        await _seed_dispatch_device(async_db)
        resp = await client.get(
            "/api/v1/dispatch/devices/summary/stats",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "total" in body
        assert body["total"] >= 1


class TestDispatchStorage:
    """储能系统 API"""

    async def test_list_storage_empty(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/dispatch/storage", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_storage(self, client, admin_user, async_db):
        _, token = admin_user
        payload = {
            "name": "新储能",
            "capacity": 100,
            "max_charge_power": 50,
            "max_discharge_power": 50,
        }
        resp = await client.post(
            "/api/v1/dispatch/storage",
            json=payload,
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "新储能"

    async def test_get_storage_detail(self, client, admin_user, async_db):
        _, token = admin_user
        s = await _seed_storage(async_db)
        resp = await client.get(
            f"/api/v1/dispatch/storage/{s.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_get_storage_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get(
            "/api/v1/dispatch/storage/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_update_storage(self, client, admin_user, async_db):
        _, token = admin_user
        s = await _seed_storage(async_db)
        resp = await client.put(
            f"/api/v1/dispatch/storage/{s.id}",
            json={"name": "已更新储能"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_delete_storage(self, client, admin_user, async_db):
        _, token = admin_user
        s = await _seed_storage(async_db)
        resp = await client.delete(
            f"/api/v1/dispatch/storage/{s.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_delete_storage_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.delete(
            "/api/v1/dispatch/storage/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404


class TestDispatchPV:
    """光伏系统 API"""

    async def test_list_pv_empty(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/dispatch/pv", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_pv(self, client, admin_user, async_db):
        _, token = admin_user
        payload = {"name": "新光伏", "rated_capacity": 100}
        resp = await client.post(
            "/api/v1/dispatch/pv",
            json=payload,
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "新光伏"

    async def test_get_pv_detail(self, client, admin_user, async_db):
        _, token = admin_user
        pv = await _seed_pv(async_db)
        resp = await client.get(
            f"/api/v1/dispatch/pv/{pv.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_get_pv_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get(
            "/api/v1/dispatch/pv/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_delete_pv(self, client, admin_user, async_db):
        _, token = admin_user
        pv = await _seed_pv(async_db)
        resp = await client.delete(
            f"/api/v1/dispatch/pv/{pv.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_delete_pv_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.delete(
            "/api/v1/dispatch/pv/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404


class TestDispatchSummary:
    """资源汇总 + 演示数据初始化"""

    async def test_summary_empty(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/dispatch/summary", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert "dispatchable_devices" in body
        assert "storage_systems" in body
        assert "pv_systems" in body

    async def test_init_demo_data(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.post(
            "/api/v1/demo/init-dispatch-data",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["created"] is True

    async def test_init_demo_data_already_exists(self, client, admin_user, async_db):
        _, token = admin_user
        await _seed_dispatch_device(async_db)
        resp = await client.post(
            "/api/v1/demo/init-dispatch-data",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["created"] is False


# ==================== FloorMap ====================


class TestFloorMap:
    """楼层图 API"""

    async def test_get_floors_uses_generated_defaults(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/floor-map/floors", headers=auth_headers(token))
        assert resp.status_code == 200
        floors = resp.json()["data"]["floors"]
        assert [floor["floor_code"] for floor in floors] == ["B1", "F1", "F2", "F3"]
        assert all(floor["map_types"] == ["2d", "3d"] for floor in floors)

    async def test_get_floors_with_data(self, client, admin_user, async_db):
        _, token = admin_user
        await _seed_floor_map(async_db)
        await _seed_floor_map(async_db, floor_code="F2", floor_name="二层", map_type="2d", is_default=False)
        resp = await client.get("/api/v1/floor-map/floors", headers=auth_headers(token))
        assert resp.status_code == 200
        floors = resp.json()["data"]["floors"]
        assert len(floors) >= 1

    async def test_get_floor_map_3d(self, client, admin_user, async_db):
        _, token = admin_user
        await _seed_floor_map(async_db)
        resp = await client.get("/api/v1/floor-map/F1/3d", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["data"]["floor_code"] == "F1"

    async def test_get_floor_map_uses_generated_fallback(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/floor-map/F9/3d", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["id"] == 0
        assert body["floor_code"] == "F9"
        assert body["map_type"] == "3d"

    async def test_get_floor_map_bad_type(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/floor-map/F1/4d", headers=auth_headers(token))
        assert resp.status_code == 400

    async def test_get_default_floor_map(self, client, admin_user, async_db):
        _, token = admin_user
        await _seed_floor_map(async_db)
        resp = await client.get(
            "/api/v1/floor-map/default",
            params={"map_type": "3d"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["is_default"] is True

    async def test_get_default_floor_map_uses_generated_fallback(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get(
            "/api/v1/floor-map/default",
            params={"map_type": "3d"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["id"] == 0
        assert body["floor_code"] == "F1"
        assert body["is_default"] is True


# ==================== Monitoring ====================


class TestMonitoring:
    """电费监控 API"""

    async def test_realtime_status_no_data(self, client, admin_user, async_db):
        """无实时数据 → 返回默认值"""
        _, token = admin_user
        await _seed_pricing(async_db)
        resp = await client.get(
            "/api/v1/monitoring/realtime/status",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["alert_level"] == "normal"
        assert body["is_demo_data"] is False

    async def test_realtime_status_with_fresh_data(self, client, admin_user, async_db):
        """有新鲜实时数据 → 使用真实数据"""
        _, token = admin_user
        await _seed_pricing(async_db)
        rm = RealtimeMonitoring(
            timestamp=datetime.now(),
            current_power=800,
            window_avg_power=750,
            demand_target=1000,
            utilization_ratio=75,
            alert_level="normal",
        )
        async_db.add(rm)
        await async_db.flush()

        resp = await client.get(
            "/api/v1/monitoring/realtime/status",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["current_power"] == 800.0

    async def test_realtime_alerts_normal(self, client, admin_user, async_db):
        """正常状态 → 无预警"""
        _, token = admin_user
        await _seed_pricing(async_db)
        resp = await client.get(
            "/api/v1/monitoring/realtime/alerts",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_realtime_curve_empty(self, client, admin_user, async_db):
        """无数据 → 空曲线"""
        _, token = admin_user
        await _seed_pricing(async_db)
        resp = await client.get(
            "/api/v1/monitoring/realtime/curve",
            params={"hours": 1},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []

    async def test_monthly_current_no_data(self, client, admin_user, async_db):
        """无月度数据 → 默认值"""
        _, token = admin_user
        await _seed_pricing(async_db)
        resp = await client.get(
            "/api/v1/monitoring/monthly/current",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_energy"] == 0

    async def test_monthly_history_empty(self, client, admin_user, async_db):
        _, token = admin_user
        await _seed_pricing(async_db)
        resp = await client.get(
            "/api/v1/monitoring/monthly/history",
            params={"months": 3},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    async def test_daily_demand_trend_empty(self, client, admin_user, async_db):
        _, token = admin_user
        await _seed_pricing(async_db)
        resp = await client.get(
            "/api/v1/monitoring/demand/daily-trend",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []
