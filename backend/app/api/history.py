"""
历史数据路由
"""
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import io
import csv

from ..core import get_db, get_current_user
from ..models import User, Point, PointHistory
from ..schemas import PointHistoryResponse

router = APIRouter(prefix="/history", tags=["历史数据"])


@router.get("/{point_id}", response_model=List[PointHistoryResponse])
async def get_point_history(
    point_id: int,
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    limit: int = Query(1000, le=10000, description="最大记录数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取点位历史数据"""
    # 默认查询最近24小时
    if not end_time:
        end_time = datetime.utcnow()
    if not start_time:
        start_time = end_time - timedelta(hours=24)

    query = select(PointHistory).where(
        and_(
            PointHistory.point_id == point_id,
            PointHistory.recorded_at >= start_time,
            PointHistory.recorded_at <= end_time
        )
    ).order_by(PointHistory.recorded_at.desc()).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{point_id}/trend")
async def get_point_trend(
    point_id: int,
    hours: int = Query(24, le=168, description="查询小时数"),
    interval: int = Query(60, description="聚合间隔(秒)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取趋势数据（用于图表）"""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)

    # 查询原始数据
    query = select(PointHistory).where(
        and_(
            PointHistory.point_id == point_id,
            PointHistory.recorded_at >= start_time,
            PointHistory.recorded_at <= end_time
        )
    ).order_by(PointHistory.recorded_at)

    result = await db.execute(query)
    records = result.scalars().all()

    # 简单聚合（按时间间隔取平均值）
    if not records:
        return {"times": [], "values": []}

    times = []
    values = []

    current_bucket = None
    bucket_values = []

    for record in records:
        bucket_time = record.recorded_at.replace(
            second=0, microsecond=0
        )
        # 按分钟聚合
        bucket_key = bucket_time.replace(
            minute=(bucket_time.minute // (interval // 60)) * (interval // 60)
        )

        if current_bucket != bucket_key:
            if bucket_values:
                times.append(current_bucket.isoformat())
                values.append(round(sum(bucket_values) / len(bucket_values), 2))
            current_bucket = bucket_key
            bucket_values = []

        bucket_values.append(record.value)

    # 最后一个桶
    if bucket_values:
        times.append(current_bucket.isoformat())
        values.append(round(sum(bucket_values) / len(bucket_values), 2))

    return {"times": times, "values": values}


@router.get("/{point_id}/statistics")
async def get_point_statistics(
    point_id: int,
    hours: int = Query(24, description="统计小时数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取点位统计数据"""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)

    query = select(
        func.min(PointHistory.value).label("min_value"),
        func.max(PointHistory.value).label("max_value"),
        func.avg(PointHistory.value).label("avg_value"),
        func.count(PointHistory.id).label("count")
    ).where(
        and_(
            PointHistory.point_id == point_id,
            PointHistory.recorded_at >= start_time,
            PointHistory.recorded_at <= end_time
        )
    )

    result = await db.execute(query)
    row = result.first()

    return {
        "point_id": point_id,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "min_value": round(row[0], 2) if row[0] else None,
        "max_value": round(row[1], 2) if row[1] else None,
        "avg_value": round(row[2], 2) if row[2] else None,
        "count": row[3] or 0
    }


@router.get("/export/csv")
async def export_history_csv(
    point_ids: str = Query(..., description="点位ID列表，逗号分隔"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """导出历史数据为 CSV"""
    point_id_list = [int(x) for x in point_ids.split(",")]

    if not end_time:
        end_time = datetime.utcnow()
    if not start_time:
        start_time = end_time - timedelta(hours=24)

    # 查询点位信息
    points_result = await db.execute(
        select(Point).where(Point.id.in_(point_id_list))
    )
    points = {p.id: p for p in points_result.scalars().all()}

    # 查询历史数据
    query = select(PointHistory).where(
        and_(
            PointHistory.point_id.in_(point_id_list),
            PointHistory.recorded_at >= start_time,
            PointHistory.recorded_at <= end_time
        )
    ).order_by(PointHistory.recorded_at)

    result = await db.execute(query)
    records = result.scalars().all()

    # 生成 CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["点位编码", "点位名称", "数值", "单位", "记录时间"])

    for record in records:
        point = points.get(record.point_id)
        if point:
            writer.writerow([
                point.point_code,
                point.point_name,
                record.value,
                point.unit or "",
                record.recorded_at.strftime("%Y-%m-%d %H:%M:%S")
            ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=history_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
        }
    )
