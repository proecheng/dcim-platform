"""
控制命令分级确认服务
Story 9-6: 控制命令分级确认
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ..models.command import CommandApproval, CommandAuditLog
from ..models.config import SystemConfig

logger = logging.getLogger(__name__)

# 默认风险等级映射
DEFAULT_RISK_CONFIGS = {
    "ac_temp_set": {"risk_level": "normal", "description": "调整空调温度"},
    "light_switch": {"risk_level": "normal", "description": "开关照明"},
    "door_access": {"risk_level": "normal", "description": "门禁开关"},
    "power_off": {"risk_level": "critical", "description": "切断回路电源"},
    "ups_switch": {"risk_level": "critical", "description": "UPS 切换"},
    "device_decommission": {"risk_level": "critical", "description": "设备下架断电"},
}


async def get_risk_level(db: AsyncSession, command_type: str) -> str:
    """获取命令类型的风险等级"""
    result = await db.execute(
        select(SystemConfig).where(
            SystemConfig.config_group == "command_risk",
            SystemConfig.config_key == command_type,
        )
    )
    config = result.scalar_one_or_none()
    if config and config.config_value in ("normal", "critical"):
        return config.config_value
    # 回退到默认配置
    default = DEFAULT_RISK_CONFIGS.get(command_type)
    if default:
        return default["risk_level"]
    return "normal"


async def submit_command(
    db: AsyncSession,
    command_type: str,
    target_device_id: int,
    target_device_name: str,
    command_content: dict,
    operator_id: int,
    operator_name: str,
    timeout_minutes: int = 30,
) -> dict:
    """
    提交控制命令，根据风险等级执行不同流程。
    返回 dict: {status, message, approval_id?, audit_log_id?}
    """
    risk_level = await get_risk_level(db, command_type)

    if risk_level == "critical":
        # 关键命令 → 创建审批工单
        now = datetime.now()
        approval = CommandApproval(
            command_type=command_type,
            risk_level=risk_level,
            target_device_id=target_device_id,
            target_device_name=target_device_name,
            command_content=command_content,
            requester_id=operator_id,
            requester_name=operator_name,
            status="pending",
            timeout_minutes=timeout_minutes,
            created_at=now,
            expired_at=now + timedelta(minutes=timeout_minutes),
        )
        db.add(approval)
        await db.flush()

        # 写入审计日志（pending 状态）
        audit_log = CommandAuditLog(
            command_type=command_type,
            risk_level=risk_level,
            target_device_id=target_device_id,
            target_device_name=target_device_name,
            command_content=command_content,
            operator_id=operator_id,
            operator_name=operator_name,
            approval_id=approval.id,
            result="pending",
            result_message="已提交审批，等待审批人确认",
        )
        db.add(audit_log)
        await db.commit()

        logger.info(f"关键命令已提交审批: approval_id={approval.id}, type={command_type}")
        return {
            "status": "pending_approval",
            "message": "已提交审批，等待审批人确认",
            "approval_id": approval.id,
            "audit_log_id": audit_log.id,
        }
    else:
        # 普通命令 → 直接执行（模拟）
        audit_log = CommandAuditLog(
            command_type=command_type,
            risk_level=risk_level,
            target_device_id=target_device_id,
            target_device_name=target_device_name,
            command_content=command_content,
            operator_id=operator_id,
            operator_name=operator_name,
            approval_id=None,
            result="success",
            result_message="命令已下发（模拟）",
        )
        db.add(audit_log)
        await db.commit()

        logger.info(f"普通命令已执行: type={command_type}, device={target_device_name}")
        return {
            "status": "executed",
            "message": "命令已下发",
            "audit_log_id": audit_log.id,
        }


async def approve_command(
    db: AsyncSession,
    approval_id: int,
    approver_id: int,
    approver_name: str,
) -> Optional[CommandApproval]:
    """批准审批工单，执行命令"""
    result = await db.execute(
        select(CommandApproval).where(CommandApproval.id == approval_id)
    )
    approval = result.scalar_one_or_none()
    if not approval:
        return None

    if approval.status != "pending":
        raise ValueError(f"审批工单状态为 {approval.status}，无法批准")

    # 检查是否已超时
    if datetime.now() > approval.expired_at:
        approval.status = "timeout"
        await _update_audit_log_result(db, approval.id, "timeout", "审批已超时")
        await db.commit()
        raise ValueError("审批工单已超时")

    now = datetime.now()
    approval.status = "approved"
    approval.approver_id = approver_id
    approval.approver_name = approver_name
    approval.approved_at = now
    approval.executed_at = now  # 模拟立即执行

    # 更新审计日志
    await _update_audit_log_result(db, approval.id, "success", "审批通过，命令已下发（模拟）")
    await db.commit()

    logger.info(f"审批通过: approval_id={approval_id}, approver={approver_name}")
    return approval


async def reject_command(
    db: AsyncSession,
    approval_id: int,
    approver_id: int,
    approver_name: str,
    reason: str,
) -> Optional[CommandApproval]:
    """驳回审批工单"""
    result = await db.execute(
        select(CommandApproval).where(CommandApproval.id == approval_id)
    )
    approval = result.scalar_one_or_none()
    if not approval:
        return None

    if approval.status != "pending":
        raise ValueError(f"审批工单状态为 {approval.status}，无法驳回")

    approval.status = "rejected"
    approval.approver_id = approver_id
    approval.approver_name = approver_name
    approval.approved_at = datetime.now()
    approval.reject_reason = reason

    # 更新审计日志
    await _update_audit_log_result(db, approval.id, "cancelled", f"审批驳回: {reason}")
    await db.commit()

    logger.info(f"审批驳回: approval_id={approval_id}, reason={reason}")
    return approval


async def check_expired_approvals(db: AsyncSession) -> int:
    """检查并标记超时的审批工单（惰性检查）"""
    now = datetime.now()
    result = await db.execute(
        select(CommandApproval).where(
            CommandApproval.status == "pending",
            CommandApproval.expired_at < now,
        )
    )
    expired_list = result.scalars().all()

    count = 0
    for approval in expired_list:
        approval.status = "timeout"
        await _update_audit_log_result(db, approval.id, "timeout", "审批超时，自动取消")
        count += 1

    if count > 0:
        await db.commit()
        logger.info(f"已标记 {count} 个超时审批工单")

    return count


async def get_risk_configs(db: AsyncSession) -> list[dict]:
    """获取所有风险等级配置"""
    result = await db.execute(
        select(SystemConfig).where(
            SystemConfig.config_group == "command_risk"
        ).order_by(SystemConfig.config_key)
    )
    configs = result.scalars().all()

    # 合并数据库配置和默认配置
    config_map = {}
    for key, default in DEFAULT_RISK_CONFIGS.items():
        config_map[key] = {
            "command_type": key,
            "risk_level": default["risk_level"],
            "description": default["description"],
        }

    for config in configs:
        if config.config_key in config_map:
            config_map[config.config_key]["risk_level"] = config.config_value
        else:
            config_map[config.config_key] = {
                "command_type": config.config_key,
                "risk_level": config.config_value,
                "description": config.description or "",
            }

    return list(config_map.values())


async def update_risk_configs(
    db: AsyncSession,
    configs: list[dict],
    updated_by: int,
) -> int:
    """批量更新风险等级配置"""
    updated = 0
    for item in configs:
        command_type = item["command_type"]
        risk_level = item["risk_level"]
        description = item.get("description", "")

        if risk_level not in ("normal", "critical"):
            raise ValueError(f"无效的风险等级: {risk_level}，只允许 normal 或 critical")

        result = await db.execute(
            select(SystemConfig).where(
                SystemConfig.config_group == "command_risk",
                SystemConfig.config_key == command_type,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.config_value = risk_level
            existing.description = description
            existing.updated_by = updated_by
            existing.updated_at = datetime.now()
        else:
            new_config = SystemConfig(
                config_group="command_risk",
                config_key=command_type,
                config_value=risk_level,
                value_type="string",
                description=description,
                is_editable=True,
                updated_by=updated_by,
            )
            db.add(new_config)
        updated += 1

    await db.commit()
    logger.info(f"已更新 {updated} 条风险配置")
    return updated


async def _update_audit_log_result(
    db: AsyncSession,
    approval_id: int,
    result: str,
    result_message: str,
) -> None:
    """更新审计日志中关联审批的结果"""
    await db.execute(
        update(CommandAuditLog).where(
            CommandAuditLog.approval_id == approval_id
        ).values(
            result=result,
            result_message=result_message,
        )
    )
