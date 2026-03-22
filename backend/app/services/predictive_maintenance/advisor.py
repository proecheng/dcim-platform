"""MaintenanceAdvisor — Story 36.3

维护建议引擎：健康度≤40时生成建议，≥60时自动关闭，支持确认转工单和拒绝。
"""

import logging
from datetime import datetime
from string import Template

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.report import MaintenanceAdvice
from ...models.operation import WorkOrder, WorkOrderType, WorkOrderStatus, WorkOrderPriority
from .base import DegradationResult

logger = logging.getLogger(__name__)

# 建议措施模板
ACTION_TEMPLATES: dict[str, dict[str, str]] = {
    "hvac": {
        "cop_trend": "COP 持续下降，建议检查制冷剂充注量、清洗冷凝器、检查压缩机运行参数",
        "compressor_hours": "压缩机累计运行 ${compressor_hours} 小时，建议安排预防性维护",
        "return_temp_trend": "回风温度上升趋势明显，建议检查设备性能、清洗过滤网",
        "default": "设备劣化评分偏低，建议安排检查",
    },
    "ups": {
        "battery_soh": "电池健康度降至 ${soh}%，建议评估电池更换计划",
        "default": "UPS 设备劣化评分偏低，建议安排检查",
    },
    "pdu": {
        "default": "PDU 设备劣化评分偏低，建议安排检查",
    },
}

# 紧急度 → 工单优先级映射
URGENCY_PRIORITY_MAP = {
    "high": WorkOrderPriority.critical,
    "medium": WorkOrderPriority.high,
}


def _calc_urgency(score: float) -> str:
    """评分→紧急度映射（仅 score≤40 时调用）"""
    if score < 20:
        return "high"
    return "medium"


def _generate_action(plugin_key: str, degradation_result: DegradationResult) -> str:
    """基于劣化因子模板生成建议措施"""
    templates = ACTION_TEMPLATES.get(plugin_key, ACTION_TEMPLATES.get("hvac", {}))
    primary = degradation_result.primary_concern

    if primary and primary in templates:
        tpl = templates[primary]
    else:
        tpl = templates.get("default", "设备劣化评分偏低，建议安排检查")

    # 安全替换变量（缺失变量保留占位符）
    return Template(tpl).safe_substitute(degradation_result.trend_factors)


def _generate_reason(device_type: str, health_score: float, degradation_result: DegradationResult) -> str:
    """生成劣化原因描述"""
    if degradation_result.primary_concern:
        return degradation_result.primary_concern
    return f"{device_type}设备劣化评分偏低（{health_score:.0f}分）"


class MaintenanceAdvisor:
    """维护建议引擎"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def evaluate(
        self,
        device,
        health_score: float,
        degradation_result: DegradationResult,
        plugin_key: str = "hvac",
    ) -> MaintenanceAdvice | None:
        """健康度≤40 时生成/更新维护建议（幂等）

        Args:
            device: Device 对象
            health_score: 当前健康度评分
            degradation_result: 劣化分析结果
            plugin_key: 设备类型插件标识

        Returns:
            MaintenanceAdvice 对象，或 None（评分 > 40）
        """
        if health_score > 40:
            return None

        urgency = _calc_urgency(health_score)
        reason = _generate_reason(device.device_type or plugin_key, health_score, degradation_result)
        action = _generate_action(plugin_key, degradation_result)

        # 查找已有 pending 建议
        result = await self.db.execute(
            select(MaintenanceAdvice).where(
                MaintenanceAdvice.device_id == device.id,
                MaintenanceAdvice.status == "pending",
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # 更新已有建议
            existing.health_score = health_score
            existing.urgency = urgency
            existing.reason = reason
            existing.suggested_action = action
            existing.updated_at = datetime.now()
            logger.info(
                "更新维护建议: advice_id=%d, device_id=%d, score=%.1f",
                existing.id, device.id, health_score,
            )
            return existing

        # 新建建议
        advice = MaintenanceAdvice(
            device_id=device.id,
            device_name=device.device_name,
            device_type=device.device_type,
            health_score=health_score,
            urgency=urgency,
            reason=reason,
            suggested_action=action,
            status="pending",
        )
        self.db.add(advice)
        await self.db.flush()  # 确保 ID 分配
        logger.info(
            "生成维护建议: advice_id=%d, device_id=%d, score=%.1f, urgency=%s",
            advice.id, device.id, health_score, urgency,
        )
        return advice

    async def auto_close_pending(self, device_id: int) -> int:
        """健康度≥60 时自动关闭 pending 建议

        Returns:
            关闭的建议数
        """
        result = await self.db.execute(
            update(MaintenanceAdvice)
            .where(
                MaintenanceAdvice.device_id == device_id,
                MaintenanceAdvice.status == "pending",
            )
            .values(status="auto_closed", updated_at=datetime.now())
        )
        count = result.rowcount
        if count > 0:
            logger.info("自动关闭维护建议: device_id=%d, count=%d", device_id, count)
        return count

    async def auto_close_pending_batch(self, device_ids: list[int]) -> int:
        """批量自动关闭 pending 建议

        Returns:
            关闭的建议数
        """
        if not device_ids:
            return 0
        result = await self.db.execute(
            update(MaintenanceAdvice)
            .where(
                MaintenanceAdvice.device_id.in_(device_ids),
                MaintenanceAdvice.status == "pending",
            )
            .values(status="auto_closed", updated_at=datetime.now())
        )
        count = result.rowcount
        if count > 0:
            logger.info("批量自动关闭维护建议: devices=%d, closed=%d", len(device_ids), count)
        return count

    async def confirm_advice(self, advice_id: int, user_id: int) -> WorkOrder:
        """确认建议 → 创建维护工单

        Raises:
            ValueError: 建议不存在或状态非 pending
        """
        advice = await self.db.get(MaintenanceAdvice, advice_id)
        if not advice:
            raise ValueError("建议不存在")
        if advice.status != "pending":
            raise ValueError(f"建议状态为 {advice.status}，仅 pending 状态可确认")

        order_no = await self._generate_order_no()
        title = f"预防性维护: {advice.device_name or '未知设备'}"
        if advice.reason:
            title += f" - {advice.reason[:40]}"
        # 工单标题不超过 200 字符
        title = title[:200]

        wo = WorkOrder(
            order_no=order_no,
            title=title,
            description=f"劣化原因: {advice.reason}\n建议措施: {advice.suggested_action}",
            order_type=WorkOrderType.maintenance,
            priority=URGENCY_PRIORITY_MAP.get(advice.urgency, WorkOrderPriority.high),
            device_id=advice.device_id,
            device_name=advice.device_name,
            status=WorkOrderStatus.pending,
            reporter="系统(预测性维护)",
        )
        self.db.add(wo)
        await self.db.flush()

        advice.status = "converted"
        advice.work_order_id = wo.id
        advice.confirmed_at = datetime.now()
        advice.confirmed_by = user_id

        logger.info(
            "维护建议确认转工单: advice_id=%d, work_order_id=%d, order_no=%s",
            advice_id, wo.id, order_no,
        )
        return wo

    async def reject_advice(self, advice_id: int, feedback: str) -> MaintenanceAdvice:
        """拒绝建议（标记误报）

        Raises:
            ValueError: 建议不存在或状态非 pending
        """
        advice = await self.db.get(MaintenanceAdvice, advice_id)
        if not advice:
            raise ValueError("建议不存在")
        if advice.status != "pending":
            raise ValueError(f"建议状态为 {advice.status}，仅 pending 状态可拒绝")

        advice.status = "rejected"
        advice.feedback = feedback
        advice.updated_at = datetime.now()

        logger.info("维护建议被拒绝: advice_id=%d, feedback=%s", advice_id, feedback[:50])
        return advice

    async def _generate_order_no(self) -> str:
        """生成维护工单编号：MA-YYYYMMDD-NNN"""
        today = datetime.now().strftime("%Y%m%d")
        prefix = f"MA-{today}-"

        result = await self.db.execute(
            select(func.count(WorkOrder.id)).where(
                WorkOrder.order_no.like(f"{prefix}%")
            )
        )
        count = result.scalar() or 0
        return f"{prefix}{count + 1:03d}"
