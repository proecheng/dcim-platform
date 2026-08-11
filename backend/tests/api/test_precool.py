"""
预冷系统 API 测试

Story 29.4: 温度预测 API 端点
"""

import pytest
from httpx import AsyncClient

from app.models.topology_config import CoolingZone


async def _create_zone(async_db, code: str = "TEST-PRECOOL") -> CoolingZone:
    zone = CoolingZone(zone_code=code, zone_name="预冷测试区域")
    async_db.add(zone)
    await async_db.flush()
    return zone


# ==================== predict 端点 ====================

class TestPredict:
    """温度预测端点测试"""

    @pytest.mark.asyncio
    async def test_predict_unauthorized(self, client: AsyncClient):
        """未授权访问"""
        response = await client.post(
            "/api/v1/precool/zones/1/predict",
            json={"hours": 1.0},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_predict_zone_not_found(self, client: AsyncClient, admin_token: str):
        """预测不存在的 zone"""
        response = await client.post(
            "/api/v1/precool/zones/99999/predict",
            json={"hours": 1.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_predict_invalid_hours(self, client: AsyncClient, admin_token: str):
        """hours 超出范围"""
        response = await client.post(
            "/api/v1/precool/zones/1/predict",
            json={"hours": 0.1},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # Pydantic 校验失败 → 422
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_predict_hours_too_large(self, client: AsyncClient, admin_token: str):
        """hours 超过最大值"""
        response = await client.post(
            "/api/v1/precool/zones/1/predict",
            json={"hours": 25.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_predict_default_hours(self, client: AsyncClient, admin_token: str, async_db, monkeypatch):
        """默认 hours 参数"""
        async def _insufficient_data(*_args, **_kwargs):
            return {"error": "insufficient_data"}

        monkeypatch.setattr(
            "app.services.precool.thermal_model.ThermalModel.predict_temperature", _insufficient_data
        )
        zone = await _create_zone(async_db)
        response = await client.post(
            f"/api/v1/precool/zones/{zone.id}/predict",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = response.json()
        # 端点应该正常响应（可能因为没有数据返回错误码）
        assert "code" in data

    @pytest.mark.asyncio
    async def test_predict_with_schedule(self, client: AsyncClient, admin_token: str, async_db, monkeypatch):
        """带制冷功率计划的预测"""
        async def _insufficient_data(*_args, **_kwargs):
            return {"error": "insufficient_data"}

        monkeypatch.setattr(
            "app.services.precool.thermal_model.ThermalModel.predict_temperature", _insufficient_data
        )
        zone = await _create_zone(async_db)
        response = await client.post(
            f"/api/v1/precool/zones/{zone.id}/predict",
            json={"hours": 0.5, "q_cool_schedule": [100.0] * 6},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = response.json()
        assert "code" in data

    @pytest.mark.asyncio
    async def test_predict_schedule_length_mismatch(
        self, client: AsyncClient, admin_token: str, async_db, monkeypatch
    ):
        """制冷功率计划长度不匹配"""
        async def _invalid_schedule(*_args, **_kwargs):
            return {"error": "invalid_q_cool_schedule"}

        monkeypatch.setattr(
            "app.services.precool.thermal_model.ThermalModel.predict_temperature", _invalid_schedule
        )
        zone = await _create_zone(async_db)
        response = await client.post(
            f"/api/v1/precool/zones/{zone.id}/predict",
            json={"hours": 1.0, "q_cool_schedule": [100.0] * 3},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = response.json()
        # 长度不匹配 → 422 或者 ThermalModel 内部返回 error
        assert data["code"] in (422, 500, 503)


# ==================== parameters 端点 ====================

class TestParameters:
    """热参数查询端点测试"""

    @pytest.mark.asyncio
    async def test_parameters_unauthorized(self, client: AsyncClient):
        """未授权访问"""
        response = await client.get("/api/v1/precool/zones/1/parameters")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_parameters_empty_zone(self, client: AsyncClient, admin_token: str, async_db):
        """查询无参数的真实 zone（返回空列表）"""
        zone = await _create_zone(async_db)
        response = await client.get(
            f"/api/v1/precool/zones/{zone.id}/parameters",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["items"] == []
        assert data["data"]["total"] == 0

    @pytest.mark.asyncio
    async def test_parameters_pagination(self, client: AsyncClient, admin_token: str, async_db):
        """分页参数"""
        zone = await _create_zone(async_db)
        response = await client.get(
            f"/api/v1/precool/zones/{zone.id}/parameters?skip=0&limit=5",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = response.json()
        assert data["code"] == 200
        assert "items" in data["data"]
        assert "total" in data["data"]

    @pytest.mark.asyncio
    async def test_parameters_invalid_limit(self, client: AsyncClient, admin_token: str):
        """limit 超过最大值"""
        response = await client.get(
            "/api/v1/precool/zones/1/parameters?limit=200",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422


# ==================== validation 端点 ====================

class TestValidation:
    """模型验证报告端点测试"""

    @pytest.mark.asyncio
    async def test_validation_unauthorized(self, client: AsyncClient):
        """未授权访问"""
        response = await client.get("/api/v1/precool/zones/1/validation")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_validation_no_data(self, client: AsyncClient, admin_token: str, async_db):
        """无预测记录时返回 null"""
        zone = await _create_zone(async_db)
        response = await client.get(
            f"/api/v1/precool/zones/{zone.id}/validation",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = response.json()
        assert data["code"] == 200
        report = data["data"]
        assert report["mae_1h"] is None
        assert report["mae_3h"] is None
        assert report["max_deviation"] is None
        assert report["sample_count"] == 0
        assert report["period_days"] == 7

    @pytest.mark.asyncio
    async def test_validation_zone_id_in_response(self, client: AsyncClient, admin_token: str, async_db):
        """响应包含 zone_id"""
        zone = await _create_zone(async_db)
        response = await client.get(
            f"/api/v1/precool/zones/{zone.id}/validation",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["zone_id"] == zone.id


# ==================== dashboard 端点 ====================

class TestDashboard:
    """仪表盘端点测试"""

    @pytest.mark.asyncio
    async def test_dashboard_unauthorized(self, client: AsyncClient):
        """未授权访问"""
        response = await client.get("/api/v1/precool/dashboard")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_dashboard_structure(self, client: AsyncClient, admin_token: str):
        """仪表盘响应结构"""
        response = await client.get(
            "/api/v1/precool/dashboard",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = response.json()
        assert data["code"] == 200
        dashboard = data["data"]
        assert "zones" in dashboard
        assert "status_summary" in dashboard
        assert "today_savings" in dashboard
        assert dashboard["today_savings"] == 0.0

    @pytest.mark.asyncio
    async def test_dashboard_status_summary(self, client: AsyncClient, admin_token: str):
        """仪表盘状态统计"""
        response = await client.get(
            "/api/v1/precool/dashboard",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = response.json()
        summary = data["data"]["status_summary"]
        assert "total_zones" in summary
        assert "thm_zones" in summary
        assert "tcl_zones" in summary
        assert "offline_zones" in summary
        assert summary["total_zones"] == summary["thm_zones"] + summary["tcl_zones"]
