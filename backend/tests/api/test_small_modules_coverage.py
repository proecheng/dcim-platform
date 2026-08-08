"""
5个小模块覆盖率测试
pricing.py / vpp.py / floor_map.py / regulation.py / dispatch.py
"""

import json
import pytest

from tests.conftest import auth_headers
from app.models.floor_map import FloorMap
from app.models.energy import (
    PowerDevice,
    LoadRegulationConfig,
    DispatchableDevice,
    StorageSystemConfig,
    PVSystemConfig,
)


# ==================== Pricing Tests ====================


@pytest.mark.asyncio
class TestPricingFullConfig:
    async def test_full_config_as_viewer(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/pricing/full-config", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_full_config_no_auth(self, client):
        resp = await client.get("/api/v1/pricing/full-config")
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
class TestPricingGlobalConfig:
    async def test_get_global_config_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/pricing/global-config", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_create_global_config(self, client, admin_user):
        _, token = admin_user
        payload = {
            "config_name": "test_config",
            "billing_mode": "demand",
            "demand_price": 38.0,
            "declared_demand": 1000.0,
            "over_demand_multiplier": 2.0,
            "capacity_price": 28.0,
            "power_factor_baseline": 0.9,
            "transmission_fee": 0.1,
            "government_fund": 0.02,
            "auxiliary_fee": 0.01,
            "other_fee": 0.0,
            "effective_date": "2025-01-01",
            "description": "test",
        }
        resp = await client.post("/api/v1/pricing/global-config", json=payload, headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["message"] == "创建成功"

    async def test_create_and_update_global_config(self, client, admin_user):
        _, token = admin_user
        payload = {
            "config_name": "to_update",
            "billing_mode": "demand",
            "demand_price": 38.0,
            "effective_date": "2025-01-01",
        }
        resp = await client.post("/api/v1/pricing/global-config", json=payload, headers=auth_headers(token))
        assert resp.status_code == 200
        config_id = resp.json()["config"]["id"]
        update_resp = await client.put(
            f"/api/v1/pricing/global-config/{config_id}",
            json={"demand_price": 40.0},
            headers=auth_headers(token),
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["message"] == "更新成功"

    async def test_update_nonexistent_config(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            "/api/v1/pricing/global-config/99999", json={"demand_price": 40.0}, headers=auth_headers(token)
        )
        assert resp.status_code == 404

    async def test_create_config_no_auth(self, client):
        resp = await client.post("/api/v1/pricing/global-config", json={})
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
class TestPricingCalculateBill:
    async def test_calculate_bill(self, client, admin_user):
        _, token = admin_user
        payload = {
            "energy_by_period": {"sharp": 100, "peak": 500, "normal": 800, "valley": 300, "deep_valley": 100},
            "max_demand": 1000.0,
            "avg_power_factor": 0.9,
            "include_fixed_fees": True,
        }
        resp = await client.post("/api/v1/pricing/calculate-bill", json=payload, headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_calculate_bill_no_auth(self, client):
        resp = await client.post("/api/v1/pricing/calculate-bill", json={})
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
class TestPricingEstimateSavings:
    async def test_estimate_savings(self, client, admin_user):
        _, token = admin_user
        payload = {
            "current_energy_by_period": {"peak": 500, "valley": 300},
            "current_max_demand": 1000.0,
            "optimized_energy_by_period": {"peak": 400, "valley": 400},
            "optimized_max_demand": 900.0,
            "avg_power_factor": 0.9,
        }
        resp = await client.post("/api/v1/pricing/estimate-savings", json=payload, headers=auth_headers(token))
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestPricingTimePeriods:
    async def test_get_time_periods(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/pricing/time-periods", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_time_periods_no_auth(self, client):
        resp = await client.get("/api/v1/pricing/time-periods")
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
class TestPricingPeakValleySpread:
    async def test_get_peak_valley_spread(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/pricing/peak-valley-spread", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_peak_valley_spread_no_auth(self, client):
        resp = await client.get("/api/v1/pricing/peak-valley-spread")
        assert resp.status_code in (401, 403)


# ==================== VPP Tests ====================


@pytest.mark.asyncio
class TestVPPAnalysis:
    async def test_full_analysis(self, client):
        payload = {
            "months": ["2025-01", "2025-03"],
            "start_date": "2025-10-01",
            "end_date": "2025-10-30",
        }
        resp = await client.post("/api/v1/vpp/analysis", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0

    async def test_analysis_invalid_body(self, client):
        resp = await client.post("/api/v1/vpp/analysis", json={})
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestVPPLoadMetrics:
    async def test_load_metrics(self, client):
        resp = await client.get("/api/v1/vpp/load-metrics?start_date=2025-10-01&end_date=2025-10-30")
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    async def test_load_metrics_missing_params(self, client):
        resp = await client.get("/api/v1/vpp/load-metrics")
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestVPPCostStructure:
    async def test_cost_structure(self, client):
        resp = await client.get("/api/v1/vpp/cost-structure/2025-01")
        assert resp.status_code == 200
        assert resp.json()["code"] == 0


@pytest.mark.asyncio
class TestVPPTransferPotential:
    async def test_transfer_potential(self, client):
        resp = await client.get("/api/v1/vpp/transfer-potential")
        assert resp.status_code == 200
        assert resp.json()["code"] == 0


@pytest.mark.asyncio
class TestVPPRevenue:
    async def test_vpp_revenue(self, client):
        resp = await client.get("/api/v1/vpp/vpp-revenue?adjustable_capacity=4500.0")
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    async def test_vpp_revenue_missing_param(self, client):
        resp = await client.get("/api/v1/vpp/vpp-revenue")
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestVPPROI:
    async def test_roi(self, client):
        resp = await client.get("/api/v1/vpp/roi?annual_benefit=5000000.0")
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    async def test_roi_missing_param(self, client):
        resp = await client.get("/api/v1/vpp/roi")
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestVPPFormulaReference:
    async def test_formula_reference(self, client):
        resp = await client.get("/api/v1/vpp/formula-reference")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "data" in data


# ==================== Floor Map Tests ====================


@pytest.mark.asyncio
class TestFloorMapFloors:
    async def test_get_floors_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/floor-map/floors", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0

    async def test_get_floors_with_data(self, client, admin_user, async_db):
        _, token = admin_user
        fm = FloorMap(
            floor_code="F1",
            floor_name="1楼",
            map_type="2d",
            map_data=json.dumps({"rooms": []}),
            is_default=True,
        )
        async_db.add(fm)
        await async_db.commit()
        resp = await client.get("/api/v1/floor-map/floors", headers=auth_headers(token))
        assert resp.status_code == 200
        floors = resp.json()["data"]["floors"]
        assert len(floors) >= 1
        floor_f1 = next(floor for floor in floors if floor["floor_code"] == "F1")
        assert floor_f1["floor_name"] == "1楼"
        assert "2d" in floor_f1["map_types"]

    async def test_get_floors_no_auth(self, client):
        resp = await client.get("/api/v1/floor-map/floors")
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
class TestFloorMapDetail:
    async def test_get_floor_map_2d(self, client, admin_user, async_db):
        _, token = admin_user
        fm = FloorMap(
            floor_code="F1",
            floor_name="1楼",
            map_type="2d",
            map_data=json.dumps({"rooms": [{"id": 1}]}),
            is_default=False,
        )
        async_db.add(fm)
        await async_db.commit()
        resp = await client.get("/api/v1/floor-map/F1/2d", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["data"]["map_type"] == "2d"

    async def test_get_floor_map_3d(self, client, admin_user, async_db):
        _, token = admin_user
        fm = FloorMap(
            floor_code="F2",
            floor_name="2楼",
            map_type="3d",
            map_data=json.dumps({"model": "test"}),
            is_default=False,
        )
        async_db.add(fm)
        await async_db.commit()
        resp = await client.get("/api/v1/floor-map/F2/3d", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_get_floor_map_invalid_type(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/floor-map/F1/4d", headers=auth_headers(token))
        assert resp.status_code == 400

    async def test_get_floor_map_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/floor-map/F99/2d", headers=auth_headers(token))
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestFloorMapDefault:
    async def test_get_default_no_data(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/floor-map/default", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_get_default_with_default_flag(self, client, admin_user, async_db):
        _, token = admin_user
        fm = FloorMap(
            floor_code="F1",
            floor_name="1楼",
            map_type="3d",
            map_data=json.dumps({"model": "x"}),
            is_default=True,
        )
        async_db.add(fm)
        await async_db.commit()
        resp = await client.get("/api/v1/floor-map/default", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["data"]["is_default"] is True

    async def test_get_default_fallback_f1(self, client, admin_user, async_db):
        _, token = admin_user
        fm = FloorMap(
            floor_code="F1",
            floor_name="1楼",
            map_type="3d",
            map_data=json.dumps({"model": "y"}),
            is_default=False,
        )
        async_db.add(fm)
        await async_db.commit()
        resp = await client.get("/api/v1/floor-map/default", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["data"]["floor_code"] == "F1"

    async def test_get_default_2d(self, client, admin_user, async_db):
        _, token = admin_user
        fm = FloorMap(
            floor_code="F1",
            floor_name="1楼",
            map_type="2d",
            map_data=json.dumps({"rooms": []}),
            is_default=True,
        )
        async_db.add(fm)
        await async_db.commit()
        resp = await client.get("/api/v1/floor-map/default?map_type=2d", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_get_floors_sorting(self, client, admin_user, async_db):
        _, token = admin_user
        for code, name in [("F2", "2楼"), ("B1", "地下1层"), ("F1", "1楼")]:
            fm = FloorMap(
                floor_code=code,
                floor_name=name,
                map_type="2d",
                map_data=json.dumps({}),
                is_default=False,
            )
            async_db.add(fm)
        await async_db.commit()
        resp = await client.get("/api/v1/floor-map/floors", headers=auth_headers(token))
        assert resp.status_code == 200
        floors = resp.json()["data"]["floors"]
        codes = [f["floor_code"] for f in floors]
        assert codes[0] == "B1"


# ==================== Regulation Tests ====================


async def _create_power_device(db, code="DEV001", name="测试空调"):
    """创建测试用电设备"""
    dev = PowerDevice(
        device_code=code,
        device_name=name,
        device_type="HVAC",
        rated_power=50.0,
        is_enabled=True,
    )
    db.add(dev)
    await db.flush()
    return dev


async def _create_regulation_config(db, device_id, reg_type="temperature"):
    """创建测试调节配置"""
    cfg = LoadRegulationConfig(
        device_id=device_id,
        regulation_type=reg_type,
        min_value=22.0,
        max_value=28.0,
        current_value=25.0,
        default_value=25.0,
        step_size=1.0,
        unit="℃",
        power_factor=-0.06,
        base_power=50.0,
        priority=5,
        comfort_impact="medium",
        performance_impact="low",
        is_enabled=True,
        is_auto=False,
    )
    db.add(cfg)
    await db.flush()
    return cfg


@pytest.mark.asyncio
class TestRegulationConfigs:
    async def test_get_configs_empty(self, client):
        resp = await client.get("/api/v1/regulation/configs")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_configs_with_data(self, client, async_db):
        dev = await _create_power_device(async_db)
        await _create_regulation_config(async_db, dev.id)
        await async_db.commit()
        resp = await client.get("/api/v1/regulation/configs")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_get_configs_auto_generates_missing_adjustable_device(self, client, async_db):
        dev = await _create_power_device(async_db, "DEV004", "自动补齐空调")
        await async_db.commit()

        resp = await client.get("/api/v1/regulation/configs")

        assert resp.status_code == 200
        generated = next(item for item in resp.json() if item["device_id"] == dev.id)
        assert generated["regulation_type"] == "temperature"
        assert generated["min_value"] == 18.0
        assert generated["max_value"] == 28.0
        assert generated["current_value"] == 23.0

    async def test_get_configs_filter_device(self, client, async_db):
        dev = await _create_power_device(async_db, "DEV002", "设备2")
        await _create_regulation_config(async_db, dev.id)
        await async_db.commit()
        resp = await client.get(f"/api/v1/regulation/configs?device_id={dev.id}")
        assert resp.status_code == 200

    async def test_get_configs_filter_type(self, client, async_db):
        dev = await _create_power_device(async_db, "DEV003", "设备3")
        await _create_regulation_config(async_db, dev.id, "brightness")
        await async_db.commit()
        resp = await client.get("/api/v1/regulation/configs?regulation_type=brightness")
        assert resp.status_code == 200

    async def test_get_configs_disabled(self, client, async_db):
        resp = await client.get("/api/v1/regulation/configs?is_enabled=false")
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestRegulationConfigCRUD:
    async def test_get_config_by_id(self, client, async_db):
        dev = await _create_power_device(async_db, "DEV010", "设备10")
        cfg = await _create_regulation_config(async_db, dev.id)
        await async_db.commit()
        resp = await client.get(f"/api/v1/regulation/configs/{cfg.id}")
        assert resp.status_code == 200

    async def test_get_config_not_found(self, client):
        resp = await client.get("/api/v1/regulation/configs/99999")
        assert resp.status_code == 404

    async def test_create_config(self, client, async_db):
        dev = await _create_power_device(async_db, "DEV020", "设备20")
        await async_db.commit()
        payload = {
            "device_id": dev.id,
            "regulation_type": "temperature",
            "min_value": 22.0,
            "max_value": 28.0,
            "current_value": 25.0,
            "default_value": 25.0,
            "step_size": 1.0,
            "unit": "℃",
            "power_factor": -0.06,
            "base_power": 50.0,
            "priority": 5,
            "comfort_impact": "medium",
            "performance_impact": "low",
        }
        resp = await client.post("/api/v1/regulation/configs", json=payload)
        assert resp.status_code == 200

    async def test_update_config(self, client, async_db):
        dev = await _create_power_device(async_db, "DEV030", "设备30")
        cfg = await _create_regulation_config(async_db, dev.id)
        await async_db.commit()
        resp = await client.put(
            f"/api/v1/regulation/configs/{cfg.id}",
            json={"min_value": 20.0, "max_value": 30.0},
        )
        assert resp.status_code == 200

    async def test_update_config_not_found(self, client):
        resp = await client.put("/api/v1/regulation/configs/99999", json={"min_value": 20.0})
        assert resp.status_code == 404

    async def test_delete_config(self, client, async_db):
        dev = await _create_power_device(async_db, "DEV040", "设备40")
        cfg = await _create_regulation_config(async_db, dev.id)
        await async_db.commit()
        resp = await client.delete(f"/api/v1/regulation/configs/{cfg.id}")
        assert resp.status_code == 200
        assert resp.json()["message"] == "删除成功"

    async def test_delete_config_not_found(self, client):
        resp = await client.delete("/api/v1/regulation/configs/99999")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestRegulationSimulate:
    async def test_simulate(self, client, async_db):
        dev = await _create_power_device(async_db, "DEV050", "设备50")
        cfg = await _create_regulation_config(async_db, dev.id)
        await async_db.commit()
        resp = await client.post(
            "/api/v1/regulation/simulate",
            json={"config_id": cfg.id, "target_value": 27.0},
        )
        assert resp.status_code == 200

    async def test_simulate_not_found(self, client):
        resp = await client.post(
            "/api/v1/regulation/simulate",
            json={"config_id": 99999, "target_value": 27.0},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestRegulationApply:
    async def test_apply(self, client, async_db):
        dev = await _create_power_device(async_db, "DEV060", "设备60")
        cfg = await _create_regulation_config(async_db, dev.id)
        await async_db.commit()
        resp = await client.post(
            "/api/v1/regulation/apply",
            json={"config_id": cfg.id, "target_value": 27.0, "reason": "manual", "remark": "test"},
        )
        assert resp.status_code == 200

    async def test_apply_not_found(self, client):
        resp = await client.post(
            "/api/v1/regulation/apply",
            json={"config_id": 99999, "target_value": 27.0, "reason": "manual"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestRegulationHistory:
    async def test_get_history_empty(self, client):
        resp = await client.get("/api/v1/regulation/history")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_history_with_filters(self, client):
        resp = await client.get("/api/v1/regulation/history?device_id=1&config_id=1&limit=10")
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestRegulationRecommendations:
    async def test_recommendations_no_params(self, client):
        resp = await client.get("/api/v1/regulation/recommendations")
        assert resp.status_code == 200

    async def test_recommendations_with_params(self, client):
        resp = await client.get("/api/v1/regulation/recommendations?current_demand=1000&declared_demand=1200")
        assert resp.status_code == 200


# ==================== Dispatch Tests ====================


@pytest.mark.asyncio
class TestDispatchDevices:
    async def test_list_devices_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/dispatch/devices", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_devices_filter_type(self, client, admin_user, async_db):
        _, token = admin_user
        dev = DispatchableDevice(name="空压机", device_type="shiftable", rated_power=150, priority=3, is_active=True)
        async_db.add(dev)
        await async_db.commit()
        resp = await client.get("/api/v1/dispatch/devices?device_type=shiftable", headers=auth_headers(token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_list_devices_filter_active(self, client, admin_user, async_db):
        _, token = admin_user
        dev = DispatchableDevice(name="照明", device_type="curtailable", rated_power=50, priority=7, is_active=False)
        async_db.add(dev)
        await async_db.commit()
        resp = await client.get("/api/v1/dispatch/devices?is_active=false", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_get_device_by_id(self, client, admin_user, async_db):
        _, token = admin_user
        dev = DispatchableDevice(
            name="冷却塔",
            device_type="modulating",
            rated_power=75,
            min_power=20,
            max_power=75,
            priority=4,
            is_active=True,
        )
        async_db.add(dev)
        await async_db.commit()
        resp = await client.get(f"/api/v1/dispatch/devices/{dev.id}", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "冷却塔"

    async def test_get_device_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/dispatch/devices/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_create_device(self, client, admin_user):
        _, token = admin_user
        payload = {
            "name": "新设备",
            "device_type": "shiftable",
            "rated_power": 100,
            "run_duration": 4,
            "daily_runs": 2,
            "allowed_periods": [0, 1, 2, 3],
            "priority": 3,
            "is_active": True,
        }
        resp = await client.post("/api/v1/dispatch/devices", json=payload, headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "新设备"

    async def test_create_device_no_auth(self, client):
        resp = await client.post(
            "/api/v1/dispatch/devices", json={"name": "x", "device_type": "shiftable", "rated_power": 10}
        )
        assert resp.status_code in (401, 403)

    async def test_update_device(self, client, admin_user, async_db):
        _, token = admin_user
        dev = DispatchableDevice(name="旧名", device_type="rigid", rated_power=500, priority=1, is_active=True)
        async_db.add(dev)
        await async_db.commit()
        resp = await client.put(
            f"/api/v1/dispatch/devices/{dev.id}",
            json={"name": "新名", "rated_power": 600},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "新名"

    async def test_update_device_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put("/api/v1/dispatch/devices/99999", json={"name": "x"}, headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_delete_device(self, client, admin_user, async_db):
        _, token = admin_user
        dev = DispatchableDevice(name="删除我", device_type="rigid", rated_power=10, priority=10, is_active=True)
        async_db.add(dev)
        await async_db.commit()
        resp = await client.delete(f"/api/v1/dispatch/devices/{dev.id}", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["message"] == "删除成功"

    async def test_delete_device_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.delete("/api/v1/dispatch/devices/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_no_auth(self, client):
        resp = await client.get("/api/v1/dispatch/devices")
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
class TestDispatchDeviceStats:
    async def test_stats_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/dispatch/devices/summary/stats", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "by_type" in data

    async def test_stats_with_data(self, client, admin_user, async_db):
        _, token = admin_user
        for i, dtype in enumerate(["shiftable", "curtailable", "modulating"]):
            dev = DispatchableDevice(
                name=f"dev_{i}", device_type=dtype, rated_power=100 * (i + 1), priority=5, is_active=True
            )
            async_db.add(dev)
        async_db.add(
            DispatchableDevice(name="inactive", device_type="rigid", rated_power=50, priority=5, is_active=False)
        )
        await async_db.commit()
        resp = await client.get("/api/v1/dispatch/devices/summary/stats", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        assert data["active_count"] == 3


@pytest.mark.asyncio
class TestDispatchStorage:
    async def test_list_storage_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/dispatch/storage", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_storage_filter_active(self, client, admin_user, async_db):
        _, token = admin_user
        s = StorageSystemConfig(
            name="储能1",
            capacity=500,
            max_charge_power=125,
            max_discharge_power=125,
            charge_efficiency=0.94,
            discharge_efficiency=0.94,
            min_soc=0.1,
            max_soc=0.9,
            cycle_cost=0.08,
            is_active=True,
        )
        async_db.add(s)
        await async_db.commit()
        resp = await client.get("/api/v1/dispatch/storage?is_active=true", headers=auth_headers(token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_get_storage_by_id(self, client, admin_user, async_db):
        _, token = admin_user
        s = StorageSystemConfig(
            name="储能2",
            capacity=100,
            max_charge_power=20,
            max_discharge_power=50,
            is_active=True,
        )
        async_db.add(s)
        await async_db.commit()
        resp = await client.get(f"/api/v1/dispatch/storage/{s.id}", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_get_storage_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/dispatch/storage/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_create_storage(self, client, admin_user):
        _, token = admin_user
        payload = {
            "name": "新储能",
            "capacity": 200,
            "max_charge_power": 50,
            "max_discharge_power": 50,
            "charge_efficiency": 0.95,
            "discharge_efficiency": 0.95,
            "min_soc": 0.1,
            "max_soc": 0.9,
            "cycle_cost": 0.1,
            "is_active": True,
        }
        resp = await client.post("/api/v1/dispatch/storage", json=payload, headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_update_storage(self, client, admin_user, async_db):
        _, token = admin_user
        s = StorageSystemConfig(
            name="更新储能", capacity=300, max_charge_power=75, max_discharge_power=75, is_active=True
        )
        async_db.add(s)
        await async_db.commit()
        resp = await client.put(f"/api/v1/dispatch/storage/{s.id}", json={"capacity": 400}, headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_update_storage_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put("/api/v1/dispatch/storage/99999", json={"capacity": 400}, headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_delete_storage(self, client, admin_user, async_db):
        _, token = admin_user
        s = StorageSystemConfig(
            name="删除储能", capacity=100, max_charge_power=20, max_discharge_power=20, is_active=True
        )
        async_db.add(s)
        await async_db.commit()
        resp = await client.delete(f"/api/v1/dispatch/storage/{s.id}", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_delete_storage_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.delete("/api/v1/dispatch/storage/99999", headers=auth_headers(token))
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestDispatchPV:
    async def test_list_pv_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/dispatch/pv", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_pv_filter_active(self, client, admin_user, async_db):
        _, token = admin_user
        pv = PVSystemConfig(name="屋顶光伏", rated_capacity=300, efficiency=0.82, is_active=True)
        async_db.add(pv)
        await async_db.commit()
        resp = await client.get("/api/v1/dispatch/pv?is_active=true", headers=auth_headers(token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_get_pv_by_id(self, client, admin_user, async_db):
        _, token = admin_user
        pv = PVSystemConfig(name="车棚光伏", rated_capacity=50, efficiency=0.85, is_active=True)
        async_db.add(pv)
        await async_db.commit()
        resp = await client.get(f"/api/v1/dispatch/pv/{pv.id}", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_get_pv_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/dispatch/pv/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_create_pv(self, client, admin_user):
        _, token = admin_user
        payload = {"name": "新光伏", "rated_capacity": 100, "efficiency": 0.85, "is_active": True}
        resp = await client.post("/api/v1/dispatch/pv", json=payload, headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_update_pv(self, client, admin_user, async_db):
        _, token = admin_user
        pv = PVSystemConfig(name="更新光伏", rated_capacity=200, efficiency=0.8, is_active=True)
        async_db.add(pv)
        await async_db.commit()
        resp = await client.put(
            f"/api/v1/dispatch/pv/{pv.id}", json={"rated_capacity": 250}, headers=auth_headers(token)
        )
        assert resp.status_code == 200

    async def test_update_pv_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put("/api/v1/dispatch/pv/99999", json={"rated_capacity": 250}, headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_delete_pv(self, client, admin_user, async_db):
        _, token = admin_user
        pv = PVSystemConfig(name="删除光伏", rated_capacity=50, efficiency=0.8, is_active=True)
        async_db.add(pv)
        await async_db.commit()
        resp = await client.delete(f"/api/v1/dispatch/pv/{pv.id}", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_delete_pv_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.delete("/api/v1/dispatch/pv/99999", headers=auth_headers(token))
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestDispatchSummary:
    async def test_summary_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/dispatch/summary", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "dispatchable_devices" in data
        assert "storage_systems" in data
        assert "pv_systems" in data

    async def test_summary_with_data(self, client, admin_user, async_db):
        _, token = admin_user
        async_db.add(
            DispatchableDevice(name="dev1", device_type="shiftable", rated_power=100, priority=5, is_active=True)
        )
        async_db.add(
            StorageSystemConfig(name="st1", capacity=500, max_charge_power=125, max_discharge_power=125, is_active=True)
        )
        async_db.add(PVSystemConfig(name="pv1", rated_capacity=300, efficiency=0.82, is_active=True))
        await async_db.commit()
        resp = await client.get("/api/v1/dispatch/summary", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["dispatchable_devices"]["count"] >= 1
        assert data["storage_systems"]["count"] >= 1
        assert data["pv_systems"]["count"] >= 1


@pytest.mark.asyncio
class TestDispatchDemoData:
    async def test_init_demo_data(self, client, admin_user):
        _, token = admin_user
        resp = await client.post("/api/v1/demo/init-dispatch-data", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] is True

    async def test_init_demo_data_already_exists(self, client, admin_user, async_db):
        _, token = admin_user
        async_db.add(
            DispatchableDevice(name="existing", device_type="rigid", rated_power=10, priority=1, is_active=True)
        )
        await async_db.commit()
        resp = await client.post("/api/v1/demo/init-dispatch-data", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["created"] is False

    async def test_init_demo_data_no_auth(self, client):
        resp = await client.post("/api/v1/demo/init-dispatch-data")
        assert resp.status_code in (401, 403)

    async def test_viewer_cannot_create_device(self, client, viewer_user):
        _, token = viewer_user
        payload = {"name": "x", "device_type": "rigid", "rated_power": 10}
        resp = await client.post("/api/v1/dispatch/devices", json=payload, headers=auth_headers(token))
        assert resp.status_code == 403

    async def test_viewer_cannot_delete_storage(self, client, viewer_user):
        _, token = viewer_user
        resp = await client.delete("/api/v1/dispatch/storage/1", headers=auth_headers(token))
        assert resp.status_code in (403, 404)

    async def test_viewer_cannot_create_pv(self, client, viewer_user):
        _, token = viewer_user
        payload = {"name": "x", "rated_capacity": 10}
        resp = await client.post("/api/v1/dispatch/pv", json=payload, headers=auth_headers(token))
        assert resp.status_code == 403
