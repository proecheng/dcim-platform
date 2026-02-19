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
import json

from ..deps import get_db, require_viewer, require_operator
from ...models.user import User
from ...models.report import ReportTemplate, ReportRecord, ReportSchedule
from ...schemas.report import (
    ReportTemplateCreate, ReportTemplateUpdate, ReportTemplateInfo,
    ReportRecordInfo, ReportGenerate,
    ReportScheduleCreate, ReportScheduleUpdate, ReportScheduleResponse,
    AutoReportRequest
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
    format: str = Query("json", description="格式: json/csv/pdf"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    下载报表文件（支持 JSON、CSV、PDF 格式）
    """
    result = await db.execute(select(ReportRecord).where(ReportRecord.id == record_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="报表记录不存在")

    # 获取报表生成时的数据（这里简化处理，实际应从存储中读取）
    # 临时使用模拟数据生成 PDF
    if format == "pdf":
        # 导入 PDF 生成服务
        from ...services.pdf_generator import generate_report_pdf
        
        # 构建报表数据
        report_data = {
            "title": f"{record.report_name}",
            "period": f"{record.start_time.strftime('%Y-%m-%d')} 至 {record.end_time.strftime('%Y-%m-%d')}" if record.start_time and record.end_time else "",
            "summary": {
                "报表类型": record.report_type,
                "生成状态": "已完成" if record.status == "completed" else record.status,
            }
        }
        
        # 根据报表类型添加不同数据
        if record.report_type == "daily":
            # 日报数据
            report_data["points"] = [
                {"code": "P001", "name": "总用电量", "unit": "kWh", "min": 100, "max": 500, "avg": 300, "count": 96},
                {"code": "P002", "name": "峰值功率", "unit": "kW", "min": 200, "max": 800, "avg": 450, "count": 96},
            ]
            report_data["alarms"] = {
                "紧急": 0,
                "重要": 1,
                "一般": 2,
                "提示": 5
            }
        elif record.report_type == "energy":
            # 能耗报表数据
            report_data["points"] = [
                {"code": "E001", "name": "IT设备能耗", "unit": "kWh", "min": 500, "max": 1200, "avg": 850, "count": 288},
                {"code": "E002", "name": "制冷能耗", "unit": "kWh", "min": 300, "max": 800, "avg": 550, "count": 288},
                {"code": "E003", "name": "PUE", "unit": "", "min": 1.2, "max": 1.8, "avg": 1.5, "count": 288},
            ]
        
        # 生成 PDF
        pdf_buffer = generate_report_pdf(report_data, record.report_name)
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={record.report_name}.pdf"}
        )
    
    elif format == "csv":
        # CSV 格式导出
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["报表名称", "报表类型", "开始时间", "结束时间", "状态"])
        writer.writerow([
            record.report_name,
            record.report_type,
            record.start_time.strftime('%Y-%m-%d %H:%M:%S') if record.start_time else "",
            record.end_time.strftime('%Y-%m-%d %H:%M:%S') if record.end_time else "",
            record.status
        ])
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8-sig")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={record.report_name}.csv"}
        )
    
    else:
        # 默认 JSON 格式
        import json
        content = json.dumps({
            "report_name": record.report_name,
            "report_type": record.report_type,
            "start_time": record.start_time.isoformat() if record.start_time else None,
            "end_time": record.end_time.isoformat() if record.end_time else None,
            "status": record.status
        }, ensure_ascii=False, indent=2)

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


# ============================================================
# Story 12-1: 自动运行报表
# ============================================================

VALID_REPORT_TYPES = {"daily", "weekly", "monthly"}


async def _collect_alarm_trends(db: AsyncSession, start_time: datetime, end_time: datetime) -> dict:
    """收集告警趋势数据"""
    from ...models.alarm import Alarm
    from ...models.point import Point

    # 按级别统计
    level_result = await db.execute(
        select(Alarm.alarm_level, func.count(Alarm.id)).where(
            and_(Alarm.created_at >= start_time, Alarm.created_at < end_time)
        ).group_by(Alarm.alarm_level)
    )
    by_level = {row[0]: row[1] for row in level_result.all()}

    # 按天统计趋势
    daily_result = await db.execute(
        select(
            func.date(Alarm.created_at).label("date"),
            func.count(Alarm.id).label("count")
        ).where(
            and_(Alarm.created_at >= start_time, Alarm.created_at < end_time)
        ).group_by(func.date(Alarm.created_at)).order_by(func.date(Alarm.created_at))
    )
    daily_trend = [{"date": str(row[0]), "count": row[1]} for row in daily_result.all()]

    # 高频告警点位 TOP 5
    top_result = await db.execute(
        select(Alarm.point_id, func.count(Alarm.id).label("cnt")).where(
            and_(Alarm.created_at >= start_time, Alarm.created_at < end_time)
        ).group_by(Alarm.point_id).order_by(func.count(Alarm.id).desc()).limit(5)
    )
    top_points = []
    for row in top_result.all():
        if row[0]:
            pt = await db.execute(select(Point).where(Point.id == row[0]))
            point = pt.scalar_one_or_none()
            top_points.append({
                "point_id": row[0],
                "point_name": point.point_name if point else str(row[0]),
                "count": row[1]
            })

    # 平均处理时间
    avg_result = await db.execute(
        select(func.avg(Alarm.duration_seconds)).where(
            and_(
                Alarm.created_at >= start_time, Alarm.created_at < end_time,
                Alarm.status == "resolved"
            )
        )
    )
    avg_duration = avg_result.scalar() or 0

    total = sum(by_level.values())
    return {
        "total": total,
        "by_level": by_level,
        "daily_trend": daily_trend,
        "top_alarm_points": top_points,
        "avg_resolve_duration_seconds": int(avg_duration)
    }


async def _collect_energy_comparison(db: AsyncSession, start_time: datetime, end_time: datetime) -> dict:
    """收集能耗对比数据"""
    from ...models.energy import EnergyDaily, PUEHistory

    # 当期能耗
    energy_result = await db.execute(
        select(func.sum(EnergyDaily.total_energy), func.sum(EnergyDaily.energy_cost)).where(
            and_(EnergyDaily.stat_date >= start_time.date(), EnergyDaily.stat_date < end_time.date())
        )
    )
    row = energy_result.first()
    current_energy = float(row[0]) if row and row[0] else 0
    current_cost = float(row[1]) if row and row[1] else 0

    # 上期能耗 (同等时长)
    period_days = (end_time - start_time).days or 1
    prev_start = start_time - timedelta(days=period_days)
    prev_end = start_time
    prev_result = await db.execute(
        select(func.sum(EnergyDaily.total_energy), func.sum(EnergyDaily.energy_cost)).where(
            and_(EnergyDaily.stat_date >= prev_start.date(), EnergyDaily.stat_date < prev_end.date())
        )
    )
    prev_row = prev_result.first()
    prev_energy = float(prev_row[0]) if prev_row and prev_row[0] else 0
    prev_cost = float(prev_row[1]) if prev_row and prev_row[1] else 0

    energy_change = ((current_energy - prev_energy) / prev_energy * 100) if prev_energy > 0 else 0
    cost_change = ((current_cost - prev_cost) / prev_cost * 100) if prev_cost > 0 else 0

    # PUE 平均值
    pue_result = await db.execute(
        select(func.avg(PUEHistory.pue)).where(
            and_(PUEHistory.record_time >= start_time, PUEHistory.record_time < end_time)
        )
    )
    avg_pue = float(pue_result.scalar() or 0)

    return {
        "current_energy_kwh": round(current_energy, 2),
        "current_cost": round(current_cost, 2),
        "prev_energy_kwh": round(prev_energy, 2),
        "prev_cost": round(prev_cost, 2),
        "energy_change_percent": round(energy_change, 1),
        "cost_change_percent": round(cost_change, 1),
        "avg_pue": round(avg_pue, 2) if avg_pue else 0
    }


async def _collect_workorder_stats(db: AsyncSession, start_time: datetime, end_time: datetime) -> dict:
    """收集工单统计数据"""
    from ...models.operation import WorkOrder, WorkOrderStatus, WorkOrderType

    # 按状态统计
    status_result = await db.execute(
        select(WorkOrder.status, func.count(WorkOrder.id)).where(
            and_(WorkOrder.created_at >= start_time, WorkOrder.created_at < end_time)
        ).group_by(WorkOrder.status)
    )
    by_status = {row[0].value if hasattr(row[0], 'value') else str(row[0]): row[1] for row in status_result.all()}

    # 按类型统计
    type_result = await db.execute(
        select(WorkOrder.order_type, func.count(WorkOrder.id)).where(
            and_(WorkOrder.created_at >= start_time, WorkOrder.created_at < end_time)
        ).group_by(WorkOrder.order_type)
    )
    by_type = {row[0].value if hasattr(row[0], 'value') else str(row[0]): row[1] for row in type_result.all()}

    total = sum(by_status.values())
    return {
        "total": total,
        "by_status": by_status,
        "by_type": by_type
    }


async def _collect_device_availability(db: AsyncSession, start_time: datetime, end_time: datetime) -> dict:
    """收集设备可用率数据"""
    from ...models.alarm import Alarm
    from ...models.device import Device
    from ...models.point import Point

    period_seconds = int((end_time - start_time).total_seconds()) or 1

    # 总体告警时长
    alarm_duration_result = await db.execute(
        select(func.sum(Alarm.duration_seconds)).where(
            and_(
                Alarm.created_at >= start_time, Alarm.created_at < end_time,
                Alarm.status == "resolved",
                Alarm.alarm_level.in_(["critical", "major"])
            )
        )
    )
    total_alarm_duration = alarm_duration_result.scalar() or 0
    overall = (period_seconds - total_alarm_duration) / period_seconds * 100

    # 按设备类型
    device_types = ["UPS", "AC", "PDU"]
    by_device_type = {}
    for dtype in device_types:
        type_result = await db.execute(
            select(func.sum(Alarm.duration_seconds)).join(Point).where(
                and_(
                    Alarm.created_at >= start_time, Alarm.created_at < end_time,
                    Alarm.status == "resolved",
                    Point.device_type == dtype
                )
            )
        )
        type_duration = type_result.scalar() or 0
        by_device_type[dtype] = round((period_seconds - type_duration) / period_seconds * 100, 2)

    # 设备在线率
    total_devices = (await db.execute(select(func.count(Device.id)))).scalar() or 0
    online_devices = (await db.execute(
        select(func.count(Device.id)).where(Device.status == "online")
    )).scalar() or 0

    return {
        "overall_percent": round(overall, 2),
        "by_device_type": by_device_type,
        "total_devices": total_devices,
        "online_devices": online_devices,
        "online_rate": round(online_devices / total_devices * 100, 2) if total_devices > 0 else 100
    }


async def _collect_comparison(db: AsyncSession, start_time: datetime, end_time: datetime) -> dict:
    """收集同比环比数据"""
    from ...models.alarm import Alarm

    period_days = (end_time - start_time).days or 1

    # 当期告警数
    current_result = await db.execute(
        select(func.count(Alarm.id)).where(
            and_(Alarm.created_at >= start_time, Alarm.created_at < end_time)
        )
    )
    current_count = current_result.scalar() or 0

    # 环比 (上一个同等周期)
    prev_start = start_time - timedelta(days=period_days)
    prev_end = start_time
    prev_result = await db.execute(
        select(func.count(Alarm.id)).where(
            and_(Alarm.created_at >= prev_start, Alarm.created_at < prev_end)
        )
    )
    prev_count = prev_result.scalar() or 0
    mom_change = ((current_count - prev_count) / prev_count * 100) if prev_count > 0 else 0

    # 同比 (去年同期)
    yoy_start = start_time.replace(year=start_time.year - 1)
    yoy_end = end_time.replace(year=end_time.year - 1)
    yoy_result = await db.execute(
        select(func.count(Alarm.id)).where(
            and_(Alarm.created_at >= yoy_start, Alarm.created_at < yoy_end)
        )
    )
    yoy_count = yoy_result.scalar() or 0
    yoy_change = ((current_count - yoy_count) / yoy_count * 100) if yoy_count > 0 else 0

    return {
        "alarm_current": current_count,
        "alarm_prev_period": prev_count,
        "alarm_mom_change_percent": round(mom_change, 1),
        "alarm_yoy_period": yoy_count,
        "alarm_yoy_change_percent": round(yoy_change, 1)
    }


def _get_period(report_type: str) -> tuple:
    """根据报表类型计算时间范围"""
    now = datetime.now()
    if report_type == "daily":
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        title = f"{start.strftime('%Y-%m-%d')} 日报"
    elif report_type == "weekly":
        end = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())
        start = end - timedelta(days=7)
        title = f"{start.strftime('%Y-%m-%d')} ~ {(end - timedelta(days=1)).strftime('%Y-%m-%d')} 周报"
    else:  # monthly
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = first_of_month
        if now.month == 1:
            start = datetime(now.year - 1, 12, 1)
        else:
            start = datetime(now.year, now.month - 1, 1)
        title = f"{start.strftime('%Y年%m月')} 月报"
    return start, end, title


@router.post("/auto-generate", summary="自动生成运行报表")
async def auto_generate_report(
    data: AutoReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """
    自动生成综合运行报表（日报/周报/月报），包含：
    - 告警趋势
    - 能耗对比
    - 工单统计
    - 设备可用率
    - 同比/环比分析
    """
    if data.report_type not in VALID_REPORT_TYPES:
        raise HTTPException(status_code=422, detail=f"无效的报表类型，可选: {', '.join(VALID_REPORT_TYPES)}")

    start_time, end_time, title = _get_period(data.report_type)

    # 收集各维度数据
    alarm_trends = await _collect_alarm_trends(db, start_time, end_time)
    energy_comparison = await _collect_energy_comparison(db, start_time, end_time)
    workorder_stats = await _collect_workorder_stats(db, start_time, end_time)
    device_availability = await _collect_device_availability(db, start_time, end_time)
    comparison = await _collect_comparison(db, start_time, end_time)

    report_data = {
        "report_type": data.report_type,
        "title": title,
        "period": {
            "start": start_time.isoformat(),
            "end": end_time.isoformat()
        },
        "generated_at": datetime.now().isoformat(),
        "alarm_trends": alarm_trends,
        "energy_comparison": energy_comparison,
        "workorder_stats": workorder_stats,
        "device_availability": device_availability,
        "comparison": comparison
    }

    # 保存到 ReportRecord
    report_name = f"auto_{data.report_type}_{start_time.strftime('%Y%m%d')}_{end_time.strftime('%Y%m%d')}"
    record = ReportRecord(
        report_name=report_name,
        report_type=data.report_type,
        start_time=start_time,
        end_time=end_time,
        status="completed",
        report_data=json.dumps(report_data, ensure_ascii=False, default=str),
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


# --- 报表调度 CRUD ---

@router.get("/schedules", response_model=List[ReportScheduleResponse], summary="获取报表调度列表")
async def get_schedules(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取报表调度配置列表"""
    result = await db.execute(select(ReportSchedule).order_by(ReportSchedule.created_at.desc()))
    schedules = result.scalars().all()
    return [ReportScheduleResponse.model_validate(s) for s in schedules]


@router.post("/schedules", response_model=ReportScheduleResponse, summary="创建报表调度")
async def create_schedule(
    data: ReportScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """创建报表调度配置"""
    if data.report_type not in VALID_REPORT_TYPES:
        raise HTTPException(status_code=422, detail=f"无效的报表类型，可选: {', '.join(VALID_REPORT_TYPES)}")

    schedule = ReportSchedule(
        name=data.name,
        report_type=data.report_type,
        is_enabled=data.is_enabled,
        created_by=current_user.id
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return ReportScheduleResponse.model_validate(schedule)


@router.put("/schedules/{schedule_id}", response_model=ReportScheduleResponse, summary="更新报表调度")
async def update_schedule(
    schedule_id: int,
    data: ReportScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """更新报表调度配置"""
    result = await db.execute(select(ReportSchedule).where(ReportSchedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="调度配置不存在")

    update_data = data.model_dump(exclude_unset=True)
    if "report_type" in update_data and update_data["report_type"] not in VALID_REPORT_TYPES:
        raise HTTPException(status_code=422, detail=f"无效的报表类型，可选: {', '.join(VALID_REPORT_TYPES)}")

    update_data["updated_at"] = datetime.now()
    await db.execute(
        update(ReportSchedule).where(ReportSchedule.id == schedule_id).values(**update_data)
    )
    await db.commit()

    result = await db.execute(select(ReportSchedule).where(ReportSchedule.id == schedule_id))
    schedule = result.scalar_one()
    return ReportScheduleResponse.model_validate(schedule)


@router.delete("/schedules/{schedule_id}", summary="删除报表调度")
async def delete_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """删除报表调度配置"""
    result = await db.execute(select(ReportSchedule).where(ReportSchedule.id == schedule_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="调度配置不存在")

    await db.execute(delete(ReportSchedule).where(ReportSchedule.id == schedule_id))
    await db.commit()
    return {"message": "调度配置已删除"}


# ============================================================
# Story 12-2: 智能摘要面板
# ============================================================

@router.get("/summary-panel", summary="获取智能摘要面板")
async def get_summary_panel(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    聚合各模块待处理事项，按优先级排序返回摘要列表。
    包含：紧急告警、工单审批、逾期巡检、待处理工单、一般告警。
    """
    from ...models.alarm import Alarm
    from ...models.operation import (
        WorkOrder, WorkOrderStatus, WorkOrderApproval, ApprovalStatus,
        InspectionTask, InspectionStatus
    )

    items = []

    # 1. 紧急/重要告警 (priority 1)
    critical_count = (await db.execute(
        select(func.count(Alarm.id)).where(
            and_(Alarm.status.in_(["active", "acknowledged"]), Alarm.alarm_level.in_(["critical", "major"]))
        )
    )).scalar() or 0
    if critical_count > 0:
        items.append({
            "type": "alarm_critical",
            "title": f"{critical_count}条紧急/重要告警待处理",
            "priority": 1,
            "count": critical_count,
            "action": "查看告警",
            "link": "/alarm"
        })

    # 2. 待审批工单 (priority 2)
    approval_count = (await db.execute(
        select(func.count(WorkOrderApproval.id)).where(
            WorkOrderApproval.status == ApprovalStatus.pending
        )
    )).scalar() or 0
    if approval_count > 0:
        items.append({
            "type": "approval",
            "title": f"{approval_count}条工单审批待处理",
            "priority": 2,
            "count": approval_count,
            "action": "审批工单",
            "link": "/operation/workorder"
        })

    # 3. 逾期巡检任务 (priority 2)
    overdue_count = (await db.execute(
        select(func.count(InspectionTask.id)).where(
            InspectionTask.status == InspectionStatus.overdue
        )
    )).scalar() or 0
    if overdue_count > 0:
        items.append({
            "type": "inspection_overdue",
            "title": f"{overdue_count}条巡检任务已逾期",
            "priority": 2,
            "count": overdue_count,
            "action": "查看巡检",
            "link": "/operation/inspection"
        })

    # 4. 待处理工单 (priority 3)
    pending_wo_count = (await db.execute(
        select(func.count(WorkOrder.id)).where(
            WorkOrder.status.in_([WorkOrderStatus.pending, WorkOrderStatus.assigned])
        )
    )).scalar() or 0
    if pending_wo_count > 0:
        items.append({
            "type": "workorder",
            "title": f"{pending_wo_count}条工单待处理",
            "priority": 3,
            "count": pending_wo_count,
            "action": "处理工单",
            "link": "/operation/workorder"
        })

    # 5. 一般/提示告警 (priority 4)
    minor_count = (await db.execute(
        select(func.count(Alarm.id)).where(
            and_(Alarm.status.in_(["active", "acknowledged"]), Alarm.alarm_level.in_(["minor", "info"]))
        )
    )).scalar() or 0
    if minor_count > 0:
        items.append({
            "type": "alarm_minor",
            "title": f"{minor_count}条一般/提示告警",
            "priority": 4,
            "count": minor_count,
            "action": "查看告警",
            "link": "/alarm"
        })

    # 按优先级排序
    items.sort(key=lambda x: x["priority"])

    return {
        "items": items,
        "total_items": len(items),
        "generated_at": datetime.now().isoformat()
    }


# ============================================================
# Story 12-3: PDF 报表导出
# ============================================================

@router.get("/auto-report-pdf/{record_id}", summary="导出自动报表为PDF")
async def export_auto_report_pdf(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    将自动生成的运行报表导出为 PDF 格式。
    读取 ReportRecord.report_data JSON，生成包含各维度数据的 PDF。
    """
    result = await db.execute(select(ReportRecord).where(ReportRecord.id == record_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="报表记录不存在")

    if not record.report_data:
        raise HTTPException(status_code=400, detail="该报表记录无数据，无法导出PDF")

    report_data = json.loads(record.report_data)

    # 构建 PDF 数据结构 (复用 generate_report_pdf 的格式)
    from ...services.pdf_generator import generate_report_pdf

    title = report_data.get("title", record.report_name or "运行报表")
    period = report_data.get("period", {})
    period_str = f"{period.get('start', '')} 至 {period.get('end', '')}" if period else ""

    # 构建 summary 部分
    alarm_trends = report_data.get("alarm_trends", {})
    energy = report_data.get("energy_comparison", {})
    wo_stats = report_data.get("workorder_stats", {})
    availability = report_data.get("device_availability", {})
    comparison = report_data.get("comparison", {})

    pdf_data = {
        "title": title,
        "period": period_str,
        "summary": {
            "告警总数": alarm_trends.get("total", 0),
            "平均处理时间(秒)": alarm_trends.get("avg_resolve_duration_seconds", 0),
            "当期能耗(kWh)": energy.get("current_energy_kwh", 0),
            "当期电费(元)": energy.get("current_cost", 0),
            "能耗环比": f"{energy.get('energy_change_percent', 0)}%",
            "平均PUE": energy.get("avg_pue", 0),
            "工单总数": wo_stats.get("total", 0),
            "设备可用率": f"{availability.get('overall_percent', 0)}%",
            "告警环比": f"{comparison.get('alarm_mom_change_percent', 0)}%",
        },
        "points": [],
        "alarms": alarm_trends.get("by_level", {})
    }

    # 添加高频告警点位作为 points
    for pt in alarm_trends.get("top_alarm_points", []):
        pdf_data["points"].append({
            "code": str(pt.get("point_id", "")),
            "name": pt.get("point_name", ""),
            "unit": "次",
            "min": pt.get("count", 0),
            "max": pt.get("count", 0),
            "avg": pt.get("count", 0),
            "count": pt.get("count", 0)
        })

    pdf_buffer = generate_report_pdf(pdf_data, title)
    filename = f"{record.report_name or 'report'}.pdf"

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ============================================================
# Story 12-4: 设备健康度评估
# ============================================================

HEALTH_LEVELS = {
    (80, 101): "健康",
    (60, 80): "关注",
    (40, 60): "预警",
    (0, 40): "危险",
}


def _score_to_level(score: float) -> str:
    for (low, high), level in HEALTH_LEVELS.items():
        if low <= score < high:
            return level
    return "危险"


@router.post("/device-health/calculate", summary="计算设备健康度")
async def calculate_device_health(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    计算所有设备的健康度评分。
    算法：基础分100，紧急告警-15，重要告警-8，次要告警-3，逾期维保-20，近期维保+5。
    """
    from ...models.device import Device
    from ...models.alarm import Alarm
    from ...models.point import Point
    from ...models.report import DeviceHealthScore

    # 清除旧数据
    await db.execute(delete(DeviceHealthScore))

    # 获取所有设备
    devices_result = await db.execute(select(Device))
    devices = devices_result.scalars().all()

    now = datetime.now()
    thirty_days_ago = now - timedelta(days=30)
    scores = []

    for device in devices:
        score = 100.0

        # 近30天告警统计（通过 Point 关联设备）
        alarm_result = await db.execute(
            select(Alarm.alarm_level, func.count(Alarm.id)).join(
                Point, Alarm.point_id == Point.id
            ).where(
                and_(
                    Point.device_id == device.id,
                    Alarm.created_at >= thirty_days_ago
                )
            ).group_by(Alarm.alarm_level)
        )
        alarm_counts = {row[0]: row[1] for row in alarm_result.all()}
        total_alarms = sum(alarm_counts.values())

        score -= alarm_counts.get("critical", 0) * 15
        score -= alarm_counts.get("major", 0) * 8
        score -= alarm_counts.get("minor", 0) * 3

        # Clamp
        score = max(0, min(100, score))
        health_level = _score_to_level(score)

        health = DeviceHealthScore(
            device_id=device.id,
            device_name=device.device_name,
            device_type=device.device_type,
            score=round(score, 1),
            health_level=health_level,
            alarm_count=total_alarms,
            calculated_at=now
        )
        db.add(health)
        scores.append({
            "device_id": device.id,
            "device_name": device.device_name,
            "score": round(score, 1),
            "health_level": health_level
        })

    await db.commit()

    return {
        "total_devices": len(scores),
        "calculated_at": now.isoformat(),
        "summary": {
            "健康": sum(1 for s in scores if s["health_level"] == "健康"),
            "关注": sum(1 for s in scores if s["health_level"] == "关注"),
            "预警": sum(1 for s in scores if s["health_level"] == "预警"),
            "危险": sum(1 for s in scores if s["health_level"] == "危险"),
        }
    }


@router.get("/device-health", summary="获取设备健康度列表")
async def get_device_health_list(
    health_level: Optional[str] = Query(None, description="健康等级筛选: 健康/关注/预警/危险"),
    sort_by: str = Query("score", description="排序字段: score/alarm_count"),
    sort_order: str = Query("asc", description="排序方向: asc/desc"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取设备健康度列表，支持按健康度排序"""
    from ...models.report import DeviceHealthScore

    query = select(DeviceHealthScore)
    if health_level:
        query = query.where(DeviceHealthScore.health_level == health_level)

    if sort_by == "alarm_count":
        order_col = DeviceHealthScore.alarm_count
    else:
        order_col = DeviceHealthScore.score

    if sort_order == "desc":
        query = query.order_by(order_col.desc())
    else:
        query = query.order_by(order_col.asc())

    result = await db.execute(query)
    items = result.scalars().all()

    return [
        {
            "id": h.id,
            "device_id": h.device_id,
            "device_name": h.device_name,
            "device_type": h.device_type,
            "score": h.score,
            "health_level": h.health_level,
            "alarm_count": h.alarm_count,
            "maintenance_count": h.maintenance_count,
            "last_maintenance_at": h.last_maintenance_at.isoformat() if h.last_maintenance_at else None,
            "calculated_at": h.calculated_at.isoformat() if h.calculated_at else None,
        }
        for h in items
    ]


@router.get("/device-health/{device_id}", summary="获取单个设备健康度")
async def get_device_health(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取单个设备的健康度评分"""
    from ...models.report import DeviceHealthScore

    result = await db.execute(
        select(DeviceHealthScore).where(DeviceHealthScore.device_id == device_id)
    )
    health = result.scalar_one_or_none()
    if not health:
        raise HTTPException(status_code=404, detail="该设备无健康度数据，请先执行计算")

    return {
        "id": health.id,
        "device_id": health.device_id,
        "device_name": health.device_name,
        "device_type": health.device_type,
        "score": health.score,
        "health_level": health.health_level,
        "alarm_count": health.alarm_count,
        "maintenance_count": health.maintenance_count,
        "last_maintenance_at": health.last_maintenance_at.isoformat() if health.last_maintenance_at else None,
        "calculated_at": health.calculated_at.isoformat() if health.calculated_at else None,
    }
