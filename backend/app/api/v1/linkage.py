"""
联动管理 API
Story 9-1: 联动引擎核心框架
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload

from ..deps import get_db, require_admin, require_operator, require_viewer
from ...models.user import User
from ...models.linkage import (
    LinkagePolicy,
    LinkageAction,
    LinkageExecution,
    LinkageLog,
    LinkageRecovery,
    LinkageRecoveryLog,
)
from ...schemas.linkage import (
    LinkagePolicyCreate,
    LinkagePolicyUpdate,
    LinkagePolicyTestRequest,
    ActionTypeInfo,
    RecoveryCreate,
    RecoveryResponse,
    TimelineReportResponse,
)
from ...engines.linkage_engine import linkage_engine
from ...engines.event_bus import Event, EventPriority, get_event_bus
from ...engines.recovery_engine import recovery_engine
from ...services.timeline_report import generate_timeline, generate_timeline_excel

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_db_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


# ==================== 消防策略管理（静态路由必须在参数化路由之前）====================


@router.post("/fire-protection/reload", response_model=dict)
async def reload_fire_protection(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """重载 YAML 消防策略"""
    from ...services.fire_protection import reload as fp_reload

    count = await fp_reload(db)
    await linkage_engine.reload_policies(db)
    return {"message": f"消防策略重载完成，共 {count} 条", "count": count}


@router.get("/fire-protection/status", response_model=dict)
async def get_fire_protection_status(
    _: User = Depends(require_viewer),
):
    """获取消防策略加载状态"""
    from ...services.fire_protection import get_status

    return get_status()


# ==================== 策略管理 ====================


@router.get("/policies", response_model=dict)
async def list_policies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_enabled: Optional[bool] = Query(None),
    trigger_type: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取联动策略列表"""
    stmt = select(LinkagePolicy)

    if is_enabled is not None:
        stmt = stmt.where(LinkagePolicy.is_enabled == is_enabled)
    if trigger_type is not None:
        stmt = stmt.where(LinkagePolicy.trigger_type == trigger_type)
    if name is not None:
        stmt = stmt.where(LinkagePolicy.name.contains(name))

    # 总数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # 分页
    stmt = stmt.order_by(LinkagePolicy.id.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    stmt = stmt.options(selectinload(LinkagePolicy.actions))
    result = await db.execute(stmt)
    policies = result.scalars().all()

    items = []
    for p in policies:
        actions = sorted(p.actions, key=lambda a: a.sort_order if a.sort_order is not None else 0) if p.actions else []

        items.append(
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "trigger_type": p.trigger_type,
                "trigger_condition": p.trigger_condition,
                "priority": p.priority,
                "is_enabled": p.is_enabled,
                "is_system": p.is_system,
                "actions": [
                    {
                        "id": a.id,
                        "policy_id": a.policy_id,
                        "action_type": a.action_type,
                        "action_config": a.action_config,
                        "sort_order": a.sort_order,
                        "timeout_seconds": a.timeout_seconds,
                        "retry_count": a.retry_count,
                        "created_at": a.created_at.isoformat() if a.created_at is not None else None,
                    }
                    for a in actions
                ],
                "created_at": p.created_at.isoformat() if p.created_at is not None else None,
                "updated_at": p.updated_at.isoformat() if p.updated_at is not None else None,
            }
        )

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/policies/{policy_id}", response_model=dict)
async def get_policy(
    policy_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取联动策略详情"""
    result = await db.execute(select(LinkagePolicy).where(LinkagePolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=404, detail="策略不存在")

    actions_result = await db.execute(
        select(LinkageAction).where(LinkageAction.policy_id == policy_id).order_by(LinkageAction.sort_order)
    )
    actions = actions_result.scalars().all()

    return {
        "id": policy.id,
        "name": policy.name,
        "description": policy.description,
        "trigger_type": policy.trigger_type,
        "trigger_condition": policy.trigger_condition,
        "priority": policy.priority,
        "is_enabled": policy.is_enabled,
        "is_system": policy.is_system,
        "actions": [
            {
                "id": a.id,
                "policy_id": a.policy_id,
                "action_type": a.action_type,
                "action_config": a.action_config,
                "sort_order": a.sort_order,
                "timeout_seconds": a.timeout_seconds,
                "retry_count": a.retry_count,
                "created_at": a.created_at.isoformat() if a.created_at is not None else None,
            }
            for a in actions
        ],
        "created_at": policy.created_at.isoformat() if policy.created_at is not None else None,
        "updated_at": policy.updated_at.isoformat() if policy.updated_at is not None else None,
    }


@router.post("/policies", response_model=dict)
async def create_policy(
    data: LinkagePolicyCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """创建联动策略"""
    policy = LinkagePolicy(
        name=data.name,
        description=data.description,
        trigger_type=data.trigger_type,
        trigger_condition=data.trigger_condition,
        priority=data.priority,
        is_enabled=data.is_enabled,
    )
    db.add(policy)
    await db.flush()

    # 创建动作
    for action_data in data.actions:
        action = LinkageAction(
            policy_id=policy.id,
            action_type=action_data.action_type,
            action_config=action_data.action_config,
            sort_order=action_data.sort_order,
            timeout_seconds=action_data.timeout_seconds,
            retry_count=action_data.retry_count,
        )
        db.add(action)

    await db.commit()
    await linkage_engine.reload_policies(db)

    return {"id": policy.id, "message": "策略创建成功"}


@router.put("/policies/{policy_id}", response_model=dict)
async def update_policy(
    policy_id: int,
    data: LinkagePolicyUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """更新联动策略"""
    result = await db.execute(select(LinkagePolicy).where(LinkagePolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=404, detail="策略不存在")

    # 系统策略限制
    if policy.is_system:
        if data.trigger_type is not None or data.trigger_condition is not None:
            raise HTTPException(status_code=403, detail="系统策略不允许修改触发类型和触发条件")

    # 更新字段
    if data.name is not None:
        policy.name = data.name
    if data.description is not None:
        policy.description = data.description
    if data.trigger_type is not None:
        policy.trigger_type = data.trigger_type
    if data.trigger_condition is not None:
        policy.trigger_condition = data.trigger_condition
    if data.priority is not None:
        policy.priority = data.priority
    if data.is_enabled is not None:
        policy.is_enabled = data.is_enabled

    # 如果提供了 actions，替换所有动作
    if data.actions is not None:
        await db.execute(delete(LinkageAction).where(LinkageAction.policy_id == policy_id))
        for action_data in data.actions:
            action = LinkageAction(
                policy_id=policy_id,
                action_type=action_data.action_type,
                action_config=action_data.action_config,
                sort_order=action_data.sort_order,
                timeout_seconds=action_data.timeout_seconds,
                retry_count=action_data.retry_count,
            )
            db.add(action)

    await db.commit()
    await linkage_engine.reload_policies(db)

    return {"message": "策略更新成功"}


@router.delete("/policies/{policy_id}", response_model=dict)
async def delete_policy(
    policy_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """删除联动策略"""
    result = await db.execute(select(LinkagePolicy).where(LinkagePolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=404, detail="策略不存在")

    if policy.is_system:
        raise HTTPException(status_code=403, detail="系统策略不允许删除")

    # 先删除动作
    await db.execute(delete(LinkageAction).where(LinkageAction.policy_id == policy_id))
    await db.delete(policy)
    await db.commit()
    await linkage_engine.reload_policies(db)

    return {"message": "策略删除成功"}


@router.put("/policies/{policy_id}/toggle", response_model=dict)
async def toggle_policy(
    policy_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """切换策略启用状态"""
    result = await db.execute(select(LinkagePolicy).where(LinkagePolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=404, detail="策略不存在")

    policy.is_enabled = not policy.is_enabled
    await db.commit()
    await linkage_engine.reload_policies(db)

    return {"is_enabled": policy.is_enabled, "message": "状态切换成功"}


@router.post("/policies/{policy_id}/test", response_model=dict)
async def test_policy(
    policy_id: int,
    data: LinkagePolicyTestRequest = LinkagePolicyTestRequest(),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """测试联动策略"""
    result = await db.execute(select(LinkagePolicy).where(LinkagePolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=404, detail="策略不存在")

    # 构建测试事件
    event = Event(
        event_type=data.event_type if data.event_type is not None else policy.trigger_type,
        source="test_trigger",
        priority=EventPriority.normal,
        payload=data.payload,
        is_test=True,
    )

    # 发布到事件总线
    event_bus = get_event_bus()
    await event_bus.publish("linkage", event)

    return {"message": f"测试事件已发布，策略: {policy.name}"}


# ==================== 执行记录 ====================


@router.get("/executions", response_model=dict)
async def list_executions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    policy_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取联动执行记录列表"""
    stmt = select(LinkageExecution)

    if policy_id is not None:
        stmt = stmt.where(LinkageExecution.policy_id == policy_id)
    if status is not None:
        stmt = stmt.where(LinkageExecution.status == status)
    if start_time is not None:
        try:
            st = _parse_db_datetime(start_time)
            stmt = stmt.where(LinkageExecution.started_at >= st)
        except ValueError:
            pass
    if end_time is not None:
        try:
            et = _parse_db_datetime(end_time)
            stmt = stmt.where(LinkageExecution.started_at <= et)
        except ValueError:
            pass

    # 总数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # 分页
    stmt = stmt.order_by(LinkageExecution.id.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    executions = result.scalars().all()

    items = []
    for e in executions:
        # 获取策略名称
        policy_result = await db.execute(select(LinkagePolicy.name).where(LinkagePolicy.id == e.policy_id))
        policy_name = policy_result.scalar_one_or_none()

        items.append(
            {
                "id": e.id,
                "policy_id": e.policy_id,
                "policy_name": policy_name,
                "event_id": e.event_id,
                "trigger_source": e.trigger_source,
                "trigger_event": e.trigger_event,
                "status": e.status,
                "started_at": e.started_at.isoformat() if e.started_at is not None else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at is not None else None,
                "total_duration_ms": e.total_duration_ms,
                "logs": [],
            }
        )

    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ==================== 事件时间线报告 (Story 9-5) ====================
# 注意: timeline 静态路由必须在 executions/{execution_id} 参数化路由之前注册


@router.get("/timeline/{execution_id}", response_model=TimelineReportResponse)
async def get_event_timeline(
    execution_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取事件时间线报告"""
    report = await generate_timeline(db, execution_id)
    if report is None:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    return report


@router.get("/timeline/{execution_id}/export")
async def export_event_timeline(
    execution_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """导出事件时间线报告为 Excel"""
    report = await generate_timeline(db, execution_id)
    if report is None:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    file_buffer = generate_timeline_excel(report)
    filename = f"timeline_{report.event_id}.xlsx"

    return StreamingResponse(
        file_buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ==================== 联动恢复: 可恢复列表 (Story 9-4) ====================
# 注意: 静态路由必须在参数化路由之前注册


@router.get("/executions/recoverable", response_model=dict)
async def list_recoverable_executions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """获取可恢复的执行记录列表"""
    # 子查询: 已有活跃恢复的 execution_id
    active_recovery_subq = (
        select(LinkageRecovery.execution_id)
        .where(LinkageRecovery.status.in_(["completed", "partial_recovery", "executing"]))
        .subquery()
    )

    stmt = select(LinkageExecution).where(
        LinkageExecution.status.in_(["completed", "partial_failure"]),
        LinkageExecution.id.notin_(select(active_recovery_subq.c.execution_id)),
    )

    # 总数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # 分页
    stmt = stmt.order_by(LinkageExecution.id.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    executions = result.scalars().all()

    items = []
    for e in executions:
        policy_result = await db.execute(select(LinkagePolicy.name).where(LinkagePolicy.id == e.policy_id))
        policy_name = policy_result.scalar_one_or_none()

        items.append(
            {
                "id": e.id,
                "policy_id": e.policy_id,
                "policy_name": policy_name,
                "event_id": e.event_id,
                "trigger_source": e.trigger_source,
                "trigger_event": e.trigger_event,
                "status": e.status,
                "started_at": e.started_at.isoformat() if e.started_at is not None else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at is not None else None,
                "total_duration_ms": e.total_duration_ms,
                "logs": [],
            }
        )

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/executions/{execution_id}", response_model=dict)
async def get_execution(
    execution_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取联动执行记录详情（含日志）"""
    result = await db.execute(select(LinkageExecution).where(LinkageExecution.id == execution_id))
    execution = result.scalar_one_or_none()
    if execution is None:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    # 获取策略名称
    policy_result = await db.execute(select(LinkagePolicy.name).where(LinkagePolicy.id == execution.policy_id))
    policy_name = policy_result.scalar_one_or_none()

    # 获取日志
    logs_result = await db.execute(
        select(LinkageLog).where(LinkageLog.execution_id == execution_id).order_by(LinkageLog.id)
    )
    logs = logs_result.scalars().all()

    return {
        "id": execution.id,
        "policy_id": execution.policy_id,
        "policy_name": policy_name,
        "event_id": execution.event_id,
        "trigger_source": execution.trigger_source,
        "trigger_event": execution.trigger_event,
        "status": execution.status,
        "started_at": execution.started_at.isoformat() if execution.started_at is not None else None,
        "completed_at": execution.completed_at.isoformat() if execution.completed_at is not None else None,
        "total_duration_ms": execution.total_duration_ms,
        "logs": [
            {
                "id": log.id,
                "execution_id": log.execution_id,
                "action_id": log.action_id,
                "action_type": log.action_type,
                "action_config": log.action_config,
                "status": log.status,
                "error_message": log.error_message,
                "started_at": log.started_at.isoformat() if log.started_at is not None else None,
                "completed_at": log.completed_at.isoformat() if log.completed_at is not None else None,
                "duration_ms": log.duration_ms,
            }
            for log in logs
        ],
    }


# ==================== 联动恢复 (Story 9-4) ====================


@router.post("/executions/{execution_id}/recover", response_model=dict)
async def create_recovery(
    execution_id: int,
    data: RecoveryCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
):
    """发起联动恢复"""
    # 查找执行记录
    result = await db.execute(select(LinkageExecution).where(LinkageExecution.id == execution_id))
    execution = result.scalar_one_or_none()
    if execution is None:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    # 检查是否已有活跃恢复
    active_result = await db.execute(
        select(LinkageRecovery).where(
            LinkageRecovery.execution_id == execution_id,
            LinkageRecovery.status.in_(["completed", "partial_recovery", "executing"]),
        )
    )
    if active_result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="该执行记录已有活跃的恢复任务")

    # 获取执行日志
    logs_result = await db.execute(select(LinkageLog).where(LinkageLog.execution_id == execution_id))
    logs = logs_result.scalars().all()
    log_dicts = [
        {
            "action_type": log.action_type,
            "action_config": log.action_config,
            "status": log.status,
        }
        for log in logs
    ]

    # 生成恢复步骤
    steps = recovery_engine.generate_recovery_steps(log_dicts)
    if not steps:
        raise HTTPException(status_code=400, detail="无可恢复的动作")

    # 创建恢复记录
    recovery = LinkageRecovery(
        execution_id=execution_id,
        operator=user.username,
        mode=data.mode,
        status="executing",
    )
    db.add(recovery)
    await db.flush()

    # 创建恢复步骤日志
    for step in steps:
        recovery_log = LinkageRecoveryLog(
            recovery_id=recovery.id,
            step_order=step["step_order"],
            action_type=step["action_type"],
            target_type=step.get("target_type"),
            recovery_command=step.get("recovery_command"),
            action_config=step.get("action_config"),
            status="pending",
        )
        db.add(recovery_log)

    await db.commit()

    # 自动模式: 后台执行
    if data.mode == "auto":
        asyncio.create_task(recovery_engine.start_recovery(recovery.id))

    return {"recovery_id": recovery.id, "message": "恢复已发起", "steps_count": len(steps)}


@router.get("/recoveries", response_model=dict)
async def list_recoveries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    execution_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取恢复记录列表"""
    stmt = select(LinkageRecovery)

    if status is not None:
        stmt = stmt.where(LinkageRecovery.status == status)
    if execution_id is not None:
        stmt = stmt.where(LinkageRecovery.execution_id == execution_id)

    # 总数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # 分页
    stmt = stmt.order_by(LinkageRecovery.id.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    stmt = stmt.options(selectinload(LinkageRecovery.logs))
    result = await db.execute(stmt)
    recoveries = result.scalars().all()

    items = [RecoveryResponse.model_validate(r).model_dump() for r in recoveries]

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/recoveries/{recovery_id}", response_model=RecoveryResponse)
async def get_recovery(
    recovery_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取恢复记录详情"""
    result = await db.execute(
        select(LinkageRecovery).where(LinkageRecovery.id == recovery_id).options(selectinload(LinkageRecovery.logs))
    )
    recovery = result.scalar_one_or_none()
    if recovery is None:
        raise HTTPException(status_code=404, detail="恢复记录不存在")

    return RecoveryResponse.model_validate(recovery)


@router.post("/recoveries/{recovery_id}/step/{step_order}/execute", response_model=dict)
async def execute_recovery_step(
    recovery_id: int,
    step_order: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """手动执行单个恢复步骤"""
    ok = await recovery_engine.execute_single_step(recovery_id, step_order, session=db)
    if not ok:
        raise HTTPException(status_code=400, detail="步骤执行失败或不存在")
    return {"message": "步骤执行完成"}


@router.post("/recoveries/{recovery_id}/step/{step_order}/skip", response_model=dict)
async def skip_recovery_step(
    recovery_id: int,
    step_order: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """跳过单个恢复步骤"""
    ok = await recovery_engine.skip_step(recovery_id, step_order, session=db)
    if not ok:
        raise HTTPException(status_code=400, detail="步骤跳过失败或不存在")
    return {"message": "步骤已跳过"}


# ==================== 动作类型 ====================


@router.get("/action-types", response_model=List[ActionTypeInfo])
async def get_action_types(
    _: User = Depends(require_viewer),
):
    """获取所有支持的动作类型"""
    from ...engines.action_handlers import default_registry

    registry = default_registry()
    # 已实现的动作类型
    implemented = {"ALARM_NOTIFY", "WEBHOOK"}
    descriptions = {
        "ALARM_NOTIFY": "告警通知 — 通过 WebSocket 广播告警消息",
        "WEBHOOK": "Webhook 回调 — 向指定 URL 发送 HTTP POST 请求",
        "MQTT_COMMAND": "MQTT 指令 — 向设备发送控制指令（未实现）",
        "VIDEO_RECORD": "视频录制 — 触发摄像头录制（未实现）",
        "VIDEO_POPUP": "视频弹窗 — 在客户端弹出视频画面（未实现）",
    }

    result = []
    for info in registry.list_types():
        action_type = info["action_type"]
        result.append(
            ActionTypeInfo(
                action_type=action_type,
                description=descriptions.get(action_type, action_type),
                is_implemented=action_type in implemented,
            )
        )

    return result
