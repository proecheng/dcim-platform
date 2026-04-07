"""
时间窗口调参服务
Story 26.4: 时间窗口自适应
"""

import logging
import json
import statistics
from typing import Optional
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models.diagnosis import TimeWindowAdjustmentLog
from app.models.config import SystemConfig

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
            # 通过 diagnosis_results.device_type 获取，JOIN annotations 通过 session_id
            query = """
                SELECT DISTINCT dr.device_type
                FROM diagnosis_results dr
                INNER JOIN diagnosis_annotations da ON da.session_id = dr.session_id
                INNER JOIN alarms a ON dr.alarm_id = a.id
                WHERE da.annotation = 'accurate'
                  AND a.resolved_at IS NOT NULL
                  AND a.duration_seconds > 0
                  AND dr.device_type IS NOT NULL
            """

            if device_type_filter:
                query += " AND dr.device_type = :device_type"

            result = await session.execute(
                text(query), {"device_type": device_type_filter} if device_type_filter else {}
            )
            device_types = [row[0] for row in result.fetchall()]

            if not device_types:
                logger.info(f"未找到有准确诊断的设备类型（过滤条件: {device_type_filter or '无'}），分析结束")
                return {"analyzed_device_types": 0, "total_adjustments": 0, "pending_approvals": 0}

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

        logger.info(
            f"时间窗口调参分析完成: 分析了 {analyzed_device_types} 个设备类型，生成 {total_adjustments} 条调参建议"
        )

        return {
            "analyzed_device_types": analyzed_device_types,
            "total_adjustments": total_adjustments,
            "pending_approvals": total_adjustments,
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
        # 使用 alarms.duration_seconds 字段（已计算），通过 Python 计算 P50/P90
        query = """
            SELECT
                a.duration_seconds AS duration_seconds
            FROM diagnosis_results dr
            INNER JOIN diagnosis_annotations da ON da.session_id = dr.session_id
            INNER JOIN alarms a ON dr.alarm_id = a.id
            WHERE dr.device_type = :device_type
              AND da.annotation = 'accurate'
              AND a.resolved_at IS NOT NULL
              AND a.duration_seconds > 0
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

        # 计算建议时间窗口: P90 × 1.2，转换为分钟，四舍五入
        proposed_window_seconds = p90_duration_seconds * 1.2
        proposed_window_minutes = round(proposed_window_seconds / 60)

        # 如果计算结果 < 1 分钟，强制设为 1 分钟
        if proposed_window_minutes < 1:
            logger.info(
                f"设备类型 {device_type} 计算的时间窗口 < 1 分钟（P90={p90_duration_seconds:.1f}秒 × 1.2 = {proposed_window_seconds:.1f}秒），设为最小值 1 分钟"
            )
            proposed_window_minutes = 1

        # 限制范围 [1, 120]
        if proposed_window_minutes > 120:
            logger.info(f"设备类型 {device_type} 计算的时间窗口 > 120 分钟，截断到最大值 120 分钟")
            proposed_window_minutes = 120

        # 计算调整百分比
        if current_window_minutes == 0:
            adjustment_percent = 0.0
            logger.error(f"设备类型 {device_type} 当前时间窗口为 0，配置错误")
        else:
            adjustment_percent = ((proposed_window_minutes - current_window_minutes) / current_window_minutes) * 100

        # 如果调整百分比 > 500%，记录警告（可能数据异常）
        if abs(adjustment_percent) > 500:
            logger.warning(f"设备类型 {device_type} 调整百分比过大（{adjustment_percent:.1f}%），可能数据异常")

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
            status="pending",
        )

        session.add(adjustment)
        logger.info(
            f"生成调参建议: {device_type}, {current_window_minutes} -> {proposed_window_minutes} 分钟 ({adjustment_percent:.2f}%)"
        )

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

        result = await session.execute(select(SystemConfig).where(SystemConfig.config_key == "diagnosis_time_windows"))
        config = result.scalar_one_or_none()

        if config and config.config_value:
            try:
                time_windows = (
                    json.loads(config.config_value) if isinstance(config.config_value, str) else config.config_value
                )
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
        logger.info(f"通知管理员审批: {result['pending_approvals']} 条待审批调参建议")

        # 查询所有管理员用户
        from app.models.user import User

        async with async_session() as session:
            admin_result = await session.execute(select(User).where(User.role == "admin", User.is_active == True))
            admins = admin_result.scalars().all()

            if not admins:
                logger.warning("未找到活跃的管理员用户，跳过通知")
                return

            # 发送邮件通知
            try:
                from app.services.email_service import email_service

                if email_service.is_available:
                    for admin in admins:
                        if admin.email:
                            try:
                                subject = "智能诊断系统 - 时间窗口调参审批通知"
                                body = f"""
                                <h2>时间窗口调参审批通知</h2>
                                <p>您好，{admin.real_name or admin.username}：</p>
                                <p>系统已完成时间窗口调参分析，有 <strong>{result["pending_approvals"]}</strong> 条调参建议待您审批。</p>
                                <p>请登录系统查看详情并进行审批。</p>
                                <p>分析结果：</p>
                                <ul>
                                    <li>分析的设备类型数量: {result["analyzed_device_types"]}</li>
                                    <li>生成的调参建议总数: {result["total_adjustments"]}</li>
                                    <li>待审批的调参建议数量: {result["pending_approvals"]}</li>
                                </ul>
                                <p>此邮件由系统自动发送，请勿回复。</p>
                                """
                                await email_service.send_html_email(
                                    to_email=admin.email, subject=subject, html_content=body
                                )
                                logger.info(f"已发送邮件通知给管理员: {admin.username} ({admin.email})")
                            except Exception as e:
                                logger.error(f"发送邮件给 {admin.username} 失败: {e}", exc_info=True)
                else:
                    logger.info("邮件服务未配置，跳过邮件通知")
            except ImportError:
                logger.warning("邮件服务模块未安装，跳过邮件通知")

            # 发送 WebSocket 通知
            try:
                from app.services.websocket import ws_manager

                message = {
                    "type": "time_window_tuning_approval",
                    "pending_count": result["pending_approvals"],
                    "analyzed_device_types": result["analyzed_device_types"],
                    "total_adjustments": result["total_adjustments"],
                }

                for admin in admins:
                    try:
                        await ws_manager.send_to_user(admin.username, message)
                        logger.info(f"已发送 WebSocket 通知给管理员: {admin.username}")
                    except Exception as e:
                        logger.error(f"发送 WebSocket 通知给 {admin.username} 失败: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"WebSocket 通知失败: {e}", exc_info=True)
