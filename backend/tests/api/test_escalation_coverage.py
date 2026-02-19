"""
告警升级规则 API 覆盖率测试 — 使用 conftest fixtures
"""
import pytest

from tests.conftest import auth_headers
from app.models.alarm import AlarmEscalation


# ==================== 辅助函数 ====================


async def _create_rule(async_db, **overrides) -> AlarmEscalation:
    """在数据库中直接创建升级规则"""
    defaults = dict(
        rule_name="测试规则",
        source_level="minor",
        timeout_minutes=30,
        target_level="major",
        notify_user_ids="1,2",
        is_enabled=True,
        description="测试描述",
    )
    defaults.update(overrides)
    rule = AlarmEscalation(**defaults)
    async_db.add(rule)
    await async_db.flush()
    return rule


# ==================== GET /api/v1/escalations ====================


class TestListEscalations:
    """获取升级规则列表"""

    async def test_list_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/escalations", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_list_with_data(self, client, admin_user, async_db):
        _, token = admin_user
        await _create_rule(async_db, rule_name="规则A")
        await _create_rule(async_db, rule_name="规则B")

        resp = await client.get("/api/v1/escalations", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_list_filter_source_level(self, client, admin_user, async_db):
        _, token = admin_user
        await _create_rule(async_db, source_level="minor", target_level="major")
        await _create_rule(async_db, source_level="major", target_level="critical")

        resp = await client.get(
            "/api/v1/escalations?source_level=minor", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["source_level"] == "minor"

    async def test_list_filter_is_enabled(self, client, admin_user, async_db):
        _, token = admin_user
        await _create_rule(async_db, is_enabled=True, rule_name="启用")
        await _create_rule(async_db, is_enabled=False, rule_name="禁用")

        resp = await client.get(
            "/api/v1/escalations?is_enabled=true", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["rule_name"] == "启用"

    async def test_list_pagination(self, client, admin_user, async_db):
        _, token = admin_user
        for i in range(5):
            await _create_rule(async_db, rule_name=f"规则{i}")

        resp = await client.get(
            "/api/v1/escalations?page=2&page_size=2", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert data["page"] == 2
        assert data["page_size"] == 2
        assert len(data["items"]) == 2


# ==================== POST /api/v1/escalations ====================


class TestCreateEscalation:
    """创建升级规则"""

    async def test_create_success(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            "/api/v1/escalations",
            json={
                "rule_name": "新规则",
                "source_level": "minor",
                "timeout_minutes": 15,
                "target_level": "major",
                "notify_user_ids": [1, 2],
                "description": "测试创建",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rule_name"] == "新规则"
        assert data["source_level"] == "minor"
        assert data["timeout_minutes"] == 15
        assert data["target_level"] == "major"
        assert data["notify_user_ids"] == [1, 2]
        assert data["is_enabled"] is True
        assert data["id"] > 0

    async def test_create_minimal(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            "/api/v1/escalations",
            json={
                "rule_name": "最小规则",
                "source_level": "info",
                "timeout_minutes": 60,
                "target_level": "minor",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notify_user_ids"] == []

    async def test_create_requires_operator(self, client, viewer_user):
        _, token = viewer_user
        resp = await client.post(
            "/api/v1/escalations",
            json={
                "rule_name": "无权限",
                "source_level": "minor",
                "timeout_minutes": 30,
                "target_level": "major",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 403


# ==================== GET /api/v1/escalations/{id} ====================


class TestGetEscalation:
    """获取升级规则详情"""

    async def test_get_success(self, client, admin_user, async_db):
        _, token = admin_user
        rule = await _create_rule(async_db, rule_name="详情测试")

        resp = await client.get(
            f"/api/v1/escalations/{rule.id}", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        assert resp.json()["rule_name"] == "详情测试"

    async def test_get_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(
            "/api/v1/escalations/99999", headers=auth_headers(token)
        )
        assert resp.status_code == 404


# ==================== PUT /api/v1/escalations/{id} ====================


class TestUpdateEscalation:
    """更新升级规则"""

    async def test_update_success(self, client, admin_user, async_db):
        _, token = admin_user
        rule = await _create_rule(async_db)

        resp = await client.put(
            f"/api/v1/escalations/{rule.id}",
            json={"rule_name": "已更新", "timeout_minutes": 45, "notify_user_ids": [3, 4]},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rule_name"] == "已更新"
        assert data["timeout_minutes"] == 45
        assert data["notify_user_ids"] == [3, 4]

    async def test_update_partial(self, client, admin_user, async_db):
        _, token = admin_user
        rule = await _create_rule(async_db, rule_name="原名称", timeout_minutes=30)

        resp = await client.put(
            f"/api/v1/escalations/{rule.id}",
            json={"timeout_minutes": 60},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rule_name"] == "原名称"
        assert data["timeout_minutes"] == 60

    async def test_update_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            "/api/v1/escalations/99999",
            json={"rule_name": "不存在"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_update_requires_operator(self, client, viewer_user, async_db):
        _, token = viewer_user
        rule = await _create_rule(async_db)

        resp = await client.put(
            f"/api/v1/escalations/{rule.id}",
            json={"rule_name": "无权限"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 403


# ==================== DELETE /api/v1/escalations/{id} ====================


class TestDeleteEscalation:
    """删除升级规则"""

    async def test_delete_success(self, client, admin_user, async_db):
        _, token = admin_user
        rule = await _create_rule(async_db)

        resp = await client.delete(
            f"/api/v1/escalations/{rule.id}", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        assert "已删除" in resp.json()["message"]

        # 确认已删除
        resp2 = await client.get(
            f"/api/v1/escalations/{rule.id}", headers=auth_headers(token)
        )
        assert resp2.status_code == 404

    async def test_delete_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.delete(
            "/api/v1/escalations/99999", headers=auth_headers(token)
        )
        assert resp.status_code == 404


# ==================== PUT /api/v1/escalations/{id}/toggle ====================


class TestToggleEscalation:
    """切换升级规则启用状态"""

    async def test_toggle_disable(self, client, admin_user, async_db):
        _, token = admin_user
        rule = await _create_rule(async_db, is_enabled=True)

        resp = await client.put(
            f"/api/v1/escalations/{rule.id}/toggle", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        assert resp.json()["is_enabled"] is False

    async def test_toggle_enable(self, client, admin_user, async_db):
        _, token = admin_user
        rule = await _create_rule(async_db, is_enabled=False)

        resp = await client.put(
            f"/api/v1/escalations/{rule.id}/toggle", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        assert resp.json()["is_enabled"] is True

    async def test_toggle_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            "/api/v1/escalations/99999/toggle", headers=auth_headers(token)
        )
        assert resp.status_code == 404
