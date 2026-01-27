"""
报表 API - v1
"""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete, and_
import os
import io

from ..deps import get_db, require_viewer, require_operator
from ...models.user import User
from ...models.report import ReportTemplate, ReportRecord
from ...schemas.report import (
    ReportTemplateCreate, ReportTemplateUpdate, ReportTemplateInfo,
    ReportRecordInfo, ReportGenerate
)
from ...schemas.common import PageResponse

router = APIRouter()


@router.get("/templates", summary="获取报表模板")
async def get_templates(
    template_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取报表模板列表
    """
    query = select(ReportTemplate)
    if template_type:
        query = query.where(ReportTemplate.template_type == template_type)

    result = await db.execute(query.order_by(ReportTemplate.template_type))
    templates = result.scalars().all()

    return [ReportTemplateInfo.model_validate(t) for t in templates]


@router.post("/templates", response_model=ReportTemplateInfo, summary="创建报表模板")
async def create_template(
    data: ReportTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """
    创建报表模板
    """
    template = ReportTemplate(
        **data.model_dump(),
        created_by=current_user.id
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    return ReportTemplateInfo.model_validate(template)


@router.put("/templates/{template_id}", response_model=ReportTemplateInfo, summary="更新报表模板")
async def update_template(
    template_id: int,
    data: ReportTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    更新报表模板
    """
    result = await db.execute(select(ReportTemplate).where(ReportTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    update_data = data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now()

    await db.execute(
        update(ReportTemplate).where(ReportTemplate.id == template_id).values(**update_data)
    )
    await db.commit()

    result = await db.execute(select(ReportTemplate).where(ReportTemplate.id == template_id))
    template = result.scalar_one()

    return ReportTemplateInfo.model_validate(template)


@router.delete("/templates/{template_id}", summary="删除报表模板")
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    删除报表模板
    """
    result = await db.execute(select(ReportTemplate).where(ReportTemplate.id == template_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="模板不存在")

    await db.execute(delete(ReportTemplate).where(ReportTemplate.id == template_id))
    await db.commit()

    return {"message": "模板已删除"}


@router.post("/generate", summary="生成报表")
async def generate_report(
    data: ReportGenerate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """
    生成报表
    """
    import json
    from ...models.point import Point
    from ...models.history import PointHistory
    from ...models.alarm import Alarm

    # 获取模板
    if data.template_id:
        template_result = await db.execute(
            select(ReportTemplate).where(ReportTemplate.id == data.template_id)
        )
        template = template_result.scalar_one_or_none()
        if not template:
            raise HTTPException(status_code=404, detail="模板不存在")
        report_type = template.template_type
        point_ids = json.loads(template.point_ids) if template.point_ids else []
    else:
        report_type = data.report_type or "custom"
        point_ids = data.point_ids or []

    start_time = data.start_time
    end_time = data.end_time

    # 生成报表数据
    report_data = {
        "title": f"{report_type}报表",
        "generated_at": datetime.now().isoformat(),
        "period": {
            "start": start_time.isoformat(),
            "end": end_time.isoformat()
        },
        "summary": {},
        "points": [],
        "alarms": []
    }

    # 获取点位数据
    for point_id in point_ids:
        point_result = await db.execute(select(Point).where(Point.id == point_id))
        point = point_result.scalar_one_or_none()
        if not point:
            continue

        # 获取统计数据
        stats_result = await db.execute(
            select(
                func.min(PointHistory.value),
                func.max(PointHistory.value),
                func.avg(PointHistory.value),
                func.count(PointHistory.id)
            ).where(
                and_(
                    PointHistory.point_id == point_id,
                    PointHistory.recorded_at >= start_time,
                    PointHistory.recorded_at <= end_time
                )
            )
        )
        stats = stats_result.first()

        report_data["points"].append({
            "code": point.point_code,
            "name": point.point_name,
            "unit": point.unit,
            "min": stats[0],
            "max": stats[1],
            "avg": round(stats[2], 2) if stats[2] else None,
            "count": stats[3]
        })

    # 获取告警统计
    alarm_result = await db.execute(
        select(Alarm.alarm_level, func.count(Alarm.id)).where(
            and_(
                Alarm.created_at >= start_time,
                Alarm.created_at <= end_time
            )
        ).group_by(Alarm.alarm_level)
    )
    alarm_counts = {row[0]: row[1] for row in alarm_result.all()}
    report_data["alarms"] = alarm_counts

    # 创建报表记录
    report_name = f"{report_type}_{start_time.strftime('%Y%m%d')}_{end_time.strftime('%Y%m%d')}"
    record = ReportRecord(
        template_id=data.template_id,
        report_name=report_name,
        report_type=report_type,
        start_time=start_time,
        end_time=end_time,
        status="completed",
        generated_by=current_user.id
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return {
        "record_id": record.id,
        "report_name": report_name,
        "data": report_data
    }


@router.get("/records", response_model=PageResponse[ReportRecordInfo], summary="获取报表记录")
async def get_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    report_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取报表生成记录
    """
    query = select(ReportRecord)
    if report_type:
        query = query.where(ReportRecord.report_type == report_type)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(ReportRecord.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    records = result.scalars().all()

    return PageResponse(
        items=[ReportRecordInfo.model_validate(r) for r in records],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/download/{record_id}", summary="下载报表")
async def download_report(
    record_id: int,
    format: str = Query("json", description="格式: json/csv"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    下载报表文件
    """
    result = await db.execute(select(ReportRecord).where(ReportRecord.id == record_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="报表记录不存在")

    # 这里返回简单的JSON响应，实际可以根据file_path返回文件
    import json

    content = json.dumps({
        "report_name": record.report_name,
        "report_type": record.report_type,
        "start_time": record.start_time.isoformat() if record.start_time else None,
        "end_time": record.end_time.isoformat() if record.end_time else None,
        "status": record.status
    }, ensure_ascii=False)

    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={record.report_name}.json"}
    )


@router.get("/daily", summary="获取日报数据")
async def get_daily_report(
    date: Optional[datetime] = Query(None, description="日期，默认昨天"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取日报数据
    """
    if not date:
        date = datetime.now() - timedelta(days=1)

    start_time = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(days=1)

    # 调用生成报表逻辑
    from ...models.point import Point
    from ...models.history import PointHistory
    from ...models.alarm import Alarm

    # 获取所有启用的点位
    points_result = await db.execute(
        select(Point).where(Point.is_enabled == True)
    )
    points = points_result.scalars().all()

    point_stats = []
    for point in points[:20]:  # 限制数量
        stats_result = await db.execute(
            select(
                func.min(PointHistory.value),
                func.max(PointHistory.value),
                func.avg(PointHistory.value)
            ).where(
                and_(
                    PointHistory.point_id == point.id,
                    PointHistory.recorded_at >= start_time,
                    PointHistory.recorded_at < end_time
                )
            )
        )
        stats = stats_result.first()
        if stats[0] is not None:
            point_stats.append({
                "code": point.point_code,
                "name": point.point_name,
                "unit": point.unit,
                "min": round(stats[0], 2) if stats[0] else None,
                "max": round(stats[1], 2) if stats[1] else None,
                "avg": round(stats[2], 2) if stats[2] else None
            })

    # 告警统计
    alarm_result = await db.execute(
        select(Alarm.alarm_level, func.count(Alarm.id)).where(
            and_(
                Alarm.created_at >= start_time,
                Alarm.created_at < end_time
            )
        ).group_by(Alarm.alarm_level)
    )
    alarm_counts = {row[0]: row[1] for row in alarm_result.all()}

    return {
        "date": start_time.strftime("%Y-%m-%d"),
        "title": f"{start_time.strftime('%Y-%m-%d')} 日报",
        "points": point_stats,
        "alarms": alarm_counts,
        "alarm_total": sum(alarm_counts.values())
    }


@router.get("/weekly", summary="获取周报数据")
async def get_weekly_report(
    date: Optional[datetime] = Query(None, description="周内任意日期"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取周报数据
    """
    if not date:
        date = datetime.now()

    # 计算本周开始日期（周一）
    start_of_week = date - timedelta(days=date.weekday())
    start_time = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(days=7)

    from ...models.alarm import Alarm

    # 按天统计告警
    daily_alarms = []
    for i in range(7):
        day_start = start_time + timedelta(days=i)
        day_end = day_start + timedelta(days=1)

        count_result = await db.execute(
            select(func.count(Alarm.id)).where(
                and_(
                    Alarm.created_at >= day_start,
                    Alarm.created_at < day_end
                )
            )
        )
        count = count_result.scalar()
        daily_alarms.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][i],
            "alarm_count": count
        })

    return {
        "week_start": start_time.strftime("%Y-%m-%d"),
        "week_end": (end_time - timedelta(days=1)).strftime("%Y-%m-%d"),
        "title": f"{start_time.strftime('%Y-%m-%d')} ~ {(end_time - timedelta(days=1)).strftime('%Y-%m-%d')} 周报",
        "daily_alarms": daily_alarms,
        "total_alarms": sum(d["alarm_count"] for d in daily_alarms)
    }


@router.get("/monthly", summary="获取月报数据")
async def get_monthly_report(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取月报数据
    """
    now = datetime.now()
    if not year:
        year = now.year
    if not month:
        month = now.month

    start_time = datetime(year, month, 1)
    if month == 12:
        end_time = datetime(year + 1, 1, 1)
    else:
        end_time = datetime(year, month + 1, 1)

    from ...models.alarm import Alarm

    # 按级别统计告警
    alarm_result = await db.execute(
        select(Alarm.alarm_level, func.count(Alarm.id)).where(
            and_(
                Alarm.created_at >= start_time,
                Alarm.created_at < end_time
            )
        ).group_by(Alarm.alarm_level)
    )
    alarm_by_level = {row[0]: row[1] for row in alarm_result.all()}

    return {
        "year": year,
        "month": month,
        "title": f"{year}年{month}月 月报",
        "alarm_by_level": alarm_by_level,
        "total_alarms": sum(alarm_by_level.values())
    }
