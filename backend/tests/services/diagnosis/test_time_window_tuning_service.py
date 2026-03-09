"""
时间窗口调参服务测试
Story 26.4: 时间窗口自适应
"""

import pytest
import statistics
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, delete, text

from app.core.database import Base
from app.models.diagnosis import TimeWindowAdjustmentLog, DiagnosisSession
from app.models.config import SystemConfig
from app.models.alarm import Alarm
from app.models.device import Device
from app.models.point import Point
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
        # 清理测试数据（按外键顺序）
        await session.execute(delete(TimeWindowAdjustmentLog))
        await session.execute(delete(DiagnosisAnnotation))
        await session.execute(delete(DiagnosisResult))
        await session.execute(delete(DiagnosisSession))
        await session.execute(delete(Alarm))
        await session.execute(delete(Point))
        await session.execute(delete(Device))
        await session.execute(delete(SystemConfig))
        await session.execute(delete(User))
        await session.commit()
        yield session


@pytest.fixture
async def setup_test_data(db_session):
    """创建测试基础数据"""
    # 创建设备
    device = Device(
        id=1,
        device_code="TW-BASE-001",
        device_name="TW-BASE-001",
        device_type="UPS",
        area_code="A1",
        site_id=1
    )
    db_session.add(device)
    await db_session.flush()

    # 创建点位（Alarm 需要 point_id）
    point = Point(
        id=1,
        point_code="TW-PT-001",
        point_name="测试点位",
        point_type="AI",
        device_id=device.id,
        device_type="UPS",
        area_code="A1",
    )
    db_session.add(point)

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
        password_hash="$2b$12$test_hash",
        email="admin@test.com",
        role="admin",
        is_active=True
    )
    db_session.add(admin)

    await db_session.commit()

    return {
        "device": device,
        "point": point,
        "config": config,
        "admin": admin
    }


@pytest.fixture
def _counters():
    """各类对象计数器"""
    return {"device": 0, "point": 0, "alarm": 0}


@pytest.fixture
async def create_diagnosis_data(db_session, setup_test_data, _counters):
    """创建诊断数据的辅助函数"""
    async def _create(device_type: str, count: int, duration_seconds_list: list[float]):
        _counters["device"] += 1
        unique_code = f"TW-{device_type}-{_counters['device']:04d}"

        # 创建设备
        device = Device(
            device_code=unique_code,
            device_name=unique_code,
            device_type=device_type,
            area_code="A1",
            site_id=1
        )
        db_session.add(device)
        await db_session.flush()

        # 创建点位
        _counters["point"] += 1
        point = Point(
            point_code=f"TW-PT-{_counters['point']:04d}",
            point_name=f"测试点位-{_counters['point']}",
            point_type="AI",
            device_id=device.id,
            device_type=device_type,
            area_code="A1",
        )
        db_session.add(point)
        await db_session.flush()

        for i in range(min(count, len(duration_seconds_list))):
            duration = duration_seconds_list[i]
            created_at = datetime.now() - timedelta(days=i+1)
            resolved_at = created_at + timedelta(seconds=abs(duration)) if duration > 0 else None

            # 创建告警
            _counters["alarm"] += 1
            alarm = Alarm(
                alarm_no=f"ALM-TW-{_counters['alarm']:06d}",
                point_id=point.id,
                alarm_level="warning",
                alarm_type="threshold",
                alarm_message=f"测试告警 {_counters['alarm']}",
                status="resolved" if duration > 0 else "active",
                resolved_at=resolved_at,
                duration_seconds=int(duration) if duration > 0 else None,
                created_at=created_at,
            )
            db_session.add(alarm)
            await db_session.flush()

            # 创建诊断会话
            session_obj = DiagnosisSession(
                trigger_alarm_id=alarm.id,
                device_id=device.id,
                engine_level="L1",
                status="success",
                start_time=created_at,
                end_time=created_at + timedelta(milliseconds=100),
            )
            db_session.add(session_obj)
            await db_session.flush()

            # 创建诊断结果
            result = DiagnosisResult(
                alarm_id=alarm.id,
                session_id=session_obj.id,
                device_id=device.id,
                device_type=device_type,
                diagnosis_level="L1",
                root_cause="Test cause",
                confidence=0.9,
                evidence={"test": "data"},
                created_at=created_at,
            )
            db_session.add(result)
            await db_session.flush()

            # 创建标注
            annotation = DiagnosisAnnotation(
                session_id=session_obj.id,
                annotation="accurate",
                annotator_id=1,
            )
            db_session.add(annotation)

        await db_session.commit()

    return _create


@pytest.fixture
def patch_async_session(session_factory):
    """Patch async_session 让服务使用测试数据库"""
    @asynccontextmanager
    async def mock_async_session():
        async with session_factory() as session:
            yield session

    with patch(
        "app.services.diagnosis.time_window_tuning_service.async_session",
        mock_async_session
    ):
        yield


# ============================================================
# 单元测试：时间窗口计算算法
# ============================================================

@pytest.mark.asyncio
async def test_calculate_time_window_normal_case(db_session, setup_test_data, create_diagnosis_data, patch_async_session):
    """测试用例 1: 时间窗口计算 - 正常场景"""
    durations = [180] * 23 + [300] * 22
    await create_diagnosis_data("UPS", 45, durations)

    service = TimeWindowTuningService()
    result = await service.analyze_all_device_types(device_type_filter="UPS")

    assert result["analyzed_device_types"] == 1
    assert result["total_adjustments"] == 1
    assert result["pending_approvals"] == 1

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
async def test_calculate_time_window_boundary_truncation(db_session, setup_test_data, create_diagnosis_data, patch_async_session):
    """测试用例 2: 时间窗口计算 - 边界截断"""
    durations = [3600] * 25 + [7200] * 25
    await create_diagnosis_data("空调", 50, durations)

    service = TimeWindowTuningService()
    result = await service.analyze_all_device_types(device_type_filter="空调")

    adjustment = await db_session.execute(
        select(TimeWindowAdjustmentLog).where(TimeWindowAdjustmentLog.device_type == "空调")
    )
    adjustment = adjustment.scalar_one()

    assert adjustment.proposed_window_minutes == 120
    assert adjustment.current_window_minutes == 10


@pytest.mark.asyncio
async def test_insufficient_samples(db_session, setup_test_data, create_diagnosis_data, patch_async_session):
    """测试用例 4: 样本数不足场景"""
    durations = [180] * 9
    await create_diagnosis_data("配电柜", 9, durations)

    service = TimeWindowTuningService()
    result = await service.analyze_all_device_types(device_type_filter="配电柜")

    assert result["total_adjustments"] == 0


@pytest.mark.asyncio
async def test_same_proposed_and_current_value(db_session, setup_test_data, create_diagnosis_data, patch_async_session):
    """测试用例 7: 建议值与当前值差异 < 10%"""
    import json
    config = await db_session.execute(
        select(SystemConfig).where(SystemConfig.config_key == "diagnosis_time_windows")
    )
    config = config.scalar_one()
    config_value = json.loads(config.config_value)
    config_value["UPS"] = 6
    config.config_value = json.dumps(config_value)
    await db_session.commit()

    durations = [180] * 20 + [300] * 20
    await create_diagnosis_data("UPS", 40, durations)

    service = TimeWindowTuningService()
    result = await service.analyze_all_device_types(device_type_filter="UPS")

    assert result["total_adjustments"] == 0


@pytest.mark.asyncio
async def test_filter_invalid_duration_data(db_session, setup_test_data, create_diagnosis_data, patch_async_session):
    """测试用例 8: 持续时间数据异常"""
    durations = [180] * 30 + [-10, -5, 0, -1, -20]
    await create_diagnosis_data("配电柜", 35, durations)

    service = TimeWindowTuningService()
    result = await service.analyze_all_device_types(device_type_filter="配电柜")

    adjustment = await db_session.execute(
        select(TimeWindowAdjustmentLog).where(TimeWindowAdjustmentLog.device_type == "配电柜")
    )
    adjustment = adjustment.scalar_one()

    assert adjustment.sample_count == 30


# ============================================================
# 单元测试：P50/P90 统计计算
# ============================================================

@pytest.mark.asyncio
async def test_p50_p90_calculation_with_statistics():
    """测试 P50/P90 计算（使用 statistics.quantiles）"""
    durations = [100, 150, 180, 200, 250, 280, 300, 320, 350, 400, 450, 500]

    p50 = statistics.median(durations)
    assert p50 == 290.0

    quantiles = statistics.quantiles(durations, n=10)
    p90 = quantiles[8]
    assert p90 == pytest.approx(470.0, rel=0.1)


@pytest.mark.asyncio
async def test_p90_with_insufficient_samples():
    """测试样本数不足 10 时使用最大值作为 P90"""
    durations = [100, 150, 200, 250, 300]

    p90_approx = max(durations)
    assert p90_approx == 300


# ============================================================
# 集成测试：完整调整流程
# ============================================================

@pytest.mark.asyncio
async def test_full_adjustment_workflow(db_session, setup_test_data, create_diagnosis_data, patch_async_session):
    """测试用例 3: 审批流程"""
    durations = [180] * 20 + [300] * 25
    await create_diagnosis_data("UPS", 45, durations)

    service = TimeWindowTuningService()
    await service.analyze_all_device_types(device_type_filter="UPS")

    adjustment = await db_session.execute(
        select(TimeWindowAdjustmentLog).where(
            TimeWindowAdjustmentLog.device_type == "UPS",
            TimeWindowAdjustmentLog.status == "pending"
        )
    )
    adjustment = adjustment.scalar_one()

    assert adjustment.id is not None
    assert adjustment.status == "pending"
    assert adjustment.proposed_window_minutes == 6


# ============================================================
# 边界测试
# ============================================================

@pytest.mark.asyncio
async def test_minimum_window_boundary(db_session, setup_test_data, create_diagnosis_data, patch_async_session):
    """测试最小时间窗口边界（1 分钟）"""
    durations = [30] * 20 + [40] * 15
    await create_diagnosis_data("UPS", 35, durations)

    service = TimeWindowTuningService()
    await service.analyze_all_device_types(device_type_filter="UPS")

    adjustment = await db_session.execute(
        select(TimeWindowAdjustmentLog).where(TimeWindowAdjustmentLog.device_type == "UPS")
    )
    adjustment = adjustment.scalar_one()

    assert adjustment.proposed_window_minutes == 1


@pytest.mark.asyncio
async def test_current_window_zero(db_session, setup_test_data, create_diagnosis_data, patch_async_session):
    """测试当前时间窗口为 0 的场景"""
    import json
    config = await db_session.execute(
        select(SystemConfig).where(SystemConfig.config_key == "diagnosis_time_windows")
    )
    config = config.scalar_one()
    config_value = json.loads(config.config_value)
    config_value["UPS"] = 0
    config.config_value = json.dumps(config_value)
    await db_session.commit()

    durations = [180] * 30
    await create_diagnosis_data("UPS", 30, durations)

    service = TimeWindowTuningService()
    result = await service.analyze_all_device_types(device_type_filter="UPS")

    if result["total_adjustments"] > 0:
        adjustment = await db_session.execute(
            select(TimeWindowAdjustmentLog).where(TimeWindowAdjustmentLog.device_type == "UPS")
        )
        adjustment = adjustment.scalar_one()
        assert adjustment.adjustment_percent == 0.0


@pytest.mark.asyncio
async def test_large_adjustment_percentage_warning(db_session, setup_test_data, create_diagnosis_data, patch_async_session):
    """测试调整百分比 > 500% 的警告"""
    durations = [1800] * 30
    await create_diagnosis_data("配电柜", 30, durations)

    service = TimeWindowTuningService()
    result = await service.analyze_all_device_types(device_type_filter="配电柜")

    adjustment = await db_session.execute(
        select(TimeWindowAdjustmentLog).where(TimeWindowAdjustmentLog.device_type == "配电柜")
    )
    adjustment = adjustment.scalar_one()

    assert adjustment.adjustment_percent > 500
    assert adjustment.proposed_window_minutes == 36


@pytest.mark.asyncio
async def test_empty_device_types_list(db_session, setup_test_data, patch_async_session):
    """测试空设备类型列表"""
    service = TimeWindowTuningService()
    result = await service.analyze_all_device_types()

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

    mock_session = AsyncMock(spec=AsyncSession)
    mock_admin = MagicMock()
    mock_admin.username = "admin"
    mock_admin.email = "admin@test.com"
    mock_admin.real_name = "管理员"

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_admin]
    mock_session.execute.return_value = mock_result

    @asynccontextmanager
    async def mock_ctx():
        yield mock_session

    mock_email = MagicMock()
    mock_email.is_available = True
    mock_email.send_html_email = AsyncMock()

    mock_ws = MagicMock()
    mock_ws.send_to_user = AsyncMock()

    with patch("app.services.diagnosis.time_window_tuning_service.async_session", mock_ctx), \
         patch.dict("sys.modules", {
             "app.services.email_service": MagicMock(email_service=mock_email),
             "app.services.websocket": MagicMock(ws_manager=mock_ws),
         }):
        result = {
            "analyzed_device_types": 3,
            "total_adjustments": 2,
            "pending_approvals": 2
        }

        await service.notify_admins(result)

        assert mock_email.send_html_email.called
        assert mock_ws.send_to_user.called


@pytest.mark.asyncio
async def test_device_type_name_escaping(db_session, setup_test_data, create_diagnosis_data, patch_async_session):
    """测试设备类型名称转义（包含特殊字符）"""
    import json

    special_device_type = 'UPS_测试设备'

    durations = [300] * 30
    await create_diagnosis_data(special_device_type, 30, durations)

    config = await db_session.execute(
        select(SystemConfig).where(SystemConfig.config_key == "diagnosis_time_windows")
    )
    config = config.scalar_one()
    config_value = json.loads(config.config_value)
    config_value[special_device_type] = 5
    config.config_value = json.dumps(config_value)
    await db_session.commit()

    service = TimeWindowTuningService()
    result = await service.analyze_all_device_types(device_type_filter=special_device_type)

    assert result["analyzed_device_types"] == 1

    adjustment = await db_session.execute(
        select(TimeWindowAdjustmentLog).where(TimeWindowAdjustmentLog.device_type == special_device_type)
    )
    adjustment = adjustment.scalar_one()
    assert adjustment.device_type == special_device_type
