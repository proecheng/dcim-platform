"""
时间窗口调参服务
Story 26.4: 时间窗口自适应
"""

import logging
import json
import statistics
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select, and_, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models.diagnosis import TimeWindowAdjustmentLog
from app.models.alarm import Alarm
from app.models.config import SystemConfig
from app.schemas.time_window_tuning import TimeWindowAdjustmentCreate

logger = logging.getLogger(__name__)


class TimeWindowTuningService:
    """时间窗口调参服务"""

    def __init__(self):
        pass

    async def analyze_all_device_types(self, device_type_filter: Optional[str] = None) -> dict:
        """
        分析所有设备类型，生成调参建议

        Args:
            device_type_filter: 可选的设备类型过滤器

        Returns:
            dict: {
                "analyzed_device_types": int,
                "total_adjustments": int,
                "pending_approvals": int
            }
        """
        logger.info(f"开始执行时间窗口调参分析，设备类型过滤: {device_type_filter}")

        analyzed_device_types = 0
        total_adjustments = 0

        async with async_session() as session:
            # 查询所有有准确诊断的设备类型
            # 注意：这里假设 diagnosis_results 表有 device_type 字段
            # 实际实现时需要通过 JOIN alarms 表获取 device_type
            query = """
                SELECT DISTINCT d.device_type
                FROM devices d
                INNER JOIN alarms a ON a.device_id = d.id
                INNER JOIN diagnosis_results dr ON dr.alarm_id = a.id
                INNER JOIN diagnosis_annotations da ON da.result_id = dr.id
                WHERE da.annotation = 'accurate'
                  AND a.recovered_at IS NOT NULL
                  AND a.recovered_at > a.created_at
            """

            if device_type_filter:
                query += f" AND d.device_type = :device_type"

            result = await session.execute(
                text(query),
                {"device_type": device_type_filter} if device_type_filter else {}
            )
            device_types = [row[0] for row in result.fetchall()]

            logger.info(f"找到 {len(device_types)} 个设备类型需要分析")

            for device_type in device_types:
                try:
                    adjustment = await self._analyze_device_type(session, device_type)
                    if adjustment:
                        total_adjustments += 1
                        analyzed_device_types += 1
                except Exception as e:
                    logger.error(f"分析设备类型 {device_type} 失败: {e}", exc_info=True)

            await session.commit()

        logger.info(f"时间窗口调参分析完成: 分析了 {analyzed_device_types} 个设备类型，生成 {total_adjustments} 条调参建议")

        return {
            "analyzed_device_types": analyzed_device_types,
            "total_adjustments": total_adjustments,
            "pending_approvals": total_adjustments
        }

    async def _analyze_device_type(self, session: AsyncSession, device_type: str) -> Optional[TimeWindowAdjustmentLog]:
        """
        分析单个设备类型，生成调参建议

        Args:
            session: 数据库会话
            device_type: 设备类型

        Returns:
            Optional[TimeWindowAdjustmentLog]: 生成的调参记录，如果不需要调参则返回 None
        """
        # 获取当前时间窗口配置
        current_window_minutes = await self._get_current_window_minutes(session, device_type)

        # 查询该设备类型的告警持续时长统计
        # 使用 SQL percentile_cont 函数计算 P50 和 P90
        # 注意：SQLite 不支持 percentile_cont，需要使用 Python 计算
        query = """
            SELECT
                (CAST(strftime('%s', a.recovered_at) AS INTEGER) - CAST(strftime('%s', a.created_at) AS INTEGER)) AS duration_seconds
            FROM alarms a
            INNER JOIN devices d ON a.device_id = d.id
            INNER JOIN diagnosis_results dr ON dr.alarm_id = a.id
            INNER JOIN diagnosis_annotations da ON da.result_id = dr.id
            WHERE d.device_type = :device_type
              AND da.annotation = 'accurate'
              AND a.recovered_at IS NOT NULL
              AND a.recovered_at > a.created_at
              AND (CAST(strftime('%s', a.recovered_at) AS INTEGER) - CAST(strftime('%s', a.created_at) AS INTEGER)) > 0
        """

        result = await session.execute(text(query), {"device_type": device_type})
        durations = [row[0] for row in result.fetchall()]

        if len(durations) < 10:
            logger.info(f"设备类型 {device_type} 样本数不足（{len(durations)} < 10），跳过调参")
            return None

        # 使用 statistics.quantiles 计算 P50 和 P90
        try:
            # quantiles(data, n=4) 返回 3 个分位数: Q1(25%), Q2(50%), Q3(75%)
            # quantiles(data, n=10) 返回 9 个分位数: 10%, 20%, ..., 90%
            quantiles_10 = statistics.quantiles(durations, n=10)
            p50_duration_seconds = quantiles_10[4]  # 第5个元素是 P50 (50%)
            p90_duration_seconds = quantiles_10[8]  # 第9个元素是 P90 (90%)
        except statistics.StatisticsError as e:
            logger.error(f"计算分位数失败: {e}")
            return None

        # 计算建议时间窗口: P90 × 1.2，转换为分钟，向上取整
        proposed_window_seconds = p90_duration_seconds * 1.2
        proposed_window_minutes = max(1, round(proposed_window_seconds / 60))

        # 限制范围 [1, 120]
        proposed_window_minutes = max(1, min(120, proposed_window_minutes))

        # 计算调整百分比
        if current_window_minutes == 0:
            adjustment_percent = 0.0
        else:
            adjustment_percent = ((proposed_window_minutes - current_window_minutes) / current_window_minutes) * 100

        # 如果调整幅度 < 10%，不生成调参建议
        if abs(adjustment_percent) < 10:
            logger.info(f"设备类型 {device_type} 调整幅度 {adjustment_percent:.2f}% < 10%，跳过调参")
            return None

        # 创建调参记录
        adjustment = TimeWindowAdjustmentLog(
            device_type=device_type,
            current_window_minutes=current_window_minutes,
            proposed_window_minutes=proposed_window_minutes,
            adjustment_percent=adjustment_percent,
            sample_count=len(durations),
            p50_duration_seconds=p50_duration_seconds,
            p90_duration_seconds=p90_duration_seconds,
            status='pending'
        )

        session.add(adjustment)
        logger.info(f"生成调参建议: {device_type}, {current_window_minutes} -> {proposed_window_minutes} 分钟 ({adjustment_percent:.2f}%)")

        return adjustment

    async def _get_current_window_minutes(self, session: AsyncSession, device_type: str) -> int:
        """
        获取当前时间窗口配置

        Args:
            session: 数据库会话
            device_type: 设备类型

        Returns:
            int: 当前时间窗口(分钟)
        """
        # 查询 system_configs 表
        # config_key = 'diagnosis_time_windows'
        # config_value = JSON: { "UPS": 30, "空调": 60, ... }

        result = await session.execute(
            select(SystemConfig).where(SystemConfig.config_key == 'diagnosis_time_windows')
        )
        config = result.scalar_one_or_none()

        if config and config.config_value:
            try:
                time_windows = json.loads(config.config_value) if isinstance(config.config_value, str) else config.config_value
                return time_windows.get(device_type, 30)  # 默认 30 分钟
            except (json.JSONDecodeError, AttributeError) as e:
                logger.error(f"解析 diagnosis_time_windows 配置失败: {e}")
                return 30

        # 如果配置不存在，返回默认值 30 分钟
        return 30

    async def notify_admins(self, result: dict):
        """
        通知管理员审批

        Args:
            result: 调参分析结果
        """
        # 注意：这里需要实现邮件和 WebSocket 通知
        # 邮件主题: "智能诊断系统 - 时间窗口调参审批通知"
        # 邮件正文: 包含待审批调参数量、设备类型、调整建议
        # WebSocket 消息: { "type": "time_window_tuning_approval", "pending_count": 5 }
        # 通知对象: 所有 role='admin' 的用户

        logger.info(f"通知管理员审批: {result['pending_approvals']} 条待审批调参建议")

        # 临时实现：仅记录日志
        pass
