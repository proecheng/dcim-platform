"""
系统配置 API 覆盖率测试 — 使用 conftest fixtures
"""
import json
import pytest
from datetime import datetime, date

from tests.conftest import auth_headers
from app.models.config import SystemConfig, Dictionary, License


# ==================== 辅助函数 ====================


async def _create_config(async_db, **overrides) -> SystemConfig:
    defaults = dict(
        config_group="system",
        config_key="app_name",
        config_value="测试系统",
        value_type="string",
        description="系统名称",
        is_editable=True,
    )
    defaults.update(overrides)
    config = SystemConfig(**defaults)
    async_db.add(config)
    await async_db.flush()
    return config


async def _create_dictionary(async_db, **overrides) -> Dictionary:
    defaults = dict(
        dict_type="alarm_level",
        dict_code="critical",
        dict_name="紧急",
        dict_value="critical",
        sort_order=0,
        is_enabled=True,
    )
    defaults.update(overrides)
    d = Dictionary(**defaults)
    async_db.add(d)
    await async_db.flush()
    return d


async def _create_license(async_db, **overrides) -> License:
    defaults = dict(
        license_key="STD-ABCDEFGH12345678",
        license_type="standard",
        max_points=100,
        features=json.dumps(["all"]),
        issue_date=date.today(),
        expire_date=date(date.today().year + 1, date.today().month, date.today().day),
        is_active=True,
        activated_at=datetime.now(),
    )
    defaults.update(overrides)
    lic = License(**defaults)
    async_db.add(lic)
    await async_db.flush()
    return lic


# ==================== GET /api/v1/configs ====================


class TestGetConfigs:
    """获取系统配置"""

    async def test_get_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/configs", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json() == {}

    async def test_get_grouped(self, client, admin_user, async_db):
        _, token = admin_user
        await _create_config(async_db, config_group="system", config_key="name")
        await _create_config(async_db, config_group="system", config_key="version")
        await _create_config(async_db, config_group="alarm", config_key="sound")

        resp = await client.get("/api/v1/configs", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "system" in data
        assert "alarm" in data
        assert len(data["system"]) == 2
        assert len(data["alarm"]) == 1

    async def test_get_filter_by_group(self, client, admin_user, async_db):
        _, token = admin_user
        await _create_config(async_db, config_group="system", config_key="name")
        await _create_config(async_db, config_group="alarm", config_key="sound")

        resp = await client.get(
            "/api/v1/configs?group=system", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "system" in data
        assert "alarm" not in data

    async def test_get_requires_admin(self, client, viewer_user):
        _, token = viewer_user
        resp = await client.get("/api/v1/configs", headers=auth_headers(token))
        assert resp.status_code == 403


# ==================== PUT /api/v1/configs ====================


class TestUpdateConfigs:
    """批量更新系统配置"""

    async def test_update_existing(self, client, admin_user, async_db):
        _, token = admin_user
        await _create_config(
            async_db, config_group="system", config_key="app_name",
            config_value="旧值", is_editable=True,
        )

        resp = await client.put(
            "/api/v1/configs",
            json=[{
                "config_group": "system",
                "config_key": "app_name",
                "config_value": "新值",
            }],
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert "1" in resp.json()["message"]

    async def test_update_non_editable_skipped(self, client, admin_user, async_db):
        _, token = admin_user
        await _create_config(
            async_db, config_group="system", config_key="locked",
            config_value="不可改", is_editable=False,
        )

        resp = await client.put(
            "/api/v1/configs",
            json=[{
                "config_group": "system",
                "config_key": "locked",
                "config_value": "尝试修改",
            }],
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert "0" in resp.json()["message"]

    async def test_update_creates_new(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            "/api/v1/configs",
            json=[{
                "config_group": "new_group",
                "config_key": "new_key",
                "config_value": "新配置",
                "value_type": "string",
                "description": "新建的配置",
            }],
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert "1" in resp.json()["message"]

    async def test_update_requires_admin(self, client, operator_user):
        _, token = operator_user
        resp = await client.put(
            "/api/v1/configs",
            json=[{"config_group": "x", "config_key": "y", "config_value": "z"}],
            headers=auth_headers(token),
        )
        assert resp.status_code == 403


# ==================== GET /api/v1/configs/dictionaries ====================


class TestGetDictionaries:
    """获取数据字典"""

    async def test_get_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(
            "/api/v1/configs/dictionaries", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        assert resp.json() == {}

    async def test_get_grouped(self, client, admin_user, async_db):
        _, token = admin_user
        await _create_dictionary(async_db, dict_type="alarm_level", dict_code="critical", dict_name="紧急")
        await _create_dictionary(async_db, dict_type="alarm_level", dict_code="major", dict_name="重要")
        await _create_dictionary(async_db, dict_type="device_type", dict_code="TH", dict_name="温湿度")

        resp = await client.get(
            "/api/v1/configs/dictionaries", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "alarm_level" in data
        assert "device_type" in data
        assert len(data["alarm_level"]) == 2

    async def test_get_filter_by_type(self, client, admin_user, async_db):
        _, token = admin_user
        await _create_dictionary(async_db, dict_type="alarm_level", dict_code="critical")
        await _create_dictionary(async_db, dict_type="device_type", dict_code="TH")

        resp = await client.get(
            "/api/v1/configs/dictionaries?dict_type=alarm_level",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "alarm_level" in data
        assert "device_type" not in data

    async def test_disabled_not_returned(self, client, admin_user, async_db):
        _, token = admin_user
        await _create_dictionary(async_db, dict_code="enabled", is_enabled=True)
        await _create_dictionary(async_db, dict_code="disabled", is_enabled=False)

        resp = await client.get(
            "/api/v1/configs/dictionaries", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        data = resp.json()
        codes = [item["dict_code"] for items in data.values() for item in items]
        assert "enabled" in codes
        assert "disabled" not in codes


# ==================== GET /api/v1/configs/license ====================


class TestGetLicense:
    """获取授权信息"""

    async def test_get_trial_default(self, client, admin_user):
        """无许可证时返回试用授权"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/configs/license", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["license_key"] == "TRIAL"
        assert data["license_type"] == "trial"
        assert data["status"] == "trial"

    async def test_get_active_license(self, client, admin_user, async_db):
        _, token = admin_user
        await _create_license(async_db)

        resp = await client.get(
            "/api/v1/configs/license", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["license_type"] == "standard"
        assert data["status"] == "active"
        assert data["license_key"].endswith("****")

    async def test_get_expired_license(self, client, admin_user, async_db):
        _, token = admin_user
        await _create_license(
            async_db,
            license_key="STD-EXPIRED123456789",
            expire_date=date(2020, 1, 1),
        )

        resp = await client.get(
            "/api/v1/configs/license", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "expired"


# ==================== POST /api/v1/configs/license/activate ====================


class TestActivateLicense:
    """激活授权许可"""

    async def test_activate_standard(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            "/api/v1/configs/license/activate",
            json={"license_key": "STD-ABCDEFGHIJKLMNOP", "hardware_id": "HW-001"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["license_type"] == "standard"
        assert data["max_points"] == 100

    async def test_activate_enterprise(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            "/api/v1/configs/license/activate",
            json={"license_key": "ENT-ABCDEFGHIJKLMNOP"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["license_type"] == "enterprise"
        assert data["max_points"] == 500

    async def test_activate_basic(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            "/api/v1/configs/license/activate",
            json={"license_key": "BSC-ABCDEFGHIJKLMNOP"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["license_type"] == "basic"

    async def test_activate_unknown_prefix(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            "/api/v1/configs/license/activate",
            json={"license_key": "XXX-ABCDEFGHIJKLMNOP"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["license_type"] == "standard"

    async def test_activate_short_key_rejected(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            "/api/v1/configs/license/activate",
            json={"license_key": "SHORT"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 400

    async def test_activate_already_active(self, client, admin_user, async_db):
        _, token = admin_user
        await _create_license(async_db, license_key="STD-DUPLICATE12345678", is_active=True)

        resp = await client.post(
            "/api/v1/configs/license/activate",
            json={"license_key": "STD-DUPLICATE12345678"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 400
        assert "已激活" in resp.json()["detail"]

    async def test_reactivate_inactive(self, client, admin_user, async_db):
        _, token = admin_user
        await _create_license(async_db, license_key="STD-REACTIVATE1234567", is_active=False)

        resp = await client.post(
            "/api/v1/configs/license/activate",
            json={"license_key": "STD-REACTIVATE1234567"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert "重新激活" in resp.json()["message"]

    async def test_activate_requires_admin(self, client, operator_user):
        _, token = operator_user
        resp = await client.post(
            "/api/v1/configs/license/activate",
            json={"license_key": "STD-ABCDEFGHIJKLMNOP"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 403


# ==================== GET /api/v1/configs/backup ====================


class TestBackupConfigs:
    """导出系统配置备份"""

    async def test_backup_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(
            "/api/v1/configs/backup", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "backup_time" in data
        assert data["version"] == "2.0"
        assert data["configs"] == []
        assert data["dictionaries"] == []

    async def test_backup_with_data(self, client, admin_user, async_db):
        _, token = admin_user
        await _create_config(async_db, config_group="system", config_key="name", config_value="DCIM")
        await _create_dictionary(async_db, dict_type="level", dict_code="c", dict_name="紧急")

        resp = await client.get(
            "/api/v1/configs/backup", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["configs"]) == 1
        assert data["configs"][0]["group"] == "system"
        assert len(data["dictionaries"]) == 1
        assert data["dictionaries"][0]["type"] == "level"

    async def test_backup_requires_admin(self, client, operator_user):
        _, token = operator_user
        resp = await client.get(
            "/api/v1/configs/backup", headers=auth_headers(token)
        )
        assert resp.status_code == 403


# ==================== POST /api/v1/configs/restore ====================


class TestRestoreConfigs:
    """从备份恢复系统配置"""

    async def test_restore_new_configs(self, client, admin_user):
        _, token = admin_user
        backup = {
            "configs": [
                {"group": "system", "key": "name", "value": "恢复系统", "type": "string"},
            ],
            "dictionaries": [
                {"type": "level", "code": "info", "name": "提示", "value": "info", "sort": 0},
            ],
        }
        resp = await client.post(
            "/api/v1/configs/restore",
            json=backup,
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["restored_configs"] == 1
        assert data["restored_dictionaries"] == 1

    async def test_restore_updates_existing(self, client, admin_user, async_db):
        _, token = admin_user
        await _create_config(
            async_db, config_group="system", config_key="name", config_value="旧值"
        )

        backup = {
            "configs": [
                {"group": "system", "key": "name", "value": "新值"},
            ],
            "dictionaries": [],
        }
        resp = await client.post(
            "/api/v1/configs/restore",
            json=backup,
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["restored_configs"] == 1

    async def test_restore_skips_existing_dict(self, client, admin_user, async_db):
        _, token = admin_user
        await _create_dictionary(async_db, dict_type="level", dict_code="info", dict_name="提示")

        backup = {
            "configs": [],
            "dictionaries": [
                {"type": "level", "code": "info", "name": "提示更新"},
            ],
        }
        resp = await client.post(
            "/api/v1/configs/restore",
            json=backup,
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["restored_dictionaries"] == 0

    async def test_restore_empty_backup(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            "/api/v1/configs/restore",
            json={},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["restored_configs"] == 0
        assert resp.json()["restored_dictionaries"] == 0

    async def test_restore_requires_admin(self, client, operator_user):
        _, token = operator_user
        resp = await client.post(
            "/api/v1/configs/restore",
            json={"configs": [], "dictionaries": []},
            headers=auth_headers(token),
        )
        assert resp.status_code == 403
