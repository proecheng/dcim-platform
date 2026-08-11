"""
空间/拓扑/联动模块覆盖率测试
spatial.py / topology_config.py / linkage.py
"""

import pytest
import uuid
from datetime import datetime
from tests.conftest import auth_headers

from app.models.spatial import Site, Floor, Room, Row, LayoutTemplate
from app.models.asset import Cabinet
from app.models.device import Device
from app.models.topology_config import (
    PowerPhaseMapping,
    CoolingZone,
)
from app.models.cooling import CoolingUnit
from app.models.linkage import (
    LinkagePolicy,
    LinkageExecution,
    LinkageLog,
    LinkageRecovery,
)


# ======================== helpers ========================


async def _mk_site(db, code="SITE-001", name="测试站点"):
    s = Site(site_code=code, site_name=name, status="active")
    db.add(s)
    await db.flush()
    return s


async def _mk_floor(db, site_id, code="F1", name="一楼"):
    f = Floor(floor_code=code, floor_name=name, site_id=site_id, sort_order=1)
    db.add(f)
    await db.flush()
    return f


async def _mk_room(db, floor_id, code="R1", name="机房A", grid_cols=20, grid_rows=20):
    r = Room(room_code=code, room_name=name, floor_id=floor_id, grid_cols=grid_cols, grid_rows=grid_rows)
    db.add(r)
    await db.flush()
    return r


async def _mk_row(db, room_id, code="ROW-1", name="第一排", aisle_type="cold"):
    r = Row(row_code=code, row_name=name, room_id=room_id, aisle_type=aisle_type, sort_order=1)
    db.add(r)
    await db.flush()
    return r


async def _mk_cabinet(db, code="CAB-001", name="机柜001", row_id=None, total_u=42):
    c = Cabinet(cabinet_code=code, cabinet_name=name, row_id=row_id, total_u=total_u)
    db.add(c)
    await db.flush()
    return c


async def _mk_device(db, code="DEV-PDU-001", name="PDU-1", dtype="PDU", status="online"):
    d = Device(device_code=code, device_name=name, device_type=dtype, area_code="A1", status=status)
    db.add(d)
    await db.flush()
    return d


async def _mk_cooling_unit(db, device_code="AC-001", device_name="空调1", capacity=50.0):
    cu = CoolingUnit(device_code=device_code, device_name=device_name, cooling_capacity_kw=capacity)
    db.add(cu)
    await db.flush()
    return cu


async def _mk_policy(db, name="测试策略", trigger_type="alarm_critical", enabled=True, is_system=False):
    p = LinkagePolicy(
        name=name,
        description="测试联动策略",
        trigger_type=trigger_type,
        trigger_condition={"level": "critical"},
        priority="normal",
        is_enabled=enabled,
        is_system=is_system,
    )
    db.add(p)
    await db.flush()
    return p


async def _mk_execution(db, policy_id, status="completed"):
    e = LinkageExecution(
        policy_id=policy_id,
        event_id=f"EVT-{uuid.uuid4().hex[:8]}",
        trigger_source="test",
        trigger_event={"test": True},
        status=status,
        started_at=datetime.now(),
        completed_at=datetime.now(),
        total_duration_ms=100,
    )
    db.add(e)
    await db.flush()
    return e


async def _mk_execution_with_log(db, policy_id, status="completed"):
    e = await _mk_execution(db, policy_id, status)
    log = LinkageLog(
        execution_id=e.id,
        action_type="ALARM_NOTIFY",
        action_config={"message": "test"},
        status="completed",
        started_at=datetime.now(),
        completed_at=datetime.now(),
        duration_ms=50,
    )
    db.add(log)
    await db.flush()
    return e, log


# ======================== Spatial Module ========================


@pytest.mark.asyncio
class TestSpatialSites:
    """站点 CRUD 测试"""

    async def test_list_sites_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/spatial/sites", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_sites_no_auth(self, client):
        resp = await client.get("/api/v1/spatial/sites")
        assert resp.status_code in (401, 403)

    async def test_create_site(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            "/api/v1/spatial/sites",
            json={"site_code": "S001", "site_name": "测试站点A", "address": "北京"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["site_code"] == "S001"
        assert data["site_name"] == "测试站点A"
        assert data["gateway_count"] == 0
        assert data["device_count"] == 0

    async def test_create_and_list_sites(self, client, admin_user):
        _, token = admin_user
        await client.post(
            "/api/v1/spatial/sites",
            json={"site_code": "S002", "site_name": "站点B"},
            headers=auth_headers(token),
        )
        resp = await client.get("/api/v1/spatial/sites", headers=auth_headers(token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_create_site_viewer_forbidden(self, client, viewer_user):
        _, token = viewer_user
        resp = await client.post(
            "/api/v1/spatial/sites",
            json={"site_code": "S003", "site_name": "站点C"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 403

    async def test_update_site(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SUPD", "原名称")
        resp = await client.put(
            f"/api/v1/spatial/sites/{site.id}",
            json={"site_name": "新名称"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["site_name"] == "新名称"

    async def test_update_site_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            "/api/v1/spatial/sites/99999",
            json={"site_name": "不存在"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_delete_site(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SDEL", "待删")
        resp = await client.delete(f"/api/v1/spatial/sites/{site.id}", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_delete_site_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.delete("/api/v1/spatial/sites/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_delete_site_with_floors_blocked(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SDEP", "有楼层")
        await _mk_floor(async_db, site.id)
        resp = await client.delete(f"/api/v1/spatial/sites/{site.id}", headers=auth_headers(token))
        assert resp.status_code == 400

    async def test_update_site_status(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SSTAT", "状态站点")
        resp = await client.put(
            f"/api/v1/spatial/sites/{site.id}/status?status=maintenance",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_update_site_status_invalid(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SINV", "无效状态")
        resp = await client.put(
            f"/api/v1/spatial/sites/{site.id}/status?status=bogus",
            headers=auth_headers(token),
        )
        assert resp.status_code == 400

    async def test_update_site_status_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            "/api/v1/spatial/sites/99999/status?status=active",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_get_sites_summary(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/spatial/sites/summary", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "total_sites" in data
        assert "sites" in data

    async def test_get_site_acl_rules(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SACL", "ACL站点")
        resp = await client.get(
            f"/api/v1/spatial/sites/{site.id}/acl-rules",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_sites_with_keyword(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_site(async_db, "KW001", "关键词站点")
        resp = await client.get(
            "/api/v1/spatial/sites?keyword=关键词",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_list_sites_with_status_filter(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_site(async_db, "SFILT", "过滤站点")
        resp = await client.get(
            "/api/v1/spatial/sites?status=active",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestSpatialFloors:
    """楼层 CRUD 测试"""

    async def test_list_floors_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/spatial/floors", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_floor(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SF01", "楼层站点")
        resp = await client.post(
            "/api/v1/spatial/floors",
            json={"floor_code": "F1", "floor_name": "一楼", "site_id": site.id},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["floor_code"] == "F1"

    async def test_create_floor_viewer_forbidden(self, client, viewer_user, async_db):
        _, token = viewer_user
        resp = await client.post(
            "/api/v1/spatial/floors",
            json={"floor_code": "F1", "floor_name": "一楼", "site_id": 1},
            headers=auth_headers(token),
        )
        assert resp.status_code == 403

    async def test_update_floor(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SF02", "更新楼层站点")
        floor = await _mk_floor(async_db, site.id, "FU1", "旧楼层")
        resp = await client.put(
            f"/api/v1/spatial/floors/{floor.id}",
            json={"floor_name": "新楼层名"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["floor_name"] == "新楼层名"

    async def test_update_floor_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            "/api/v1/spatial/floors/99999",
            json={"floor_name": "不存在"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_delete_floor(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SF03", "删除楼层站点")
        floor = await _mk_floor(async_db, site.id, "FD1", "待删楼层")
        resp = await client.delete(f"/api/v1/spatial/floors/{floor.id}", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_delete_floor_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.delete("/api/v1/spatial/floors/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_delete_floor_with_rooms_blocked(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SF04", "有房间楼层")
        floor = await _mk_floor(async_db, site.id, "FDR", "有房间")
        await _mk_room(async_db, floor.id)
        resp = await client.delete(f"/api/v1/spatial/floors/{floor.id}", headers=auth_headers(token))
        assert resp.status_code == 400

    async def test_list_floors_by_site(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SF05", "按站点过滤")
        await _mk_floor(async_db, site.id, "FFS", "过滤楼层")
        resp = await client.get(
            f"/api/v1/spatial/floors?site_id={site.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


@pytest.mark.asyncio
class TestSpatialRooms:
    """房间 CRUD 测试"""

    async def test_list_rooms_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/spatial/rooms", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_create_room(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SR01", "房间站点")
        floor = await _mk_floor(async_db, site.id, "FR1", "楼层")
        resp = await client.post(
            "/api/v1/spatial/rooms",
            json={
                "room_code": "RM01",
                "room_name": "机房A",
                "floor_id": floor.id,
                "grid_cols": 10,
                "grid_rows": 10,
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["room_code"] == "RM01"

    async def test_create_room_grid_too_large(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SR02", "大网格")
        floor = await _mk_floor(async_db, site.id, "FR2", "楼层")
        resp = await client.post(
            "/api/v1/spatial/rooms",
            json={
                "room_code": "RM02",
                "room_name": "大网格房间",
                "floor_id": floor.id,
                "grid_cols": 51,
                "grid_rows": 10,
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 400

    async def test_update_room(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SR03", "更新房间站点")
        floor = await _mk_floor(async_db, site.id, "FR3", "楼层")
        room = await _mk_room(async_db, floor.id, "RU1", "旧房间")
        resp = await client.put(
            f"/api/v1/spatial/rooms/{room.id}",
            json={"room_name": "新房间名"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["room_name"] == "新房间名"

    async def test_update_room_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            "/api/v1/spatial/rooms/99999",
            json={"room_name": "不存在"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_update_room_grid_too_large(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SR04", "更新网格")
        floor = await _mk_floor(async_db, site.id, "FR4", "楼层")
        room = await _mk_room(async_db, floor.id, "RG1", "网格房间")
        resp = await client.put(
            f"/api/v1/spatial/rooms/{room.id}",
            json={"grid_cols": 51},
            headers=auth_headers(token),
        )
        assert resp.status_code == 400

    async def test_delete_room(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SR05", "删除房间")
        floor = await _mk_floor(async_db, site.id, "FR5", "楼层")
        room = await _mk_room(async_db, floor.id, "RD1", "待删")
        resp = await client.delete(f"/api/v1/spatial/rooms/{room.id}", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_delete_room_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.delete("/api/v1/spatial/rooms/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_delete_room_with_rows_blocked(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SR06", "有行房间")
        floor = await _mk_floor(async_db, site.id, "FR6", "楼层")
        room = await _mk_room(async_db, floor.id, "RDR", "有行")
        await _mk_row(async_db, room.id)
        resp = await client.delete(f"/api/v1/spatial/rooms/{room.id}", headers=auth_headers(token))
        assert resp.status_code == 400

    async def test_list_rooms_by_floor(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SR07", "按楼层过滤")
        floor = await _mk_floor(async_db, site.id, "FR7", "楼层")
        await _mk_room(async_db, floor.id, "RFL", "过滤房间")
        resp = await client.get(
            f"/api/v1/spatial/rooms?floor_id={floor.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


@pytest.mark.asyncio
class TestSpatialRows:
    """行 CRUD 测试"""

    async def test_list_rows_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/spatial/rows", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_create_row(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SW01", "行站点")
        floor = await _mk_floor(async_db, site.id, "FW1", "楼层")
        room = await _mk_room(async_db, floor.id, "RW1", "房间")
        resp = await client.post(
            "/api/v1/spatial/rows",
            json={
                "row_code": "ROW-01",
                "row_name": "第一排",
                "room_id": room.id,
                "aisle_type": "cold",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["row_code"] == "ROW-01"

    async def test_update_row(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SW02", "更新行站点")
        floor = await _mk_floor(async_db, site.id, "FW2", "楼层")
        room = await _mk_room(async_db, floor.id, "RW2", "房间")
        row = await _mk_row(async_db, room.id, "RU01", "旧行")
        resp = await client.put(
            f"/api/v1/spatial/rows/{row.id}",
            json={"row_name": "新行名"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["row_name"] == "新行名"

    async def test_update_row_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            "/api/v1/spatial/rows/99999",
            json={"row_name": "不存在"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_delete_row(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SW03", "删除行站点")
        floor = await _mk_floor(async_db, site.id, "FW3", "楼层")
        room = await _mk_room(async_db, floor.id, "RW3", "房间")
        row = await _mk_row(async_db, room.id, "RD01", "待删")
        resp = await client.delete(f"/api/v1/spatial/rows/{row.id}", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_delete_row_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.delete("/api/v1/spatial/rows/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_delete_row_with_cabinets_blocked(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SW04", "有机柜行")
        floor = await _mk_floor(async_db, site.id, "FW4", "楼层")
        room = await _mk_room(async_db, floor.id, "RW4", "房间")
        row = await _mk_row(async_db, room.id, "RDC", "有机柜")
        await _mk_cabinet(async_db, "CAB-BLK", "阻塞机柜", row_id=row.id)
        resp = await client.delete(f"/api/v1/spatial/rows/{row.id}", headers=auth_headers(token))
        assert resp.status_code == 400

    async def test_list_rows_by_room(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SW05", "按房间过滤")
        floor = await _mk_floor(async_db, site.id, "FW5", "楼层")
        room = await _mk_room(async_db, floor.id, "RW5", "房间")
        await _mk_row(async_db, room.id, "RFL01", "过滤行")
        resp = await client.get(
            f"/api/v1/spatial/rows?room_id={room.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


@pytest.mark.asyncio
class TestSpatialTree:
    """空间树 测试"""

    async def test_get_spatial_tree_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/spatial/tree", headers=auth_headers(token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_get_spatial_tree_with_data(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "STREE", "树站点")
        floor = await _mk_floor(async_db, site.id, "FT", "楼层")
        room = await _mk_room(async_db, floor.id, "RT", "房间")
        await _mk_row(async_db, room.id, "RWT", "行")
        resp = await client.get("/api/v1/spatial/tree", headers=auth_headers(token))
        assert resp.status_code == 200
        tree = resp.json()
        assert len(tree) >= 1

    async def test_tree_no_auth(self, client):
        resp = await client.get("/api/v1/spatial/tree")
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
class TestSpatialCabinetPosition:
    """机柜位置更新测试"""

    async def test_update_cabinet_position(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "SCP01", "位置站点")
        floor = await _mk_floor(async_db, site.id, "FCP", "楼层")
        room = await _mk_room(async_db, floor.id, "RCP", "房间", grid_cols=20, grid_rows=20)
        row = await _mk_row(async_db, room.id, "RWCP", "行")
        cab = await _mk_cabinet(async_db, "CAB-POS", "定位机柜", row_id=row.id)
        resp = await client.put(
            f"/api/v1/spatial/cabinets/{cab.id}/position",
            json={"grid_x": 5, "grid_y": 3},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_update_cabinet_position_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            "/api/v1/spatial/cabinets/99999/position",
            json={"grid_x": 0, "grid_y": 0},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestSpatialExport:
    """导出测试"""

    async def test_export_spatial(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/spatial/export", headers=auth_headers(token))
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
class TestSpatialTemplates:
    """布局模板测试"""

    async def test_list_templates(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/spatial/templates", headers=auth_headers(token))
        assert resp.status_code == 200
        templates = resp.json()
        assert isinstance(templates, list)

    async def test_apply_template_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            "/api/v1/spatial/templates/99999/apply",
            json={"room_id": 1},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_apply_template_room_not_found(self, client, admin_user, async_db):
        _, token = admin_user
        tpl = LayoutTemplate(
            template_code="test_tpl",
            template_name="测试模板",
            template_data='{"rows":[{"row_code":"R1","cabinets":2}]}',
        )
        async_db.add(tpl)
        await async_db.flush()
        resp = await client.post(
            f"/api/v1/spatial/templates/{tpl.id}/apply",
            json={"room_id": 99999},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_apply_template_success(self, client, admin_user, async_db):
        _, token = admin_user
        site = await _mk_site(async_db, "STPL", "模板站点")
        floor = await _mk_floor(async_db, site.id, "FTPL", "楼层")
        room = await _mk_room(async_db, floor.id, "RTPL", "房间")
        tpl = LayoutTemplate(
            template_code="apply_tpl",
            template_name="应用模板",
            template_data='{"rows":[{"row_code":"R1","aisle_type":"cold","cabinets":2}]}',
        )
        async_db.add(tpl)
        await async_db.flush()
        resp = await client.post(
            f"/api/v1/spatial/templates/{tpl.id}/apply",
            json={"room_id": room.id, "cabinet_prefix": "TPL"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["created_rows"] >= 0
        assert data["created_cabinets"] >= 0


# ======================== Topology Config Module ========================


@pytest.mark.asyncio
class TestPowerPhaseMapping:
    """三相接线映射测试"""

    async def test_list_power_phase_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/topology-config/power-phase", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_power_phase_no_auth(self, client):
        resp = await client.get("/api/v1/topology-config/power-phase")
        assert resp.status_code in (401, 403)

    async def test_create_power_phase_mapping(self, client, admin_user, async_db):
        _, token = admin_user
        cab = await _mk_cabinet(async_db, "CAB-PP01", "配电机柜")
        dev = await _mk_device(async_db, "PDU-PP01", "PDU设备")
        resp = await client.post(
            "/api/v1/topology-config/power-phase",
            json={
                "cabinet_id": cab.id,
                "pdu_device_id": dev.id,
                "phase": "A",
                "feed_type": "primary",
                "rated_current": 32.0,
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "A"
        assert data["feed_type"] == "primary"

    async def test_create_and_list_power_phase(self, client, admin_user, async_db):
        _, token = admin_user
        cab = await _mk_cabinet(async_db, "CAB-PP02", "配电机柜2")
        dev = await _mk_device(async_db, "PDU-PP02", "PDU设备2")
        await client.post(
            "/api/v1/topology-config/power-phase",
            json={
                "cabinet_id": cab.id,
                "pdu_device_id": dev.id,
                "phase": "B",
                "feed_type": "backup",
            },
            headers=auth_headers(token),
        )
        resp = await client.get("/api/v1/topology-config/power-phase", headers=auth_headers(token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_get_cabinet_power_phase(self, client, admin_user, async_db):
        _, token = admin_user
        cab = await _mk_cabinet(async_db, "CAB-PP03", "机柜3")
        dev = await _mk_device(async_db, "PDU-PP03", "PDU3")
        mapping = PowerPhaseMapping(
            cabinet_id=cab.id, pdu_device_id=dev.id, phase="C", feed_type="primary"
        )
        async_db.add(mapping)
        await async_db.flush()
        resp = await client.get(
            f"/api/v1/topology-config/power-phase/cabinet/{cab.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_get_cabinet_power_phase_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(
            "/api/v1/topology-config/power-phase/cabinet/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_update_power_phase_mapping(self, client, admin_user, async_db):
        _, token = admin_user
        cab = await _mk_cabinet(async_db, "CAB-PP04", "机柜4")
        dev = await _mk_device(async_db, "PDU-PP04", "PDU4")
        mapping = PowerPhaseMapping(
            cabinet_id=cab.id, pdu_device_id=dev.id, phase="A", feed_type="primary"
        )
        async_db.add(mapping)
        await async_db.flush()
        resp = await client.put(
            f"/api/v1/topology-config/power-phase/{mapping.id}",
            json={"phase": "B", "rated_current": 16.0},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_update_power_phase_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            "/api/v1/topology-config/power-phase/99999",
            json={"phase": "C"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_delete_power_phase_mapping(self, client, admin_user, async_db):
        _, token = admin_user
        cab = await _mk_cabinet(async_db, "CAB-PP05", "机柜5")
        dev = await _mk_device(async_db, "PDU-PP05", "PDU5")
        mapping = PowerPhaseMapping(
            cabinet_id=cab.id, pdu_device_id=dev.id, phase="A", feed_type="primary"
        )
        async_db.add(mapping)
        await async_db.flush()
        resp = await client.delete(
            f"/api/v1/topology-config/power-phase/{mapping.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_delete_power_phase_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.delete(
            "/api/v1/topology-config/power-phase/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_get_phase_balance(self, client, admin_user, async_db):
        _, token = admin_user
        dev = await _mk_device(async_db, "PDU-BAL", "PDU-平衡")
        resp = await client.get(
            f"/api/v1/topology-config/power-phase/pdu/{dev.id}/balance",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "pdu_device_id" in data

    async def test_list_power_phase_filter_by_pdu(self, client, admin_user, async_db):
        _, token = admin_user
        dev = await _mk_device(async_db, "PDU-FLT", "PDU过滤")
        resp = await client.get(
            f"/api/v1/topology-config/power-phase?pdu_device_id={dev.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestCoolingZones:
    """制冷区域测试"""

    async def test_list_cooling_zones_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/topology-config/cooling-zones", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_cooling_zone(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            "/api/v1/topology-config/cooling-zones",
            json={
                "zone_name": "制冷区域A",
                "design_capacity_kw": 100.0,
                "description": "测试制冷区域",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["zone_name"] == "制冷区域A"

    async def test_create_cooling_zone_with_cabinets(self, client, admin_user, async_db):
        _, token = admin_user
        cab = await _mk_cabinet(async_db, "CAB-CZ01", "制冷机柜")
        resp = await client.post(
            "/api/v1/topology-config/cooling-zones",
            json={
                "zone_name": "制冷区域B",
                "cabinet_ids": [cab.id],
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_create_cooling_zone_viewer_forbidden(self, client, viewer_user):
        _, token = viewer_user
        resp = await client.post(
            "/api/v1/topology-config/cooling-zones",
            json={"zone_name": "禁止区域"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 403

    async def test_get_cooling_zone_detail(self, client, admin_user, async_db):
        _, token = admin_user
        zone = CoolingZone(
            zone_code=f"CZ-{uuid.uuid4().hex[:6]}",
            zone_name="详情区域",
            design_capacity_kw=50.0,
        )
        async_db.add(zone)
        await async_db.flush()
        resp = await client.get(
            f"/api/v1/topology-config/cooling-zones/{zone.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["zone_name"] == "详情区域"

    async def test_get_cooling_zone_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(
            "/api/v1/topology-config/cooling-zones/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_update_cooling_zone(self, client, admin_user, async_db):
        _, token = admin_user
        zone = CoolingZone(
            zone_code=f"CZ-UPD-{uuid.uuid4().hex[:4]}",
            zone_name="待更新区域",
        )
        async_db.add(zone)
        await async_db.flush()
        resp = await client.put(
            f"/api/v1/topology-config/cooling-zones/{zone.id}",
            json={"zone_name": "已更新区域", "design_capacity_kw": 80.0},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_update_cooling_zone_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            "/api/v1/topology-config/cooling-zones/99999",
            json={"zone_name": "不存在"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_delete_cooling_zone(self, client, admin_user, async_db):
        _, token = admin_user
        zone = CoolingZone(
            zone_code=f"CZ-DEL-{uuid.uuid4().hex[:4]}",
            zone_name="待删区域",
        )
        async_db.add(zone)
        await async_db.flush()
        resp = await client.delete(
            f"/api/v1/topology-config/cooling-zones/{zone.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_delete_cooling_zone_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.delete(
            "/api/v1/topology-config/cooling-zones/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_get_cooling_zone_capacity(self, client, admin_user, async_db):
        _, token = admin_user
        zone = CoolingZone(
            zone_code=f"CZ-CAP-{uuid.uuid4().hex[:4]}",
            zone_name="容量区域",
            design_capacity_kw=100.0,
        )
        async_db.add(zone)
        await async_db.flush()
        resp = await client.get(
            f"/api/v1/topology-config/cooling-zones/{zone.id}/capacity",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "zone_id" in data

    async def test_get_cooling_zone_capacity_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(
            "/api/v1/topology-config/cooling-zones/99999/capacity",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestTopologySummary:
    """机柜拓扑汇总与智能选址/故障分析测试"""

    async def test_cabinet_topology_summary(self, client, admin_user, async_db):
        _, token = admin_user
        cab = await _mk_cabinet(async_db, "CAB-TOPO", "拓扑机柜")
        resp = await client.get(
            f"/api/v1/topology-config/cabinet/{cab.id}/topology-summary",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["cabinet_id"] == cab.id

    async def test_cabinet_topology_summary_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(
            "/api/v1/topology-config/cabinet/99999/topology-summary",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_smart_site_selection(self, client, admin_user, async_db):
        _, token = admin_user
        # 创建一些机柜数据
        site = await _mk_site(async_db, "SSS01", "选址站点")
        floor = await _mk_floor(async_db, site.id, "FSS", "楼层")
        room = await _mk_room(async_db, floor.id, "RSS", "房间")
        row = await _mk_row(async_db, room.id, "RWSS", "行")
        await _mk_cabinet(async_db, "CAB-SS01", "选址机柜", row_id=row.id)
        resp = await client.post(
            "/api/v1/topology-config/smart-site-selection",
            json={"required_u": 10, "limit": 5},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "candidates" in data
        assert "total_evaluated" in data

    async def test_fault_impact_analysis(self, client, admin_user, async_db):
        _, token = admin_user
        dev = await _mk_device(async_db, "PDU-FIA", "故障PDU")
        resp = await client.post(
            "/api/v1/topology-config/fault-impact-analysis",
            json={"fault_source_type": "pdu", "fault_source_id": dev.id},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "fault_source_type" in data
        assert "affected_cabinets" in data

    async def test_fault_impact_analysis_no_auth(self, client):
        resp = await client.post(
            "/api/v1/topology-config/fault-impact-analysis",
            json={"fault_source_type": "pdu", "fault_source_id": 1},
        )
        assert resp.status_code in (401, 403)


# ======================== Linkage Module ========================


@pytest.mark.asyncio
class TestLinkageFireProtection:
    """消防策略测试"""

    async def test_fire_protection_status(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/linkage/fire-protection/status", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_fire_protection_status_no_auth(self, client):
        resp = await client.get("/api/v1/linkage/fire-protection/status")
        assert resp.status_code in (401, 403)

    async def test_fire_protection_reload(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            "/api/v1/linkage/fire-protection/reload",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data

    async def test_fire_protection_reload_viewer_forbidden(self, client, viewer_user):
        _, token = viewer_user
        resp = await client.post(
            "/api/v1/linkage/fire-protection/reload",
            headers=auth_headers(token),
        )
        assert resp.status_code == 403

    async def test_fire_protection_reload_operator_forbidden(self, client, operator_user):
        _, token = operator_user
        resp = await client.post(
            "/api/v1/linkage/fire-protection/reload",
            headers=auth_headers(token),
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestLinkagePolicies:
    """联动策略 CRUD 测试"""

    async def test_list_policies_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/linkage/policies", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    async def test_list_policies_no_auth(self, client):
        resp = await client.get("/api/v1/linkage/policies")
        assert resp.status_code in (401, 403)

    async def test_create_policy(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            "/api/v1/linkage/policies",
            json={
                "name": "测试策略1",
                "trigger_type": "alarm_critical",
                "trigger_condition": {"level": "critical"},
                "actions": [
                    {
                        "action_type": "ALARM_NOTIFY",
                        "action_config": {"message": "测试告警"},
                        "sort_order": 0,
                    }
                ],
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data

    async def test_create_policy_viewer_forbidden(self, client, viewer_user):
        _, token = viewer_user
        resp = await client.post(
            "/api/v1/linkage/policies",
            json={
                "name": "禁止策略",
                "trigger_type": "test",
                "trigger_condition": {},
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 403

    async def test_create_policy_operator_forbidden(self, client, operator_user):
        _, token = operator_user
        resp = await client.post(
            "/api/v1/linkage/policies",
            json={
                "name": "禁止策略",
                "trigger_type": "test",
                "trigger_condition": {},
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 403

    async def test_get_policy_detail(self, client, admin_user, async_db):
        _, token = admin_user
        policy = await _mk_policy(async_db)
        resp = await client.get(
            f"/api/v1/linkage/policies/{policy.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == policy.id
        assert data["name"] == "测试策略"

    async def test_get_policy_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(
            "/api/v1/linkage/policies/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_update_policy(self, client, admin_user, async_db):
        _, token = admin_user
        policy = await _mk_policy(async_db, name="待更新策略")
        resp = await client.put(
            f"/api/v1/linkage/policies/{policy.id}",
            json={"name": "已更新策略", "priority": "high"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_update_policy_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            "/api/v1/linkage/policies/99999",
            json={"name": "不存在"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_update_system_policy_trigger_blocked(self, client, admin_user, async_db):
        _, token = admin_user
        policy = await _mk_policy(async_db, name="系统策略", is_system=True)
        resp = await client.put(
            f"/api/v1/linkage/policies/{policy.id}",
            json={"trigger_type": "new_type"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 403

    async def test_update_policy_with_actions(self, client, admin_user, async_db):
        _, token = admin_user
        policy = await _mk_policy(async_db, name="更新动作策略")
        resp = await client.put(
            f"/api/v1/linkage/policies/{policy.id}",
            json={
                "actions": [
                    {
                        "action_type": "WEBHOOK",
                        "action_config": {"url": "http://example.com"},
                        "sort_order": 0,
                    }
                ],
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_delete_policy(self, client, admin_user, async_db):
        _, token = admin_user
        policy = await _mk_policy(async_db, name="待删策略")
        resp = await client.delete(
            f"/api/v1/linkage/policies/{policy.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_delete_policy_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.delete(
            "/api/v1/linkage/policies/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_delete_system_policy_blocked(self, client, admin_user, async_db):
        _, token = admin_user
        policy = await _mk_policy(async_db, name="系统策略2", is_system=True)
        resp = await client.delete(
            f"/api/v1/linkage/policies/{policy.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 403

    async def test_toggle_policy(self, client, admin_user, async_db):
        _, token = admin_user
        policy = await _mk_policy(async_db, name="切换策略", enabled=True)
        resp = await client.put(
            f"/api/v1/linkage/policies/{policy.id}/toggle",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "is_enabled" in data

    async def test_toggle_policy_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            "/api/v1/linkage/policies/99999/toggle",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_test_policy(self, client, admin_user, async_db):
        _, token = admin_user
        policy = await _mk_policy(async_db, name="测试执行策略")
        resp = await client.post(
            f"/api/v1/linkage/policies/{policy.id}/test",
            json={"payload": {"test": True}},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_test_policy_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            "/api/v1/linkage/policies/99999/test",
            json={},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_list_policies_with_filters(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_policy(async_db, name="过滤策略", trigger_type="alarm_filter")
        resp = await client.get(
            "/api/v1/linkage/policies?trigger_type=alarm_filter&name=过滤",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_list_policies_enabled_filter(self, client, admin_user, async_db):
        _, token = admin_user
        await _mk_policy(async_db, name="启用策略", enabled=True)
        resp = await client.get(
            "/api/v1/linkage/policies?is_enabled=true",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestLinkageExecutions:
    """联动执行记录测试"""

    async def test_list_executions_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/linkage/executions", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_executions_no_auth(self, client):
        resp = await client.get("/api/v1/linkage/executions")
        assert resp.status_code in (401, 403)

    async def test_get_execution_detail(self, client, admin_user, async_db):
        _, token = admin_user
        policy = await _mk_policy(async_db, name="执行策略")
        exe = await _mk_execution(async_db, policy.id)
        resp = await client.get(
            f"/api/v1/linkage/executions/{exe.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == exe.id
        assert "logs" in data

    async def test_get_execution_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(
            "/api/v1/linkage/executions/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_list_executions_with_filters(self, client, admin_user, async_db):
        _, token = admin_user
        policy = await _mk_policy(async_db, name="过滤执行策略")
        await _mk_execution(async_db, policy.id, status="completed")
        resp = await client.get(
            f"/api/v1/linkage/executions?policy_id={policy.id}&status=completed",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_list_executions_with_time_filters(self, client, admin_user, async_db):
        _, token = admin_user
        policy = await _mk_policy(async_db, name="时间过滤策略")
        await _mk_execution(async_db, policy.id)
        resp = await client.get(
            "/api/v1/linkage/executions?start_time=2020-01-01T00:00:00&end_time=2030-01-01T00:00:00",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_list_recoverable_executions(self, client, admin_user, async_db):
        _, token = admin_user
        policy = await _mk_policy(async_db, name="可恢复策略")
        await _mk_execution(async_db, policy.id, status="completed")
        resp = await client.get(
            "/api/v1/linkage/executions/recoverable",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    async def test_list_recoverable_viewer_forbidden(self, client, viewer_user):
        _, token = viewer_user
        resp = await client.get(
            "/api/v1/linkage/executions/recoverable",
            headers=auth_headers(token),
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestLinkageTimeline:
    """事件时间线测试"""

    async def test_get_timeline_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(
            "/api/v1/linkage/timeline/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_get_timeline(self, client, admin_user, async_db):
        _, token = admin_user
        policy = await _mk_policy(async_db, name="时间线策略")
        exe, _ = await _mk_execution_with_log(async_db, policy.id)
        resp = await client.get(
            f"/api/v1/linkage/timeline/{exe.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["execution_id"] == exe.id

    async def test_export_timeline_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(
            "/api/v1/linkage/timeline/99999/export",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_export_timeline(self, client, admin_user, async_db):
        _, token = admin_user
        policy = await _mk_policy(async_db, name="导出时间线策略")
        exe, _ = await _mk_execution_with_log(async_db, policy.id)
        resp = await client.get(
            f"/api/v1/linkage/timeline/{exe.id}/export",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
class TestLinkageRecovery:
    """联动恢复测试"""

    async def test_create_recovery_execution_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            "/api/v1/linkage/executions/99999/recover",
            json={"mode": "manual"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_create_recovery_no_recoverable_actions(self, client, admin_user, async_db):
        _, token = admin_user
        policy = await _mk_policy(async_db, name="无恢复策略")
        exe = await _mk_execution(async_db, policy.id)
        # 没有日志 → 没有可恢复步骤
        resp = await client.post(
            f"/api/v1/linkage/executions/{exe.id}/recover",
            json={"mode": "manual"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 400

    async def test_list_recoveries_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/linkage/recoveries", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    async def test_get_recovery_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(
            "/api/v1/linkage/recoveries/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_get_recovery_detail(self, client, admin_user, async_db):
        _, token = admin_user
        policy = await _mk_policy(async_db, name="恢复详情策略")
        exe = await _mk_execution(async_db, policy.id)
        recovery = LinkageRecovery(
            execution_id=exe.id,
            operator="test_admin",
            mode="manual",
            status="executing",
        )
        async_db.add(recovery)
        await async_db.flush()
        resp = await client.get(
            f"/api/v1/linkage/recoveries/{recovery.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == recovery.id

    async def test_list_recoveries_with_filters(self, client, admin_user, async_db):
        _, token = admin_user
        policy = await _mk_policy(async_db, name="恢复过滤策略")
        exe = await _mk_execution(async_db, policy.id)
        recovery = LinkageRecovery(
            execution_id=exe.id,
            operator="test_admin",
            mode="manual",
            status="executing",
        )
        async_db.add(recovery)
        await async_db.flush()
        resp = await client.get(
            f"/api/v1/linkage/recoveries?status=executing&execution_id={exe.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_execute_recovery_step_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            "/api/v1/linkage/recoveries/99999/step/1/execute",
            headers=auth_headers(token),
        )
        assert resp.status_code == 400

    async def test_skip_recovery_step_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            "/api/v1/linkage/recoveries/99999/step/1/skip",
            headers=auth_headers(token),
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
class TestLinkageActionTypes:
    """动作类型测试"""

    async def test_get_action_types(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/linkage/action-types", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "action_type" in data[0]
            assert "is_implemented" in data[0]

    async def test_get_action_types_no_auth(self, client):
        resp = await client.get("/api/v1/linkage/action-types")
        assert resp.status_code in (401, 403)
