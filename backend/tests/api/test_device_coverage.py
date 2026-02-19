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
