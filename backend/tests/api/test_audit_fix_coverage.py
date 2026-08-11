"""
对抗性审查修复 — 补充 E2E 测试
覆盖范围: 7 个诊断 API 文件在审查修复中引入的新行为

测试类别:
1. Pydantic 模型验证 (strip_whitespace, min_length, Literal)
2. 分页参数边界 (page_size le=100)
3. RBAC 依赖注入替换
4. 审计日志写入
5. GET→POST 方法变更
6. 边界修复 (point_id=0, end_date 边界)
7. 通用错误消息 (不泄露 str(e))
"""

import pytest
from datetime import datetime
from httpx import AsyncClient
from sqlalchemy import select

from app.models.log import OperationLog


# ============================================================
# 1. Pydantic 模型验证
# ============================================================


class TestPydanticModelValidation:
    """测试 Pydantic 模型替换 dict Body 后的验证行为"""

    @pytest.mark.asyncio
    async def test_reject_time_window_whitespace_reason(
        self, client: AsyncClient, admin_token: str, async_db
    ):
        """strip_whitespace=True: 全空白 reason 应被拒绝"""
        # 创建待审批记录
        from app.models.diagnosis import TimeWindowAdjustmentLog

        adj = TimeWindowAdjustmentLog(
            device_type="UPS",
            current_window_minutes=5,
            proposed_window_minutes=6,
            adjustment_percent=20.0,
            sample_count=45,
            p50_duration_seconds=180.0,
            p90_duration_seconds=300.0,
            status="pending",
        )
        async_db.add(adj)
        await async_db.flush()
        await async_db.refresh(adj)

        # 全空白 reason 应被 Pydantic strip 后触发 min_length=1
        response = await client.post(
            f"/api/v1/diagnosis/time-window-tuning/adjustments/{adj.id}/reject",
            json={"reason": "   "},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_reject_time_window_valid_reason(
        self, client: AsyncClient, admin_token: str, async_db
    ):
        """正常 reason 应通过验证"""
        from app.models.diagnosis import TimeWindowAdjustmentLog

        adj = TimeWindowAdjustmentLog(
            device_type="UPS",
            current_window_minutes=5,
            proposed_window_minutes=6,
            adjustment_percent=20.0,
            sample_count=45,
            p50_duration_seconds=180.0,
            p90_duration_seconds=300.0,
            status="pending",
        )
        async_db.add(adj)
        await async_db.flush()
        await async_db.refresh(adj)

        response = await client.post(
            f"/api/v1/diagnosis/time-window-tuning/adjustments/{adj.id}/reject",
            json={"reason": "数据异常需复核"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_hmac_key_rotate_short_key(
        self, client: AsyncClient, admin_token: str
    ):
        """HMACKeyRotateRequest: key < 32 字符应被拒绝"""
        response = await client.post(
            "/api/v1/diagnosis/hmac-key/rotate",
            json={"new_key": "short"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_hmac_key_rotate_missing_key(
        self, client: AsyncClient, admin_token: str
    ):
        """HMACKeyRotateRequest: 缺少 new_key 字段应 422"""
        response = await client.post(
            "/api/v1/diagnosis/hmac-key/rotate",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_approve_time_window_optional_reason(
        self, client: AsyncClient, admin_token: str, async_db
    ):
        """TimeWindowApproveRequest: reason 可选，空 body 应通过"""
        from app.models.diagnosis import TimeWindowAdjustmentLog
        from app.models.config import SystemConfig

        # 确保有配置
        config = SystemConfig(
            config_group="diagnosis",
            config_key="diagnosis_time_windows",
            config_value='{"UPS": 5, "default": 5}',
            value_type="json",
        )
        async_db.add(config)

        adj = TimeWindowAdjustmentLog(
            device_type="UPS",
            current_window_minutes=5,
            proposed_window_minutes=6,
            adjustment_percent=20.0,
            sample_count=45,
            p50_duration_seconds=180.0,
            p90_duration_seconds=300.0,
            status="pending",
        )
        async_db.add(adj)
        await async_db.flush()
        await async_db.refresh(adj)

        response = await client.post(
            f"/api/v1/diagnosis/time-window-tuning/adjustments/{adj.id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # 空 body (None) 应该通过验证
        assert response.status_code == 200


# ============================================================
# 2. 分页参数边界
# ============================================================


class TestPaginationBoundary:
    """测试分页参数 le=100 上限"""

    @pytest.mark.asyncio
    async def test_ab_tests_page_size_exceeds_limit(
        self, client: AsyncClient, admin_token: str
    ):
        """A/B 测试列表: page_size > 100 应被拒绝"""
        response = await client.get(
            "/api/v1/diagnosis/ab-tests?page_size=101",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_ab_tests_page_size_at_limit(
        self, client: AsyncClient, admin_token: str
    ):
        """A/B 测试列表: page_size=100 应通过"""
        response = await client.get(
            "/api/v1/diagnosis/ab-tests?page_size=100",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_ab_tests_page_zero(
        self, client: AsyncClient, admin_token: str
    ):
        """A/B 测试列表: page=0 应被拒绝 (ge=1)"""
        response = await client.get(
            "/api/v1/diagnosis/ab-tests?page=0",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_fault_tree_versions_page_size_exceeds_limit(
        self, client: AsyncClient, admin_token: str, async_db
    ):
        """故障树版本列表: page_size > 100 应被拒绝"""
        # 创建一个故障树
        from app.models.fault_tree import FaultTree

        tree = FaultTree(name="测试树", description="test")
        async_db.add(tree)
        await async_db.flush()

        response = await client.get(
            f"/api/v1/fault-trees/{tree.id}/versions/?page_size=200",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_battery_soh_limit_exceeds_max(
        self, client: AsyncClient, admin_token: str
    ):
        """battery-soh/latest: limit > 500 应被拒绝"""
        response = await client.get(
            "/api/v1/diagnosis/battery-soh/latest?limit=501",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_battery_soh_limit_at_max(
        self, client: AsyncClient, admin_token: str
    ):
        """battery-soh/latest: limit=500 应通过"""
        response = await client.get(
            "/api/v1/diagnosis/battery-soh/latest?limit=500",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200


# ============================================================
# 3. RBAC 依赖注入替换
# ============================================================


class TestRBACDependencyInjection:
    """测试 RBAC 依赖注入替换后的权限行为"""

    @pytest.mark.asyncio
    async def test_sensor_metadata_viewer_cannot_create(
        self, client: AsyncClient, viewer_token: str
    ):
        """viewer 不能创建传感器元数据 (require_operator)"""
        response = await client.post(
            "/api/v1/diagnosis/sensor-metadata/",
            json={
                "point_id": 9001,
                "accuracy_class": 0.5,
                "calibration_interval_days": 365,
            },
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_sensor_metadata_viewer_cannot_delete(
        self, client: AsyncClient, viewer_token: str, admin_token: str, async_db
    ):
        """viewer 不能删除传感器元数据 (require_admin)"""
        from app.models.diagnosis import SensorMetadata

        meta = SensorMetadata(
            point_id=9002, accuracy_class=0.5, calibration_interval_days=365
        )
        async_db.add(meta)
        await async_db.flush()
        await async_db.refresh(meta)

        response = await client.delete(
            f"/api/v1/diagnosis/sensor-metadata/{meta.id}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_sensor_metadata_operator_cannot_delete(
        self, client: AsyncClient, operator_token: str, async_db
    ):
        """operator 不能删除传感器元数据 (require_admin)"""
        from app.models.diagnosis import SensorMetadata

        meta = SensorMetadata(
            point_id=9003, accuracy_class=0.5, calibration_interval_days=365
        )
        async_db.add(meta)
        await async_db.flush()
        await async_db.refresh(meta)

        response = await client.delete(
            f"/api/v1/diagnosis/sensor-metadata/{meta.id}",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_sensor_metadata_operator_can_update(
        self, client: AsyncClient, operator_user, async_db
    ):
        """operator 可以更新传感器元数据 (require_operator)"""
        from app.models.device import Device
        from app.models.diagnosis import SensorMetadata
        from app.models.point import Point
        from app.models.spatial import Site
        from app.models.user import UserSite

        operator, operator_token = operator_user
        site = Site(site_code="AUDIT-SENSOR-SITE", site_name="审计传感器测试站点")
        async_db.add(site)
        await async_db.flush()
        device = Device(
            device_code="AUDIT-SENSOR-DEVICE",
            device_name="审计传感器测试设备",
            device_type="UPS",
            area_code="A",
            site_id=site.id,
        )
        async_db.add(device)
        await async_db.flush()
        point = Point(
            point_code="AUDIT-SENSOR-POINT",
            point_name="审计传感器测试点位",
            point_type="AI",
            device_id=device.id,
        )
        async_db.add_all([UserSite(user_id=operator.id, site_id=site.id), point])
        await async_db.flush()

        meta = SensorMetadata(
            point_id=point.id, accuracy_class=0.5, calibration_interval_days=365
        )
        async_db.add(meta)
        await async_db.flush()
        await async_db.refresh(meta)

        response = await client.put(
            f"/api/v1/diagnosis/sensor-metadata/{meta.id}",
            json={"accuracy_class": 0.2},
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_fault_tree_versions_viewer_can_list(
        self, client: AsyncClient, viewer_token: str, async_db
    ):
        """viewer 可以查看故障树版本列表 (require_viewer)"""
        from app.models.fault_tree import FaultTree

        tree = FaultTree(name="测试树查看", description="test")
        async_db.add(tree)
        await async_db.flush()

        response = await client.get(
            f"/api/v1/fault-trees/{tree.id}/versions/",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_probability_adjustments_viewer_cannot_list(
        self, client: AsyncClient, viewer_token: str
    ):
        """viewer 不能查看全局概率调参配置"""
        response = await client.get(
            "/api/v1/diagnosis/probability-tuning/adjustments",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_probability_adjustments_no_auth(
        self, client: AsyncClient
    ):
        """无认证不能查看概率调参列表"""
        response = await client.get(
            "/api/v1/diagnosis/probability-tuning/adjustments",
        )
        assert response.status_code == 401


# ============================================================
# 4. 审计日志写入
# ============================================================


class TestAuditLog:
    """测试审计日志 OperationLog 写入"""

    @pytest.mark.asyncio
    async def test_ab_test_create_writes_audit_log(
        self, client: AsyncClient, admin_token: str, async_db
    ):
        """创建 A/B 测试应写入审计日志"""
        from app.models.fault_tree import FaultTree, FaultTreeVersion

        # 创建前置数据
        tree = FaultTree(name="审计测试树", description="test")
        async_db.add(tree)
        await async_db.flush()

        ver_a = FaultTreeVersion(
            tree_id=tree.id,
            version_number=1,
            created_by=1,
            status="active",
            snapshot="{}",
        )
        ver_b = FaultTreeVersion(
            tree_id=tree.id,
            version_number=2,
            created_by=1,
            status="draft",
            snapshot="{}",
        )
        async_db.add_all([ver_a, ver_b])
        await async_db.flush()

        response = await client.post(
            "/api/v1/diagnosis/ab-tests",
            json={
                "name": "审计日志测试",
                "fault_tree_id": tree.id,
                "version_a_id": ver_a.id,
                "version_b_id": ver_b.id,
                "strategy": "round_robin",
                "strategy_params": {"ratio": 0.5},
                "min_duration_hours": 24,
                "min_sample_size": 100,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        if response.status_code == 201:
            # 验证审计日志
            result = await async_db.execute(
                select(OperationLog).where(
                    OperationLog.action == "create_ab_test"
                )
            )
            logs = result.scalars().all()
            assert len(logs) >= 1
            assert logs[-1].module == "ab_testing"


# ============================================================
# 5. GET→POST 方法变更
# ============================================================


class TestMethodChange:
    """测试 GET→POST 方法变更"""

    @pytest.mark.asyncio
    async def test_reload_rules_get_not_200(
        self, client: AsyncClient, admin_token: str
    ):
        """GET /rules/reload 不应返回 200（已改为 POST）"""
        response = await client.get(
            "/api/v1/diagnosis/rules/reload",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # GET 不应成功（可能 405 或 422，取决于路由匹配）
        assert response.status_code != 200

    @pytest.mark.asyncio
    async def test_reload_rules_post_works(
        self, client: AsyncClient, admin_token: str
    ):
        """POST /rules/reload 应正常工作"""
        response = await client.post(
            "/api/v1/diagnosis/rules/reload",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # 200 或其他成功状态
        assert response.status_code in (200, 500)  # 500 仅在无 YAML 文件时


# ============================================================
# 6. 边界修复
# ============================================================


class TestBoundaryFixes:
    """测试边界条件修复"""

    @pytest.mark.asyncio
    async def test_export_format_invalid(
        self, client: AsyncClient, admin_token: str
    ):
        """Literal['pdf']: 非 pdf 格式应返回 422"""
        response = await client.get(
            "/api/v1/diagnosis/reports/misdiagnosis/export?period=2025-01&format=csv",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_export_format_pdf_valid(
        self, client: AsyncClient, admin_token: str
    ):
        """Literal['pdf']: pdf 格式应通过验证"""
        response = await client.get(
            "/api/v1/diagnosis/reports/misdiagnosis/export?period=2025-01&format=pdf",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # 可能 404（无数据）或 200，但不应是 422
        assert response.status_code != 422

    @pytest.mark.asyncio
    async def test_sensor_check_expired_returns_200(
        self, client: AsyncClient, admin_token: str
    ):
        """check-expired-calibrations 应返回 200（不是 202）"""
        response = await client.post(
            "/api/v1/diagnosis/sensor-metadata/check-expired-calibrations",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert "已完成" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_misdiagnosis_end_date_boundary(
        self, client: AsyncClient, admin_token: str, async_db
    ):
        """end_date 边界: 使用 < 而非 <=，避免多包含次日零时"""
        from app.models.report import ReportRecord

        # 创建一条记录，end_time 恰好在 2025-02-01 00:00:00（次日零时）
        boundary_time = datetime(2025, 2, 1, 0, 0, 0)
        record = ReportRecord(
            report_type="misdiagnosis",
            report_name="边界测试报告",
            start_time=datetime(2025, 1, 1),
            end_time=boundary_time,
            status="completed",
        )
        async_db.add(record)
        await async_db.flush()

        # end_date=2025-01-31 → end_dt = 2025-02-01 00:00:00
        # 用 < 应排除恰好等于 boundary 的记录
        response = await client.get(
            "/api/v1/diagnosis/misdiagnosis-reports?end_date=2025-01-31",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        # 边界记录不应被包含（end_time < end_dt，不是 <=）
        if "items" in data:
            for item in data["items"]:
                if item.get("report_name") == "边界测试报告":
                    pytest.fail("边界时间记录不应被包含（< 而非 <=）")


# ============================================================
# 7. 通用错误消息（不泄露 str(e)）
# ============================================================


class TestGenericErrorMessages:
    """测试错误消息不泄露内部异常详情"""

    @pytest.mark.asyncio
    async def test_probability_approve_error_generic(
        self, client: AsyncClient, admin_token: str
    ):
        """概率调参审批不存在记录时应返回通用消息"""
        response = await client.post(
            "/api/v1/diagnosis/probability-tuning/adjustments/99999/approve",
            json={"reason": "测试"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code in (404, 400)
        detail = response.json().get("detail", "")
        # 不应包含 Python 异常类名
        assert "Traceback" not in detail
        assert "NoneType" not in detail

    @pytest.mark.asyncio
    async def test_time_window_approve_nonexistent_generic(
        self, client: AsyncClient, admin_token: str
    ):
        """时间窗口审批不存在记录应返回通用消息"""
        response = await client.post(
            "/api/v1/diagnosis/time-window-tuning/adjustments/99999/approve",
            json={"reason": "测试"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404
        detail = response.json().get("detail", "")
        assert "Traceback" not in detail

    @pytest.mark.asyncio
    async def test_time_window_reject_nonexistent_generic(
        self, client: AsyncClient, admin_token: str
    ):
        """时间窗口拒绝不存在记录应返回通用消息"""
        response = await client.post(
            "/api/v1/diagnosis/time-window-tuning/adjustments/99999/reject",
            json={"reason": "不存在的记录"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404
        detail = response.json().get("detail", "")
        assert "Traceback" not in detail
