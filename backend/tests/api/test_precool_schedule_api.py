"""
预冷计划 API 端点单元测试

Story 31.3: 测试 4 个预冷计划 REST API 端点的功能、权限和错误处理。
"""

import pytest
from datetime import date, time, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import auth_headers


# ==================== Fixtures ====================


@pytest.fixture
async def sample_zone(async_db):
    """创建测试用制冷区域"""
    from app.models.topology_config import CoolingZone

    zone = CoolingZone(
        zone_code="TEST-ZONE-A",
        zone_name="测试区域A",
        thermal_R=0.005,
        thermal_C=500.0,
    )
    async_db.add(zone)
    await async_db.flush()
    return zone


@pytest.fixture
async def sample_plan(async_db, sample_zone):
    """创建测试用预冷计划（pending 状态）"""
    from app.models.thermal import PrecoolSchedule

    plan = PrecoolSchedule(
        cooling_zone_id=sample_zone.id,
        schedule_date=date(2026, 3, 12),
        precool_start_time=time(0, 0),
        precool_end_time=time(8, 0),
        target_temp=18.0,
        peak_start_time=time(11, 0),
        peak_end_time=time(21, 0),
        planned_savings_kwh=50.0,
        status="pending",
        temperature_trajectory={
            "predicted": [22.0 - i * 0.01 for i in range(288)],
            "timestamps": [f"{i * 5 // 60:02d}:{i * 5 % 60:02d}" for i in range(288)],
            "q_cool": [100.0 + (i % 20) for i in range(288)],
            "prices": [0.25] * 288,
        },
        is_validated=True,
    )
    async_db.add(plan)
    await async_db.flush()
    return plan


@pytest.fixture
async def executing_plan(async_db, sample_zone):
    """创建 executing 状态的预冷计划"""
    from app.models.thermal import PrecoolSchedule

    plan = PrecoolSchedule(
        cooling_zone_id=sample_zone.id,
        schedule_date=date(2026, 3, 13),
        precool_start_time=time(0, 0),
        precool_end_time=time(8, 0),
        target_temp=18.0,
        peak_start_time=time(11, 0),
        peak_end_time=time(21, 0),
        planned_savings_kwh=45.0,
        status="executing",
        temperature_trajectory={"predicted": [22.0] * 288},
    )
    async_db.add(plan)
    await async_db.flush()
    return plan


# ==================== POST /zones/{zone_id}/schedule 测试 ====================


class TestCreateSchedule:
    async def test_create_schedule_success(self, client, admin_user, sample_zone):
        """成功生成预冷计划"""
        _, token = admin_user
        from app.models.thermal import PrecoolSchedule
        from app.services.precool.scheduler import PrecoolPlanResult

        mock_plan = PrecoolSchedule(
            cooling_zone_id=sample_zone.id,
            schedule_date=date(2026, 3, 15),
            precool_start_time=time(0, 0),
            precool_end_time=time(8, 0),
            target_temp=18.0,
            peak_start_time=time(11, 0),
            peak_end_time=time(21, 0),
            planned_savings_kwh=50.0,
            status="pending",
            temperature_trajectory={"predicted": [22.0] * 10},
            is_validated=True,
        )
        mock_result = PrecoolPlanResult(schedule=mock_plan)

        with patch(
            "app.services.precool.scheduler.load_time_slots_from_db",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "app.services.precool.scheduler.PrecoolScheduler.generate_precool_plan",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await client.post(
                f"/api/v1/precool/zones/{sample_zone.id}/schedule",
                json={"schedule_date": "2026-03-15"},
                headers=auth_headers(token),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["cooling_zone_id"] == sample_zone.id
        assert data["data"]["status"] == "pending"

    async def test_create_schedule_zone_not_found(self, client, admin_user):
        """zone 不存在返回 404"""
        _, token = admin_user
        resp = await client.post(
            "/api/v1/precool/zones/99999/schedule",
            json={"schedule_date": "2026-03-15"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == 404

    async def test_create_schedule_invalid_date(self, client, admin_user, sample_zone):
        """日期格式错误返回 422"""
        _, token = admin_user
        resp = await client.post(
            f"/api/v1/precool/zones/{sample_zone.id}/schedule",
            json={"schedule_date": "invalid-date"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == 422

    async def test_create_schedule_plan_error(self, client, admin_user, sample_zone):
        """算法不可行返回 422 含错误详情"""
        _, token = admin_user
        from app.services.precool.scheduler import PrecoolPlanError

        with patch(
            "app.services.precool.scheduler.load_time_slots_from_db",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "app.services.precool.scheduler.PrecoolScheduler.generate_precool_plan",
            new_callable=AsyncMock,
            side_effect=PrecoolPlanError(
                error="no_feasible_plan",
                reason="约束验证失败",
                suggestions=["调整热参数"],
            ),
        ):
            resp = await client.post(
                f"/api/v1/precool/zones/{sample_zone.id}/schedule",
                json={"schedule_date": "2026-03-15"},
                headers=auth_headers(token),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 422
        assert data["data"]["error"] == "no_feasible_plan"
        assert "suggestions" in data["data"]

    async def test_create_schedule_duplicate_409(self, client, admin_user, sample_zone, sample_plan):
        """重复生成同 zone+date 返回 409"""
        _, token = admin_user
        from app.models.thermal import PrecoolSchedule
        from app.services.precool.scheduler import PrecoolPlanResult

        mock_plan = PrecoolSchedule(
            cooling_zone_id=sample_zone.id,
            schedule_date=sample_plan.schedule_date,  # 同日期
            precool_start_time=time(0, 0),
            precool_end_time=time(8, 0),
            target_temp=18.0,
            peak_start_time=time(11, 0),
            peak_end_time=time(21, 0),
            planned_savings_kwh=50.0,
            status="pending",
        )
        mock_result = PrecoolPlanResult(schedule=mock_plan)

        with patch(
            "app.services.precool.scheduler.load_time_slots_from_db",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "app.services.precool.scheduler.PrecoolScheduler.generate_precool_plan",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await client.post(
                f"/api/v1/precool/zones/{sample_zone.id}/schedule",
                json={"schedule_date": str(sample_plan.schedule_date)},
                headers=auth_headers(token),
            )

        assert resp.status_code == 200
        assert resp.json()["code"] == 409

    async def test_create_schedule_default_date(self, client, admin_user, sample_zone):
        """不传 schedule_date 默认明天"""
        _, token = admin_user
        from app.models.thermal import PrecoolSchedule
        from app.services.precool.scheduler import PrecoolPlanResult

        tomorrow = date.today()
        from datetime import timedelta
        tomorrow = date.today() + timedelta(days=1)

        mock_plan = PrecoolSchedule(
            cooling_zone_id=sample_zone.id,
            schedule_date=tomorrow,
            precool_start_time=time(0, 0),
            precool_end_time=time(8, 0),
            target_temp=18.0,
            peak_start_time=time(11, 0),
            peak_end_time=time(21, 0),
            planned_savings_kwh=30.0,
            status="pending",
        )
        mock_result = PrecoolPlanResult(schedule=mock_plan)

        with patch(
            "app.services.precool.scheduler.load_time_slots_from_db",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "app.services.precool.scheduler.PrecoolScheduler.generate_precool_plan",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await client.post(
                f"/api/v1/precool/zones/{sample_zone.id}/schedule",
                json={},
                headers=auth_headers(token),
            )

        assert resp.status_code == 200
        assert resp.json()["code"] == 200


# ==================== GET /zones/{zone_id}/schedule 测试 ====================


class TestListSchedules:
    async def test_list_schedules_success(self, client, admin_user, sample_zone, sample_plan):
        """成功查询计划列表"""
        _, token = admin_user
        resp = await client.get(
            f"/api/v1/precool/zones/{sample_zone.id}/schedule",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["total"] >= 1
        assert len(data["data"]["items"]) >= 1
        # 列表项不含 trajectory
        item = data["data"]["items"][0]
        assert "temperature_trajectory" not in item

    async def test_list_schedules_with_status_filter(
        self, client, admin_user, sample_zone, sample_plan, executing_plan
    ):
        """status 筛选"""
        _, token = admin_user
        resp = await client.get(
            f"/api/v1/precool/zones/{sample_zone.id}/schedule?status=pending",
            headers=auth_headers(token),
        )
        data = resp.json()
        assert data["code"] == 200
        for item in data["data"]["items"]:
            assert item["status"] == "pending"

    async def test_list_schedules_zone_not_found(self, client, admin_user):
        """zone 不存在返回 404"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/precool/zones/99999/schedule",
            headers=auth_headers(token),
        )
        assert resp.json()["code"] == 404

    async def test_list_schedules_pagination(self, client, admin_user, sample_zone, sample_plan):
        """分页参数"""
        _, token = admin_user
        resp = await client.get(
            f"/api/v1/precool/zones/{sample_zone.id}/schedule?skip=0&limit=1",
            headers=auth_headers(token),
        )
        data = resp.json()
        assert data["code"] == 200
        assert len(data["data"]["items"]) <= 1


# ==================== GET /schedules/{schedule_id} 测试 ====================


class TestGetSchedule:
    async def test_get_schedule_success(self, client, admin_user, sample_plan):
        """成功查询计划详情"""
        _, token = admin_user
        resp = await client.get(
            f"/api/v1/precool/schedules/{sample_plan.id}",
            headers=auth_headers(token),
        )
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["id"] == sample_plan.id
        # 详情含 trajectory
        assert "temperature_trajectory" in data["data"]
        assert data["data"]["temperature_trajectory"] is not None

    async def test_get_schedule_not_found(self, client, admin_user):
        """计划不存在返回 404"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/precool/schedules/99999",
            headers=auth_headers(token),
        )
        assert resp.json()["code"] == 404


# ==================== POST /schedules/{schedule_id}/abort 测试 ====================


class TestAbortSchedule:
    async def test_abort_executing_plan(self, client, admin_user, executing_plan):
        """成功中止 executing 计划"""
        _, token = admin_user
        with patch(
            "app.services.precool.executor.PrecoolExecutor.abort_plan_by_api",
            new_callable=AsyncMock,
        ) as mock_abort:
            # abort_plan_by_api 修改 plan 状态
            async def side_effect(plan, reason, session):
                plan.status = "aborted"
                plan.abort_reason = reason[:500]

            mock_abort.side_effect = side_effect

            resp = await client.post(
                f"/api/v1/precool/schedules/{executing_plan.id}/abort",
                json={"reason": "手动中止测试"},
                headers=auth_headers(token),
            )

        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["status"] == "aborted"
        assert data["data"]["abort_reason"] == "手动中止测试"

    async def test_abort_non_executing_plan(self, client, admin_user, sample_plan):
        """中止非 executing 状态返回 400"""
        _, token = admin_user
        resp = await client.post(
            f"/api/v1/precool/schedules/{sample_plan.id}/abort",
            json={"reason": "测试"},
            headers=auth_headers(token),
        )
        data = resp.json()
        assert data["code"] == 400

    async def test_abort_plan_not_found(self, client, admin_user):
        """计划不存在返回 404"""
        _, token = admin_user
        resp = await client.post(
            "/api/v1/precool/schedules/99999/abort",
            json={"reason": "测试"},
            headers=auth_headers(token),
        )
        assert resp.json()["code"] == 404

    async def test_abort_default_reason(self, client, admin_user, executing_plan):
        """不传 reason 使用默认值"""
        _, token = admin_user
        with patch(
            "app.services.precool.executor.PrecoolExecutor.abort_plan_by_api",
            new_callable=AsyncMock,
        ) as mock_abort:
            async def side_effect(plan, reason, session):
                plan.status = "aborted"
                plan.abort_reason = reason[:500]

            mock_abort.side_effect = side_effect

            resp = await client.post(
                f"/api/v1/precool/schedules/{executing_plan.id}/abort",
                json={},
                headers=auth_headers(token),
            )

        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["abort_reason"] == "manual_abort"


# ==================== 权限测试 ====================


class TestPermissions:
    async def test_viewer_cannot_create(self, client, viewer_user, sample_zone):
        """viewer 无权创建计划"""
        _, token = viewer_user
        resp = await client.post(
            f"/api/v1/precool/zones/{sample_zone.id}/schedule",
            json={"schedule_date": "2026-03-15"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 403

    async def test_viewer_cannot_abort(self, client, viewer_user, executing_plan):
        """viewer 无权中止计划"""
        _, token = viewer_user
        resp = await client.post(
            f"/api/v1/precool/schedules/{executing_plan.id}/abort",
            json={"reason": "测试"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 403
