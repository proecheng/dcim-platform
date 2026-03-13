"""
Story 33.1: VPP 可调容量查询 API — 测试

测试 GET /api/v1/precool/vpp/capacity 端点：
- 部署阶段 4 时正常返回
- 部署阶段非 4 时返回 403
- Redis 缓存命中
- Redis 缓存未命中（实时计算）
- 异常处理
"""

import pytest

from tests.conftest import auth_headers
from unittest.mock import AsyncMock, patch


# ==================== VPP Capacity Tests ====================


@pytest.mark.asyncio
class TestGetVppCapacity:
    """测试 GET /vpp/capacity"""

    async def test_returns_403_when_not_phase_4(self, client, admin_user):
        """部署阶段不是 4 时返回 code=403"""
        _, token = admin_user

        with patch(
            "app.api.v1.precool.deployment_phase_service",
            create=True,
        ) as mock_deploy:
            mock_deploy.get_current_phase = AsyncMock(return_value={
                "current_phase": 2,
                "phase_name": "校准模式",
                "description": "RC 参数校准",
                "updated_at": None,
            })

            # 需要 patch 到正确的导入位置
            with patch(
                "app.services.precool.deployment_phase.deployment_phase_service",
                mock_deploy,
            ):
                resp = await client.get(
                    "/api/v1/precool/vpp/capacity",
                    headers=auth_headers(token),
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 403
        assert "阶段 4" in body["message"]
        assert body["data"] is None

    async def test_returns_cached_data_when_phase_4(self, client, admin_user):
        """部署阶段 4 + 缓存命中时返回缓存数据"""
        _, token = admin_user

        cached_data = {
            "down_adjustable_kw": 100.0,
            "up_adjustable_kw": 50.0,
            "cached_at": "2026-03-13T10:00:00",
            "zones": [],
        }

        with patch(
            "app.services.precool.deployment_phase.deployment_phase_service"
        ) as mock_deploy, patch(
            "app.services.precool.vpp_capacity.vpp_capacity_service"
        ) as mock_vpp:
            mock_deploy.get_current_phase = AsyncMock(return_value={
                "current_phase": 4,
                "phase_name": "VPP 接入",
                "description": "VPP 虚拟电厂集成",
                "updated_at": None,
            })
            mock_vpp.get_cached_capacity = AsyncMock(return_value=cached_data)

            resp = await client.get(
                "/api/v1/precool/vpp/capacity",
                headers=auth_headers(token),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["down_adjustable_kw"] == 100.0
        assert body["data"]["cached_at"] == "2026-03-13T10:00:00"

    async def test_returns_realtime_when_cache_miss(self, client, admin_user):
        """部署阶段 4 + 缓存未命中时实时计算"""
        _, token = admin_user

        realtime_data = {
            "down_adjustable_kw": 200.0,
            "up_adjustable_kw": 100.0,
            "cached_at": None,
            "zones": [],
        }

        with patch(
            "app.services.precool.deployment_phase.deployment_phase_service"
        ) as mock_deploy, patch(
            "app.services.precool.vpp_capacity.vpp_capacity_service"
        ) as mock_vpp:
            mock_deploy.get_current_phase = AsyncMock(return_value={
                "current_phase": 4,
                "phase_name": "VPP 接入",
                "description": "VPP 虚拟电厂集成",
                "updated_at": None,
            })
            mock_vpp.get_cached_capacity = AsyncMock(return_value=None)
            mock_vpp.calculate_capacity = AsyncMock(return_value=realtime_data)

            resp = await client.get(
                "/api/v1/precool/vpp/capacity",
                headers=auth_headers(token),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["down_adjustable_kw"] == 200.0
        assert body["data"]["cached_at"] is None

    async def test_returns_500_on_exception(self, client, admin_user):
        """服务异常时返回 code=500"""
        _, token = admin_user

        with patch(
            "app.services.precool.deployment_phase.deployment_phase_service"
        ) as mock_deploy, patch(
            "app.services.precool.vpp_capacity.vpp_capacity_service"
        ) as mock_vpp:
            mock_deploy.get_current_phase = AsyncMock(return_value={
                "current_phase": 4,
                "phase_name": "VPP 接入",
                "description": "VPP 虚拟电厂集成",
                "updated_at": None,
            })
            mock_vpp.get_cached_capacity = AsyncMock(return_value=None)
            mock_vpp.calculate_capacity = AsyncMock(side_effect=Exception("db error"))

            resp = await client.get(
                "/api/v1/precool/vpp/capacity",
                headers=auth_headers(token),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 500
        assert "VPP" in body["message"]

    async def test_no_auth_returns_401(self, client):
        """未认证请求返回 401"""
        resp = await client.get("/api/v1/precool/vpp/capacity")
        assert resp.status_code in (401, 403)

    async def test_deployment_phase_check_failure_returns_500(self, client, admin_user):
        """部署阶段检查异常时返回 500"""
        _, token = admin_user

        with patch(
            "app.services.precool.deployment_phase.deployment_phase_service"
        ) as mock_deploy:
            mock_deploy.get_current_phase = AsyncMock(
                side_effect=Exception("config table missing")
            )

            resp = await client.get(
                "/api/v1/precool/vpp/capacity",
                headers=auth_headers(token),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 500
        assert "部署阶段" in body["message"]
