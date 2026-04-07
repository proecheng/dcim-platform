"""
VPP 调控指令接收与处理服务

Story 33.2: 接收 VPP 平台下发的负荷调控指令，校验安全约束，
检测冲突并中止预冷计划，记录指令处理结果。
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.sql import func

from ...core.database import async_session
from ...core.redis import redis_service
from ...models.thermal import PrecoolSchedule, VppDispatch

logger = logging.getLogger(__name__)


class VppDispatchService:
    """VPP 调控指令处理服务"""

    MAX_RATE_PER_HOUR = 12

    async def check_rate_limit(self) -> bool:
        """检查速率限制（每小时 ≤ 12 条）"""
        hour_key = f"vpp:dispatch:rate:{datetime.now().strftime('%Y%m%d%H')}"
        try:
            count_data = await redis_service.get_json(hour_key)
            current = count_data if isinstance(count_data, int) else 0
            if current >= self.MAX_RATE_PER_HOUR:
                return False
            await redis_service.set_json(hour_key, current + 1, ttl=3600)
            return True
        except Exception as e:
            logger.warning("VPP 速率限制检查失败（降级放行）: %s", e)
            return True

    async def validate_and_execute(self, request: dict) -> dict:
        """验证并处理 VPP 调控指令

        Args:
            request: 包含 command_type, target_power_kw, duration_minutes, priority

        Returns:
            VppDispatchResponse 字典
        """
        async with async_session() as session:
            # 1. 创建 VppDispatch 记录
            dispatch = VppDispatch(
                dispatch_id=str(uuid.uuid4()),
                command_type=request["command_type"],
                target_power_kw=request["target_power_kw"],
                duration_minutes=request["duration_minutes"],
                priority=request.get("priority", 1),
                status="received",
            )
            session.add(dispatch)

            # 2. 基本参数校验
            if request["target_power_kw"] <= 0:
                dispatch.status = "rejected"
                dispatch.reject_reason = "target_power_kw 必须大于 0"
                await session.commit()
                return self._build_response(dispatch)

            if request["duration_minutes"] <= 0:
                dispatch.status = "rejected"
                dispatch.reject_reason = "duration_minutes 必须大于 0"
                await session.commit()
                return self._build_response(dispatch)

            # 3. 获取当前可调容量
            try:
                from .vpp_capacity import vpp_capacity_service

                capacity = await vpp_capacity_service.calculate_capacity()
            except Exception as e:
                logger.error("VPP 调控 - 容量计算失败: %s", e, exc_info=True)
                dispatch.status = "rejected"
                dispatch.reject_reason = f"容量计算失败: {e}"
                await session.commit()
                return self._build_response(dispatch)

            # 4. 确定可调容量上限
            if request["command_type"] == "down_adjust":
                max_kw = capacity["down_adjustable_kw"]
            else:  # up_adjust
                max_kw = capacity["up_adjustable_kw"]

            # 5. 安全约束校验
            if request["target_power_kw"] > max_kw:
                dispatch.status = "rejected"
                dispatch.reject_reason = f"请求功率 {request['target_power_kw']:.1f} kW 超过可调容量 {max_kw:.1f} kW"
                dispatch.max_adjustable_kw = max_kw
                await session.commit()
                return self._build_response(dispatch)

            # 6. 冲突检测（仅 down_adjust 需要检查预冷计划冲突）
            if request["command_type"] == "down_adjust":
                aborted_id = await self._check_and_abort_conflicts(session)
                if aborted_id:
                    dispatch.aborted_schedule_id = aborted_id

            # 7. 接受指令
            dispatch.status = "accepted"
            dispatch.accepted_power_kw = min(request["target_power_kw"], max_kw)
            await session.commit()

            logger.info(
                "VPP 调控指令已接受: dispatch_id=%s, type=%s, power=%.1f kW",
                dispatch.dispatch_id,
                dispatch.command_type,
                dispatch.accepted_power_kw,
            )

            return self._build_response(dispatch)

    async def _check_and_abort_conflicts(self, session) -> Optional[int]:
        """检查并中止与 VPP down_adjust 冲突的执行中预冷计划

        冲突条件：当前有 executing 状态的预冷计划且处于预冷时段
        处理：VPP 优先级 > 预冷计划，中止预冷计划
        """
        now = datetime.now()
        today = now.date()
        current_time = now.time()

        result = await session.execute(
            select(PrecoolSchedule).where(
                PrecoolSchedule.status == "executing",
                PrecoolSchedule.schedule_date == today,
                PrecoolSchedule.precool_start_time <= current_time,
                PrecoolSchedule.precool_end_time > current_time,
            )
        )
        active_plans = result.scalars().all()

        if not active_plans:
            return None

        # 中止第一个冲突计划
        plan = active_plans[0]
        try:
            from .executor import precool_executor

            await precool_executor.abort_plan_by_api(plan, "vpp_override", session)
            logger.info(
                "VPP 指令中止预冷计划: schedule_id=%d, zone_id=%d",
                plan.id,
                plan.cooling_zone_id,
            )
            return plan.id
        except Exception as e:
            logger.error(
                "中止预冷计划失败: schedule_id=%d, error=%s",
                plan.id,
                e,
                exc_info=True,
            )
            return None

    async def list_dispatches(self, page: int = 1, page_size: int = 20, status: str = None) -> dict:
        """查询 VPP 调控指令列表（分页）"""
        async with async_session() as session:
            query = select(VppDispatch).order_by(VppDispatch.created_at.desc())
            count_query = select(func.count()).select_from(VppDispatch)

            if status:
                query = query.where(VppDispatch.status == status)
                count_query = count_query.where(VppDispatch.status == status)

            total_result = await session.execute(count_query)
            total = total_result.scalar() or 0

            query = query.offset((page - 1) * page_size).limit(page_size)
            result = await session.execute(query)
            dispatches = result.scalars().all()

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [self._build_response(d) for d in dispatches],
            }

    async def get_statistics(self) -> dict:
        """查询 VPP 需求响应统计（日/月）"""
        async with async_session() as session:
            now = datetime.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # 日统计
            daily_result = await session.execute(
                select(
                    func.count().label("count"),
                    func.sum(VppDispatch.accepted_power_kw).label("total_power"),
                ).where(
                    VppDispatch.status == "accepted",
                    VppDispatch.created_at >= today_start,
                )
            )
            daily = daily_result.first()

            # 月统计
            monthly_result = await session.execute(
                select(
                    func.count().label("count"),
                    func.sum(VppDispatch.accepted_power_kw).label("total_power"),
                ).where(
                    VppDispatch.status == "accepted",
                    VppDispatch.created_at >= month_start,
                )
            )
            monthly = monthly_result.first()

            # 峰谷价差估算节省电费（0.5 元/kWh）
            PRICE_DIFF = 0.5
            daily_count = daily.count if daily else 0
            daily_power = float(daily.total_power or 0)
            monthly_count = monthly.count if monthly else 0
            monthly_power = float(monthly.total_power or 0)

            return {
                "daily": {
                    "count": daily_count,
                    "total_power_kw": round(daily_power, 1),
                    "estimated_savings_yuan": round(daily_power * PRICE_DIFF, 2),
                },
                "monthly": {
                    "count": monthly_count,
                    "total_power_kw": round(monthly_power, 1),
                    "estimated_savings_yuan": round(monthly_power * PRICE_DIFF, 2),
                },
            }

    def _build_response(self, dispatch: VppDispatch) -> dict:
        """构建响应字典"""
        return {
            "dispatch_id": dispatch.dispatch_id,
            "command_type": dispatch.command_type,
            "target_power_kw": dispatch.target_power_kw,
            "duration_minutes": dispatch.duration_minutes,
            "status": dispatch.status,
            "reject_reason": dispatch.reject_reason,
            "max_adjustable_kw": dispatch.max_adjustable_kw,
            "accepted_power_kw": dispatch.accepted_power_kw,
            "aborted_schedule_id": dispatch.aborted_schedule_id,
            "created_at": (dispatch.created_at.isoformat() if dispatch.created_at else None),
        }


# 全局单例
vpp_dispatch_service = VppDispatchService()
