"""
Story 25.3: UPS电池SOH预测 API 集成测试
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers


@pytest.fixture
async def battery_assets(async_db):
    """创建真实站点和设备，供可信归属解析使用。"""
    from app.models.device import Device
    from app.models.spatial import Site

    site = Site(site_code="SOH-TEST", site_name="SOH Test Site")
    async_db.add(site)
    await async_db.flush()

    devices = [
        Device(
            device_code=f"SOH-UPS-{index}",
            device_name=f"SOH UPS {index}",
            device_type="UPS",
            area_code="A1",
            site_id=site.id,
        )
        for index in range(1, 4)
    ]
    async_db.add_all(devices)
    await async_db.flush()
    return site, devices


@pytest.mark.asyncio
class TestBatterySOHAPI:
    """测试 SOH API 端点"""

    async def test_get_device_soh_history(self, client: AsyncClient, admin_user, async_db, battery_assets):
        """测试查询设备 SOH 历史"""
        from app.models.diagnosis import BatterySOHRecord

        _, token = admin_user
        _, devices = battery_assets
        device_id = devices[0].id

        for i in range(5):
            record = BatterySOHRecord(
                device_id=device_id,
                soh_percent=90.0 - i * 2,
                resistance_mohm=50.0 + i * 2,
                cycle_count=100 + i * 50,
                weights_version="v1.0",
                calculated_at=datetime.now(timezone.utc) - timedelta(days=i)
            )
            async_db.add(record)
        await async_db.flush()

        response = await client.get(
            f"/api/v1/diagnosis/battery-soh/{device_id}",
            headers=auth_headers(token)
        )
        assert response.status_code == 200
        data = response.json()
        assert data["device_id"] == device_id
        assert data["total"] == 5
        assert len(data["records"]) == 5
        assert data["records"][0]["soh_percent"] == 90.0

    async def test_get_device_soh_history_with_limit(
        self, client: AsyncClient, admin_user, async_db, battery_assets
    ):
        """测试分页查询"""
        from app.models.diagnosis import BatterySOHRecord

        _, token = admin_user
        _, devices = battery_assets
        device_id = devices[0].id

        for i in range(10):
            record = BatterySOHRecord(
                device_id=device_id,
                soh_percent=90.0 - i,
                resistance_mohm=50.0,
                cycle_count=100,
                weights_version="v1.0",
                calculated_at=datetime.now(timezone.utc) - timedelta(days=i)
            )
            async_db.add(record)
        await async_db.flush()

        response = await client.get(
            f"/api/v1/diagnosis/battery-soh/{device_id}?limit=3",
            headers=auth_headers(token)
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["records"]) == 3

    async def test_get_all_latest_soh(self, client: AsyncClient, admin_user, async_db, battery_assets):
        """测试查询所有设备最新 SOH"""
        from app.models.diagnosis import BatterySOHRecord

        _, token = admin_user
        _, devices = battery_assets

        for device in devices:
            for i in range(3):
                record = BatterySOHRecord(
                    device_id=device.id,
                    soh_percent=90.0 - i * 5,
                    resistance_mohm=50.0,
                    cycle_count=100,
                    weights_version="v1.0",
                    calculated_at=datetime.now(timezone.utc) - timedelta(days=i)
                )
                async_db.add(record)
        await async_db.flush()

        response = await client.get(
            "/api/v1/diagnosis/battery-soh/latest",
            headers=auth_headers(token)
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        device_ids = [r["device_id"] for r in data["records"]]
        assert device_ids == [device.id for device in devices]
        assert all(r["soh_percent"] == 90.0 for r in data["records"])

    async def test_trigger_soh_calculation_success(
        self, client: AsyncClient, operator_user, async_db, battery_assets
    ):
        """测试手动触发 SOH 计算"""
        from app.models.user import UserSite

        operator, token = operator_user
        site, devices = battery_assets
        device = devices[0]
        async_db.add(UserSite(user_id=operator.id, site_id=site.id))
        await async_db.flush()

        with patch(
            "app.services.diagnosis.battery_soh_service.calculate_soh",
            new_callable=AsyncMock,
            return_value=88.0,
        ) as calculate_soh:
            response = await client.post(
                f"/api/v1/diagnosis/battery-soh/calculate/{device.id}",
                headers=auth_headers(token),
            )

        assert response.status_code == 200
        assert response.json()["soh_percent"] == 88.0
        calculate_soh.assert_awaited_once_with(device.id)

    async def test_trigger_soh_calculation_permission(self, client: AsyncClient, viewer_user):
        """测试权限控制：viewer 无法触发计算"""
        _, token = viewer_user
        response = await client.post(
            "/api/v1/diagnosis/battery-soh/calculate/1",
            headers=auth_headers(token)
        )
        assert response.status_code == 403

    async def test_get_soh_weights_config(self, client: AsyncClient, admin_user):
        """测试获取 SOH 权重配置"""
        _, token = admin_user

        with patch(
            "app.services.diagnosis.battery_soh_service.get_soh_weights",
            new_callable=AsyncMock,
            return_value={"w_r": 0.6, "w_c": 0.4, "version": "v1.0"},
        ) as get_soh_weights:
            response = await client.get(
                "/api/v1/diagnosis/config/soh-weights",
                headers=auth_headers(token),
            )

        assert response.status_code == 200
        data = response.json()
        # 验证返回包含必要字段
        assert "w_r" in data
        assert "w_c" in data
        assert "version" in data
        # 验证权重是合理数值
        assert 0 <= data["w_r"] <= 1
        assert 0 <= data["w_c"] <= 1
        get_soh_weights.assert_awaited_once_with()

    async def test_update_soh_weights_config(self, client: AsyncClient, admin_user, async_db):
        """测试更新 SOH 权重配置（admin）"""
        from app.models.config import SystemConfig
        import json
        _, token = admin_user

        # 确保 async_db 中存在配置（API 的 db 依赖被 override 为 async_db）
        config = SystemConfig(
            config_group="diagnosis",
            config_key="soh_weights",
            config_value=json.dumps({"w_r": 0.6, "w_c": 0.4, "version": "v1.0"}),
            value_type="json",
            description="Test",
            is_editable=True
        )
        async_db.add(config)
        await async_db.flush()

        response = await client.put(
            "/api/v1/diagnosis/config/soh-weights",
            headers=auth_headers(token),
            json={"w_r": 0.7, "w_c": 0.3, "version": "v1.1"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "SOH 权重配置已更新"
        assert data["config"]["w_r"] == 0.7

    async def test_update_soh_weights_validation(self, client: AsyncClient, admin_user):
        """测试权重和校验（w_r + w_c ≈ 1.0）"""
        _, token = admin_user

        # 测试无效权重（和不为 1.0）
        response = await client.put(
            "/api/v1/diagnosis/config/soh-weights",
            headers=auth_headers(token),
            json={"w_r": 0.8, "w_c": 0.5, "version": "v1.1"}  # 和为 1.3
        )
        assert response.status_code == 422

    async def test_update_soh_weights_permission(self, client: AsyncClient, operator_user):
        """测试权限控制：operator 无法更新配置"""
        _, token = operator_user

        response = await client.put(
            "/api/v1/diagnosis/config/soh-weights",
            headers=auth_headers(token),
            json={"w_r": 0.7, "w_c": 0.3, "version": "v1.1"}
        )
        assert response.status_code == 403
