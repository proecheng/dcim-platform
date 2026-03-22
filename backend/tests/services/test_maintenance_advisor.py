"""MaintenanceAdvisor 测试 — Story 36.3

18 个测试覆盖 AC #1~#5:
  6.1  evaluate 生成新建议
  6.2  evaluate 幂等（更新已有 pending）
  6.3  confirm_advice 创建工单
  6.4  reject_advice 误报反馈
  6.5  auto_close_pending 自动关闭
  6.6  urgency 映射
  6.7  action 模板生成
  6.8  API 端点集成测试（列表+确认+拒绝+权限）— 4 个测试
  6.9  健康度恢复后不再生成建议
  6.10 calculate_all 集成 advisor 流程
  6.11 confirm/reject 对非 pending 状态返回错误 — 2 个测试
  6.12 score=40/41 边界触发 + batch 自动关闭 — 3 个测试
"""

import pytest
from datetime import datetime, timedelta

from app.models.device import Device
from app.models.point import Point
from app.models.alarm import Alarm
from app.models.operation import WorkOrder, WorkOrderStatus, WorkOrderType, WorkOrderPriority
from app.models.report import MaintenanceAdvice, DeviceHealthScore
from app.services.predictive_maintenance.base import DegradationResult
from app.services.predictive_maintenance.advisor import (
    MaintenanceAdvisor,
    _calc_urgency,
    _generate_action,
    _generate_reason,
    ACTION_TEMPLATES,
)
from app.services.predictive_maintenance.health_calculator import DeviceHealthScoreCalculator

from sqlalchemy import select


# ==================== Helpers ====================

async def _make_device(db, device_type="AC", code_suffix="001"):
    device = Device(
        device_code=f"MA-{device_type}-{code_suffix}",
        device_name=f"测试{device_type}设备{code_suffix}",
        device_type=device_type,
        area_code="A1",
    )
    db.add(device)
    await db.flush()
    return device


async def _make_point(db, device_id, suffix="return_temp"):
    p = Point(
        point_code=f"MA-POINT-{device_id}_{suffix}",
        point_name=f"测试{suffix}",
        point_type="AI",
        device_id=device_id,
        device_type="AC",
    )
    db.add(p)
    await db.flush()
    return p


async def _make_alarms(db, point_id, count=5):
    now = datetime.now()
    for i in range(count):
        alarm = Alarm(
            alarm_no=f"ALM-MA-{point_id}-{i}",
            point_id=point_id,
            alarm_level="minor",
            alarm_message=f"测试告警{i}",
            created_at=now - timedelta(days=i),
        )
        db.add(alarm)
    await db.flush()


async def _make_work_order(db, device_id, days_ago=15):
    wo = WorkOrder(
        order_no=f"WO-MA-{device_id}-{days_ago}",
        title=f"维保工单-{device_id}",
        device_id=device_id,
        status=WorkOrderStatus.completed,
        completed_at=datetime.now() - timedelta(days=days_ago),
    )
    db.add(wo)
    await db.flush()
    return wo


async def _make_pending_advice(db, device, score=35.0):
    advice = MaintenanceAdvice(
        device_id=device.id,
        device_name=device.device_name,
        device_type=device.device_type,
        health_score=score,
        urgency="medium",
        reason="测试原因",
        suggested_action="测试措施",
        status="pending",
    )
    db.add(advice)
    await db.flush()
    return advice


# ==================== 6.1 evaluate 生成新建议 ====================

@pytest.mark.asyncio
async def test_evaluate_creates_new_advice(async_db):
    """AC#1: 健康度≤40 时生成新的 MaintenanceAdvice"""
    device = await _make_device(async_db, "AC", "E01")
    dr = DegradationResult(
        device_id=device.id, score=30.0, confidence=0.8,
        available_points=3, total_points=5, data_sufficiency="full",
        primary_concern="cop_trend",
    )

    advisor = MaintenanceAdvisor(async_db)
    advice = await advisor.evaluate(device, health_score=30.0, degradation_result=dr, plugin_key="hvac")

    assert advice is not None
    assert advice.device_id == device.id
    assert advice.status == "pending"
    assert advice.urgency == "medium"  # 20-40 → medium
    assert "COP" in advice.suggested_action


# ==================== 6.2 evaluate 幂等 ====================

@pytest.mark.asyncio
async def test_evaluate_idempotent_update(async_db):
    """AC#2: 同一设备已有 pending 建议时不重复创建，更新已有"""
    device = await _make_device(async_db, "AC", "E02")
    existing = await _make_pending_advice(async_db, device, score=38.0)
    old_id = existing.id

    dr = DegradationResult(
        device_id=device.id, score=25.0, confidence=0.8,
        available_points=3, total_points=5, data_sufficiency="full",
    )

    advisor = MaintenanceAdvisor(async_db)
    advice = await advisor.evaluate(device, health_score=25.0, degradation_result=dr, plugin_key="hvac")

    assert advice.id == old_id  # 同一条记录
    assert advice.health_score == 25.0  # 已更新

    # 确认只有 1 条 pending
    result = await async_db.execute(
        select(MaintenanceAdvice).where(
            MaintenanceAdvice.device_id == device.id,
            MaintenanceAdvice.status == "pending",
        )
    )
    assert len(result.scalars().all()) == 1


# ==================== 6.3 confirm_advice 创建工单 ====================

@pytest.mark.asyncio
async def test_confirm_advice_creates_work_order(async_db):
    """AC#3: 确认建议 → 创建 WorkOrder"""
    device = await _make_device(async_db, "AC", "C01")
    advice = await _make_pending_advice(async_db, device)

    advisor = MaintenanceAdvisor(async_db)
    wo = await advisor.confirm_advice(advice.id, user_id=1)

    assert wo.order_no.startswith("MA-")
    assert wo.order_type == WorkOrderType.maintenance
    assert wo.priority == WorkOrderPriority.high  # medium → high
    assert wo.status == WorkOrderStatus.pending
    assert wo.device_id == device.id
    assert "预测性维护" in wo.reporter

    # 建议状态已更新
    assert advice.status == "converted"
    assert advice.work_order_id == wo.id
    assert advice.confirmed_at is not None
    assert advice.confirmed_by == 1


# ==================== 6.4 reject_advice 误报反馈 ====================

@pytest.mark.asyncio
async def test_reject_advice_records_feedback(async_db):
    """AC#4: 拒绝建议 → status=rejected + feedback"""
    device = await _make_device(async_db, "AC", "R01")
    advice = await _make_pending_advice(async_db, device)

    advisor = MaintenanceAdvisor(async_db)
    result = await advisor.reject_advice(advice.id, feedback="测试误报原因")

    assert result.status == "rejected"
    assert result.feedback == "测试误报原因"


# ==================== 6.5 auto_close_pending 自动关闭 ====================

@pytest.mark.asyncio
async def test_auto_close_pending(async_db):
    """AC#5: 健康度≥60 时自动关闭 pending 建议"""
    device = await _make_device(async_db, "AC", "AC01")
    advice = await _make_pending_advice(async_db, device)

    # 创建一条已 converted 的建议（不应被关闭）
    converted = MaintenanceAdvice(
        device_id=device.id, device_name=device.device_name,
        device_type=device.device_type, health_score=35.0,
        urgency="medium", reason="旧建议", suggested_action="旧措施",
        status="converted",
    )
    async_db.add(converted)
    await async_db.flush()

    advisor = MaintenanceAdvisor(async_db)
    count = await advisor.auto_close_pending(device.id)

    assert count == 1  # 只关闭 pending 的

    # 验证状态
    result = await async_db.execute(
        select(MaintenanceAdvice).where(MaintenanceAdvice.id == advice.id)
    )
    assert result.scalar_one().status == "auto_closed"

    # converted 不受影响
    result2 = await async_db.execute(
        select(MaintenanceAdvice).where(MaintenanceAdvice.id == converted.id)
    )
    assert result2.scalar_one().status == "converted"


# ==================== 6.6 urgency 映射 ====================

@pytest.mark.asyncio
async def test_urgency_mapping():
    """紧急度映射：score<20→high, 20-40→medium"""
    assert _calc_urgency(0) == "high"
    assert _calc_urgency(10) == "high"
    assert _calc_urgency(19.9) == "high"
    assert _calc_urgency(20) == "medium"
    assert _calc_urgency(30) == "medium"
    assert _calc_urgency(40) == "medium"


# ==================== 6.7 action 模板生成 ====================

@pytest.mark.asyncio
async def test_action_template_generation():
    """建议措施模板生成 + 变量替换"""
    # HVAC cop_trend
    dr1 = DegradationResult(
        device_id=1, score=30.0, confidence=0.8,
        available_points=3, total_points=5, data_sufficiency="full",
        primary_concern="cop_trend",
    )
    action1 = _generate_action("hvac", dr1)
    assert "COP" in action1

    # HVAC compressor_hours with variable
    dr2 = DegradationResult(
        device_id=1, score=30.0, confidence=0.8,
        available_points=3, total_points=5, data_sufficiency="full",
        primary_concern="compressor_hours",
        trend_factors={"compressor_hours": 25000},
    )
    action2 = _generate_action("hvac", dr2)
    assert "25000" in action2

    # UPS default (no primary_concern)
    dr3 = DegradationResult(
        device_id=1, score=30.0, confidence=0.8,
        available_points=1, total_points=1, data_sufficiency="partial",
    )
    action3 = _generate_action("ups", dr3)
    assert "UPS" in action3

    # Unknown plugin → fallback
    action4 = _generate_action("unknown_type", dr3)
    assert "劣化" in action4 or "检查" in action4


# ==================== 6.8 API 端点集成测试 ====================

@pytest.mark.asyncio
async def test_api_list_advices(client, async_db, admin_token):
    """API: GET /predictive-maintenance/advices"""
    device = await _make_device(async_db, "AC", "API01")
    await _make_pending_advice(async_db, device)
    await async_db.commit()

    resp = await client.get(
        "/api/v1/predictive-maintenance/advices",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["status"] == "pending"


@pytest.mark.asyncio
async def test_api_confirm_advice(client, async_db, admin_token):
    """API: POST /predictive-maintenance/advices/{id}/confirm"""
    device = await _make_device(async_db, "AC", "API02")
    advice = await _make_pending_advice(async_db, device)
    await async_db.commit()

    resp = await client.post(
        f"/api/v1/predictive-maintenance/advices/{advice.id}/confirm",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "converted"
    assert data["work_order_no"].startswith("MA-")


@pytest.mark.asyncio
async def test_api_reject_advice(client, async_db, admin_token):
    """API: POST /predictive-maintenance/advices/{id}/reject"""
    device = await _make_device(async_db, "AC", "API03")
    advice = await _make_pending_advice(async_db, device)
    await async_db.commit()

    resp = await client.post(
        f"/api/v1/predictive-maintenance/advices/{advice.id}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"feedback": "测试误报原因"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_api_viewer_cannot_confirm(client, async_db, viewer_token):
    """API 权限: viewer 不能确认建议"""
    device = await _make_device(async_db, "AC", "API04")
    advice = await _make_pending_advice(async_db, device)
    await async_db.commit()

    resp = await client.post(
        f"/api/v1/predictive-maintenance/advices/{advice.id}/confirm",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403


# ==================== 6.9 健康度恢复后不再生成建议 ====================

@pytest.mark.asyncio
async def test_no_advice_when_score_above_40(async_db):
    """健康度>40 时 evaluate 返回 None"""
    device = await _make_device(async_db, "AC", "N01")
    dr = DegradationResult(
        device_id=device.id, score=50.0, confidence=0.8,
        available_points=3, total_points=5, data_sufficiency="full",
    )

    advisor = MaintenanceAdvisor(async_db)
    result = await advisor.evaluate(device, health_score=50.0, degradation_result=dr)

    assert result is None


# ==================== 6.10 calculate_all 集成 advisor ====================

@pytest.mark.asyncio
async def test_calculate_all_integrates_advisor(async_db):
    """calculate_all_health_scores 自动调用 advisor"""
    device = await _make_device(async_db, "AC", "INT01")

    # 大量告警 + 过期维保 → 低分
    pt = await _make_point(async_db, device.id, "return_temp")
    await _make_alarms(async_db, pt.id, count=25)
    await _make_work_order(async_db, device.id, days_ago=400)

    calculator = DeviceHealthScoreCalculator(async_db)
    count = await calculator.calculate_all_health_scores()
    assert count >= 1

    # 检查是否生成了建议（取决于实际评分是否≤40）
    result = await async_db.execute(
        select(DeviceHealthScore).where(DeviceHealthScore.device_id == device.id)
    )
    health_record = result.scalar_one()

    if health_record.score <= 40:
        advices = await async_db.execute(
            select(MaintenanceAdvice).where(
                MaintenanceAdvice.device_id == device.id,
                MaintenanceAdvice.status == "pending",
            )
        )
        assert len(advices.scalars().all()) >= 1


# ==================== 6.11 confirm/reject 非 pending 返回错误 ====================

@pytest.mark.asyncio
async def test_confirm_non_pending_raises_error(async_db):
    """确认非 pending 状态的建议应报错"""
    device = await _make_device(async_db, "AC", "NP01")
    advice = await _make_pending_advice(async_db, device)
    advice.status = "rejected"
    await async_db.flush()

    advisor = MaintenanceAdvisor(async_db)
    with pytest.raises(ValueError, match="仅 pending 状态可确认"):
        await advisor.confirm_advice(advice.id, user_id=1)


@pytest.mark.asyncio
async def test_reject_non_pending_raises_error(async_db):
    """拒绝非 pending 状态的建议应报错"""
    device = await _make_device(async_db, "AC", "NP02")
    advice = await _make_pending_advice(async_db, device)
    advice.status = "converted"
    await async_db.flush()

    advisor = MaintenanceAdvisor(async_db)
    with pytest.raises(ValueError, match="仅 pending 状态可拒绝"):
        await advisor.reject_advice(advice.id, feedback="不应成功")


# ==================== 6.12 边界测试 ====================

@pytest.mark.asyncio
async def test_score_40_boundary_triggers_advice(async_db):
    """score=40 边界值应触发建议（≤40）"""
    device = await _make_device(async_db, "AC", "BD01")
    dr = DegradationResult(
        device_id=device.id, score=40.0, confidence=0.8,
        available_points=3, total_points=5, data_sufficiency="full",
    )

    advisor = MaintenanceAdvisor(async_db)
    advice = await advisor.evaluate(device, health_score=40.0, degradation_result=dr)

    assert advice is not None
    assert advice.urgency == "medium"


@pytest.mark.asyncio
async def test_score_41_no_advice(async_db):
    """score=41 不触发建议（>40）"""
    device = await _make_device(async_db, "AC", "BD02")
    dr = DegradationResult(
        device_id=device.id, score=41.0, confidence=0.8,
        available_points=3, total_points=5, data_sufficiency="full",
    )

    advisor = MaintenanceAdvisor(async_db)
    advice = await advisor.evaluate(device, health_score=41.0, degradation_result=dr)
    assert advice is None


@pytest.mark.asyncio
async def test_auto_close_batch(async_db):
    """批量自动关闭测试"""
    d1 = await _make_device(async_db, "AC", "BT01")
    d2 = await _make_device(async_db, "AC", "BT02")
    await _make_pending_advice(async_db, d1)
    await _make_pending_advice(async_db, d2)

    advisor = MaintenanceAdvisor(async_db)
    count = await advisor.auto_close_pending_batch([d1.id, d2.id])
    assert count == 2
