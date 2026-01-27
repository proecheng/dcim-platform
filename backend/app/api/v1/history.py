"""
历史数据 API - v1
"""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import csv
import io

from ..deps import get_db, require_viewer, require_operator, require_admin
from ...models.user import User
from ...models.point import Point
from ...models.history import PointHistory, PointHistoryArchive, PointChangeLog
from ...schemas.history import (
    HistoryQuery, HistoryData, TrendData, HistoryStatistics, CompareQuery
)

router = APIRouter()


@router.get("/{point_id}", summary="获取点位历史数据")
async def get_point_history(
    point_id: int,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    granularity: Optional[str] = Query("raw", description="聚合间隔: raw/minute/hour/day"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取点位历史数据（分页）
    返回格式: { items: [...], total, page, page_size }
    """
    # 检查点位
    point_result = await db.execute(select(Point).where(Point.id == point_id))
    point = point_result.scalar_one_or_none()
    if not point:
        raise HTTPException(status_code=404, detail="点位不存在")

    if not start_time:
        start_time = datetime.now() - timedelta(hours=24)
    if not end_time:
        end_time = datetime.now()

    if granularity == "raw":
        # 原始数据
        query = select(PointHistory).where(
            and_(
                PointHistory.point_id == point_id,
                PointHistory.recorded_at >= start_time,
                PointHistory.recorded_at <= end_time
            )
        ).order_by(PointHistory.recorded_at.desc())

        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar()

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        history = result.scalars().all()

        items = [
            {
                "id": h.id,
                "point_id": h.point_id,
                "raw_value": h.value,
                "value": h.value,
                "quality": h.quality,
                "created_at": h.recorded_at.isoformat() if h.recorded_at else None
            } for h in history
        ]
    else:
        # 聚合数据
        archive_type = granularity + "ly" if granularity != "day" else "daily"
        query = select(PointHistoryArchive).where(
            and_(
                PointHistoryArchive.point_id == point_id,
                PointHistoryArchive.archive_type == archive_type,
                PointHistoryArchive.recorded_at >= start_time,
                PointHistoryArchive.recorded_at <= end_time
            )
        ).order_by(PointHistoryArchive.recorded_at.desc())

        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar()

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        archive = result.scalars().all()

        items = [
            {
                "id": a.id,
                "point_id": a.point_id,
                "raw_value": a.value_avg,
                "value": a.value_avg,
                "quality": 0,
                "created_at": a.recorded_at.isoformat() if a.recorded_at else None
            } for a in archive
        ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/{point_id}/trend", summary="获取趋势数据")
async def get_trend_data(
    point_id: int,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    granularity: Optional[str] = Query("raw", description="聚合间隔: raw/minute/hour/day"),
    limit: int = Query(500, ge=1, le=2000, description="最大数据点数"),
    duration: Optional[int] = Query(None, description="时长(分钟)，与start_time/end_time二选一"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取趋势数据（用于图表显示）
    返回格式: TrendData[] 数组
    """
    # 检查点位
    point_result = await db.execute(select(Point).where(Point.id == point_id))
    point = point_result.scalar_one_or_none()
    if not point:
        raise HTTPException(status_code=404, detail="点位不存在")

    # 确定时间范围
    if duration is not None:
        # 使用 duration 参数
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=duration)
    else:
        # 使用 start_time/end_time 参数
        if not start_time:
            start_time = datetime.now() - timedelta(hours=24)
        if not end_time:
            end_time = datetime.now()

    result = await db.execute(
        select(PointHistory).where(
            and_(
                PointHistory.point_id == point_id,
                PointHistory.recorded_at >= start_time,
                PointHistory.recorded_at <= end_time
            )
        ).order_by(PointHistory.recorded_at)
    )
    history = result.scalars().all()

    # 如果数据点太多，进行降采样
    if len(history) > limit:
        step = len(history) // limit
        history = history[::step][:limit]

    # 返回 TrendData[] 数组格式
    return [
        {"time": h.recorded_at.isoformat(), "value": h.value}
        for h in history
    ]


@router.get("/{point_id}/statistics", response_model=HistoryStatistics, summary="获取统计数据")
async def get_history_statistics(
    point_id: int,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取历史数据统计
    """
    # 检查点位
    point_result = await db.execute(select(Point).where(Point.id == point_id))
    point = point_result.scalar_one_or_none()
    if not point:
        raise HTTPException(status_code=404, detail="点位不存在")

    if not start_time:
        start_time = datetime.now() - timedelta(hours=24)
    if not end_time:
        end_time = datetime.now()

    result = await db.execute(
        select(
            func.count(PointHistory.id).label("count"),
            func.min(PointHistory.value).label("min"),
            func.max(PointHistory.value).label("max"),
            func.avg(PointHistory.value).label("avg")
        ).where(
            and_(
                PointHistory.point_id == point_id,
                PointHistory.recorded_at >= start_time,
                PointHistory.recorded_at <= end_time
            )
        )
    )
    row = result.first()

    # 计算标准差
    from sqlalchemy import cast, Float
    std_result = await db.execute(
        select(
            func.avg(
                (PointHistory.value - row.avg) * (PointHistory.value - row.avg)
            )
        ).where(
            and_(
                PointHistory.point_id == point_id,
                PointHistory.recorded_at >= start_time,
                PointHistory.recorded_at <= end_time
            )
        )
    )
    variance = std_result.scalar() or 0
    std_dev = variance ** 0.5 if variance else 0

    return HistoryStatistics(
        point_id=point_id,
        point_code=point.point_code,
        point_name=point.point_name,
        start_time=start_time,
        end_time=end_time,
        count=row.count or 0,
        min_value=row.min,
        max_value=row.max,
        avg_value=round(row.avg, 2) if row.avg else None,
        std_dev=round(std_dev, 2)
    )


@router.get("/compare", summary="多点位对比查询")
async def compare_points(
    point_ids: str = Query(..., description="点位ID列表，逗号分隔"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    多个点位数据对比查询
    """
    ids = [int(x.strip()) for x in point_ids.split(",") if x.strip()]

    if len(ids) > 10:
        raise HTTPException(status_code=400, detail="最多支持10个点位对比")

    if not start_time:
        start_time = datetime.now() - timedelta(hours=24)
    if not end_time:
        end_time = datetime.now()

    result_data = {}
    for point_id in ids:
        point_result = await db.execute(select(Point).where(Point.id == point_id))
        point = point_result.scalar_one_or_none()
        if not point:
            continue

        history_result = await db.execute(
            select(PointHistory).where(
                and_(
                    PointHistory.point_id == point_id,
                    PointHistory.recorded_at >= start_time,
                    PointHistory.recorded_at <= end_time
                )
            ).order_by(PointHistory.recorded_at)
        )
        history = history_result.scalars().all()

        result_data[point.point_code] = {
            "point_name": point.point_name,
            "unit": point.unit,
            "data": [{"time": h.recorded_at.isoformat(), "value": h.value} for h in history]
        }

    return result_data


@router.get("/changes/{point_id}", summary="获取变化记录")
async def get_change_log(
    point_id: int,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取DI点位的变化记录
    """
    point_result = await db.execute(select(Point).where(Point.id == point_id))
    point = point_result.scalar_one_or_none()
    if not point:
        raise HTTPException(status_code=404, detail="点位不存在")

    if point.point_type != "DI":
        raise HTTPException(status_code=400, detail="该接口仅适用于DI点位")

    if not start_time:
        start_time = datetime.now() - timedelta(days=7)
    if not end_time:
        end_time = datetime.now()

    query = select(PointChangeLog).where(
        and_(
            PointChangeLog.point_id == point_id,
            PointChangeLog.changed_at >= start_time,
            PointChangeLog.changed_at <= end_time
        )
    ).order_by(PointChangeLog.changed_at.desc())

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    changes = result.scalars().all()

    return {
        "point": {
            "id": point.id,
            "code": point.point_code,
            "name": point.point_name
        },
        "data": [
            {
                "time": c.changed_at.isoformat(),
                "old_value": c.old_value,
                "new_value": c.new_value,
                "change_type": c.change_type
            } for c in changes
        ],
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/export", summary="导出历史数据")
async def export_history(
    point_id: int,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    format: str = Query("csv", description="导出格式: csv/json"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    导出历史数据
    """
    point_result = await db.execute(select(Point).where(Point.id == point_id))
    point = point_result.scalar_one_or_none()
    if not point:
        raise HTTPException(status_code=404, detail="点位不存在")

    if not start_time:
        start_time = datetime.now() - timedelta(hours=24)
    if not end_time:
        end_time = datetime.now()

    result = await db.execute(
        select(PointHistory).where(
            and_(
                PointHistory.point_id == point_id,
                PointHistory.recorded_at >= start_time,
                PointHistory.recorded_at <= end_time
            )
        ).order_by(PointHistory.recorded_at)
    )
    history = result.scalars().all()

    if format == "json":
        import json
        data = {
            "point": {"code": point.point_code, "name": point.point_name, "unit": point.unit},
            "data": [{"time": h.recorded_at.isoformat(), "value": h.value} for h in history]
        }
        return StreamingResponse(
            io.BytesIO(json.dumps(data, ensure_ascii=False).encode("utf-8")),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={point.point_code}_history.json"}
        )
    else:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["时间", "数值", "单位", "质量"])
        for h in history:
            writer.writerow([h.recorded_at.isoformat(), h.value, point.unit, h.quality])

        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8-sig")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={point.point_code}_history.csv"}
        )


@router.delete("/cleanup", summary="清理过期数据")
async def cleanup_history(
    days: int = Query(30, ge=1, le=365, description="保留天数"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    清理过期的历史数据
    """
    from sqlalchemy import delete

    cutoff_time = datetime.now() - timedelta(days=days)

    # 删除历史数据
    result = await db.execute(
        delete(PointHistory).where(PointHistory.recorded_at < cutoff_time)
    )
    deleted_count = result.rowcount

    await db.commit()

    return {
        "message": f"已清理 {deleted_count} 条历史数据",
        "cutoff_time": cutoff_time.isoformat()
    }
