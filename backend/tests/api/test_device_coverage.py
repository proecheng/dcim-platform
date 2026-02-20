"""
设备管理 API 覆盖率测试 — 覆盖 device.py 中未测试的端点
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, PropertyMock

from app.models.device import Device
from app.models.point import Point, PointRealtime
from app.models.alarm import Alarm
from tests.conftest import auth_headers


# ============== 辅助函数 ==============

async def _seed_devices(async_db):
    """创建测试设备数据，返回设备列表"""
    devices = [
        Device(
            device_code="UPS-COV-001", device_name="覆盖测试UPS-1",
            device_type="UPS", area_code="A1", status="online", is_enabled=True,
        ),
        Device(
            device_code="AC-COV-001", device_name="覆盖测试空调-1",
            device_type="AC", area_code="A1", status="offline", is_enabled=True,
        ),
        Device(
            device_code="TH-COV-001", device_name="覆盖测试温湿度-1",
            device_type="TH", area_code="B1", status="alarm", is_enabled=True,
        ),
        Device(
            device_code="PDU-COV-001", device_name="覆盖测试PDU-1",
            device_type="PDU", area_code="B1", status="maintenance", is_enabled=False,
        ),
    ]
    async_db.add_all(devices)
    await async_db.flush()
    return devices


# ============== 设备列表 ==============

class TestDeviceList:
    """设备列表查询"""

    async def test_get_devices_basic(self, client, admin_user, async_db):
        """GET /devices — 基本分页"""
        _, token = admin_user
        await _seed_devices(async_db)
        resp = await client.get("/api/v1/devices", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 4

    async def test_get_devices_filter_keyword(self, client, admin_user, async_db):
        """GET /devices?keyword=UPS — 关键词搜索"""
        _, token = admin_user
        await _seed_devices(async_db)
        resp = await client.get(
            "/api/v1/devices", params={"keyword": "UPS"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    async def test_get_devices_filter_type(self, client, admin_user, async_db):
        """GET /devices?device_type=AC — 按类型筛选"""
        _, token = admin_user
        await _seed_devices(async_db)
        resp = await client.get(
            "/api/v1/devices", params={"device_type": "AC"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["device_type"] == "AC"

    async def test_get_devices_filter_area(self, client, admin_user, async_db):
        """GET /devices?area_code=B1 — 按区域筛选"""
        _, token = admin_user
        await _seed_devices(async_db)
        resp = await client.get(
            "/api/v1/devices", params={"area_code": "B1"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["area_code"] == "B1"

    async def test_get_devices_filter_status(self, client, admin_user, async_db):
        """GET /devices?status=online — 按状态筛选"""
        _, token = admin_user
        await _seed_devices(async_db)
        resp = await client.get(
            "/api/v1/devices", params={"status": "online"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["status"] == "online"

    async def test_get_devices_pagination(self, client, admin_user, async_db):
        """GET /devices — 分页参数"""
        _, token = admin_user
        await _seed_devices(async_db)
        resp = await client.get(
            "/api/v1/devices", params={"page": 1, "page_size": 2},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 2
        assert data["page"] == 1
        assert data["page_size"] == 2


# ============== 设备树 ==============

class TestDeviceTree:
    """设备树结构"""

    async def test_get_device_tree(self, client, admin_user, async_db):
        """GET /devices/tree — 设备树"""
        _, token = admin_user
        await _seed_devices(async_db)
        resp = await client.get("/api/v1/devices/tree", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # 应有区域节点
        if data:
            assert "label" in data[0]
            assert "children" in data[0]

    async def test_get_device_tree_empty(self, client, admin_user, async_db):
        """GET /devices/tree — 无设备时返回空列表"""
        _, token = admin_user
        resp = await client.get("/api/v1/devices/tree", headers=auth_headers(token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ============== 设备状态汇总 ==============

class TestDeviceStatusSummary:
    """设备状态汇总"""

    async def test_get_status_summary(self, client, admin_user, async_db):
        """GET /devices/status-summary — 状态汇总"""
        _, token = admin_user
        await _seed_devices(async_db)
        resp = await client.get(
            "/api/v1/devices/status-summary", headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "enabled" in data
        assert "online" in data
        assert "offline" in data
        assert "by_type" in data
        assert data["total"] >= 4

    async def test_get_status_summary_empty(self, client, admin_user, async_db):
        """GET /devices/status-summary — 无设备"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/devices/status-summary", headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


# ============== 设备详情 ==============

class TestDeviceDetail:
    """设备详情"""

    async def test_get_device(self, client, admin_user, async_db):
        """GET /devices/{id} — 设备详情"""
        _, token = admin_user
        devices = await _seed_devices(async_db)
        resp = await client.get(
            f"/api/v1/devices/{devices[0].id}", headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["device_code"] == "UPS-COV-001"

    async def test_get_device_not_found(self, client, admin_user, async_db):
        """GET /devices/99999 — 不存在"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/devices/99999", headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_get_device_points(self, client, admin_user, async_db):
        """GET /devices/{id}/points — 设备下的点位"""
        _, token = admin_user
        devices = await _seed_devices(async_db)
        device = devices[0]
        point = Point(
            point_code="UPS-COV-P1", point_name="UPS输出电压",
            point_type="AI", device_id=device.id, device_type="UPS",
        )
        async_db.add(point)
        await async_db.flush()

        resp = await client.get(
            f"/api/v1/devices/{device.id}/points", headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "device" in data
        assert "points" in data
        assert len(data["points"]) >= 1

    async def test_get_device_points_not_found(self, client, admin_user, async_db):
        """GET /devices/99999/points — 设备不存在"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/devices/99999/points", headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_get_device_detail_aggregated(self, client, admin_user, async_db):
        """GET /devices/{id}/detail — 聚合详情"""
        _, token = admin_user
        devices = await _seed_devices(async_db)
        device = devices[0]

        point = Point(
            point_code="UPS-COV-D1", point_name="UPS电压",
            point_type="AI", device_id=device.id, device_type="UPS", unit="V",
        )
        async_db.add(point)
        await async_db.flush()

        rt = PointRealtime(
            point_id=point.id, value=220.5, value_text="220.5",
            quality=0, status="normal",
        )
        async_db.add(rt)

        alarm = Alarm(
            alarm_no="ALM-DEV-COV-001", point_id=point.id,
            alarm_level="major", alarm_message="电压偏高",
            trigger_value=220.5, threshold_value=220.0,
            status="active",
        )
        async_db.add(alarm)
        await async_db.flush()

        resp = await client.get(
            f"/api/v1/devices/{device.id}/detail", headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["device"]["device_code"] == "UPS-COV-001"
        assert len(data["points"]) >= 1
        assert len(data["alarms"]) >= 1

    async def test_get_device_detail_not_found(self, client, admin_user, async_db):
        """GET /devices/99999/detail — 不存在"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/devices/99999/detail", headers=auth_headers(token),
        )
        assert resp.status_code == 404


# ============== 设备 CRUD ==============

class TestDeviceCRUD:
    """设备创建、更新、删除"""

    async def test_create_device(self, client, operator_user, async_db):
        """POST /devices — 创建设备"""
        _, token = operator_user
        resp = await client.post(
            "/api/v1/devices",
            json={
                "device_code": "NEW-DEV-001",
                "device_name": "新建测试设备",
                "device_type": "UPS",
                "area_code": "A1",
                "manufacturer": "测试厂商",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["device_code"] == "NEW-DEV-001"
        assert data["id"] is not None

    async def test_create_device_duplicate_code(self, client, operator_user, async_db):
        """POST /devices — 重复编码"""
        _, token = operator_user
        device = Device(
            device_code="DUP-DEV-001", device_name="已存在设备",
            device_type="AC", area_code="A1",
        )
        async_db.add(device)
        await async_db.flush()

        resp = await client.post(
            "/api/v1/devices",
            json={
                "device_code": "DUP-DEV-001",
                "device_name": "重复设备",
                "device_type": "AC",
                "area_code": "A1",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 400

    async def test_update_device(self, client, operator_user, async_db):
        """PUT /devices/{id} — 更新设备"""
        _, token = operator_user
        device = Device(
            device_code="UPD-DEV-001", device_name="待更新设备",
            device_type="TH", area_code="B1",
        )
        async_db.add(device)
        await async_db.flush()

        resp = await client.put(
            f"/api/v1/devices/{device.id}",
            json={"device_name": "已更新设备", "status": "maintenance"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["device_name"] == "已更新设备"
        assert data["status"] == "maintenance"

    async def test_update_device_not_found(self, client, operator_user, async_db):
        """PUT /devices/99999 — 不存在"""
        _, token = operator_user
        resp = await client.put(
            "/api/v1/devices/99999",
            json={"device_name": "x"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_delete_device(self, client, admin_user, async_db):
        """DELETE /devices/{id} — 删除设备（无关联点位）"""
        _, token = admin_user
        device = Device(
            device_code="DEL-DEV-001", device_name="待删除设备",
            device_type="PDU", area_code="A1",
        )
        async_db.add(device)
        await async_db.flush()

        resp = await client.delete(
            f"/api/v1/devices/{device.id}", headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert "已删除" in resp.json()["message"]

    async def test_delete_device_with_points(self, client, admin_user, async_db):
        """DELETE /devices/{id} — 有关联点位时拒绝删除"""
        _, token = admin_user
        device = Device(
            device_code="DEL-DEV-002", device_name="有点位设备",
            device_type="UPS", area_code="A1",
        )
        async_db.add(device)
        await async_db.flush()

        point = Point(
            point_code="DEL-P-001", point_name="关联点位",
            point_type="AI", device_id=device.id, device_type="UPS",
        )
        async_db.add(point)
        await async_db.flush()

        resp = await client.delete(
            f"/api/v1/devices/{device.id}", headers=auth_headers(token),
        )
        assert resp.status_code == 400
        assert "点位" in resp.json()["detail"]

    async def test_delete_device_not_found(self, client, admin_user, async_db):
        """DELETE /devices/99999 — 不存在"""
        _, token = admin_user
        resp = await client.delete(
            "/api/v1/devices/99999", headers=auth_headers(token),
        )
        assert resp.status_code == 404


# ============== 设备状态看板（补充 redis mock） ==============

class TestDeviceStatusBoard:
    """设备状态看板"""

    @patch("app.api.v1.device.redis_service")
    async def test_status_board_no_redis(self, mock_redis, client, admin_user, async_db):
        """GET /devices/status-board — Redis 不可用"""
        _, token = admin_user
        mock_redis.is_available = False
        await _seed_devices(async_db)
        resp = await client.get(
            "/api/v1/devices/status-board", headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "groups" in data

    @patch("app.api.v1.device.redis_service")
    async def test_status_board_with_filters(self, mock_redis, client, admin_user, async_db):
        """GET /devices/status-board — 带筛选"""
        _, token = admin_user
        mock_redis.is_available = False
        await _seed_devices(async_db)
        resp = await client.get(
            "/api/v1/devices/status-board",
            params={"area_code": "A1", "device_type": "UPS"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200


# ============== 补充覆盖率测试 ==============

class TestDeviceListCoverageExtra:
    """补充 get_devices 的 site_id 筛选和分页 (L48, L65-68)"""

    async def test_get_devices_site_id_filter(self, client, admin_user, async_db):
        """GET /devices?site_id=1 — 按站点筛选 (L47-48)"""
        _, token = admin_user
        await _seed_devices(async_db)
        resp = await client.get(
            "/api/v1/devices", params={"site_id": 1},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_get_devices_combined_filters(self, client, admin_user, async_db):
        """GET /devices — 多条件组合筛选"""
        _, token = admin_user
        await _seed_devices(async_db)
        resp = await client.get(
            "/api/v1/devices",
            params={"keyword": "覆盖", "device_type": "UPS", "area_code": "A1", "status": "online"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["device_type"] == "UPS"
            assert item["area_code"] == "A1"

    async def test_get_devices_empty_result(self, client, admin_user, async_db):
        """GET /devices — 无匹配结果"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/devices", params={"keyword": "nonexistent_xyz"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


class TestDeviceTreeCoverageExtra:
    """补充设备树的多区域多类型 (L89-124)"""

    async def test_device_tree_structure(self, client, admin_user, async_db):
        """GET /devices/tree — 验证树结构层级"""
        _, token = admin_user
        await _seed_devices(async_db)
        resp = await client.get("/api/v1/devices/tree", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        for area_node in data:
            assert "label" in area_node
            assert "children" in area_node
            for type_node in area_node["children"]:
                assert "label" in type_node
                assert "children" in type_node
                for device in type_node["children"]:
                    assert "id" in device
                    assert "label" in device
                    assert "code" in device
                    assert "status" in device


class TestDeviceStatusSummaryCoverageExtra:
    """补充设备状态汇总 (L137-145, L151, L156)"""

    async def test_status_summary_by_type(self, client, admin_user, async_db):
        """GET /devices/status-summary — 验证按类型统计"""
        _, token = admin_user
        await _seed_devices(async_db)
        resp = await client.get(
            "/api/v1/devices/status-summary", headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "by_type" in data
        assert len(data["by_type"]) >= 1
        assert data["online"] >= 1
        assert data["offline"] >= 1


class TestDeviceDetailCoverageExtra:
    """补充设备详情聚合 (L184-189, L191-225, L241-244, L257-264, L283-334)"""

    async def test_device_points_with_multiple(self, client, admin_user, async_db):
        """GET /devices/{id}/points — 多个点位"""
        _, token = admin_user
        devices = await _seed_devices(async_db)
        device = devices[0]
        for i in range(3):
            p = Point(
                point_code=f"UPS-MULTI-P{i}", point_name=f"UPS点位{i}",
                point_type="AI", device_id=device.id, device_type="UPS",
            )
            async_db.add(p)
        await async_db.flush()

        resp = await client.get(
            f"/api/v1/devices/{device.id}/points", headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["points"]) == 3

    async def test_device_detail_no_alarms(self, client, admin_user, async_db):
        """GET /devices/{id}/detail — 有点位无告警"""
        _, token = admin_user
        devices = await _seed_devices(async_db)
        device = devices[1]
        point = Point(
            point_code="AC-NOALM-P1", point_name="无告警点位",
            point_type="AI", device_id=device.id, device_type="AC",
        )
        async_db.add(point)
        await async_db.flush()

        resp = await client.get(
            f"/api/v1/devices/{device.id}/detail", headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["points"]) >= 1
        assert len(data["alarms"]) == 0

    async def test_device_detail_with_realtime(self, client, admin_user, async_db):
        """GET /devices/{id}/detail — 点位有实时数据"""
        _, token = admin_user
        devices = await _seed_devices(async_db)
        device = devices[0]
        point = Point(
            point_code="UPS-RT-P1", point_name="实时数据点位",
            point_type="AI", device_id=device.id, device_type="UPS", unit="V",
        )
        async_db.add(point)
        await async_db.flush()

        rt = PointRealtime(
            point_id=point.id, value=230.0, value_text="230.0",
            quality=0, status="normal",
        )
        async_db.add(rt)
        await async_db.flush()

        resp = await client.get(
            f"/api/v1/devices/{device.id}/detail", headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        pt_data = [p for p in data["points"] if p["point_code"] == "UPS-RT-P1"]
        assert len(pt_data) == 1
        assert pt_data[0]["value"] == 230.0
        assert pt_data[0]["status"] == "normal"

    async def test_device_detail_no_points(self, client, admin_user, async_db):
        """GET /devices/{id}/detail — 无点位"""
        _, token = admin_user
        devices = await _seed_devices(async_db)
        device = devices[3]  # PDU, disabled
        resp = await client.get(
            f"/api/v1/devices/{device.id}/detail", headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["points"]) == 0
        assert len(data["alarms"]) == 0


class TestDeviceCRUDCoverageExtra:
    """补充设备 CRUD (L352-360, L374-387, L400-419)"""

    async def test_create_device_full(self, client, operator_user, async_db):
        """POST /devices — 完整参数创建"""
        _, token = operator_user
        resp = await client.post(
            "/api/v1/devices",
            json={
                "device_code": "FULL-DEV-001",
                "device_name": "完整参数设备",
                "device_type": "PDU",
                "area_code": "C1",
                "manufacturer": "厂商A",
                "status": "offline",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["device_code"] == "FULL-DEV-001"
        assert data["device_type"] == "PDU"

    async def test_update_device_multiple_fields(self, client, operator_user, async_db):
        """PUT /devices/{id} — 更新多个字段"""
        _, token = operator_user
        device = Device(
            device_code="UPD-MULTI-001", device_name="多字段更新",
            device_type="AC", area_code="A1",
        )
        async_db.add(device)
        await async_db.flush()

        resp = await client.put(
            f"/api/v1/devices/{device.id}",
            json={
                "device_name": "已更新多字段",
                "status": "online",
                "area_code": "B1",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["device_name"] == "已更新多字段"
        assert data["status"] == "online"
        assert data["area_code"] == "B1"


class TestDeviceStatusBoardCoverageExtra:
    """补充设备状态看板 (L184-189, L191-225)"""

    @patch("app.api.v1.device.redis_service")
    async def test_status_board_groups(self, mock_redis, client, admin_user, async_db):
        """GET /devices/status-board — 验证分组结构"""
        _, token = admin_user
        mock_redis.is_available = False
        await _seed_devices(async_db)
        resp = await client.get(
            "/api/v1/devices/status-board", headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total"] >= 3
        assert len(data["groups"]) >= 1
        for group in data["groups"]:
            assert "area_code" in group
            assert "device_type" in group
            assert "devices" in group
            assert "stats" in group
            for dev in group["devices"]:
                assert "id" in dev
                assert "status" in dev

    @patch("app.api.v1.device.redis_service")
    async def test_status_board_empty(self, mock_redis, client, admin_user, async_db):
        """GET /devices/status-board — 无设备"""
        _, token = admin_user
        mock_redis.is_available = False
        resp = await client.get(
            "/api/v1/devices/status-board", headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total"] == 0
        assert data["groups"] == []
