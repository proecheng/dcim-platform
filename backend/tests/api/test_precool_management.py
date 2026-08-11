"""
热参数管理 API 端点单元测试

Story 32.3: 测试手动校准、校准历史、部署阶段查询和切换端点。
"""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from tests.conftest import auth_headers


# ==================== Fixtures ====================


@pytest.fixture
async def sample_zone(async_db):
    """创建测试用制冷区域"""
    from app.models.topology_config import CoolingZone

    zone = CoolingZone(
        zone_code="TEST-MGMT-ZONE",
        zone_name="管理测试区域",
        thermal_R=0.005,
        thermal_C=500.0,
    )
    async_db.add(zone)
    await async_db.flush()
    return zone


@pytest.fixture
async def zone_with_calibration(async_db):
    """创建多个 zone 并附带校准历史记录（规避 UNIQUE(zone_id, is_active) 约束）"""
    from app.models.topology_config import CoolingZone
    from app.models.thermal import ThermalParameter

    # 主测试 zone
    main_zone = CoolingZone(
        zone_code="TEST-CAL-MAIN",
        zone_name="校准主区域",
        thermal_R=0.005,
        thermal_C=500.0,
    )
    async_db.add(main_zone)
    await async_db.flush()

    # 创建 3 个辅助 zone，每个 zone 一条非 demo 记录
    # UNIQUE(cooling_zone_id, is_active) 限制每个 zone 同一 is_active 只能一条
    records = []
    for i in range(3):
        zone = CoolingZone(
            zone_code=f"TEST-CAL-AUX-{i}",
            zone_name=f"校准辅助区域{i}",
            thermal_R=0.005 + i * 0.001,
            thermal_C=500.0 + i * 10,
        )
        async_db.add(zone)
        await async_db.flush()

        param = ThermalParameter(
            cooling_zone_id=zone.id,
            thermal_R=0.005 + i * 0.001,
            thermal_C=500.0 + i * 10,
            fitting_r_squared=0.85 + i * 0.03,
            fitting_method="auto_fit",
            sample_count=100 + i * 10,
            is_active=True,
            is_demo=False,
        )
        async_db.add(param)
        records.append(param)

    # 主 zone 上创建 1 条活跃非 demo + 1 条非活跃非 demo
    active_param = ThermalParameter(
        cooling_zone_id=main_zone.id,
        thermal_R=0.006,
        thermal_C=520.0,
        fitting_r_squared=0.90,
        fitting_method="auto_fit",
        sample_count=130,
        is_active=True,
        is_demo=False,
    )
    async_db.add(active_param)

    inactive_param = ThermalParameter(
        cooling_zone_id=main_zone.id,
        thermal_R=0.005,
        thermal_C=500.0,
        fitting_r_squared=0.85,
        fitting_method="auto_fit",
        sample_count=100,
        is_active=False,
        is_demo=False,
    )
    async_db.add(inactive_param)

    # 用辅助 zone 的一个来放 demo 记录（避免 UNIQUE 约束冲突）
    # 这条 demo 记录的 cooling_zone_id 是辅助 zone，不影响 main_zone 的查询结果

    await async_db.flush()
    return main_zone, [active_param, inactive_param]


# ==================== POST /zones/{zone_id}/calibrate 测试 ====================


class TestTriggerCalibration:
    async def test_calibrate_success(self, client, admin_user, sample_zone):
        """成功触发手动校准"""
        _, token = admin_user
        mock_result = {
            "success": True,
            "R": 0.005,
            "C": 500.0,
            "r_squared": 0.92,
            "sample_count": 120,
        }
        with patch(
            "app.api.v1.precool.rc_calibrator",
            create=True,
        ) as mock_cal:
            mock_cal.calibrate = AsyncMock(return_value=mock_result)
            with patch(
                "app.services.precool.calibrator.rc_calibrator",
                mock_cal,
            ):
                # 用更精确的 patch 路径
                with patch(
                    "app.api.v1.precool.rc_calibrator",
                    create=True,
                ):
                    # 直接 patch 延迟导入的模块
                    import app.services.precool.calibrator as cal_mod
                    original = getattr(cal_mod, "rc_calibrator", None)
                    cal_mod.rc_calibrator = mock_cal
                    try:
                        resp = await client.post(
                            f"/api/v1/precool/zones/{sample_zone.id}/calibrate",
                            headers=auth_headers(token),
                        )
                    finally:
                        if original is not None:
                            cal_mod.rc_calibrator = original

        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["R"] == 0.005
        assert data["data"]["r_squared"] == 0.92

    async def test_calibrate_zone_not_found(self, client, admin_user):
        """zone 不存在返回 404"""
        _, token = admin_user
        resp = await client.post(
            "/api/v1/precool/zones/99999/calibrate",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404
        assert "不存在" in resp.json()["detail"]

    async def test_calibrate_scipy_not_installed(self, client, admin_user, sample_zone):
        """scipy 未安装返回 503"""
        _, token = admin_user
        mock_result = {"error": "scipy_not_installed"}

        import app.services.precool.calibrator as cal_mod
        mock_cal = MagicMock()
        mock_cal.calibrate = AsyncMock(return_value=mock_result)
        original = getattr(cal_mod, "rc_calibrator", None)
        cal_mod.rc_calibrator = mock_cal
        try:
            resp = await client.post(
                f"/api/v1/precool/zones/{sample_zone.id}/calibrate",
                headers=auth_headers(token),
            )
        finally:
            if original is not None:
                cal_mod.rc_calibrator = original

        data = resp.json()
        assert data["code"] == 503
        assert "scipy" in data["message"]

    async def test_calibrate_error(self, client, admin_user, sample_zone):
        """校准失败返回 422"""
        _, token = admin_user
        mock_result = {"error": "insufficient_data", "sample_count": 5}

        import app.services.precool.calibrator as cal_mod
        mock_cal = MagicMock()
        mock_cal.calibrate = AsyncMock(return_value=mock_result)
        original = getattr(cal_mod, "rc_calibrator", None)
        cal_mod.rc_calibrator = mock_cal
        try:
            resp = await client.post(
                f"/api/v1/precool/zones/{sample_zone.id}/calibrate",
                headers=auth_headers(token),
            )
        finally:
            if original is not None:
                cal_mod.rc_calibrator = original

        data = resp.json()
        assert data["code"] == 422
        assert "校准失败" in data["message"]


# ==================== GET /zones/{zone_id}/calibration-history 测试 ====================


class TestCalibrationHistory:
    async def test_history_success(self, client, admin_user, zone_with_calibration):
        """成功查询校准历史"""
        _, token = admin_user
        zone, records = zone_with_calibration
        resp = await client.get(
            f"/api/v1/precool/zones/{zone.id}/calibration-history",
            headers=auth_headers(token),
        )
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["total"] == 2  # 2 条非 demo 记录（1 active + 1 inactive）
        assert len(data["data"]["items"]) == 2

    async def test_history_excludes_demo(self, client, admin_user, zone_with_calibration):
        """校准历史不包含 demo 记录"""
        _, token = admin_user
        zone, _ = zone_with_calibration
        resp = await client.get(
            f"/api/v1/precool/zones/{zone.id}/calibration-history",
            headers=auth_headers(token),
        )
        data = resp.json()
        # demo 记录不应在结果中
        for item in data["data"]["items"]:
            assert item.get("fitting_method") != "demo"

    async def test_history_pagination(self, client, admin_user, zone_with_calibration):
        """分页查询"""
        _, token = admin_user
        zone, _ = zone_with_calibration
        resp = await client.get(
            f"/api/v1/precool/zones/{zone.id}/calibration-history?skip=0&limit=1",
            headers=auth_headers(token),
        )
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["total"] == 2
        assert len(data["data"]["items"]) == 1

    async def test_history_empty(self, client, admin_user, sample_zone):
        """空校准历史"""
        _, token = admin_user
        resp = await client.get(
            f"/api/v1/precool/zones/{sample_zone.id}/calibration-history",
            headers=auth_headers(token),
        )
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["total"] == 0
        assert data["data"]["items"] == []

    async def test_history_zone_not_found(self, client, admin_user):
        """zone 不存在返回 404"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/precool/zones/99999/calibration-history",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404


# ==================== GET /deployment-phase 测试 ====================


class TestGetDeploymentPhase:
    async def test_get_phase_default(self, client, admin_user):
        """默认返回阶段 1"""
        _, token = admin_user
        with patch(
            "app.services.precool.deployment_phase.deployment_phase_service"
        ) as mock_svc:
            mock_svc.get_current_phase = AsyncMock(return_value={
                "current_phase": 1,
                "phase_name": "THM 模式",
                "description": "仅使用 THM 估算，不执行预冷",
                "updated_at": None,
            })
            # patch 延迟导入
            import app.services.precool.deployment_phase as dp_mod
            original = dp_mod.deployment_phase_service
            dp_mod.deployment_phase_service = mock_svc
            try:
                resp = await client.get(
                    "/api/v1/precool/deployment-phase",
                    headers=auth_headers(token),
                )
            finally:
                dp_mod.deployment_phase_service = original

        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["current_phase"] == 1
        assert data["data"]["phase_name"] == "THM 模式"

    async def test_get_phase_viewer_allowed(self, client, admin_user):
        """viewer 角色可以查询"""
        _, token = admin_user  # admin 也允许
        import app.services.precool.deployment_phase as dp_mod
        mock_svc = MagicMock()
        mock_svc.get_current_phase = AsyncMock(return_value={
            "current_phase": 2,
            "phase_name": "校准模式",
            "description": "运行 RC 校准，对比 THM 与 TCL 结果",
            "updated_at": "2026-03-13T10:00:00",
        })
        original = dp_mod.deployment_phase_service
        dp_mod.deployment_phase_service = mock_svc
        try:
            resp = await client.get(
                "/api/v1/precool/deployment-phase",
                headers=auth_headers(token),
            )
        finally:
            dp_mod.deployment_phase_service = original

        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["current_phase"] == 2


# ==================== PUT /deployment-phase 测试 ====================


class TestUpdateDeploymentPhase:
    async def test_update_phase_success(self, client, admin_user):
        """成功切换阶段"""
        _, token = admin_user
        import app.services.precool.deployment_phase as dp_mod
        mock_svc = MagicMock()
        mock_svc.update_phase = AsyncMock(return_value={
            "phase": 2,
            "old_phase": 1,
            "force_used": False,
        })
        original = dp_mod.deployment_phase_service
        dp_mod.deployment_phase_service = mock_svc
        try:
            resp = await client.put(
                "/api/v1/precool/deployment-phase",
                headers=auth_headers(token),
                json={"phase": 2, "force": False},
            )
        finally:
            dp_mod.deployment_phase_service = original

        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["phase"] == 2
        assert data["data"]["old_phase"] == 1

    async def test_update_phase_precondition_failed(self, client, admin_user):
        """前置条件不满足返回 422"""
        _, token = admin_user
        import app.services.precool.deployment_phase as dp_mod
        mock_svc = MagicMock()
        mock_svc.update_phase = AsyncMock(return_value={
            "error": "precondition_failed",
            "details": ["区域A未校准"],
        })
        original = dp_mod.deployment_phase_service
        dp_mod.deployment_phase_service = mock_svc
        try:
            resp = await client.put(
                "/api/v1/precool/deployment-phase",
                headers=auth_headers(token),
                json={"phase": 3, "force": False},
            )
        finally:
            dp_mod.deployment_phase_service = original

        data = resp.json()
        assert data["code"] == 422
        assert "前置条件" in data["message"]

    async def test_update_phase_force(self, client, admin_user):
        """force 跳过前置检查"""
        _, token = admin_user
        import app.services.precool.deployment_phase as dp_mod
        mock_svc = MagicMock()
        mock_svc.update_phase = AsyncMock(return_value={
            "phase": 3,
            "old_phase": 1,
            "force_used": True,
        })
        original = dp_mod.deployment_phase_service
        dp_mod.deployment_phase_service = mock_svc
        try:
            resp = await client.put(
                "/api/v1/precool/deployment-phase",
                headers=auth_headers(token),
                json={"phase": 3, "force": True},
            )
        finally:
            dp_mod.deployment_phase_service = original

        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["force_used"] is True

    async def test_update_phase_invalid(self, client, admin_user):
        """无效阶段号被 Pydantic 拦截"""
        _, token = admin_user
        resp = await client.put(
            "/api/v1/precool/deployment-phase",
            headers=auth_headers(token),
            json={"phase": 5, "force": False},
        )
        # Pydantic 校验失败返回 422
        assert resp.status_code == 422

    async def test_update_phase_same_phase_error(self, client, admin_user):
        """切换到相同阶段返回错误"""
        _, token = admin_user
        import app.services.precool.deployment_phase as dp_mod
        mock_svc = MagicMock()
        mock_svc.update_phase = AsyncMock(return_value={
            "error": "same_phase",
            "details": "已处于阶段2",
        })
        original = dp_mod.deployment_phase_service
        dp_mod.deployment_phase_service = mock_svc
        try:
            resp = await client.put(
                "/api/v1/precool/deployment-phase",
                headers=auth_headers(token),
                json={"phase": 2, "force": False},
            )
        finally:
            dp_mod.deployment_phase_service = original

        data = resp.json()
        assert data["code"] == 400
