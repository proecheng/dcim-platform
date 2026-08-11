"""
传感器元数据 API 集成测试
Story 25.5: 传感器元数据与精度加权
"""

import pytest
from datetime import date, timedelta
from httpx import AsyncClient

from app.models.device import Device
from app.models.diagnosis import SensorMetadata, CalibrationStatus
from app.models.point import Point
from app.models.spatial import Site
from app.models.user import UserSite


@pytest.fixture(autouse=True)
async def sensor_points(async_db, operator_user):
    operator, _ = operator_user
    site = Site(site_code="SENSOR-METADATA-SITE", site_name="传感器元数据测试站点")
    async_db.add(site)
    await async_db.flush()
    device = Device(
        device_code="SENSOR-METADATA-DEVICE",
        device_name="传感器元数据测试设备",
        device_type="UPS",
        area_code="A",
        site_id=site.id,
    )
    async_db.add(device)
    await async_db.flush()
    async_db.add(UserSite(user_id=operator.id, site_id=site.id))
    async_db.add_all(
        [
            Point(
                id=point_id,
                point_code=f"SENSOR-METADATA-{point_id}",
                point_name=f"传感器点位 {point_id}",
                point_type="AI",
                device_id=device.id,
            )
            for point_id in [*range(1001, 1012), 2001, 2002]
        ]
    )
    await async_db.flush()


class TestSensorMetadataAPI:
    """传感器元数据 API 测试"""

    @pytest.mark.asyncio
    async def test_create_sensor_metadata(self, client: AsyncClient, admin_token: str, async_db):
        """测试创建传感器元数据"""
        # 先创建一个点位（假设点位 ID 1001 存在）
        response = await client.post(
            "/api/v1/diagnosis/sensor-metadata/",
            json={
                "point_id": 1001,
                "ct_pt_ratio": 100.0,
                "accuracy_class": 0.2,
                "calibration_date": str(date.today() - timedelta(days=100)),
                "calibration_interval_days": 365,
                "calibration_result": "校准合格"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["point_id"] == 1001
        assert data["accuracy_class"] == 0.2
        assert data["ct_pt_ratio"] == 100.0

    @pytest.mark.asyncio
    async def test_create_duplicate_point_id(self, client: AsyncClient, admin_token: str, async_db):
        """测试创建重复点位元数据"""
        # 创建第一个元数据
        metadata = SensorMetadata(
            point_id=1002,
            accuracy_class=0.5,
            calibration_interval_days=365
        )
        async_db.add(metadata)
        await async_db.commit()

        # 尝试创建重复点位
        response = await client.post(
            "/api/v1/diagnosis/sensor-metadata/",
            json={
                "point_id": 1002,
                "accuracy_class": 0.2,
                "calibration_interval_days": 365
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 400
        assert "已存在元数据" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_sensor_metadata(self, client: AsyncClient, admin_token: str, async_db):
        """测试查询传感器元数据列表"""
        # 创建测试数据
        metadata1 = SensorMetadata(
            point_id=1003,
            accuracy_class=0.2,
            calibration_interval_days=365
        )
        metadata2 = SensorMetadata(
            point_id=1004,
            accuracy_class=0.5,
            calibration_interval_days=365
        )
        async_db.add_all([metadata1, metadata2])
        await async_db.commit()

        # 查询所有
        response = await client.get(
            "/api/v1/diagnosis/sensor-metadata/",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "items" in data
        assert len(data["items"]) >= 2

    @pytest.mark.asyncio
    async def test_list_sensor_metadata_with_filters(self, client: AsyncClient, admin_token: str, async_db):
        """测试带过滤条件的查询"""
        # 创建测试数据
        metadata = SensorMetadata(
            point_id=1005,
            accuracy_class=0.2,
            calibration_interval_days=365
        )
        async_db.add(metadata)
        await async_db.commit()

        # 按精度等级过滤
        response = await client.get(
            "/api/v1/diagnosis/sensor-metadata/?accuracy_class=0.2",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert all(item["accuracy_class"] == 0.2 for item in data["items"])

    @pytest.mark.asyncio
    async def test_get_sensor_metadata(self, client: AsyncClient, admin_token: str, async_db):
        """测试获取传感器元数据详情"""
        # 创建测试数据
        metadata = SensorMetadata(
            point_id=1006,
            accuracy_class=0.5,
            calibration_interval_days=365
        )
        async_db.add(metadata)
        await async_db.commit()
        await async_db.refresh(metadata)

        # 获取详情
        response = await client.get(
            f"/api/v1/diagnosis/sensor-metadata/{metadata.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == metadata.id
        assert data["point_id"] == 1006

    @pytest.mark.asyncio
    async def test_get_nonexistent_metadata(self, client: AsyncClient, admin_token: str):
        """测试获取不存在的元数据"""
        response = await client.get(
            "/api/v1/diagnosis/sensor-metadata/99999",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_sensor_metadata(self, client: AsyncClient, admin_token: str, async_db):
        """测试更新传感器元数据"""
        # 创建测试数据
        metadata = SensorMetadata(
            point_id=1007,
            accuracy_class=0.5,
            calibration_interval_days=365
        )
        async_db.add(metadata)
        await async_db.commit()
        await async_db.refresh(metadata)

        # 更新元数据
        response = await client.put(
            f"/api/v1/diagnosis/sensor-metadata/{metadata.id}",
            json={
                "accuracy_class": 0.2,
                "calibration_result": "重新校准合格"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["accuracy_class"] == 0.2
        assert data["calibration_result"] == "重新校准合格"

    @pytest.mark.asyncio
    async def test_delete_sensor_metadata(self, client: AsyncClient, admin_token: str, async_db):
        """测试删除传感器元数据"""
        # 创建测试数据
        metadata = SensorMetadata(
            point_id=1008,
            accuracy_class=0.5,
            calibration_interval_days=365
        )
        async_db.add(metadata)
        await async_db.commit()
        await async_db.refresh(metadata)

        # 删除元数据
        response = await client.delete(
            f"/api/v1/diagnosis/sensor-metadata/{metadata.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 204

        # 验证已删除
        response = await client.get(
            f"/api/v1/diagnosis/sensor-metadata/{metadata.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_calibration_status_valid(self, client: AsyncClient, admin_token: str, async_db):
        """测试获取校准状态 - 有效"""
        # 创建测试数据
        calibration_date = date.today() - timedelta(days=100)
        metadata = SensorMetadata(
            point_id=1009,
            accuracy_class=0.5,
            calibration_date=calibration_date,
            calibration_interval_days=365
        )
        async_db.add(metadata)
        await async_db.commit()

        # 获取校准状态
        response = await client.get(
            "/api/v1/diagnosis/sensor-metadata/calibration-status/1009",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["point_id"] == 1009
        assert data["status"] == CalibrationStatus.VALID.value
        assert data["expired_days"] is None

    @pytest.mark.asyncio
    async def test_get_calibration_status_expired(self, client: AsyncClient, admin_token: str, async_db):
        """测试获取校准状态 - 过期"""
        # 创建测试数据
        calibration_date = date.today() - timedelta(days=400)
        metadata = SensorMetadata(
            point_id=1010,
            accuracy_class=0.5,
            calibration_date=calibration_date,
            calibration_interval_days=365
        )
        async_db.add(metadata)
        await async_db.commit()

        # 获取校准状态
        response = await client.get(
            "/api/v1/diagnosis/sensor-metadata/calibration-status/1010",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["point_id"] == 1010
        assert data["status"] == CalibrationStatus.EXPIRED.value
        assert data["expired_days"] == 35  # 400 - 365

    @pytest.mark.asyncio
    async def test_get_calibration_status_no_metadata(self, client: AsyncClient, admin_token: str):
        """测试获取校准状态 - 无元数据"""
        response = await client.get(
            "/api/v1/diagnosis/sensor-metadata/calibration-status/1011",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["point_id"] == 1011
        assert data["status"] == CalibrationStatus.NO_METADATA.value

    @pytest.mark.asyncio
    async def test_trigger_expired_calibrations_check(self, client: AsyncClient, admin_token: str):
        """测试手动触发校准过期检查"""
        response = await client.post(
            "/api/v1/diagnosis/sensor-metadata/check-expired-calibrations",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        assert "已完成" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_permission_operator_can_create(self, client: AsyncClient, operator_token: str):
        """测试 operator 权限可以创建元数据"""
        response = await client.post(
            "/api/v1/diagnosis/sensor-metadata/",
            json={
                "point_id": 2001,
                "accuracy_class": 0.5,
                "calibration_interval_days": 365
            },
            headers={"Authorization": f"Bearer {operator_token}"}
        )

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_permission_viewer_cannot_create(self, client: AsyncClient, viewer_token: str):
        """测试 viewer 权限不能创建元数据"""
        response = await client.post(
            "/api/v1/diagnosis/sensor-metadata/",
            json={
                "point_id": 2002,
                "accuracy_class": 0.5,
                "calibration_interval_days": 365
            },
            headers={"Authorization": f"Bearer {viewer_token}"}
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_permission_viewer_can_read(self, client: AsyncClient, viewer_token: str):
        """测试 viewer 权限可以查询元数据"""
        response = await client.get(
            "/api/v1/diagnosis/sensor-metadata/",
            headers={"Authorization": f"Bearer {viewer_token}"}
        )

        assert response.status_code == 200
