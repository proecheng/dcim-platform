"""
Energy/History/Demand/Power/Cooling API coverage tests
"""

from datetime import datetime, timedelta, date

from app.models.energy import PowerDevice
from app.models.point import Point
from app.models.device import Device
from app.models.history import PointHistory
from app.models.power import UPSDevice, BatteryGroup
from app.models.cooling import CoolingGroup
from tests.conftest import auth_headers


# ============== Seed helpers ==============


async def _seed_power_device(db, code="PD-TEST-001", name="Test Device", dtype="IT"):
    dev = PowerDevice(
        device_code=code,
        device_name=name,
        device_type=dtype,
        rated_power=100.0,
        phase_type="3P",
        is_enabled=True,
        is_it_load=(dtype == "IT"),
    )
    db.add(dev)
    await db.flush()
    return dev


async def _seed_point(db, code="PT-TEST-001", name="Test Point", ptype="AI"):
    pt = Point(point_code=code, point_name=name, point_type=ptype, device_type="TH", area_code="A1")
    db.add(pt)
    await db.flush()
    return pt


async def _seed_device(db, code="DEV-TEST-001", name="Test Dev", dtype="UPS"):
    dev = Device(device_code=code, device_name=name, device_type=dtype, area_code="A1", status="online")
    db.add(dev)
    await db.flush()
    return dev


async def _seed_history(db, point_id, count=5):
    now = datetime.now()
    records = []
    for i in range(count):
        h = PointHistory(point_id=point_id, value=20.0 + i, quality=0, recorded_at=now - timedelta(hours=i))
        records.append(h)
    db.add_all(records)
    await db.flush()
    return records


# ============== Energy API Tests ==============


class TestEnergyDevices:
    async def test_get_devices_empty(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/energy/devices", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body

    async def test_create_device(self, client, admin_user, async_db):
        _, token = admin_user
        payload = {
            "device_code": "PD-NEW-001",
            "device_name": "New Device",
            "device_type": "IT",
            "rated_power": 50.0,
            "phase_type": "3P",
        }
        resp = await client.post("/api/v1/energy/devices", json=payload, headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["data"]["device_code"] == "PD-NEW-001"

    async def test_create_device_duplicate_code(self, client, admin_user, async_db):
        _, token = admin_user
        await _seed_power_device(async_db, code="PD-DUP-001")
        payload = {"device_code": "PD-DUP-001", "device_name": "Dup", "device_type": "IT"}
        resp = await client.post("/api/v1/energy/devices", json=payload, headers=auth_headers(token))
        assert resp.status_code == 400

    async def test_get_device_detail(self, client, admin_user, async_db):
        _, token = admin_user
        dev = await _seed_power_device(async_db)
        resp = await client.get(f"/api/v1/energy/devices/{dev.id}", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_get_device_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/energy/devices/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_update_device(self, client, admin_user, async_db):
        _, token = admin_user
        dev = await _seed_power_device(async_db)
        resp = await client.put(
            f"/api/v1/energy/devices/{dev.id}",
            json={"device_name": "Updated Name"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_delete_device(self, client, admin_user, async_db):
        _, token = admin_user
        dev = await _seed_power_device(async_db)
        resp = await client.delete(f"/api/v1/energy/devices/{dev.id}", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_delete_device_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.delete("/api/v1/energy/devices/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_get_device_tree(self, client, admin_user, async_db):
        _, token = admin_user
        await _seed_power_device(async_db)
        resp = await client.get("/api/v1/energy/devices/tree", headers=auth_headers(token))
        assert resp.status_code == 200


class TestEnergyRealtime:
    async def test_get_realtime_power(self, client, admin_user, async_db):
        _, token = admin_user
        await _seed_power_device(async_db)
        resp = await client.get("/api/v1/energy/realtime", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_get_power_summary(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/energy/realtime/summary", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_get_device_realtime_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/energy/realtime/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_get_device_realtime(self, client, admin_user, async_db):
        _, token = admin_user
        dev = await _seed_power_device(async_db)
        resp = await client.get(f"/api/v1/energy/realtime/{dev.id}", headers=auth_headers(token))
        assert resp.status_code == 200


class TestEnergyPUE:
    async def test_get_current_pue(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/energy/pue", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_get_pue_trend(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/energy/pue/trend", params={"period": "day"}, headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body


class TestEnergyStatistics:
    async def test_get_daily_statistics(self, client, admin_user, async_db):
        _, token = admin_user
        today = date.today()
        resp = await client.get(
            "/api/v1/energy/statistics/daily",
            params={"start_date": str(today - timedelta(days=7)), "end_date": str(today)},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_get_monthly_statistics(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get(
            "/api/v1/energy/statistics/monthly",
            params={"year": 2026},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_get_energy_summary(self, client, admin_user, async_db):
        _, token = admin_user
        today = date.today()
        resp = await client.get(
            "/api/v1/energy/statistics/summary",
            params={"start_date": str(today - timedelta(days=7)), "end_date": str(today)},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_get_energy_trend(self, client, admin_user, async_db):
        _, token = admin_user
        today = date.today()
        resp = await client.get(
            "/api/v1/energy/statistics/trend",
            params={
                "start_date": str(today - timedelta(days=7)),
                "end_date": str(today),
                "granularity": "daily",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_get_energy_comparison(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get(
            "/api/v1/energy/statistics/comparison",
            params={"comparison_type": "mom", "period": "month"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200


# ============== History API Tests ==============


class TestHistoryAPI:
    async def test_get_point_history(self, client, admin_user, async_db):
        _, token = admin_user
        pt = await _seed_point(async_db)
        await _seed_history(async_db, pt.id)
        resp = await client.get(f"/api/v1/history/{pt.id}", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body

    async def test_get_point_history_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/history/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_get_trend_data(self, client, admin_user, async_db):
        _, token = admin_user
        pt = await _seed_point(async_db)
        await _seed_history(async_db, pt.id)
        resp = await client.get(f"/api/v1/history/{pt.id}/trend", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_get_trend_with_duration(self, client, admin_user, async_db):
        _, token = admin_user
        pt = await _seed_point(async_db)
        await _seed_history(async_db, pt.id)
        resp = await client.get(
            f"/api/v1/history/{pt.id}/trend",
            params={"duration": 60},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_get_statistics(self, client, admin_user, async_db):
        _, token = admin_user
        pt = await _seed_point(async_db)
        await _seed_history(async_db, pt.id)
        resp = await client.get(f"/api/v1/history/{pt.id}/statistics", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert "point_id" in body

    async def test_get_statistics_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/history/99999/statistics", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_get_change_log(self, client, admin_user, async_db):
        _, token = admin_user
        pt = await _seed_point(async_db, code="DI-TEST-001", name="DI Point", ptype="DI")
        resp = await client.get(f"/api/v1/history/changes/{pt.id}", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_get_change_log_non_di(self, client, admin_user, async_db):
        _, token = admin_user
        pt = await _seed_point(async_db)
        resp = await client.get(f"/api/v1/history/changes/{pt.id}", headers=auth_headers(token))
        assert resp.status_code == 400

    async def test_cleanup_history(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.delete(
            "/api/v1/history/cleanup",
            params={"days": 30},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200


# ============== Demand API Tests ==============


class TestDemandAPI:
    async def test_get_demand_comparison(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/demand/comparison", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body

    async def test_get_demand_curve_mini(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get(
            "/api/v1/demand/curve-mini",
            params={"months": 6},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["max_value"] >= 0  # 无真实数据时返回0

    async def test_get_load_period(self, client, admin_user, async_db):
        """GET /demand/load-period — 负荷时段分布"""
        _, token = admin_user
        resp = await client.get("/api/v1/demand/load-period", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_get_power_factor_trend(self, client, admin_user, async_db):
        """GET /demand/power-factor-trend — 功率因数趋势"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/demand/power-factor-trend",
            params={"days": 7},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200


# ============== Power API Tests ==============


class TestPowerOverview:
    async def test_get_power_overview(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/power/overview", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert "ups_total" in body


class TestPowerUPS:
    async def test_list_ups_empty(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/power/ups", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0

    async def test_create_ups(self, client, admin_user, async_db):
        _, token = admin_user
        dev = await _seed_device(async_db, code="UPS-DEV-001", dtype="UPS")
        payload = {"device_id": dev.id, "ups_type": "standalone", "rated_capacity": 100.0}
        resp = await client.post("/api/v1/power/ups", json=payload, headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_create_ups_no_device(self, client, admin_user, async_db):
        _, token = admin_user
        payload = {"device_id": 99999, "ups_type": "standalone"}
        resp = await client.post("/api/v1/power/ups", json=payload, headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_get_ups_detail(self, client, admin_user, async_db):
        _, token = admin_user
        dev = await _seed_device(async_db, code="UPS-DEV-002", dtype="UPS")
        ups = UPSDevice(device_id=dev.id, ups_type="standalone", rated_capacity=80.0)
        async_db.add(ups)
        await async_db.flush()
        resp = await client.get(f"/api/v1/power/ups/{ups.id}", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_get_ups_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/power/ups/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_update_ups(self, client, admin_user, async_db):
        _, token = admin_user
        dev = await _seed_device(async_db, code="UPS-DEV-003", dtype="UPS")
        ups = UPSDevice(device_id=dev.id, ups_type="standalone")
        async_db.add(ups)
        await async_db.flush()
        resp = await client.put(
            f"/api/v1/power/ups/{ups.id}",
            json={"rated_capacity": 200.0},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_delete_ups(self, client, admin_user, async_db):
        _, token = admin_user
        dev = await _seed_device(async_db, code="UPS-DEV-004", dtype="UPS")
        ups = UPSDevice(device_id=dev.id, ups_type="standalone")
        async_db.add(ups)
        await async_db.flush()
        resp = await client.delete(f"/api/v1/power/ups/{ups.id}", headers=auth_headers(token))
        assert resp.status_code == 200


class TestPowerBatteries:
    async def test_list_batteries_empty(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/power/batteries", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_create_battery(self, client, admin_user, async_db):
        _, token = admin_user
        dev = await _seed_device(async_db, code="UPS-BAT-001", dtype="UPS")
        ups = UPSDevice(device_id=dev.id, ups_type="standalone")
        async_db.add(ups)
        await async_db.flush()
        payload = {"ups_device_id": ups.id, "group_name": "BG-1", "battery_type": "lead_acid"}
        resp = await client.post("/api/v1/power/batteries", json=payload, headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_create_battery_no_ups(self, client, admin_user, async_db):
        _, token = admin_user
        payload = {"ups_device_id": 99999, "group_name": "BG-X"}
        resp = await client.post("/api/v1/power/batteries", json=payload, headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_get_battery_detail(self, client, admin_user, async_db):
        _, token = admin_user
        dev = await _seed_device(async_db, code="UPS-BAT-002", dtype="UPS")
        ups = UPSDevice(device_id=dev.id, ups_type="standalone")
        async_db.add(ups)
        await async_db.flush()
        bg = BatteryGroup(ups_device_id=ups.id, group_name="BG-2")
        async_db.add(bg)
        await async_db.flush()
        resp = await client.get(f"/api/v1/power/batteries/{bg.id}", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_get_battery_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/power/batteries/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_delete_battery(self, client, admin_user, async_db):
        _, token = admin_user
        dev = await _seed_device(async_db, code="UPS-BAT-003", dtype="UPS")
        ups = UPSDevice(device_id=dev.id, ups_type="standalone")
        async_db.add(ups)
        await async_db.flush()
        bg = BatteryGroup(ups_device_id=ups.id, group_name="BG-3")
        async_db.add(bg)
        await async_db.flush()
        resp = await client.delete(f"/api/v1/power/batteries/{bg.id}", headers=auth_headers(token))
        assert resp.status_code == 200


class TestPowerCabinetsPDUs:
    async def test_list_cabinets(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/power/cabinets", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_list_pdus(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/power/pdus", headers=auth_headers(token))
        assert resp.status_code == 200


# ============== Cooling API Tests ==============


class TestCoolingOverview:
    async def test_get_cooling_overview(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/cooling/overview", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert "ac_total" in body


class TestCoolingGroups:
    async def test_list_groups_empty(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/cooling/groups", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_create_group(self, client, admin_user, async_db):
        _, token = admin_user
        payload = {"group_name": "Group-A", "group_mode": "linked"}
        resp = await client.post("/api/v1/cooling/groups", json=payload, headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_get_group_detail(self, client, admin_user, async_db):
        _, token = admin_user
        grp = CoolingGroup(group_name="Group-B", group_mode="independent")
        async_db.add(grp)
        await async_db.flush()
        resp = await client.get(f"/api/v1/cooling/groups/{grp.id}", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_get_group_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/cooling/groups/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_update_group(self, client, admin_user, async_db):
        _, token = admin_user
        grp = CoolingGroup(group_name="Group-C", group_mode="independent")
        async_db.add(grp)
        await async_db.flush()
        resp = await client.put(
            f"/api/v1/cooling/groups/{grp.id}",
            json={"group_name": "Group-C-Updated"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_delete_group(self, client, admin_user, async_db):
        _, token = admin_user
        grp = CoolingGroup(group_name="Group-D", group_mode="independent")
        async_db.add(grp)
        await async_db.flush()
        resp = await client.delete(f"/api/v1/cooling/groups/{grp.id}", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_delete_group_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.delete("/api/v1/cooling/groups/99999", headers=auth_headers(token))
        assert resp.status_code == 404


class TestCoolingUnits:
    async def test_list_units_empty(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/cooling/units", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_create_unit(self, client, admin_user, async_db):
        _, token = admin_user
        dev = await _seed_device(async_db, code="AC-DEV-001", name="AC Unit", dtype="PRECISION_AC_INDOOR")
        payload = {"device_id": dev.id, "unit_type": "indoor", "cooling_capacity_kw": 50.0}
        resp = await client.post("/api/v1/cooling/units", json=payload, headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_create_unit_no_device(self, client, admin_user, async_db):
        _, token = admin_user
        payload = {"device_id": 99999, "unit_type": "indoor"}
        resp = await client.post("/api/v1/cooling/units", json=payload, headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_get_unit_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/cooling/units/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_delete_unit_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.delete("/api/v1/cooling/units/99999", headers=auth_headers(token))
        assert resp.status_code == 404


class TestColdAisles:
    async def test_list_cold_aisles(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/cooling/cold-aisles", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_create_cold_aisle(self, client, admin_user, async_db):
        _, token = admin_user
        dev = await _seed_device(async_db, code="CA-DEV-001", name="Cold Aisle Dev", dtype="COLD_AISLE")
        payload = {"device_id": dev.id, "aisle_code": "CA-001", "aisle_name": "Cold Aisle 1"}
        resp = await client.post("/api/v1/cooling/cold-aisles", json=payload, headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_create_cold_aisle_no_device(self, client, admin_user, async_db):
        _, token = admin_user
        payload = {"device_id": 99999, "aisle_code": "CA-X", "aisle_name": "X"}
        resp = await client.post("/api/v1/cooling/cold-aisles", json=payload, headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_get_cold_aisle_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.get("/api/v1/cooling/cold-aisles/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_delete_cold_aisle_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        resp = await client.delete("/api/v1/cooling/cold-aisles/99999", headers=auth_headers(token))
        assert resp.status_code == 404
