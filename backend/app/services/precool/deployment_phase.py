"""
预冷功能分阶段部署控制服务

Story 32.2: 分阶段部署控制
- Phase 1: THM 模式（仅使用 THM 估算，不执行预冷）
- Phase 2: 校准模式（运行 RC 校准，对比 THM 与 TCL 结果）
- Phase 3: TCL 上线（使用校准后的 TCL 模型执行预冷）
- Phase 4: VPP 接入（开放 VPP 接口）
"""

import json
import logging
from typing import Any

from sqlalchemy import select, func

from app.core.database import async_session
from app.models.config import SystemConfig

logger = logging.getLogger(__name__)

# 阶段名称和描述映射
PHASE_NAMES = {
    1: ("THM 模式", "仅使用 THM 估算，不执行预冷"),
    2: ("校准模式", "运行 RC 校准，对比 THM 与 TCL 结果"),
    3: ("TCL 上线", "使用校准后的 TCL 模型执行预冷"),
    4: ("VPP 接入", "开放 VPP 接口"),
}

# 前置检查阈值
PHASE3_MIN_R_SQUARED = 0.85  # TCL 上线阈值（区别于校准写入阈值 0.7）
PHASE4_MIN_COMPLETED_DAYS = 7  # VPP 接入前需至少 7 天成功预冷记录

CONFIG_GROUP = "precool"
CONFIG_KEY = "deployment_phase"


class DeploymentPhaseService:
    """分阶段部署控制服务"""

    async def get_current_phase(self) -> dict[str, Any]:
        """获取当前部署阶段"""
        async with async_session() as session:
            config = await self._get_phase_config(session)
            try:
                phase = int(config.config_value) if config else 1
            except (ValueError, TypeError):
                phase = 1
            name, desc = PHASE_NAMES.get(phase, ("未知", "未知阶段"))
            return {
                "current_phase": phase,
                "phase_name": name,
                "description": desc,
                "updated_at": config.updated_at.isoformat() if config and config.updated_at else None,
            }

    async def update_phase(
        self,
        new_phase: int,
        force: bool,
        user_id: int,
        username: str = "",
    ) -> dict[str, Any]:
        """切换部署阶段

        Args:
            new_phase: 目标阶段 (1-4)
            force: 是否强制跳过前置检查（仅 admin）
            user_id: 操作用户 ID
            username: 操作用户名（审计日志用）

        Returns:
            成功: {"phase": N, "old_phase": M, "force_used": bool}
            失败: {"error": "...", "details": ...}
        """
        if new_phase < 1 or new_phase > 4:
            return {
                "error": "invalid_phase",
                "details": f"阶段必须在1-4之间，当前请求: {new_phase}",
            }

        async with async_session() as session:
            # 1. 获取当前阶段
            config = await self._get_phase_config(session)
            try:
                old_phase = int(config.config_value) if config else 1
            except (ValueError, TypeError):
                old_phase = 1

            if old_phase == new_phase:
                return {
                    "error": "same_phase",
                    "details": f"已处于阶段{new_phase}",
                }

            # 2. 前置检查（仅向上切换时）
            check_result = {"passed": True, "details": []}
            is_upgrade = new_phase > old_phase
            if is_upgrade and new_phase >= 3:
                phase3_result = await self._check_phase3_preconditions(session)
                if not phase3_result["passed"]:
                    check_result["passed"] = False
                    check_result["details"].extend(phase3_result["details"])

            if is_upgrade and new_phase >= 4:
                phase4_result = await self._check_phase4_preconditions(session)
                if not phase4_result["passed"]:
                    check_result["passed"] = False
                    check_result["details"].extend(phase4_result["details"])

            if not check_result["passed"] and not force:
                return {
                    "error": "precondition_failed",
                    "details": check_result["details"],
                }

            # 3. 更新阶段
            if config:
                config.config_value = str(new_phase)
                config.updated_by = user_id
            else:
                config = SystemConfig(
                    config_group=CONFIG_GROUP,
                    config_key=CONFIG_KEY,
                    config_value=str(new_phase),
                    value_type="number",
                    description="预冷功能部署阶段: 1=THM, 2=校准, 3=TCL上线, 4=VPP接入",
                    updated_by=user_id,
                )
                session.add(config)

            # 4. 审计日志
            from app.models.log import OperationLog

            log = OperationLog(
                user_id=user_id,
                username=username,
                module="precool",
                action="phase_switch",
                target_type="deployment_phase",
                target_id=0,
                target_name=f"phase_{old_phase}_to_{new_phase}",
                old_value=json.dumps({"phase": old_phase}),
                new_value=json.dumps(
                    {
                        "phase": new_phase,
                        "force": force,
                        "check_result": check_result,
                    }
                ),
            )
            session.add(log)

            try:
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error("部署阶段切换提交失败: %s", e)
                return {"error": "commit_failed", "details": str(e)}

            logger.info(
                "部署阶段切换: %d → %d (force=%s, user=%s)",
                old_phase,
                new_phase,
                force,
                username,
            )
            return {
                "phase": new_phase,
                "old_phase": old_phase,
                "force_used": force,
            }

    async def _get_phase_config(self, session) -> SystemConfig | None:
        """获取部署阶段配置记录"""
        result = await session.execute(
            select(SystemConfig)
            .where(SystemConfig.config_group == CONFIG_GROUP)
            .where(SystemConfig.config_key == CONFIG_KEY)
        )
        return result.scalar_one_or_none()

    async def _check_phase3_preconditions(self, session) -> dict[str, Any]:
        """Phase 3 前置检查：所有非 demo 区域已完成校准且 R² >= 0.85"""
        from app.models.thermal import ThermalParameter
        from app.models.topology_config import CoolingZone

        # 排除 demo zone
        demo_zone_ids = (
            select(ThermalParameter.cooling_zone_id)
            .where(ThermalParameter.is_demo == True)  # noqa: E712
            .where(ThermalParameter.is_active == True)  # noqa: E712
            .distinct()
        ).scalar_subquery()

        zones = (await session.execute(select(CoolingZone).where(CoolingZone.id.notin_(demo_zone_ids)))).scalars().all()

        # 无非 demo zone 时视为通过
        if not zones:
            return {"passed": True, "details": []}

        failures = []
        for zone in zones:
            param = (
                await session.execute(
                    select(ThermalParameter)
                    .where(ThermalParameter.cooling_zone_id == zone.id)
                    .where(ThermalParameter.is_active == True)  # noqa: E712
                    .where(ThermalParameter.is_demo == False)  # noqa: E712
                )
            ).scalar_one_or_none()

            if param is None or param.fitting_method not in ("auto_fit", "manual"):
                method = getattr(param, "fitting_method", None) if param else None
                failures.append(f"区域{zone.zone_name}(id={zone.id})未校准(fitting_method={method})")
            elif param.fitting_r_squared is None or param.fitting_r_squared < PHASE3_MIN_R_SQUARED:
                r2 = param.fitting_r_squared or 0
                failures.append(f"区域{zone.zone_name}(id={zone.id}) R²={r2:.2f}<{PHASE3_MIN_R_SQUARED}")

        return {"passed": len(failures) == 0, "details": failures}

    async def _check_phase4_preconditions(self, session) -> dict[str, Any]:
        """Phase 4 前置检查：预冷执行历史 >= 7 天"""
        from app.models.thermal import PrecoolSchedule

        result = await session.execute(
            select(func.count(func.distinct(PrecoolSchedule.schedule_date))).where(
                PrecoolSchedule.status == "completed"
            )
        )
        completed_days = result.scalar() or 0

        if completed_days >= PHASE4_MIN_COMPLETED_DAYS:
            return {"passed": True, "details": []}

        return {
            "passed": False,
            "details": [
                f"已完成预冷天数={completed_days}<{PHASE4_MIN_COMPLETED_DAYS}天，"
                f"需至少{PHASE4_MIN_COMPLETED_DAYS}天成功执行记录"
            ],
        }


# 模块级单例
deployment_phase_service = DeploymentPhaseService()
