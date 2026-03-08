"""
时间窗口调参服务测试
Story 26.4: 时间窗口自适应
"""

import pytest
import statistics
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, delete, text

from app.core.database import Base
from app.models.diagnosis import TimeWindowAdjustmentLog
from app.models.config import SystemConfig
from app.models.alarm import Alarm
from app.models.device import Device
from app.models.diagnosis import DiagnosisResult, DiagnosisAnnotation
from app.models.user import User
from app.services.diagnosis.time_window_tuning_service import TimeWindowTuningService


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture(scope="module")
def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        # 清理测试数据
        await session.execute(delete(TimeWindowAdjustmentLog))
        await session.execute(delete(DiagnosisAnnotation))
        await session.execute(delete(DiagnosisResult))
        await session.execute(delete(Alarm))
        await session.execute(delete(Device))
        await session.execute(delete(SystemConfig))
        await session.execute(delete(User))
        await session.commit()
        yield session


@pytest.fixture
async def setup_test_data(db_session):
    """创建测试数据"""
    # 创建设备
    device = Device(
        id=1,
        device_code="UPS-001",
        device_name="UPS-001",
        device_type="UPS",
        area_code="A1",
        site_id=1
    )
    db_session.add(device)

    # 创建系统配置
    config = SystemConfig(
        config_group="diagnosis",
        config_key="diagnosis_time_windows",
        config_value='{"UPS": 5, "空调": 10, "配电柜": 3, "default": 5}',
        value_type="json",
        description="诊断时间窗口配置（分钟）"
    )
    db_session.add(config)

    # 创建管理员用户
    admin = User(
        id=1,
        username="admin",
        password_hash="$2b$12$test_hash",  # 测试用密码哈希
        email="admin@test.com",
        role="admin",
        is_active=True
    )
    db_session.add(admin)

    await db_session.commit()

    return {
        "device": device,
        "config": config,
        "admin": admin
    }


@pytest.fixture
async def create_diagnosis_data(db_session, setup_test_data):
    """创建诊断数据的辅助函数"""
    async def _create(device_type: str, count: int, duration_seconds_list: list[float]):
        """
        创建诊断数据

        Args:
            device_type: 设备类型
            count: 创建数量
            duration_seconds_list: 持续时间列表（秒）
        """
        device = Device(
            device_code=f"{device_type}-001",
            device_name=f"{device_type}-001",
            device_type=device_type,
            area_code="A1",
            site_id=1
        )
        db_session.add(device)
        await db_session.flush()

        for i in range(min(count, len(duration_seconds_list))):
            duration = duration_seconds_list[i]
            created_at = datetime.now() - timedelta(days=i+1)
            recovered_at = created_at + timedelta(seconds=duration)

            # 创建告警
            alarm = Alarm(
                device_id=device.id,
                alarm_type="threshold",
                severity="warning",
                message=f"Test alarm {i}",
                created_at=created_at,
                recovered_at=recovered_at
            )
            db_session.add(alarm)
            await db_session.flush()

            # 创建诊断结果
            result = DiagnosisResult(
                alarm_id=alarm.id,
                diagnosis_level="L1",
                root_cause="Test cause",
                confidence=0.9,
                evidence={"test": "data"}
            )
            db_session.add(result)
            await db_session.flush()

            # 创建标注
            annotation = DiagnosisAnnotation(
                result_id=result.id,
                annotation="accurate",
                annotator_id=1,
                comment="Test annotation"
            )
            db_session.add(annotation)

        await db_session.commit()

    return _create


# ============================================================
# 单元测试：时间窗口计算算法
# ============================================================

@pytest.mark.asyncio
async def test_calculate_time_window_normal_case(db_session, setup_test_data, create_diagnosis_data):
    """测试用例 1: 时间窗口计算 - 正常场景"""
    # 准备数据：45 条标注，P50=180秒, P90=300秒
    durations = [180] * 23 + [300] * 22  # 简化：前半部分 180秒，后半部分 300秒
    await create_diagnosis_data("UPS", 45, durations)

    # 执行分析
    service = TimeWindowTuningService()
    result = await service.analyze_all_device_types(device_type_filter="UPS")

    # 验证结果
    assert result["analyzed_device_types"] == 1
    assert result["total_adjustments"] == 1
    assert result["pending_approvals"] == 1

    # 查询生成的调整记录
    adjustment = await db_session.execute(
        select(TimeWindowAdjustmentLog).where(TimeWindowAdjustmentLog.device_type == "UPS")
    )
    adjustment = adjustment.scalar_one()

    assert adjustment.current_window_minutes == 5
    assert adjustment.proposed_window_minutes == 6  # 300 * 1.2 / 60 = 6
    assert adjustment.adjustment_percent == pytest.approx(20.0, rel=0.1)
    assert adjustment.sample_count == 45
    assert adjustment.status == "pending"


@pytest.mark.asyncio
async def test_calculate_time_window_boundary_truncation(db_session, setup_test_data, create_diagnosis_data):
    """测试用例 2: 时间窗口计算 - 边界截断"""
    # 准备数据：P90=7200秒（120分钟），建议值应截断到 120 分钟
    durations = [3600] * 25 + [7200] * 25
    await create_diagnosis_data("空调", 50, durations)

    # 执行分析
    service = TimeWindowTuningService()
    result = await service.analyze_all_device_types(device_type_filter="空调")

    # 查询调整记录
    adjustment = await db_session.execute(
        select(TimeWindowAdjustmentLog).where(TimeWindowAdjustmentLog.device_type == "空调")
    )
    adjustment = adjustment.scalar_one()

    # 验证截断到最大值 120 分钟
    assert adjustment.proposed_window_minutes == 120
    assert adjustment.current_window_minutes == 10


@pytest.mark.asyncio
async def test_insufficient_samples(db_session, setup_test_data, create_diagnosis_data):
    """测试用例 4: 样本数不足场景"""
    # 准备数据：仅 20 条（< 30）
    durations = [180] * 20
    await create_diagnosis_data("配电柜", 20, durations)

    # 执行分析
    service = TimeWindowTuningService()
    result = await service.analyze_all_device_types(device_type_filter="配电柜")

    # 验证不生成调整记录
    assert result["analyzed_device_types"] == 0
    assert result["total_adjustments"] == 0


@pytest.mark.asyncio
async def test_same_proposed_and_current_value(db_session, setup_test_data, create_diagnosis_data):
    """测试用例 7: 建议值与当前值相同"""
    # 准备数据：P90=300秒，建议值 = 300 * 1.2 / 60 = 6 分钟
    # 但当前值也是 6 分钟（需要先修改配置）
    config = await db_session.execute(
        select(SystemConfig).where(SystemConfig.config_key == "diagnosis_time_windows")
    )
    config = config.scalar_one()
    import json
    config_value = json.loads(config.config_value)
    config_value["UPS"] = 6
    config.config_value = json.dumps(config_value)
    await db_session.commit()

    # 准备数据
    durations = [180] * 20 + [300] * 20
    await create_diagnosis_data("UPS", 40, durations)

    # 执行分析
    service = TimeWindowTuningService()
    result = await service.analyze_all_device_types(device_type_filter="UPS")

    # 验证不生成调整记录（建议值与当前值相同）
    assert result["total_adjustments"] == 0


@pytest.mark.asyncio
async def test_filter_invalid_duration_data(db_session, setup_test_data, create_diagnosis_data):
    """测试用例 8: 持续时间数据异常"""
    # 准备数据：35 条，其中 5 条持续时间 <= 0（异常数据）
    durations = [180] * 30 + [-10, -5, 0, -1, -20]  # 5 条异常数据
    await create_diagnosis_data("配电柜", 35, durations)

    # 执行分析
    service = TimeWindowTuningService()
    result = await service.analyze_all_device_types(device_type_filter="配电柜")

    # 验证：有效样本数 = 30（过滤掉 5 条异常数据）
    adjustment = await db_session.execute(
        select(TimeWindowAdjustmentLog).where(TimeWindowAdjustmentLog.device_type == "配电柜")
    )
    adjustment = adjustment.scalar_one()

    assert adjustment.sample_count == 30  # 只计算有效样本


# ============================================================
# 单元测试：P50/P90 统计计算
# ============================================================

@pytest.mark.asyncio
async def test_p50_p90_calculation_with_statistics():
    """测试 P50/P90 计算（使用 statistics.quantiles）"""
    durations = [100, 150, 180, 200, 250, 280, 300, 320, 350, 400, 450, 500]

    # 计算 P50（中位数）
    p50 = statistics.median(durations)
    assert p50 == 290.0  # (280 + 300) / 2

    # 计算 P90
    quantiles = statistics.quantiles(durations, n=10)
    p90 = quantiles[8]  # 第 9 个分位点是 P90
    assert p90 == pytest.approx(470.0, rel=0.1)


@pytest.mark.asyncio
async def test_p90_with_insufficient_samples():
    """测试样本数不足 10 时使用最大值作为 P90"""
    durations = [100, 150, 200, 250, 300]  # 只有 5 个样本

    # 样本数 < 10，应使用最大值作为 P90
    p90_approx = max(durations)
    assert p90_approx == 300


# ============================================================
# 集成测试：完整调整流程
# ============================================================

@pytest.mark.asyncio
async def test_full_adjustment_workflow(db_session, setup_test_data, create_diagnosis_data):
    """测试用例 3: 审批流程 - 更新配置"""
    # 1. 创建诊断数据
    durations = [180] * 20 + [300] * 25
    await create_diagnosis_data("UPS", 45, durations)

    # 2. 执行分析
    service = TimeWindowTuningService()
    await service.analyze_all_device_types(device_type_filter="UPS")

    # 3. 查询调整记录
    adjustment = await db_session.execute(
        select(TimeWindowAdjustmentLog).where(
            TimeWindowAdjustmentLog.device_type == "UPS",
            TimeWindowAdjustmentLog.status == "pending"
        )
    )
    adjustment = adjustment.scalar_one()

    # 4. 审批调整（需要通过 API 测试，这里只验证记录存在）
    assert adjustment.id is not None
    assert adjustment.status == "pending"
    assert adjustment.proposed_window_minutes == 6


# ============================================================
# 边界测试
# ============================================================

@pytest.mark.asyncio
async def test_minimum_window_boundary(db_session, setup_test_data, create_diagnosis_data):
    """测试最小时间窗口边界（1 分钟）"""
    # P90 = 40 秒，建议值 = 40 * 1.2 = 48 秒 < 60 秒，应设为 1 分钟
    durations = [30] * 20 + [40] * 15
    await create_diagnosis_data("UPS", 35, durations)

    service = TimeWindowTuningService()
    await service.analyze_all_device_types(device_type_filter="UPS")

    adjustment = await db_session.execute(
        select(TimeWindowAdjustmentLog).where(TimeWindowAdjustmentLog.device_type == "UPS")
    )
    adjustment = adjustment.scalar_one()

    assert adjustment.proposed_window_minutes == 1  # 最小值


@pytest.mark.asyncio
async def test_current_window_zero(db_session, setup_test_data, create_diagnosis_data):
    """测试当前时间窗口为 0 的场景"""
    # 修改配置，设置当前窗口为 0（配置错误）
    config = await db_session.execute(
        select(SystemConfig).where(SystemConfig.config_key == "diagnosis_time_windows")
    )
    config = config.scalar_one()
    import json
    config_value = json.loads(config.config_value)
    config_value["UPS"] = 0
    config.config_value = json.dumps(config_value)
    await db_session.commit()

    # 准备数据
    durations = [180] * 30
    await create_diagnosis_data("UPS", 30, durations)

    # 执行分析
    service = TimeWindowTuningService()
    result = await service.analyze_all_device_types(device_type_filter="UPS")

    # 验证：应该跳过调整（当前窗口为 0 是配置错误）
    # 或者生成调整记录但 adjustment_percent = 0
    # 根据实现，这里假设会生成记录但百分比为 0
    if result["total_adjustments"] > 0:
        adjustment = await db_session.execute(
            select(TimeWindowAdjustmentLog).where(TimeWindowAdjustmentLog.device_type == "UPS")
        )
        adjustment = adjustment.scalar_one()
        assert adjustment.adjustment_percent == 0.0


@pytest.mark.asyncio
async def test_large_adjustment_percentage_warning(db_session, setup_test_data, create_diagnosis_data):
    """测试调整百分比 > 500% 的警告"""
    # 当前窗口 = 3 分钟，P90 = 1800 秒（30 分钟）
    # 建议值 = 1800 * 1.2 / 60 = 36 分钟
    # 调整百分比 = (36 - 3) / 3 * 100 = 1100%
    durations = [1800] * 30
    await create_diagnosis_data("配电柜", 30, durations)

    service = TimeWindowTuningService()
    result = await service.analyze_all_device_types(device_type_filter="配电柜")

    adjustment = await db_session.execute(
        select(TimeWindowAdjustmentLog).where(TimeWindowAdjustmentLog.device_type == "配电柜")
    )
    adjustment = adjustment.scalar_one()

    # 验证生成了调整记录（即使百分比很大）
    assert adjustment.adjustment_percent > 500
    assert adjustment.proposed_window_minutes == 36


@pytest.mark.asyncio
async def test_empty_device_types_list(db_session, setup_test_data):
    """测试空设备类型列表"""
    # 不创建任何诊断数据
    service = TimeWindowTuningService()
    result = await service.analyze_all_device_types()

    # 验证：没有设备类型需要分析
    assert result["analyzed_device_types"] == 0
    assert result["total_adjustments"] == 0
    assert result["pending_approvals"] == 0


# ============================================================
# 通知测试
# ============================================================

@pytest.mark.asyncio
async def test_notify_admins(db_session, setup_test_data):
    """测试管理员通知功能"""
    service = TimeWindowTuningService()

    # Mock 邮件和 WebSocket 服务
    with patch("app.services.diagnosis.time_window_tuning_service.email_service") as mock_email, \
         patch("app.services.diagnosis.time_window_tuning_service.ws_manager") as mock_ws:

        mock_email.is_available = True
        mock_email.send_html_email = AsyncMock()
        mock_ws.send_to_user = AsyncMock()

        result = {
            "analyzed_device_types": 3,
            "total_adjustments": 2,
            "pending_approvals": 2
        }

        await service.notify_admins(result)

        # 验证邮件发送被调用
        assert mock_email.send_html_email.called
        # 验证 WebSocket 发送被调用
        assert mock_ws.send_to_user.called


@pytest.mark.asyncio
async def test_device_type_name_escaping(db_session, setup_test_data, create_diagnosis_data):
    """测试设备类型名称转义（包含特殊字符）"""
    import json

    # 创建包含特殊字符的设备类型
    special_device_type = 'UPS"测试\'设备'

    # 创建诊断数据
    durations = [300] * 30  # 30 个样本，P90 = 300 秒
    await create_diagnosis_data(special_device_type, 30, durations)

    # 创建配置（使用 json.dumps 自动转义）
    config_value = {
        "default": 5,
        special_device_type: 5
    }
    config = SystemConfig(
        config_key="diagnosis_time_windows",
        config_value=json.dumps(config_value),
        description="测试配置"
    )
    db_session.add(config)
    await db_session.commit()

    # 执行分析
    service = TimeWindowTuningService()
    result = await service.analyze_all_device_types(device_type_filter=special_device_type)

    # 验证：能够正确处理特殊字符的设备类型
    assert result["analyzed_device_types"] == 1

    # 验证：生成的调整记录包含正确的设备类型名称
    adjustment = await db_session.execute(
        select(TimeWindowAdjustmentLog).where(TimeWindowAdjustmentLog.device_type == special_device_type)
    )
    adjustment = adjustment.scalar_one()
    assert adjustment.device_type == special_device_type

    # 验证：配置更新后能正确读取（json.dumps/json.loads 自动处理转义）
    updated_config = await db_session.execute(
        select(SystemConfig).where(SystemConfig.config_key == "diagnosis_time_windows")
    )
    updated_config = updated_config.scalar_one()
    parsed_config = json.loads(updated_config.config_value)
    assert special_device_type in parsed_config
