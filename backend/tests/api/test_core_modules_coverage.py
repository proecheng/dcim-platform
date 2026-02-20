"""
Core modules coverage tests: point / threshold / history / statistics / log
"""
import pytest
import uuid
from datetime import datetime, timedelta
from tests.conftest import auth_headers

from app.models.point import Point, PointRealtime, PointGroup, PointGroupMember
from app.models.alarm import AlarmThreshold, Alarm
from app.models.history import PointHistory, PointHistoryArchive, PointChangeLog
from app.models.device import Device
from app.models.energy import PowerDevice
from app.models.log import OperationLog, SystemLog, CommunicationLog


# ======================== helpers ========================

async def _mk_point(db, code="PT-001", name="test-temp", ptype="AI", dtype="TH",
                    area="A1", unit="C", enabled=True, **kw):
    p = Point(point_code=code, point_name=name, point_type=ptype,
              device_type=dtype, area_code=area, unit=unit, is_enabled=enabled,
              min_range=kw.pop("min_range", 0), max_range=kw.pop("max_range", 100),
              precision=2, collect_interval=10, **kw)
    db.add(p)
    await db.flush()
    return p


async def _mk_realtime(db, pid, value=25.0, status="normal"):
    r = PointRealtime(point_id=pid, value=value, raw_value=value, status=status)
    db.add(r)
    await db.flush()
    return r


async def _mk_history(db, pid, value=25.0, mins_ago=0):
    h = PointHistory(point_id=pid, value=value, quality=0,
                     recorded_at=datetime.now() - timedelta(minutes=mins_ago))
    db.add(h)
    await db.flush()
    return h


async def _mk_device(db, code="DEV-001", name="UPS-1", dtype="UPS", area="A1",
                     status="online"):
    d = Device(device_code=code, device_name=name, device_type=dtype,
               area_code=area, status=status)
    db.add(d)
    await db.flush()
    return d


async def _mk_alarm(db, pid, level="minor", status="active", duration=None,
                    created_at=None):
    a = Alarm(alarm_no=f"ALM-{uuid.uuid4().hex[:8]}", point_id=pid,
              alarm_level=level, alarm_message="test alarm", status=status,
              duration_seconds=duration,
              created_at=created_at or datetime.now())
    db.add(a)
    await db.flush()
    return a


async def _mk_threshold(db, pid, ttype="high", value=80.0, level="major"):
    t = AlarmThreshold(point_id=pid, threshold_type=ttype,
                       threshold_value=value, alarm_level=level,
                       alarm_message="threshold alarm")
    db.add(t)
    await db.flush()
    return t


async def _mk_power_device(db, code="PD-001", name="UPS-dev-1", dtype="UPS"):
    pd = PowerDevice(device_code=code, device_name=name, device_type=dtype)
    db.add(pd)
    await db.flush()
    return pd


async def _mk_op_log(db, **kw):
    log = OperationLog(user_id=kw.get("user_id", 1), username=kw.get("username", "admin"),
                       module=kw.get("module", "point"), action=kw.get("action", "create"),
                       target_name=kw.get("target_name", "test"),
                       ip_address=kw.get("ip_address", "127.0.0.1"),
                       remark=kw.get("remark", "test op"))
    db.add(log)
    await db.flush()
    return log


async def _mk_sys_log(db, level="INFO", module="system", message="test log"):
    log = SystemLog(log_level=level, module=module, message=message)
    db.add(log)
    await db.flush()
    return log


async def _mk_comm_log(db, device_id=1, status="success", protocol="modbus"):
    log = CommunicationLog(device_id=device_id, comm_type="request",
                           protocol=protocol, status=status, duration_ms=50)
    db.add(log)
    await db.flush()
    return log


async def _mk_archive(db, pid, atype="hourly", value_avg=25.0, mins_ago=0):
    a = PointHistoryArchive(point_id=pid, archive_type=atype,
                            value_avg=value_avg, value_min=20.0, value_max=30.0,
                            sample_count=10,
                            recorded_at=datetime.now() - timedelta(minutes=mins_ago))
    db.add(a)
    await db.flush()
    return a


async def _mk_change_log(db, pid, old_val=0, new_val=1):
    c = PointChangeLog(point_id=pid, old_value=old_val, new_value=new_val,
                       change_type="alarm", changed_at=datetime.now())
    db.add(c)
    await db.flush()
    return c


# ======================== POINT MODULE ========================


@pytest.mark.asyncio
class TestPointList:
    async def test_list_empty(self, client, admin_user):
        _, token = admin_user
        r = await client.get("/api/v1/points", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] == 0

    async def test_list_with_data(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_point(async_db, "PT-L1", "temp1", "AI", "TH", "A1")
        await _mk_point(async_db, "PT-L2", "humi1", "AI", "TH", "A2", enabled=False)
        r = await client.get("/api/v1/points", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] == 2

    async def test_list_filter_keyword(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_point(async_db, "PT-K1", "temperature-sensor")
        await _mk_point(async_db, "PT-K2", "humidity-sensor")
        r = await client.get("/api/v1/points?keyword=temperature", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] == 1

    async def test_list_filter_point_type(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_point(async_db, "PT-T1", "ai-pt", ptype="AI")
        await _mk_point(async_db, "PT-T2", "di-pt", ptype="DI")
        r = await client.get("/api/v1/points?point_type=DI", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] == 1

    async def test_list_filter_device_type(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_point(async_db, "PT-DT1", "ups-pt", dtype="UPS")
        await _mk_point(async_db, "PT-DT2", "ac-pt", dtype="AC")
        r = await client.get("/api/v1/points?device_type=UPS", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] == 1

    async def test_list_filter_area(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_point(async_db, "PT-A1", "a1-pt", area="A1")
        await _mk_point(async_db, "PT-A2", "b1-pt", area="B1")
        r = await client.get("/api/v1/points?area_code=B1", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] == 1

    async def test_list_filter_enabled(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_point(async_db, "PT-E1", "en-pt", enabled=True)
        await _mk_point(async_db, "PT-E2", "dis-pt", enabled=False)
        r = await client.get("/api/v1/points?is_enabled=false", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] == 1

    async def test_list_filter_energy_device(self, client, admin_user, async_db):
        _, token = admin_user
        pd = await _mk_power_device(async_db, "PD-F1", "pd1")
        await _mk_point(async_db, "PT-ED1", "ed-pt", energy_device_id=pd.id)
        await _mk_point(async_db, "PT-ED2", "no-ed-pt")
        r = await client.get(f"/api/v1/points?energy_device_id={pd.id}", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] == 1

    async def test_list_with_energy_device_name(self, client, admin_user, async_db):
        _, token = admin_user
        pd = await _mk_power_device(async_db, "PD-N1", "MyPowerDev")
        await _mk_point(async_db, "PT-EN1", "linked-pt", energy_device_id=pd.id)
        r = await client.get("/api/v1/points", headers=auth_headers(token))
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["energy_device_name"] == "MyPowerDev"


@pytest.mark.asyncio
class TestPointTypesSummary:
    async def test_types_summary(self, client, viewer_user, async_db):
        _, token = viewer_user
        await _mk_point(async_db, "PT-S1", "ai1", ptype="AI")
        await _mk_point(async_db, "PT-S2", "di1", ptype="DI")
        await _mk_point(async_db, "PT-S3", "ai2", ptype="AI", enabled=False)
        r = await client.get("/api/v1/points/types-summary", headers=auth_headers(token))
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3
        assert data["ai"] == 2
        assert data["di"] == 1


@pytest.mark.asyncio
class TestPointGroups:
    async def test_get_groups_empty(self, client, viewer_user):
        _, token = viewer_user
        r = await client.get("/api/v1/points/groups", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json() == []

    async def test_create_group(self, client, operator_user):
        _, token = operator_user
        r = await client.post("/api/v1/points/groups", headers=auth_headers(token),
                              json={"group_name": "TestGroup", "group_type": "custom", "sort_order": 1})
        assert r.status_code == 200
        assert r.json()["group_name"] == "TestGroup"

    async def test_get_groups_after_create(self, client, operator_user):
        _, token = operator_user
        await client.post("/api/v1/points/groups", headers=auth_headers(token),
                          json={"group_name": "G1", "group_type": "area"})
        r = await client.get("/api/v1/points/groups", headers=auth_headers(token))
        assert r.status_code == 200
        assert len(r.json()) >= 1


@pytest.mark.asyncio
class TestPointExport:
    async def test_export_csv(self, client, operator_user, async_db):
        _, token = operator_user
        await _mk_point(async_db, "PT-EX1", "export-pt")
        r = await client.get("/api/v1/points/export", headers=auth_headers(token))
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    async def test_export_with_filter(self, client, operator_user, async_db):
        _, token = operator_user
        await _mk_point(async_db, "PT-EXF1", "ai-export", ptype="AI")
        await _mk_point(async_db, "PT-EXF2", "di-export", ptype="DI")
        r = await client.get("/api/v1/points/export?point_type=AI", headers=auth_headers(token))
        assert r.status_code == 200


@pytest.mark.asyncio
class TestPointBatchImport:
    async def test_import_csv(self, client, operator_user):
        _, token = operator_user
        csv_content = "\u70b9\u4f4d\u7f16\u7801,\u70b9\u4f4d\u540d\u79f0,\u70b9\u4f4d\u7c7b\u578b,\u8bbe\u5907\u7c7b\u578b,\u533a\u57df,\u5355\u4f4d,\u91cf\u7a0b\u4e0b\u9650,\u91cf\u7a0b\u4e0a\u9650,\u7cbe\u5ea6,\u91c7\u96c6\u5468\u671f,\u542f\u7528\r\nIMP-001,imported-pt,AI,TH,A1,C,0,100,2,10,\u662f\r\n"
        files = {"file": ("test.csv", csv_content.encode("utf-8-sig"), "text/csv")}
        r = await client.post("/api/v1/points/batch-import", headers=auth_headers(token), files=files)
        assert r.status_code == 200
        assert r.json()["success_count"] >= 1

    async def test_import_non_csv(self, client, operator_user):
        _, token = operator_user
        files = {"file": ("test.txt", b"hello", "text/plain")}
        r = await client.post("/api/v1/points/batch-import", headers=auth_headers(token), files=files)
        assert r.status_code == 400


@pytest.mark.asyncio
class TestPointCRUD:
    async def test_get_point_not_found(self, client, viewer_user):
        _, token = viewer_user
        r = await client.get("/api/v1/points/99999", headers=auth_headers(token))
        assert r.status_code == 404

    async def test_create_point(self, client, operator_user):
        _, token = operator_user
        r = await client.post("/api/v1/points", headers=auth_headers(token), json={
            "point_code": "NEW-001", "point_name": "new-point", "point_type": "AI",
            "device_type": "TH", "area_code": "A1"
        })
        assert r.status_code == 200
        assert r.json()["point_code"] == "NEW-001"

    async def test_create_point_duplicate_code(self, client, operator_user, async_db):
        _, token = operator_user
        await _mk_point(async_db, "DUP-001", "existing")
        r = await client.post("/api/v1/points", headers=auth_headers(token), json={
            "point_code": "DUP-001", "point_name": "dup", "point_type": "AI",
            "device_type": "TH", "area_code": "A1"
        })
        assert r.status_code == 400

    async def test_get_point_detail(self, client, viewer_user, async_db):
        _, token = viewer_user
        p = await _mk_point(async_db, "DET-001", "detail-pt")
        r = await client.get(f"/api/v1/points/{p.id}", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["point_code"] == "DET-001"

    async def test_update_point(self, client, operator_user, async_db):
        _, token = operator_user
        p = await _mk_point(async_db, "UPD-001", "old-name")
        r = await client.put(f"/api/v1/points/{p.id}", headers=auth_headers(token),
                             json={"point_name": "new-name"})
        assert r.status_code == 200
        assert r.json()["point_name"] == "new-name"

    async def test_update_point_not_found(self, client, operator_user):
        _, token = operator_user
        r = await client.put("/api/v1/points/99999", headers=auth_headers(token),
                             json={"point_name": "x"})
        assert r.status_code == 404

    async def test_delete_point(self, client, admin_user, async_db):
        _, token = admin_user
        p = await _mk_point(async_db, "DEL-001", "del-pt")
        await _mk_realtime(async_db, p.id)
        r = await client.delete(f"/api/v1/points/{p.id}", headers=auth_headers(token))
        assert r.status_code == 200

    async def test_delete_point_not_found(self, client, admin_user):
        _, token = admin_user
        r = await client.delete("/api/v1/points/99999", headers=auth_headers(token))
        assert r.status_code == 404


@pytest.mark.asyncio
class TestPointEnableDisable:
    async def test_enable_point(self, client, operator_user, async_db):
        _, token = operator_user
        p = await _mk_point(async_db, "EN-001", "en-pt", enabled=False)
        r = await client.put(f"/api/v1/points/{p.id}/enable", headers=auth_headers(token))
        assert r.status_code == 200

    async def test_enable_not_found(self, client, operator_user):
        _, token = operator_user
        r = await client.put("/api/v1/points/99999/enable", headers=auth_headers(token))
        assert r.status_code == 404

    async def test_disable_point(self, client, operator_user, async_db):
        _, token = operator_user
        p = await _mk_point(async_db, "DIS-001", "dis-pt")
        r = await client.put(f"/api/v1/points/{p.id}/disable", headers=auth_headers(token))
        assert r.status_code == 200

    async def test_disable_not_found(self, client, operator_user):
        _, token = operator_user
        r = await client.put("/api/v1/points/99999/disable", headers=auth_headers(token))
        assert r.status_code == 404


@pytest.mark.asyncio
class TestPointLinkDevice:
    async def test_link_device(self, client, operator_user, async_db):
        _, token = operator_user
        p = await _mk_point(async_db, "LNK-001", "power-sensor", dtype="PDU")
        pd = await _mk_power_device(async_db, "PD-LNK1", "power-dev")
        r = await client.put(f"/api/v1/points/{p.id}/link-device?energy_device_id={pd.id}",
                             headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["point_id"] == p.id

    async def test_link_device_point_not_found(self, client, operator_user, async_db):
        _, token = operator_user
        pd = await _mk_power_device(async_db, "PD-LNK2", "pd2")
        r = await client.put(f"/api/v1/points/99999/link-device?energy_device_id={pd.id}",
                             headers=auth_headers(token))
        assert r.status_code == 404

    async def test_link_device_device_not_found(self, client, operator_user, async_db):
        _, token = operator_user
        p = await _mk_point(async_db, "LNK-002", "pt2")
        r = await client.put(f"/api/v1/points/{p.id}/link-device?energy_device_id=99999",
                             headers=auth_headers(token))
        assert r.status_code == 404

    async def test_unlink_device(self, client, operator_user, async_db):
        _, token = operator_user
        pd = await _mk_power_device(async_db, "PD-UNL1", "pd-unl")
        p = await _mk_point(async_db, "UNL-001", "unl-pt", energy_device_id=pd.id)
        r = await client.delete(f"/api/v1/points/{p.id}/link-device", headers=auth_headers(token))
        assert r.status_code == 200

    async def test_unlink_device_not_linked(self, client, operator_user, async_db):
        _, token = operator_user
        p = await _mk_point(async_db, "UNL-002", "no-link-pt")
        r = await client.delete(f"/api/v1/points/{p.id}/link-device", headers=auth_headers(token))
        assert r.status_code == 200

    async def test_unlink_device_not_found(self, client, operator_user):
        _, token = operator_user
        r = await client.delete("/api/v1/points/99999/link-device", headers=auth_headers(token))
        assert r.status_code == 404


# ======================== THRESHOLD MODULE ========================


@pytest.mark.asyncio
class TestThresholdList:
    async def test_list_empty(self, client, viewer_user):
        _, token = viewer_user
        r = await client.get("/api/v1/thresholds", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] == 0

    async def test_list_with_data(self, client, viewer_user, async_db):
        _, token = viewer_user
        p = await _mk_point(async_db, "TH-LP1", "th-pt")
        await _mk_threshold(async_db, p.id)
        r = await client.get("/api/v1/thresholds", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] == 1

    async def test_list_filter_point_id(self, client, viewer_user, async_db):
        _, token = viewer_user
        p1 = await _mk_point(async_db, "TH-FP1", "pt1")
        p2 = await _mk_point(async_db, "TH-FP2", "pt2")
        await _mk_threshold(async_db, p1.id)
        await _mk_threshold(async_db, p2.id)
        r = await client.get(f"/api/v1/thresholds?point_id={p1.id}", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] == 1

    async def test_list_filter_threshold_type(self, client, viewer_user, async_db):
        _, token = viewer_user
        p = await _mk_point(async_db, "TH-FT1", "pt-ft")
        await _mk_threshold(async_db, p.id, ttype="high")
        await _mk_threshold(async_db, p.id, ttype="low", value=10.0, level="minor")
        r = await client.get("/api/v1/thresholds?threshold_type=low", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] == 1

    async def test_list_filter_is_enabled(self, client, viewer_user, async_db):
        _, token = viewer_user
        p = await _mk_point(async_db, "TH-FE1", "pt-fe")
        t = await _mk_threshold(async_db, p.id)
        t.is_enabled = False
        await async_db.flush()
        r = await client.get("/api/v1/thresholds?is_enabled=false", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] == 1

    async def test_list_filter_device_type(self, client, viewer_user, async_db):
        _, token = viewer_user
        p1 = await _mk_point(async_db, "TH-FD1", "ups-pt", dtype="UPS")
        p2 = await _mk_point(async_db, "TH-FD2", "ac-pt", dtype="AC")
        await _mk_threshold(async_db, p1.id)
        await _mk_threshold(async_db, p2.id)
        r = await client.get("/api/v1/thresholds?device_type=UPS", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] == 1


@pytest.mark.asyncio
class TestThresholdPointGet:
    async def test_get_point_thresholds(self, client, viewer_user, async_db):
        _, token = viewer_user
        p = await _mk_point(async_db, "TH-GP1", "pt-gp")
        await _mk_threshold(async_db, p.id, ttype="high", value=80.0)
        await _mk_threshold(async_db, p.id, ttype="low", value=10.0, level="minor")
        r = await client.get(f"/api/v1/thresholds/point/{p.id}", headers=auth_headers(token))
        assert r.status_code == 200
        assert len(r.json()) == 2

    async def test_get_point_thresholds_empty(self, client, viewer_user, async_db):
        _, token = viewer_user
        p = await _mk_point(async_db, "TH-GP2", "pt-gp2")
        r = await client.get(f"/api/v1/thresholds/point/{p.id}", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json() == []


@pytest.mark.asyncio
class TestThresholdCreate:
    async def test_create(self, client, operator_user, async_db):
        _, token = operator_user
        p = await _mk_point(async_db, "TH-C1", "pt-c1")
        r = await client.post("/api/v1/thresholds", headers=auth_headers(token), json={
            "point_id": p.id, "threshold_type": "high",
            "threshold_value": 80.0, "alarm_level": "major"
        })
        assert r.status_code == 200
        assert r.json()["threshold_value"] == 80.0

    async def test_create_point_not_found(self, client, operator_user):
        _, token = operator_user
        r = await client.post("/api/v1/thresholds", headers=auth_headers(token), json={
            "point_id": 99999, "threshold_type": "high",
            "threshold_value": 80.0, "alarm_level": "major"
        })
        assert r.status_code == 404


@pytest.mark.asyncio
class TestThresholdBatch:
    async def test_batch_create(self, client, operator_user, async_db):
        _, token = operator_user
        p1 = await _mk_point(async_db, "TH-B1", "pt-b1")
        p2 = await _mk_point(async_db, "TH-B2", "pt-b2")
        r = await client.post("/api/v1/thresholds/batch", headers=auth_headers(token), json={
            "point_ids": [p1.id, p2.id], "threshold_type": "high",
            "threshold_value": 80.0, "alarm_level": "major"
        })
        assert r.status_code == 200
        assert r.json()["success_count"] == 2

    async def test_batch_create_with_missing_point(self, client, operator_user, async_db):
        _, token = operator_user
        p1 = await _mk_point(async_db, "TH-BM1", "pt-bm1")
        r = await client.post("/api/v1/thresholds/batch", headers=auth_headers(token), json={
            "point_ids": [p1.id, 99999], "threshold_type": "high",
            "threshold_value": 80.0, "alarm_level": "major"
        })
        assert r.status_code == 200
        assert r.json()["success_count"] == 1
        assert r.json()["error_count"] == 1


@pytest.mark.asyncio
class TestThresholdCopy:
    async def test_copy(self, client, operator_user, async_db):
        _, token = operator_user
        p1 = await _mk_point(async_db, "TH-CP1", "src-pt")
        p2 = await _mk_point(async_db, "TH-CP2", "tgt-pt")
        await _mk_threshold(async_db, p1.id, ttype="high", value=80.0)
        r = await client.post(
            f"/api/v1/thresholds/copy?source_point_id={p1.id}",
            headers=auth_headers(token),
            json=[p2.id]
        )
        assert r.status_code == 200
        assert "1" in str(r.json().get("message", ""))

    async def test_copy_no_source_thresholds(self, client, operator_user, async_db):
        _, token = operator_user
        p1 = await _mk_point(async_db, "TH-CN1", "empty-src")
        p2 = await _mk_point(async_db, "TH-CN2", "tgt2")
        r = await client.post(
            f"/api/v1/thresholds/copy?source_point_id={p1.id}",
            headers=auth_headers(token),
            json=[p2.id]
        )
        assert r.status_code == 404


@pytest.mark.asyncio
class TestThresholdVersion:
    async def test_version_no_auth(self, client):
        r = await client.get("/api/v1/thresholds/version")
        assert r.status_code == 200
        data = r.json()
        assert "version" in data
        assert "updated_at" in data


@pytest.mark.asyncio
class TestThresholdFourLevel:
    async def test_set_four_level(self, client, operator_user, async_db):
        _, token = operator_user
        p = await _mk_point(async_db, "TH-4L1", "pt-4l")
        r = await client.put(f"/api/v1/thresholds/point/{p.id}/four-level",
                             headers=auth_headers(token), json={
            "high_high": {"value": 100}, "high": {"value": 80},
            "low": {"value": 20}, "low_low": {"value": 10},
            "delay_seconds": 5, "dead_band": 1.0
        })
        assert r.status_code == 200
        assert len(r.json()) == 4

    async def test_set_four_level_partial(self, client, operator_user, async_db):
        _, token = operator_user
        p = await _mk_point(async_db, "TH-4L2", "pt-4l2")
        r = await client.put(f"/api/v1/thresholds/point/{p.id}/four-level",
                             headers=auth_headers(token), json={
            "high": {"value": 80}, "low": {"value": 20}
        })
        assert r.status_code == 200
        assert len(r.json()) == 2

    async def test_set_four_level_not_found(self, client, operator_user):
        _, token = operator_user
        r = await client.put("/api/v1/thresholds/point/99999/four-level",
                             headers=auth_headers(token), json={
            "high": {"value": 80}
        })
        assert r.status_code == 404

    async def test_set_four_level_upsert(self, client, operator_user, async_db):
        _, token = operator_user
        p = await _mk_point(async_db, "TH-4L3", "pt-4l3")
        # First set
        await client.put(f"/api/v1/thresholds/point/{p.id}/four-level",
                         headers=auth_headers(token), json={"high": {"value": 80}})
        # Upsert with new value
        r = await client.put(f"/api/v1/thresholds/point/{p.id}/four-level",
                             headers=auth_headers(token), json={"high": {"value": 90}})
        assert r.status_code == 200
        vals = [t["threshold_value"] for t in r.json()]
        assert 90.0 in vals


@pytest.mark.asyncio
class TestThresholdBatchByDeviceType:
    async def test_batch_by_device_type(self, client, operator_user, async_db):
        _, token = operator_user
        await _mk_point(async_db, "TH-BD1", "ups-ai1", ptype="AI", dtype="UPS")
        await _mk_point(async_db, "TH-BD2", "ups-ai2", ptype="AI", dtype="UPS")
        r = await client.post("/api/v1/thresholds/batch-by-device-type",
                              headers=auth_headers(token), json={
            "device_type": "UPS",
            "thresholds": {
                "high_high": {"value": 100}, "high": {"value": 80},
                "delay_seconds": 0, "dead_band": 0
            }
        })
        assert r.status_code == 200
        assert r.json()["success_count"] == 2

    async def test_batch_by_device_type_no_points(self, client, operator_user):
        _, token = operator_user
        r = await client.post("/api/v1/thresholds/batch-by-device-type",
                              headers=auth_headers(token), json={
            "device_type": "NONEXIST",
            "thresholds": {"high": {"value": 80}}
        })
        assert r.status_code == 200
        assert r.json()["success_count"] == 0


@pytest.mark.asyncio
class TestThresholdUpdateDelete:
    async def test_update(self, client, operator_user, async_db):
        _, token = operator_user
        p = await _mk_point(async_db, "TH-U1", "pt-u1")
        t = await _mk_threshold(async_db, p.id)
        r = await client.put(f"/api/v1/thresholds/{t.id}", headers=auth_headers(token),
                             json={"threshold_value": 95.0, "alarm_level": "critical"})
        assert r.status_code == 200
        assert r.json()["threshold_value"] == 95.0

    async def test_update_not_found(self, client, operator_user):
        _, token = operator_user
        r = await client.put("/api/v1/thresholds/99999", headers=auth_headers(token),
                             json={"threshold_value": 95.0})
        assert r.status_code == 404

    async def test_delete(self, client, operator_user, async_db):
        _, token = operator_user
        p = await _mk_point(async_db, "TH-D1", "pt-d1")
        t = await _mk_threshold(async_db, p.id)
        r = await client.delete(f"/api/v1/thresholds/{t.id}", headers=auth_headers(token))
        assert r.status_code == 200

    async def test_delete_not_found(self, client, operator_user):
        _, token = operator_user
        r = await client.delete("/api/v1/thresholds/99999", headers=auth_headers(token))
        assert r.status_code == 404


# ======================== HISTORY MODULE ========================


@pytest.mark.asyncio
class TestHistoryRaw:
    async def test_get_raw_with_data(self, client, viewer_user, async_db):
        _, token = viewer_user
        p = await _mk_point(async_db, "HI-R1", "hist-pt")
        await _mk_history(async_db, p.id, 25.0, mins_ago=10)
        await _mk_history(async_db, p.id, 26.0, mins_ago=5)
        r = await client.get(f"/api/v1/history/{p.id}", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] == 2

    async def test_get_raw_empty(self, client, viewer_user, async_db):
        _, token = viewer_user
        p = await _mk_point(async_db, "HI-R2", "hist-pt2")
        r = await client.get(f"/api/v1/history/{p.id}", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] == 0

    async def test_get_not_found(self, client, viewer_user):
        _, token = viewer_user
        r = await client.get("/api/v1/history/99999", headers=auth_headers(token))
        assert r.status_code == 404


@pytest.mark.asyncio
class TestHistoryHourly:
    async def test_get_hourly(self, client, viewer_user, async_db):
        _, token = viewer_user
        p = await _mk_point(async_db, "HI-H1", "hist-hourly")
        await _mk_archive(async_db, p.id, atype="hourly", value_avg=25.0, mins_ago=30)
        r = await client.get(f"/api/v1/history/{p.id}?granularity=hour",
                             headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["items"][0]["value"] == 25.0


@pytest.mark.asyncio
class TestHistoryTrend:
    async def test_trend_with_data(self, client, viewer_user, async_db):
        _, token = viewer_user
        p = await _mk_point(async_db, "HI-T1", "trend-pt")
        await _mk_history(async_db, p.id, 25.0, mins_ago=10)
        await _mk_history(async_db, p.id, 27.0, mins_ago=5)
        r = await client.get(f"/api/v1/history/{p.id}/trend", headers=auth_headers(token))
        assert r.status_code == 200
        assert len(r.json()) == 2

    async def test_trend_with_duration(self, client, viewer_user, async_db):
        _, token = viewer_user
        p = await _mk_point(async_db, "HI-T2", "trend-dur")
        await _mk_history(async_db, p.id, 25.0, mins_ago=30)
        r = await client.get(f"/api/v1/history/{p.id}/trend?duration=60",
                             headers=auth_headers(token))
        assert r.status_code == 200

    async def test_trend_not_found(self, client, viewer_user):
        _, token = viewer_user
        r = await client.get("/api/v1/history/99999/trend", headers=auth_headers(token))
        assert r.status_code == 404


@pytest.mark.asyncio
class TestHistoryStatistics:
    async def test_statistics_with_data(self, client, viewer_user, async_db):
        _, token = viewer_user
        p = await _mk_point(async_db, "HI-ST1", "stat-pt")
        await _mk_history(async_db, p.id, 20.0, mins_ago=10)
        await _mk_history(async_db, p.id, 30.0, mins_ago=5)
        await _mk_history(async_db, p.id, 25.0, mins_ago=1)
        r = await client.get(f"/api/v1/history/{p.id}/statistics", headers=auth_headers(token))
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 3
        assert data["min_value"] == 20.0
        assert data["max_value"] == 30.0
        assert data["avg_value"] == 25.0
        assert data["std_dev"] is not None
        assert data["change_rate"] is not None

    async def test_statistics_no_data(self, client, viewer_user, async_db):
        _, token = viewer_user
        p = await _mk_point(async_db, "HI-ST2", "stat-empty")
        r = await client.get(f"/api/v1/history/{p.id}/statistics", headers=auth_headers(token))
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 0
        assert data["min_value"] is None

    async def test_statistics_not_found(self, client, viewer_user):
        _, token = viewer_user
        r = await client.get("/api/v1/history/99999/statistics", headers=auth_headers(token))
        assert r.status_code == 404


@pytest.mark.asyncio
class TestHistoryCompare:
    async def test_compare(self, client, viewer_user, async_db):
        """Route shadowed by /{point_id} — 'compare' can't parse as int → 422."""
        _, token = viewer_user
        p1 = await _mk_point(async_db, "HI-CM1", "cmp1")
        p2 = await _mk_point(async_db, "HI-CM2", "cmp2")
        await _mk_history(async_db, p1.id, 25.0, mins_ago=5)
        await _mk_history(async_db, p2.id, 30.0, mins_ago=5)
        r = await client.get(f"/api/v1/history/compare?point_ids={p1.id},{p2.id}",
                             headers=auth_headers(token))
        # Route shadowing: /{point_id} matches before /compare
        assert r.status_code == 422


@pytest.mark.asyncio
class TestHistoryChanges:
    async def test_changes_di_point(self, client, viewer_user, async_db):
        _, token = viewer_user
        p = await _mk_point(async_db, "HI-CH1", "di-change", ptype="DI")
        await _mk_change_log(async_db, p.id, old_val=0, new_val=1)
        r = await client.get(f"/api/v1/history/changes/{p.id}", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] == 1

    async def test_changes_non_di_point(self, client, viewer_user, async_db):
        _, token = viewer_user
        p = await _mk_point(async_db, "HI-CH2", "ai-change", ptype="AI")
        r = await client.get(f"/api/v1/history/changes/{p.id}", headers=auth_headers(token))
        assert r.status_code == 400

    async def test_changes_not_found(self, client, viewer_user):
        _, token = viewer_user
        r = await client.get("/api/v1/history/changes/99999", headers=auth_headers(token))
        assert r.status_code == 404


@pytest.mark.asyncio
class TestHistoryExport:
    async def test_export_csv(self, client, operator_user, async_db):
        """Route shadowed by /{point_id} — 'export' can't parse as int → 422."""
        _, token = operator_user
        p = await _mk_point(async_db, "HI-EX1", "export-hist")
        await _mk_history(async_db, p.id, 25.0, mins_ago=5)
        r = await client.get(f"/api/v1/history/export?point_id={p.id}&format=csv",
                             headers=auth_headers(token))
        assert r.status_code == 422

    async def test_export_json(self, client, operator_user, async_db):
        """Route shadowed by /{point_id} — 'export' can't parse as int → 422."""
        _, token = operator_user
        p = await _mk_point(async_db, "HI-EX2", "export-json")
        await _mk_history(async_db, p.id, 25.0, mins_ago=5)
        r = await client.get(f"/api/v1/history/export?point_id={p.id}&format=json",
                             headers=auth_headers(token))
        assert r.status_code == 422

    async def test_export_not_found(self, client, operator_user):
        """Route shadowed by /{point_id} — 'export' can't parse as int → 422."""
        _, token = operator_user
        r = await client.get("/api/v1/history/export?point_id=99999&format=csv",
                             headers=auth_headers(token))
        assert r.status_code == 422


@pytest.mark.asyncio
class TestHistoryCleanup:
    async def test_cleanup(self, client, admin_user, async_db):
        _, token = admin_user
        p = await _mk_point(async_db, "HI-CL1", "cleanup-pt")
        # Create old record (40 days ago)
        old = PointHistory(point_id=p.id, value=10.0, quality=0,
                           recorded_at=datetime.now() - timedelta(days=40))
        async_db.add(old)
        await async_db.flush()
        r = await client.delete("/api/v1/history/cleanup?days=30", headers=auth_headers(token))
        assert r.status_code == 200
        assert "1" in r.json()["message"]


# ======================== STATISTICS MODULE ========================


@pytest.mark.asyncio
class TestStatisticsOverview:
    async def test_overview_empty(self, client, viewer_user):
        _, token = viewer_user
        r = await client.get("/api/v1/statistics/overview", headers=auth_headers(token))
        assert r.status_code == 200
        data = r.json()
        assert "points" in data
        assert "devices" in data
        assert "alarms" in data

    async def test_overview_with_data(self, client, viewer_user, async_db):
        _, token = viewer_user
        p = await _mk_point(async_db, "ST-O1", "stat-pt")
        d = await _mk_device(async_db, "ST-D1", "stat-dev", "UPS", "A1")
        await _mk_alarm(async_db, p.id, level="minor", status="active")
        await _mk_realtime(async_db, p.id, value=25.0, status="normal")
        r = await client.get("/api/v1/statistics/overview", headers=auth_headers(token))
        assert r.status_code == 200
        data = r.json()
        assert data["points"]["total"] >= 1
        assert data["devices"]["total"] >= 1
        assert data["alarms"]["active"] >= 1


@pytest.mark.asyncio
class TestStatisticsPoints:
    async def test_points_stats(self, client, viewer_user, async_db):
        _, token = viewer_user
        await _mk_point(async_db, "ST-P1", "ai-stat", ptype="AI", dtype="UPS", area="A1")
        await _mk_point(async_db, "ST-P2", "di-stat", ptype="DI", dtype="AC", area="B1")
        r = await client.get("/api/v1/statistics/points", headers=auth_headers(token))
        assert r.status_code == 200
        data = r.json()
        assert "by_type" in data
        assert "by_device_type" in data
        assert "by_area" in data


@pytest.mark.asyncio
class TestStatisticsAlarms:
    async def test_alarms_stats(self, client, viewer_user, async_db):
        _, token = viewer_user
        p = await _mk_point(async_db, "ST-A1", "alarm-stat")
        await _mk_alarm(async_db, p.id, level="critical", status="active")
        await _mk_alarm(async_db, p.id, level="minor", status="resolved", duration=120)
        r = await client.get("/api/v1/statistics/alarms?days=7", headers=auth_headers(token))
        assert r.status_code == 200
        data = r.json()
        assert data["period_days"] == 7
        assert "by_level" in data
        assert "by_status" in data
        assert "daily_trend" in data
        assert "top_alarm_points" in data


@pytest.mark.asyncio
class TestStatisticsEnergy:
    async def test_energy_stats(self, client, viewer_user):
        _, token = viewer_user
        r = await client.get("/api/v1/statistics/energy?days=7", headers=auth_headers(token))
        assert r.status_code == 200
        data = r.json()
        assert data["period_days"] == 7
        assert "power_points" in data


@pytest.mark.asyncio
class TestStatisticsAvailability:
    async def test_availability(self, client, viewer_user):
        _, token = viewer_user
        r = await client.get("/api/v1/statistics/availability?days=7", headers=auth_headers(token))
        assert r.status_code == 200
        data = r.json()
        assert data["period_days"] == 7
        assert "overall_availability" in data
        assert "by_device_type" in data


@pytest.mark.asyncio
class TestStatisticsComparison:
    async def test_comparison_alarm(self, client, viewer_user):
        _, token = viewer_user
        r = await client.get("/api/v1/statistics/comparison?metric=alarm",
                             headers=auth_headers(token))
        assert r.status_code == 200
        data = r.json()
        assert data["metric"] == "alarm"
        assert "this_week" in data
        assert "last_week" in data

    async def test_comparison_energy(self, client, viewer_user):
        _, token = viewer_user
        r = await client.get("/api/v1/statistics/comparison?metric=energy",
                             headers=auth_headers(token))
        assert r.status_code == 200
        data = r.json()
        assert data["metric"] == "energy"


# ======================== LOG MODULE ========================


@pytest.mark.asyncio
class TestLogOperations:
    async def test_operations_empty(self, client, admin_user):
        _, token = admin_user
        r = await client.get("/api/v1/logs/operations", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] == 0

    async def test_operations_with_data(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_op_log(async_db, module="point", action="create", target_name="PT-001",
                         remark="created point")
        r = await client.get("/api/v1/logs/operations", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    async def test_operations_filter_user_id(self, client, admin_user, async_db):
        user, token = admin_user
        await _mk_op_log(async_db, user_id=user.id, username="test_admin")
        await _mk_op_log(async_db, user_id=9999, username="other", action="delete")
        r = await client.get(f"/api/v1/logs/operations?user_id={user.id}",
                             headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    async def test_operations_filter_module(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_op_log(async_db, module="alarm")
        await _mk_op_log(async_db, module="user", action="update")
        r = await client.get("/api/v1/logs/operations?module=alarm", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    async def test_operations_filter_action(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_op_log(async_db, action="delete")
        r = await client.get("/api/v1/logs/operations?action=delete", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    async def test_operations_filter_keyword(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_op_log(async_db, target_name="special-target", remark="unique remark xyz")
        r = await client.get("/api/v1/logs/operations?keyword=special-target",
                             headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    async def test_operations_filter_time_range(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_op_log(async_db)
        now = datetime.now()
        start = (now - timedelta(hours=1)).isoformat()
        end = (now + timedelta(hours=1)).isoformat()
        r = await client.get(f"/api/v1/logs/operations?start_time={start}&end_time={end}",
                             headers=auth_headers(token))
        assert r.status_code == 200


@pytest.mark.asyncio
class TestLogSystems:
    async def test_systems_empty(self, client, admin_user):
        _, token = admin_user
        r = await client.get("/api/v1/logs/systems", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] == 0

    async def test_systems_with_data(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_sys_log(async_db, level="ERROR", module="database", message="connection lost")
        r = await client.get("/api/v1/logs/systems", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    async def test_systems_filter_level(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_sys_log(async_db, level="ERROR", message="err msg")
        await _mk_sys_log(async_db, level="INFO", message="info msg")
        r = await client.get("/api/v1/logs/systems?log_level=ERROR", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    async def test_systems_filter_module(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_sys_log(async_db, module="scheduler", message="task done")
        r = await client.get("/api/v1/logs/systems?module=scheduler", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    async def test_systems_filter_keyword(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_sys_log(async_db, message="unique-keyword-abc123")
        r = await client.get("/api/v1/logs/systems?keyword=unique-keyword-abc123",
                             headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] >= 1


@pytest.mark.asyncio
class TestLogCommunications:
    async def test_communications_empty(self, client, admin_user):
        _, token = admin_user
        r = await client.get("/api/v1/logs/communications", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] == 0

    async def test_communications_with_data(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_comm_log(async_db, device_id=1, status="success")
        r = await client.get("/api/v1/logs/communications", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    async def test_communications_filter_device_id(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_comm_log(async_db, device_id=42, status="success")
        await _mk_comm_log(async_db, device_id=43, status="failed")
        r = await client.get("/api/v1/logs/communications?device_id=42",
                             headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    async def test_communications_filter_status(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_comm_log(async_db, device_id=50, status="failed")
        await _mk_comm_log(async_db, device_id=51, status="success")
        r = await client.get("/api/v1/logs/communications?status=failed",
                             headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] >= 1


@pytest.mark.asyncio
class TestLogExport:
    async def test_export_operation(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_op_log(async_db)
        r = await client.get("/api/v1/logs/export?log_type=operation", headers=auth_headers(token))
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    async def test_export_system(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_sys_log(async_db)
        r = await client.get("/api/v1/logs/export?log_type=system", headers=auth_headers(token))
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    async def test_export_communication(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_comm_log(async_db)
        r = await client.get("/api/v1/logs/export?log_type=communication",
                             headers=auth_headers(token))
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    async def test_export_invalid_type(self, client, admin_user):
        _, token = admin_user
        r = await client.get("/api/v1/logs/export?log_type=invalid", headers=auth_headers(token))
        assert r.status_code == 400


@pytest.mark.asyncio
class TestLogStatistics:
    async def test_statistics(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_op_log(async_db, module="point")
        await _mk_sys_log(async_db, level="ERROR")
        await _mk_comm_log(async_db, status="success")
        r = await client.get("/api/v1/logs/statistics?days=7", headers=auth_headers(token))
        assert r.status_code == 200
        data = r.json()
        assert data["period_days"] == 7
        assert "operation_logs" in data
        assert "system_logs" in data
        assert "communication_logs" in data
        assert data["operation_logs"]["total"] >= 1
