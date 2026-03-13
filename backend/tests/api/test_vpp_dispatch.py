"""
VPP 调控指令 API 测试

Story 33.2: POST /api/v1/precool/vpp/dispatch 端点测试
"""

import pytest
from unittest.mock import AsyncMock, patch


VPP_API_KEY = "dcim-vpp-default-key-change-me"


def vpp_headers():
    """VPP API Key 请求头"""
    return {"X-VPP-API-Key": VPP_API_KEY}


def _make_dispatch_result(status="accepted", **kwargs):
    """创建模拟调控结果"""
    base = {
        "dispatch_id": "test-uuid",
        "command_type": "down_adjust",
        "target_power_kw": 30.0,
        "duration_minutes": 60,
        "status": status,
        "reject_reason": None,
        "max_adjustable_kw": None,
        "accepted_power_kw": 30.0 if status == "accepted" else None,
        "aborted_schedule_id": None,
    }
    base.update(kwargs)
    return base


VALID_REQUEST = {
    "command_type": "down_adjust",
    "target_power_kw": 30.0,
    "duration_minutes": 60,
    "priority": 1,
}


@pytest.mark.asyncio
class TestVppDispatchAPI:
    """POST /vpp/dispatch API 测试"""

    async def test_missing_api_key_returns_401(self, client):
        """缺少 API Key 返回 401"""
        resp = await client.post(
            "/api/v1/precool/vpp/dispatch",
            json=VALID_REQUEST,
        )
        body = resp.json()
        assert body["code"] == 401
        assert "认证失败" in body["message"]

    async def test_invalid_api_key_returns_401(self, client):
        """无效 API Key 返回 401"""
        resp = await client.post(
            "/api/v1/precool/vpp/dispatch",
            json=VALID_REQUEST,
            headers={"X-VPP-API-Key": "wrong-key"},
        )
        body = resp.json()
        assert body["code"] == 401

    async def test_not_phase_4_returns_403(self, client):
        """非阶段 4 返回 403"""
        with patch(
            "app.services.precool.deployment_phase.deployment_phase_service.get_current_phase",
            new_callable=AsyncMock,
            return_value={"current_phase": 3, "phase_name": "TCL 正式运行"},
        ):
            resp = await client.post(
                "/api/v1/precool/vpp/dispatch",
                json=VALID_REQUEST,
                headers=vpp_headers(),
            )
        body = resp.json()
        assert body["code"] == 403
        assert "阶段 4" in body["message"]

    async def test_invalid_command_type_returns_400(self, client):
        """无效 command_type 返回 400"""
        with patch(
            "app.services.precool.deployment_phase.deployment_phase_service.get_current_phase",
            new_callable=AsyncMock,
            return_value={"current_phase": 4},
        ):
            resp = await client.post(
                "/api/v1/precool/vpp/dispatch",
                json={
                    "command_type": "invalid",
                    "target_power_kw": 10,
                    "duration_minutes": 30,
                },
                headers=vpp_headers(),
            )
        body = resp.json()
        assert body["code"] == 400
        assert "command_type" in body["message"]

    async def test_missing_field_returns_400(self, client):
        """缺少必填字段返回 400"""
        with patch(
            "app.services.precool.deployment_phase.deployment_phase_service.get_current_phase",
            new_callable=AsyncMock,
            return_value={"current_phase": 4},
        ):
            resp = await client.post(
                "/api/v1/precool/vpp/dispatch",
                json={"command_type": "down_adjust", "duration_minutes": 30},
                headers=vpp_headers(),
            )
        body = resp.json()
        assert body["code"] == 400

    async def test_rate_limit_exceeded_returns_429(self, client):
        """超出速率限制返回 429"""
        with patch(
            "app.services.precool.deployment_phase.deployment_phase_service.get_current_phase",
            new_callable=AsyncMock,
            return_value={"current_phase": 4},
        ):
            with patch(
                "app.services.precool.vpp_dispatch.vpp_dispatch_service.check_rate_limit",
                new_callable=AsyncMock,
                return_value=False,
            ):
                resp = await client.post(
                    "/api/v1/precool/vpp/dispatch",
                    json=VALID_REQUEST,
                    headers=vpp_headers(),
                )
        body = resp.json()
        assert body["code"] == 429
        assert "速率限制" in body["message"]

    async def test_accepted_dispatch(self, client):
        """正常指令被接受"""
        with patch(
            "app.services.precool.deployment_phase.deployment_phase_service.get_current_phase",
            new_callable=AsyncMock,
            return_value={"current_phase": 4},
        ):
            with patch(
                "app.services.precool.vpp_dispatch.vpp_dispatch_service.check_rate_limit",
                new_callable=AsyncMock,
                return_value=True,
            ):
                with patch(
                    "app.services.precool.vpp_dispatch.vpp_dispatch_service.validate_and_execute",
                    new_callable=AsyncMock,
                    return_value=_make_dispatch_result("accepted"),
                ):
                    resp = await client.post(
                        "/api/v1/precool/vpp/dispatch",
                        json=VALID_REQUEST,
                        headers=vpp_headers(),
                    )
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["status"] == "accepted"
        assert body["data"]["accepted_power_kw"] == 30.0

    async def test_rejected_dispatch(self, client):
        """超过容量的指令被拒绝"""
        with patch(
            "app.services.precool.deployment_phase.deployment_phase_service.get_current_phase",
            new_callable=AsyncMock,
            return_value={"current_phase": 4},
        ):
            with patch(
                "app.services.precool.vpp_dispatch.vpp_dispatch_service.check_rate_limit",
                new_callable=AsyncMock,
                return_value=True,
            ):
                with patch(
                    "app.services.precool.vpp_dispatch.vpp_dispatch_service.validate_and_execute",
                    new_callable=AsyncMock,
                    return_value=_make_dispatch_result(
                        "rejected",
                        reject_reason="超过可调容量",
                        max_adjustable_kw=50.0,
                    ),
                ):
                    resp = await client.post(
                        "/api/v1/precool/vpp/dispatch",
                        json=VALID_REQUEST,
                        headers=vpp_headers(),
                    )
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["status"] == "rejected"
        assert body["data"]["max_adjustable_kw"] == 50.0

    async def test_service_exception_returns_500(self, client):
        """服务异常返回 500"""
        with patch(
            "app.services.precool.deployment_phase.deployment_phase_service.get_current_phase",
            new_callable=AsyncMock,
            return_value={"current_phase": 4},
        ):
            with patch(
                "app.services.precool.vpp_dispatch.vpp_dispatch_service.check_rate_limit",
                new_callable=AsyncMock,
                return_value=True,
            ):
                with patch(
                    "app.services.precool.vpp_dispatch.vpp_dispatch_service.validate_and_execute",
                    new_callable=AsyncMock,
                    side_effect=Exception("数据库异常"),
                ):
                    resp = await client.post(
                        "/api/v1/precool/vpp/dispatch",
                        json=VALID_REQUEST,
                        headers=vpp_headers(),
                    )
        body = resp.json()
        assert body["code"] == 500
