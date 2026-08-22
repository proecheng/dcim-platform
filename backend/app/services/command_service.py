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
from .command_registry import COMMAND_DEFINITIONS, CommandPolicyError, authorize_command, get_command_definition

logger = logging.getLogger(__name__)

# 默认风险等级映射
DEFAULT_RISK_CONFIGS = {
    key: {"risk_level": definition.minimum_risk, "description": definition.description}
    for key, definition in COMMAND_DEFINITIONS.items()
    if "command_api" in definition.entrypoints
}


async def get_risk_level(db: AsyncSession, command_type: str) -> str:
    """获取命令类型的风险等级"""
    definition = get_command_definition(command_type)
    result = await db.execute(
        select(SystemConfig).where(
            SystemConfig.config_group == "command_risk",
            SystemConfig.config_key == command_type,
        )
    )
    config = result.scalar_one_or_none()
    if config:
        if config.config_value not in ("normal", "critical"):
            raise CommandPolicyError(f"命令 {command_type!r} 的风险分类无效")
        if definition.minimum_risk == "critical" and config.config_value != "critical":
            raise CommandPolicyError(f"命令 {command_type!r} 低于最低风险等级 critical")
        return config.config_value
    return definition.minimum_risk


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
    try:
        authorization = authorize_command(command_type, command_content, entrypoint="command_api")
        risk_level = await get_risk_level(db, command_type)
    except CommandPolicyError as exc:
        audit_log = CommandAuditLog(
            command_type=command_type[:50] or "<empty>",
            risk_level="unclassified",
            target_device_id=target_device_id,
            target_device_name=target_device_name,
            command_content=command_content,
            operator_id=operator_id,
            operator_name=operator_name,
            result="rejected",
            result_message=str(exc),
        )
        db.add(audit_log)
        await db.commit()
        raise

    if authorization.requires_approval and risk_level != "critical":
        raise CommandPolicyError(f"受保护命令 {command_type!r} 必须使用 critical 风险等级")

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
    result = await db.execute(select(CommandApproval).where(CommandApproval.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        return None

    if approval.requester_id == approver_id:
        _add_approval_audit_event(
            db,
            approval,
            operator_id=approver_id,
            operator_name=approver_name,
            result="rejected",
            result_message="拒绝自审批尝试：请求人不能审批自己的受保护命令",
        )
        await db.commit()
        raise ValueError("请求人不能审批自己的受保护命令")

    if approval.status != "pending":
        _add_approval_audit_event(
            db,
            approval,
            operator_id=approver_id,
            operator_name=approver_name,
            result="rejected",
            result_message=f"拒绝重复审批尝试：工单状态为 {approval.status}",
        )
        await db.commit()
        raise ValueError(f"审批工单状态为 {approval.status}，无法批准")

    # 检查是否已超时
    if datetime.now() > approval.expired_at:
        timeout_result = await db.execute(
            update(CommandApproval)
            .where(CommandApproval.id == approval_id, CommandApproval.status == "pending")
            .values(status="timeout")
        )
        if timeout_result.rowcount != 1:
            await db.rollback()
            current = (await db.execute(select(CommandApproval).where(CommandApproval.id == approval_id))).scalar_one()
            _add_approval_audit_event(
                db,
                current,
                operator_id=approver_id,
                operator_name=approver_name,
                result="rejected",
                result_message=f"拒绝并发超时处理：工单状态为 {current.status}",
            )
            await db.commit()
            raise ValueError(f"审批工单状态为 {current.status}，无法批准")
        _add_approval_audit_event(
            db,
            approval,
            operator_id=approver_id,
            operator_name=approver_name,
            result="timeout",
            result_message="审批已超时",
        )
        await db.commit()
        raise ValueError("审批工单已超时")

    now = datetime.now()
    result = await db.execute(
        update(CommandApproval)
        .where(
            CommandApproval.id == approval_id,
            CommandApproval.status == "pending",
            CommandApproval.requester_id != approver_id,
            CommandApproval.expired_at >= now,
        )
        .values(
            status="approved",
            approver_id=approver_id,
            approver_name=approver_name,
            approved_at=now,
            executed_at=now,
        )
    )
    if result.rowcount != 1:
        await db.rollback()
        current = (await db.execute(select(CommandApproval).where(CommandApproval.id == approval_id))).scalar_one()
        _add_approval_audit_event(
            db,
            current,
            operator_id=approver_id,
            operator_name=approver_name,
            result="rejected",
            result_message=f"拒绝并发审批尝试：工单状态为 {current.status}",
        )
        await db.commit()
        raise ValueError(f"审批工单状态为 {current.status}，无法批准")

    _add_approval_audit_event(
        db,
        approval,
        operator_id=approver_id,
        operator_name=approver_name,
        result="success",
        result_message="审批通过，命令已下发（模拟）",
    )
    await db.commit()
    await db.refresh(approval)

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
    result = await db.execute(select(CommandApproval).where(CommandApproval.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        return None

    if approval.requester_id == approver_id:
        _add_approval_audit_event(
            db,
            approval,
            operator_id=approver_id,
            operator_name=approver_name,
            result="rejected",
            result_message="拒绝自处理尝试：请求人不能审批自己的受保护命令",
        )
        await db.commit()
        raise ValueError("请求人不能审批自己的受保护命令")

    if approval.status != "pending":
        _add_approval_audit_event(
            db,
            approval,
            operator_id=approver_id,
            operator_name=approver_name,
            result="rejected",
            result_message=f"拒绝重复驳回尝试：工单状态为 {approval.status}",
        )
        await db.commit()
        raise ValueError(f"审批工单状态为 {approval.status}，无法驳回")

    if datetime.now() > approval.expired_at:
        timeout_result = await db.execute(
            update(CommandApproval)
            .where(CommandApproval.id == approval_id, CommandApproval.status == "pending")
            .values(status="timeout")
        )
        if timeout_result.rowcount != 1:
            await db.rollback()
            current = (await db.execute(select(CommandApproval).where(CommandApproval.id == approval_id))).scalar_one()
            _add_approval_audit_event(
                db,
                current,
                operator_id=approver_id,
                operator_name=approver_name,
                result="rejected",
                result_message=f"拒绝并发超时处理：工单状态为 {current.status}",
            )
            await db.commit()
            raise ValueError(f"审批工单状态为 {current.status}，无法驳回")
        _add_approval_audit_event(
            db,
            approval,
            operator_id=approver_id,
            operator_name=approver_name,
            result="timeout",
            result_message="审批已超时",
        )
        await db.commit()
        raise ValueError("审批工单已超时")

    now = datetime.now()
    result = await db.execute(
        update(CommandApproval)
        .where(
            CommandApproval.id == approval_id,
            CommandApproval.status == "pending",
            CommandApproval.requester_id != approver_id,
            CommandApproval.expired_at >= now,
        )
        .values(
            status="rejected",
            approver_id=approver_id,
            approver_name=approver_name,
            approved_at=now,
            reject_reason=reason,
        )
    )
    if result.rowcount != 1:
        await db.rollback()
        current = (await db.execute(select(CommandApproval).where(CommandApproval.id == approval_id))).scalar_one()
        _add_approval_audit_event(
            db,
            current,
            operator_id=approver_id,
            operator_name=approver_name,
            result="rejected",
            result_message=f"拒绝并发驳回尝试：工单状态为 {current.status}",
        )
        await db.commit()
        raise ValueError(f"审批工单状态为 {current.status}，无法驳回")

    _add_approval_audit_event(
        db,
        approval,
        operator_id=approver_id,
        operator_name=approver_name,
        result="cancelled",
        result_message=f"审批驳回: {reason}",
    )
    await db.commit()
    await db.refresh(approval)

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
        timeout_result = await db.execute(
            update(CommandApproval)
            .where(
                CommandApproval.id == approval.id,
                CommandApproval.status == "pending",
                CommandApproval.expired_at < now,
            )
            .values(status="timeout")
            .execution_options(synchronize_session=False)
        )
        if timeout_result.rowcount != 1:
            continue
        _add_approval_audit_event(
            db,
            approval,
            operator_id=approval.requester_id,
            operator_name="system",
            result="timeout",
            result_message="审批超时，自动取消",
        )
        count += 1

    if count > 0:
        await db.commit()
        logger.info(f"已标记 {count} 个超时审批工单")

    return count


async def get_risk_configs(db: AsyncSession) -> list[dict]:
    """获取所有风险等级配置"""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_group == "command_risk").order_by(SystemConfig.config_key)
    )
    configs = result.scalars().all()

    # 合并数据库配置和默认配置
    config_map = {}
    for key, default in DEFAULT_RISK_CONFIGS.items():
        config_map[key] = {
            "command_type": key,
            "risk_level": default["risk_level"],
            "minimum_risk": COMMAND_DEFINITIONS[key].minimum_risk,
            "description": default["description"],
        }

    for config in configs:
        definition = COMMAND_DEFINITIONS.get(config.config_key)
        if definition is None:
            logger.warning("忽略未注册命令的历史风险配置: %s", config.config_key)
            continue
        if config.config_value not in {"normal", "critical"}:
            logger.warning("忽略命令 %s 的无效历史风险分类", config.config_key)
            continue
        if definition.minimum_risk == "critical" and config.config_value != "critical":
            logger.warning("忽略命令 %s 的历史风险降级配置", config.config_key)
            continue
        config_map[config.config_key]["risk_level"] = config.config_value
        if config.description:
            config_map[config.config_key]["description"] = config.description

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

        definition = get_command_definition(command_type)

        if risk_level not in ("normal", "critical"):
            raise ValueError(f"无效的风险等级: {risk_level}，只允许 normal 或 critical")
        if definition.minimum_risk == "critical" and risk_level != "critical":
            raise ValueError(f"命令 {command_type} 的最低风险等级为 critical，不允许降级")

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


def _add_approval_audit_event(
    db: AsyncSession,
    approval: CommandApproval,
    *,
    operator_id: int,
    operator_name: str,
    result: str,
    result_message: str,
) -> None:
    """Append an immutable event for an approval transition or rejected attempt."""
    db.add(
        CommandAuditLog(
            command_type=approval.command_type,
            risk_level=approval.risk_level,
            target_device_id=approval.target_device_id,
            target_device_name=approval.target_device_name,
            command_content=approval.command_content,
            operator_id=operator_id,
            operator_name=operator_name,
            approval_id=approval.id,
            result=result,
            result_message=result_message,
        )
    )
