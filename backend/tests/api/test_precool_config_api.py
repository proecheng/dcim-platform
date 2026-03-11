"""
预冷配置 API 端点单元测试

Story 31.4: 测试预冷配置查询和更新端点的功能、权限和审计日志。
"""

import pytest
from unittest.mock import AsyncMock, patch

from tests.conftest import auth_headers


# ==================== Fixtures ====================


@pytest.fixture
async def sample_zone(async_db):
    """创建测试用制冷区域"""
    from app.models.topology_config import CoolingZone

    zone = CoolingZone(
        zone_code="TEST-CFG-ZONE",
        zone_name="配置测试区域",
        thermal_R=0.005,
        thermal_C=500.0,
    )
    async_db.add(zone)
    await async_db.flush()
    return zone


@pytest.fixture
async def zone_with_config(async_db, sample_zone):
    """创建带预冷配置的 zone"""
    from app.models.load_shift import CoolingLinkageConfig

    config = CoolingLinkageConfig(
        cooling_zone_id=sample_zone.id,
        precool_enabled=True,
        precool_target_temp=20.0,
    )
    async_db.add(config)
    await async_db.flush()
    return sample_zone, config


# ==================== GET /zones/{zone_id}/config 测试 ====================


class TestGetPrecoolConfig:
    async def test_get_config_with_existing(self, client, admin_user, zone_with_config):
        """查询已有配置"""
        _, token = admin_user
        zone, config = zone_with_config
        resp = await client.get(
            f"/api/v1/precool/zones/{zone.id}/config",
            headers=auth_headers(token),
        )
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["zone_id"] == zone.id
        assert data["data"]["precool_enabled"] is True
        assert data["data"]["precool_target_temp"] == 20.0

    async def test_get_config_default_when_no_config(self, client, admin_user, sample_zone):
        """无配置时返回默认值"""
        _, token = admin_user
        resp = await client.get(
            f"/api/v1/precool/zones/{sample_zone.id}/config",
            headers=auth_headers(token),
        )
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["precool_enabled"] is False
        assert data["data"]["precool_target_temp"] == 18.0

    async def test_get_config_zone_not_found(self, client, admin_user):
        """zone 不存在返回 404"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/precool/zones/99999/config",
            headers=auth_headers(token),
        )
        assert resp.json()["code"] == 404


# ==================== PUT /zones/{zone_id}/config 测试 ====================


class TestUpdatePrecoolConfig:
    async def test_update_config_success(self, client, admin_user, zone_with_config):
        """成功更新配置"""
        _, token = admin_user
        zone, _ = zone_with_config
        resp = await client.put(
            f"/api/v1/precool/zones/{zone.id}/config",
            json={"precool_enabled": False, "precool_target_temp": 22.0},
            headers=auth_headers(token),
        )
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["precool_enabled"] is False
        assert data["data"]["precool_target_temp"] == 22.0

    async def test_update_config_auto_create(self, client, admin_user, sample_zone):
        """无配置时自动创建"""
        _, token = admin_user
        resp = await client.put(
            f"/api/v1/precool/zones/{sample_zone.id}/config",
            json={"precool_enabled": True, "precool_target_temp": 19.0},
            headers=auth_headers(token),
        )
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["precool_enabled"] is True
        assert data["data"]["precool_target_temp"] == 19.0

    async def test_update_partial_fields(self, client, admin_user, zone_with_config):
        """只更新部分字段"""
        _, token = admin_user
        zone, _ = zone_with_config
        resp = await client.put(
            f"/api/v1/precool/zones/{zone.id}/config",
            json={"precool_enabled": False},
            headers=auth_headers(token),
        )
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["precool_enabled"] is False
        # target_temp 保持不变
        assert data["data"]["precool_target_temp"] == 20.0

    async def test_update_config_zone_not_found(self, client, admin_user):
        """zone 不存在返回 404"""
        _, token = admin_user
        resp = await client.put(
            "/api/v1/precool/zones/99999/config",
            json={"precool_enabled": True},
            headers=auth_headers(token),
        )
        assert resp.json()["code"] == 404

    async def test_target_temp_below_min(self, client, admin_user, sample_zone):
        """precool_target_temp < 18 被 Pydantic 拒绝"""
        _, token = admin_user
        resp = await client.put(
            f"/api/v1/precool/zones/{sample_zone.id}/config",
            json={"precool_target_temp": 17.0},
            headers=auth_headers(token),
        )
        assert resp.status_code == 422

    async def test_target_temp_above_max(self, client, admin_user, sample_zone):
        """precool_target_temp > 25 被 Pydantic 拒绝"""
        _, token = admin_user
        resp = await client.put(
            f"/api/v1/precool/zones/{sample_zone.id}/config",
            json={"precool_target_temp": 26.0},
            headers=auth_headers(token),
        )
        assert resp.status_code == 422


# ==================== 审计日志测试 ====================


class TestAuditLog:
    async def test_audit_log_created(self, client, admin_user, zone_with_config, async_db):
        """更新配置时写入审计日志"""
        _, token = admin_user
        zone, _ = zone_with_config

        resp = await client.put(
            f"/api/v1/precool/zones/{zone.id}/config",
            json={"precool_enabled": False},
            headers=auth_headers(token),
        )
        assert resp.json()["code"] == 200

        # 检查审计日志
        from app.models.log import OperationLog
        from sqlalchemy import select

        result = await async_db.execute(
            select(OperationLog).where(
                OperationLog.module == "precool",
                OperationLog.target_type == "cooling_linkage_config",
            )
        )
        logs = result.scalars().all()
        assert len(logs) >= 1
        log = logs[-1]
        assert log.action == "update"
        assert "precool_enabled" in log.old_value
        assert "precool_enabled" in log.new_value


# ==================== 权限测试 ====================


class TestConfigPermissions:
    async def test_operator_can_read(self, client, operator_user, sample_zone):
        """operator 可以查询配置"""
        _, token = operator_user
        resp = await client.get(
            f"/api/v1/precool/zones/{sample_zone.id}/config",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_operator_cannot_update(self, client, operator_user, sample_zone):
        """operator 不能更新配置"""
        _, token = operator_user
        resp = await client.put(
            f"/api/v1/precool/zones/{sample_zone.id}/config",
            json={"precool_enabled": True},
            headers=auth_headers(token),
        )
        assert resp.status_code == 403

    async def test_viewer_cannot_read(self, client, viewer_user, sample_zone):
        """viewer 不能查询配置"""
        _, token = viewer_user
        resp = await client.get(
            f"/api/v1/precool/zones/{sample_zone.id}/config",
            headers=auth_headers(token),
        )
        assert resp.status_code == 403

    async def test_viewer_cannot_update(self, client, viewer_user, sample_zone):
        """viewer 不能更新配置"""
        _, token = viewer_user
        resp = await client.put(
            f"/api/v1/precool/zones/{sample_zone.id}/config",
            json={"precool_enabled": True},
            headers=auth_headers(token),
        )
        assert resp.status_code == 403
