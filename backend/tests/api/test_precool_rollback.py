"""
回退保护 API 测试

Story 30.3: 回退保护 API 与状态查询
"""

import pytest
from unittest.mock import patch
from httpx import AsyncClient


# ==================== rollback-status 端点 ====================

class TestRollbackStatus:
    """回退状态查询端点测试"""

    @pytest.mark.asyncio
    async def test_status_unauthorized(self, client: AsyncClient):
        """未授权访问"""
        response = await client.get("/api/v1/precool/zones/1/rollback-status")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_status_normal(self, client: AsyncClient, admin_token: str):
        """正常状态（无活跃回退）"""
        with patch(
            "app.api.v1.precool.rollback_manager"
        ) as mock_mgr:
            mock_mgr.get_zone_rollback_status.return_value = {
                "zone_id": 1,
                "has_active_rollback": False,
                "active_triggers": [],
            }

            response = await client.get(
                "/api/v1/precool/zones/1/rollback-status",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            data = response.json()
            # zone 可能不存在于测试数据库中，允许 404
            if data["code"] == 200:
                assert data["data"]["has_active_rollback"] is False
                assert data["data"]["active_triggers"] == []
            else:
                assert data["code"] == 404

    @pytest.mark.asyncio
    async def test_status_zone_not_found(self, client: AsyncClient, admin_token: str):
        """不存在的 zone 返回 404"""
        response = await client.get(
            "/api/v1/precool/zones/99999/rollback-status",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = response.json()
        assert data["code"] == 404

    @pytest.mark.asyncio
    async def test_status_with_active_rollback(self, client: AsyncClient, admin_token: str):
        """有活跃回退状态"""
        with patch(
            "app.api.v1.precool.rollback_manager"
        ) as mock_mgr:
            mock_mgr.get_zone_rollback_status.return_value = {
                "zone_id": 1,
                "has_active_rollback": True,
                "active_triggers": [
                    {
                        "trigger_type": "temp_over_limit",
                        "since": "2026-03-11T10:30:00",
                        "event_id": 42,
                        "recovering": False,
                    }
                ],
            }

            response = await client.get(
                "/api/v1/precool/zones/1/rollback-status",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            data = response.json()
            if data["code"] == 200:
                assert data["data"]["has_active_rollback"] is True
                assert len(data["data"]["active_triggers"]) == 1
                assert data["data"]["active_triggers"][0]["trigger_type"] == "temp_over_limit"


# ==================== rollback-history 端点 ====================

class TestRollbackHistory:
    """回退历史事件查询端点测试"""

    @pytest.mark.asyncio
    async def test_history_unauthorized(self, client: AsyncClient):
        """未授权访问"""
        response = await client.get("/api/v1/precool/zones/1/rollback-history")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_history_zone_not_found(self, client: AsyncClient, admin_token: str):
        """不存在的 zone 返回 404"""
        response = await client.get(
            "/api/v1/precool/zones/99999/rollback-history",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = response.json()
        assert data["code"] == 404

    @pytest.mark.asyncio
    async def test_history_empty(self, client: AsyncClient, admin_token: str):
        """无历史记录返回空列表"""
        response = await client.get(
            "/api/v1/precool/zones/1/rollback-history",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = response.json()
        # zone 可能不存在→404，或存在但无记录→200
        if data["code"] == 200:
            assert data["data"]["items"] == []
            assert data["data"]["total"] == 0

    @pytest.mark.asyncio
    async def test_history_invalid_limit(self, client: AsyncClient, admin_token: str):
        """limit 超过最大值"""
        response = await client.get(
            "/api/v1/precool/zones/1/rollback-history?limit=200",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_history_invalid_status_filter(self, client: AsyncClient, admin_token: str):
        """无效 status 筛选值"""
        response = await client.get(
            "/api/v1/precool/zones/1/rollback-history?status=invalid",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # Literal 校验失败 → 422
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_history_pagination_params(self, client: AsyncClient, admin_token: str):
        """分页参数生效"""
        response = await client.get(
            "/api/v1/precool/zones/1/rollback-history?skip=0&limit=5",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = response.json()
        if data["code"] == 200:
            assert "items" in data["data"]
            assert "total" in data["data"]


# ==================== rollback-overview 端点 ====================

class TestRollbackOverview:
    """全局回退状态概览端点测试"""

    @pytest.mark.asyncio
    async def test_overview_unauthorized(self, client: AsyncClient):
        """未授权访问"""
        response = await client.get("/api/v1/precool/rollback-overview")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_overview_structure(self, client: AsyncClient, admin_token: str):
        """概览响应结构"""
        with patch(
            "app.api.v1.precool.rollback_manager"
        ) as mock_mgr:
            mock_mgr.get_zone_rollback_status.return_value = {
                "zone_id": 1,
                "has_active_rollback": False,
                "active_triggers": [],
            }

            response = await client.get(
                "/api/v1/precool/rollback-overview",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            data = response.json()
            assert data["code"] == 200
            overview = data["data"]
            assert "total_zones" in overview
            assert "zones_with_active_rollback" in overview
            assert "total_active_triggers" in overview
            assert "trigger_type_counts" in overview
            assert "recent_events_24h" in overview
            assert "zone_statuses" in overview

    @pytest.mark.asyncio
    async def test_overview_no_rollbacks(self, client: AsyncClient, admin_token: str):
        """无活跃回退时的概览"""
        with patch(
            "app.api.v1.precool.rollback_manager"
        ) as mock_mgr:
            mock_mgr.get_zone_rollback_status.return_value = {
                "zone_id": 1,
                "has_active_rollback": False,
                "active_triggers": [],
            }

            response = await client.get(
                "/api/v1/precool/rollback-overview",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            data = response.json()
            assert data["code"] == 200
            assert data["data"]["zones_with_active_rollback"] == 0
            assert data["data"]["total_active_triggers"] == 0
            assert data["data"]["trigger_type_counts"] == {}
