"""
日志查询 API - v1
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import csv
import io

from ..deps import get_db, require_admin
from ...models.user import User
from ...models.log import OperationLog, SystemLog, CommunicationLog
from ...schemas.log import OperationLogInfo, SystemLogInfo, CommunicationLogInfo
from ...schemas.common import PageResponse

router = APIRouter()


@router.get("/operations", response_model=PageResponse[OperationLogInfo], summary="获取操作日志")
async def get_operation_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[int] = Query(None, description="用户ID"),
    module: Optional[str] = Query(None, description="模块"),
    action: Optional[str] = Query(None, description="操作类型"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    keyword: Optional[str] = Query(None, description="关键词"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    获取操作日志（分页）
    """
    query = select(OperationLog)

    if user_id:
        query = query.where(OperationLog.user_id == user_id)
    if module:
        query = query.where(OperationLog.module == module)
    if action:
        query = query.where(OperationLog.action == action)
    if start_time:
        query = query.where(OperationLog.created_at >= start_time)
    if end_time:
        query = query.where(OperationLog.created_at <= end_time)
    if keyword:
        query = query.where(
            (OperationLog.target_name.contains(keyword)) |
            (OperationLog.remark.contains(keyword))
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(OperationLog.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    logs = result.scalars().all()

    return PageResponse(
        items=[OperationLogInfo.model_validate(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/systems", response_model=PageResponse[SystemLogInfo], summary="获取系统日志")
async def get_system_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    log_level: Optional[str] = Query(None, description="日志级别"),
    module: Optional[str] = Query(None, description="模块"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    keyword: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    获取系统日志（分页）
    """
    query = select(SystemLog)

    if log_level:
        query = query.where(SystemLog.log_level == log_level)
    if module:
        query = query.where(SystemLog.module == module)
    if start_time:
        query = query.where(SystemLog.created_at >= start_time)
    if end_time:
        query = query.where(SystemLog.created_at <= end_time)
    if keyword:
        query = query.where(SystemLog.message.contains(keyword))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(SystemLog.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    logs = result.scalars().all()

    return PageResponse(
        items=[SystemLogInfo.model_validate(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/communications", response_model=PageResponse[CommunicationLogInfo], summary="获取通讯日志")
async def get_communication_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    device_id: Optional[int] = Query(None, description="设备ID"),
    status: Optional[str] = Query(None, description="状态"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    获取通讯日志（分页）
    """
    query = select(CommunicationLog)

    if device_id:
        query = query.where(CommunicationLog.device_id == device_id)
    if status:
        query = query.where(CommunicationLog.status == status)
    if start_time:
        query = query.where(CommunicationLog.created_at >= start_time)
    if end_time:
        query = query.where(CommunicationLog.created_at <= end_time)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(CommunicationLog.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    logs = result.scalars().all()

    return PageResponse(
        items=[CommunicationLogInfo.model_validate(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/export", summary="导出日志")
async def export_logs(
    log_type: str = Query(..., description="日志类型: operation/system/communication"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    导出日志为CSV
    """
    if not start_time:
        start_time = datetime.now() - timedelta(days=7)
    if not end_time:
        end_time = datetime.now()

    output = io.StringIO()
    writer = csv.writer(output)

    if log_type == "operation":
        query = select(OperationLog).where(
            and_(
                OperationLog.created_at >= start_time,
                OperationLog.created_at <= end_time
            )
        ).order_by(OperationLog.created_at.desc())

        result = await db.execute(query)
        logs = result.scalars().all()

        writer.writerow(["时间", "用户", "模块", "操作", "目标", "IP地址", "备注"])
        for log in logs:
            writer.writerow([
                log.created_at, log.username, log.module, log.action,
                log.target_name, log.ip_address, log.remark
            ])

    elif log_type == "system":
        query = select(SystemLog).where(
            and_(
                SystemLog.created_at >= start_time,
                SystemLog.created_at <= end_time
            )
        ).order_by(SystemLog.created_at.desc())

        result = await db.execute(query)
        logs = result.scalars().all()

        writer.writerow(["时间", "级别", "模块", "消息", "异常信息"])
        for log in logs:
            writer.writerow([
                log.created_at, log.log_level, log.module,
                log.message, log.exception
            ])

    elif log_type == "communication":
        query = select(CommunicationLog).where(
            and_(
                CommunicationLog.created_at >= start_time,
                CommunicationLog.created_at <= end_time
            )
        ).order_by(CommunicationLog.created_at.desc())

        result = await db.execute(query)
        logs = result.scalars().all()

        writer.writerow(["时间", "设备ID", "类型", "协议", "状态", "耗时(ms)", "错误信息"])
        for log in logs:
            writer.writerow([
                log.created_at, log.device_id, log.comm_type,
                log.protocol, log.status, log.duration_ms, log.error_message
            ])

    else:
        raise HTTPException(status_code=400, detail="无效的日志类型")

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={log_type}_logs.csv"}
    )


@router.get("/statistics", summary="获取日志统计")
async def get_log_statistics(
    days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    获取日志统计信息
    """
    start_time = datetime.now() - timedelta(days=days)

    # 操作日志统计
    op_total_result = await db.execute(
        select(func.count(OperationLog.id)).where(OperationLog.created_at >= start_time)
    )
    op_total = op_total_result.scalar()

    op_by_module_result = await db.execute(
        select(OperationLog.module, func.count(OperationLog.id)).where(
            OperationLog.created_at >= start_time
        ).group_by(OperationLog.module)
    )
    op_by_module = {row[0]: row[1] for row in op_by_module_result.all()}

    # 系统日志统计
    sys_by_level_result = await db.execute(
        select(SystemLog.log_level, func.count(SystemLog.id)).where(
            SystemLog.created_at >= start_time
        ).group_by(SystemLog.log_level)
    )
    sys_by_level = {row[0]: row[1] for row in sys_by_level_result.all()}

    # 通讯日志统计
    comm_total_result = await db.execute(
        select(func.count(CommunicationLog.id)).where(CommunicationLog.created_at >= start_time)
    )
    comm_total = comm_total_result.scalar()

    comm_by_status_result = await db.execute(
        select(CommunicationLog.status, func.count(CommunicationLog.id)).where(
            CommunicationLog.created_at >= start_time
        ).group_by(CommunicationLog.status)
    )
    comm_by_status = {row[0]: row[1] for row in comm_by_status_result.all()}

    return {
        "period_days": days,
        "operation_logs": {
            "total": op_total,
            "by_module": op_by_module
        },
        "system_logs": {
            "by_level": sys_by_level
        },
        "communication_logs": {
            "total": comm_total,
            "by_status": comm_by_status
        }
    }
