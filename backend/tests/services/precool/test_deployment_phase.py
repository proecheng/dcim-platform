"""
Story 32.2: 分阶段部署控制 — 单元测试

测试 DeploymentPhaseService 的所有功能：
- get_current_phase: 查询当前阶段
- update_phase: 切换阶段（含前置检查、force 跳过、审计日志）
- _check_phase3_preconditions: Phase 3 校准检查
- _check_phase4_preconditions: Phase 4 预冷历史检查
"""

import json
from datetime import datetime, date
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from app.services.precool.deployment_phase import (
    DeploymentPhaseService,
    PHASE_NAMES,
    PHASE3_MIN_R_SQUARED,
    PHASE4_MIN_COMPLETED_DAYS,
    CONFIG_GROUP,
    CONFIG_KEY,
)


# ==================== Fixtures ====================


@pytest.fixture
def service():
    """创建 DeploymentPhaseService 实例"""
    return DeploymentPhaseService()


def _make_config(phase: int = 1, updated_at=None):
    """创建模拟的 SystemConfig 对象"""
    config = MagicMock()
    config.config_value = str(phase)
    config.config_group = CONFIG_GROUP
    config.config_key = CONFIG_KEY
    config.updated_at = updated_at or datetime(2026, 3, 13, 10, 0, 0)
    config.updated_by = 1
    return config


def _make_zone(zone_id: int, zone_name: str):
    """创建模拟的 CoolingZone 对象"""
    zone = MagicMock()
    zone.id = zone_id
    zone.zone_name = zone_name
    return zone


def _make_param(fitting_method="auto_fit", r_squared=0.90, is_active=True, is_demo=False):
    """创建模拟的 ThermalParameter 对象"""
    param = MagicMock()
    param.fitting_method = fitting_method
    param.fitting_r_squared = r_squared
    param.is_active = is_active
    param.is_demo = is_demo
    return param


# ==================== TestGetCurrentPhase ====================


class TestGetCurrentPhase:
    """测试 get_current_phase 方法"""

    @pytest.mark.asyncio
    async def test_returns_existing_phase(self, service):
        """正常查询已有的部署阶段"""
        config = _make_config(phase=2)
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = config
        mock_session.execute.return_value = mock_result

        with patch("app.services.precool.deployment_phase.async_session") as mock_async_session:
            mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.get_current_phase()

        assert result["current_phase"] == 2
        assert result["phase_name"] == "校准模式"
        assert result["description"] == "运行 RC 校准，对比 THM 与 TCL 结果"
        assert result["updated_at"] is not None

    @pytest.mark.asyncio
    async def test_default_phase_when_no_config(self, service):
        """无配置记录时返回默认阶段 1"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with patch("app.services.precool.deployment_phase.async_session") as mock_async_session:
            mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.get_current_phase()

        assert result["current_phase"] == 1
        assert result["phase_name"] == "THM 模式"

    @pytest.mark.asyncio
    async def test_all_phases(self, service):
        """验证所有 4 个阶段的名称映射"""
        for phase_num in range(1, 5):
            config = _make_config(phase=phase_num)
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = config
            mock_session.execute.return_value = mock_result

            with patch("app.services.precool.deployment_phase.async_session") as mock_async_session:
                mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

                result = await service.get_current_phase()

            assert result["current_phase"] == phase_num
            assert result["phase_name"] == PHASE_NAMES[phase_num][0]
            assert result["description"] == PHASE_NAMES[phase_num][1]


# ==================== TestUpdatePhase ====================


class TestUpdatePhase:
    """测试 update_phase 方法"""

    @pytest.mark.asyncio
    async def test_invalid_phase_below_range(self, service):
        """阶段号 < 1 返回错误"""
        result = await service.update_phase(0, force=False, user_id=1)
        assert result["error"] == "invalid_phase"

    @pytest.mark.asyncio
    async def test_invalid_phase_above_range(self, service):
        """阶段号 > 4 返回错误"""
        result = await service.update_phase(5, force=False, user_id=1)
        assert result["error"] == "invalid_phase"

    @pytest.mark.asyncio
    async def test_same_phase_error(self, service):
        """切换到当前相同阶段返回错误"""
        config = _make_config(phase=2)
        mock_session = AsyncMock()

        # _get_phase_config 返回
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = config
        mock_session.execute.return_value = mock_result

        with patch("app.services.precool.deployment_phase.async_session") as mock_async_session:
            mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.update_phase(2, force=False, user_id=1)

        assert result["error"] == "same_phase"

    @pytest.mark.asyncio
    async def test_switch_phase_1_to_2_no_checks(self, service):
        """1→2 不需要前置检查，直接切换"""
        config = _make_config(phase=1)
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = config
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()
        mock_session.add = MagicMock()

        with patch("app.services.precool.deployment_phase.async_session") as mock_async_session:
            mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.update_phase(2, force=False, user_id=1, username="admin")

        assert result["phase"] == 2
        assert result["old_phase"] == 1
        assert result["force_used"] is False
        # 验证审计日志被添加
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_downgrade_no_checks(self, service):
        """降级（3→1）不需要前置检查"""
        config = _make_config(phase=3)
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = config
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()
        mock_session.add = MagicMock()

        with patch("app.services.precool.deployment_phase.async_session") as mock_async_session:
            mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.update_phase(1, force=False, user_id=1, username="admin")

        assert result["phase"] == 1
        assert result["old_phase"] == 3

    @pytest.mark.asyncio
    async def test_creates_config_when_not_exists(self, service):
        """首次切换时创建 SystemConfig 记录"""
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # 无记录
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()
        mock_session.add = MagicMock()

        with patch("app.services.precool.deployment_phase.async_session") as mock_async_session:
            mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.update_phase(2, force=False, user_id=1, username="admin")

        assert result["phase"] == 2
        assert result["old_phase"] == 1  # 默认旧阶段
        # add 应被调用 2 次：1 次 SystemConfig + 1 次 OperationLog
        assert mock_session.add.call_count == 2

    @pytest.mark.asyncio
    async def test_commit_failure(self, service):
        """commit 失败返回错误"""
        config = _make_config(phase=1)
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = config
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock(side_effect=Exception("DB error"))
        mock_session.rollback = AsyncMock()
        mock_session.add = MagicMock()

        with patch("app.services.precool.deployment_phase.async_session") as mock_async_session:
            mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.update_phase(2, force=False, user_id=1)

        assert result["error"] == "commit_failed"
        mock_session.rollback.assert_awaited_once()


# ==================== TestPhase3Preconditions ====================


class TestPhase3Preconditions:
    """测试 Phase 3 前置检查"""

    @pytest.mark.asyncio
    async def test_all_zones_calibrated(self, service):
        """所有 zone 已校准且 R² >= 0.85"""
        zone = _make_zone(1, "Zone-A")
        param = _make_param(fitting_method="auto_fit", r_squared=0.92)

        mock_session = AsyncMock()
        zones_result = MagicMock()
        zones_result.scalars.return_value.all.return_value = [zone]

        param_result = MagicMock()
        param_result.scalar_one_or_none.return_value = param

        mock_session.execute = AsyncMock(side_effect=[zones_result, param_result])

        result = await service._check_phase3_preconditions(mock_session)
        assert result["passed"] is True
        assert result["details"] == []

    @pytest.mark.asyncio
    async def test_zone_not_calibrated(self, service):
        """zone 无校准记录"""
        zone = _make_zone(1, "Zone-A")

        mock_session = AsyncMock()
        zones_result = MagicMock()
        zones_result.scalars.return_value.all.return_value = [zone]

        param_result = MagicMock()
        param_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(side_effect=[zones_result, param_result])

        result = await service._check_phase3_preconditions(mock_session)
        assert result["passed"] is False
        assert len(result["details"]) == 1
        assert "未校准" in result["details"][0]

    @pytest.mark.asyncio
    async def test_zone_default_params(self, service):
        """zone 使用默认参数（fitting_method='default'）"""
        zone = _make_zone(1, "Zone-A")
        param = _make_param(fitting_method="default", r_squared=None)

        mock_session = AsyncMock()
        zones_result = MagicMock()
        zones_result.scalars.return_value.all.return_value = [zone]

        param_result = MagicMock()
        param_result.scalar_one_or_none.return_value = param

        mock_session.execute = AsyncMock(side_effect=[zones_result, param_result])

        result = await service._check_phase3_preconditions(mock_session)
        assert result["passed"] is False
        assert "未校准" in result["details"][0]

    @pytest.mark.asyncio
    async def test_zone_low_r_squared(self, service):
        """zone 已校准但 R² < 0.85"""
        zone = _make_zone(1, "Zone-A")
        param = _make_param(fitting_method="auto_fit", r_squared=0.72)

        mock_session = AsyncMock()
        zones_result = MagicMock()
        zones_result.scalars.return_value.all.return_value = [zone]

        param_result = MagicMock()
        param_result.scalar_one_or_none.return_value = param

        mock_session.execute = AsyncMock(side_effect=[zones_result, param_result])

        result = await service._check_phase3_preconditions(mock_session)
        assert result["passed"] is False
        assert "R²=0.72<0.85" in result["details"][0]

    @pytest.mark.asyncio
    async def test_r_squared_at_boundary(self, service):
        """R² 恰好等于 0.85 时通过"""
        zone = _make_zone(1, "Zone-A")
        param = _make_param(fitting_method="auto_fit", r_squared=0.85)

        mock_session = AsyncMock()
        zones_result = MagicMock()
        zones_result.scalars.return_value.all.return_value = [zone]

        param_result = MagicMock()
        param_result.scalar_one_or_none.return_value = param

        mock_session.execute = AsyncMock(side_effect=[zones_result, param_result])

        result = await service._check_phase3_preconditions(mock_session)
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_no_non_demo_zones(self, service):
        """无非 demo zone 时通过"""
        mock_session = AsyncMock()
        zones_result = MagicMock()
        zones_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(return_value=zones_result)

        result = await service._check_phase3_preconditions(mock_session)
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_multiple_zones_mixed(self, service):
        """多个 zone 混合状态"""
        zone_a = _make_zone(1, "Zone-A")
        zone_b = _make_zone(2, "Zone-B")
        param_a = _make_param(fitting_method="auto_fit", r_squared=0.92)
        param_b = _make_param(fitting_method="auto_fit", r_squared=0.70)

        mock_session = AsyncMock()
        zones_result = MagicMock()
        zones_result.scalars.return_value.all.return_value = [zone_a, zone_b]

        param_result_a = MagicMock()
        param_result_a.scalar_one_or_none.return_value = param_a

        param_result_b = MagicMock()
        param_result_b.scalar_one_or_none.return_value = param_b

        mock_session.execute = AsyncMock(side_effect=[zones_result, param_result_a, param_result_b])

        result = await service._check_phase3_preconditions(mock_session)
        assert result["passed"] is False
        assert len(result["details"]) == 1
        assert "Zone-B" in result["details"][0]

    @pytest.mark.asyncio
    async def test_manual_calibration_passes(self, service):
        """手动校准（fitting_method='manual'）也通过"""
        zone = _make_zone(1, "Zone-A")
        param = _make_param(fitting_method="manual", r_squared=0.90)

        mock_session = AsyncMock()
        zones_result = MagicMock()
        zones_result.scalars.return_value.all.return_value = [zone]

        param_result = MagicMock()
        param_result.scalar_one_or_none.return_value = param

        mock_session.execute = AsyncMock(side_effect=[zones_result, param_result])

        result = await service._check_phase3_preconditions(mock_session)
        assert result["passed"] is True


# ==================== TestPhase4Preconditions ====================


class TestPhase4Preconditions:
    """测试 Phase 4 前置检查"""

    @pytest.mark.asyncio
    async def test_enough_completed_days(self, service):
        """完成天数 >= 7 通过"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 10

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await service._check_phase4_preconditions(mock_session)
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_insufficient_completed_days(self, service):
        """完成天数 < 7 失败"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 3

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await service._check_phase4_preconditions(mock_session)
        assert result["passed"] is False
        assert "3<7" in result["details"][0]

    @pytest.mark.asyncio
    async def test_zero_completed_days(self, service):
        """零完成天数失败"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await service._check_phase4_preconditions(mock_session)
        assert result["passed"] is False

    @pytest.mark.asyncio
    async def test_exactly_seven_days(self, service):
        """恰好 7 天通过"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 7

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await service._check_phase4_preconditions(mock_session)
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_null_result(self, service):
        """查询返回 None 时失败"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = None

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await service._check_phase4_preconditions(mock_session)
        assert result["passed"] is False


# ==================== TestForceSwitch ====================


class TestForceSwitch:
    """测试 force 参数跳过前置检查"""

    @pytest.mark.asyncio
    async def test_force_skips_phase3_check(self, service):
        """force=True 跳过 Phase 3 前置检查"""
        config = _make_config(phase=1)
        mock_session = AsyncMock()

        # _get_phase_config 返回
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = config
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()
        mock_session.add = MagicMock()

        with patch("app.services.precool.deployment_phase.async_session") as mock_async_session:
            mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch.object(service, "_check_phase3_preconditions") as mock_check:
                mock_check.return_value = {"passed": False, "details": ["zone未校准"]}

                result = await service.update_phase(3, force=True, user_id=1, username="admin")

        # 即使检查失败，force=True 也应成功
        assert result["phase"] == 3
        assert result["force_used"] is True

    @pytest.mark.asyncio
    async def test_precondition_failed_without_force(self, service):
        """force=False 且检查不通过时阻止切换"""
        config = _make_config(phase=1)
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = config
        mock_session.execute.return_value = mock_result

        with patch("app.services.precool.deployment_phase.async_session") as mock_async_session:
            mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch.object(service, "_check_phase3_preconditions") as mock_check:
                mock_check.return_value = {"passed": False, "details": ["zone未校准"]}

                result = await service.update_phase(3, force=False, user_id=1)

        assert result["error"] == "precondition_failed"
        assert "zone未校准" in result["details"]


# ==================== TestAuditLog ====================


class TestAuditLog:
    """测试审计日志"""

    @pytest.mark.asyncio
    async def test_audit_log_contains_phase_info(self, service):
        """审计日志包含阶段切换信息"""
        config = _make_config(phase=1)
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = config
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()

        added_objects = []
        mock_session.add = lambda obj: added_objects.append(obj)

        with patch("app.services.precool.deployment_phase.async_session") as mock_async_session:
            mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

            await service.update_phase(2, force=False, user_id=42, username="testadmin")

        # 查找 OperationLog 对象
        log_objs = [obj for obj in added_objects if hasattr(obj, "module")]
        assert len(log_objs) == 1
        log = log_objs[0]
        assert log.module == "precool"
        assert log.action == "phase_switch"
        assert log.user_id == 42
        assert log.username == "testadmin"
        assert log.target_name == "phase_1_to_2"

        old_value = json.loads(log.old_value)
        assert old_value["phase"] == 1

        new_value = json.loads(log.new_value)
        assert new_value["phase"] == 2
        assert new_value["force"] is False

    @pytest.mark.asyncio
    async def test_force_switch_logged(self, service):
        """force 跳过记录到审计日志"""
        config = _make_config(phase=2)
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = config
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()

        added_objects = []
        mock_session.add = lambda obj: added_objects.append(obj)

        with patch("app.services.precool.deployment_phase.async_session") as mock_async_session:
            mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch.object(service, "_check_phase3_preconditions") as mock_check:
                mock_check.return_value = {"passed": False, "details": ["zone未校准"]}

                await service.update_phase(3, force=True, user_id=1, username="admin")

        log_objs = [obj for obj in added_objects if hasattr(obj, "module")]
        assert len(log_objs) == 1
        new_value = json.loads(log_objs[0].new_value)
        assert new_value["force"] is True
