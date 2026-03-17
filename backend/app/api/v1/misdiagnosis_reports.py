"""
Misdiagnosis Report API - Story 26.6
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import require_role
from app.models.report import ReportRecord
from app.schemas.misdiagnosis_report import (
    MisdiagnosisReportGenerateRequest,
    MisdiagnosisReportDetailResponse,
    MisdiagnosisReportListResponse,
    MisdiagnosisReportListItem,
)
from app.services.diagnosis.misdiagnosis_report_service import MisdiagnosisReportServiceV2

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diagnosis/misdiagnosis-reports", tags=["misdiagnosis-reports"])


@router.get("", response_model=MisdiagnosisReportListResponse, dependencies=[Depends(require_role(["admin"]))])
async def list_misdiagnosis_reports(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    start_date: Optional[str] = Query(None, description="过滤开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="过滤结束日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    """
    查询历史报告列表

    权限: 仅管理员
    """
    # 构建查询
    query = select(ReportRecord).where(
        ReportRecord.report_type == "diagnosis_monthly"
    )

    # 时间范围过滤
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.where(ReportRecord.start_time >= start_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的 start_date 格式")

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date) + timedelta(days=1)
            query = query.where(ReportRecord.end_time < end_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的 end_date 格式")

    # 查询总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 分页查询
    query = query.order_by(ReportRecord.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    reports = result.scalars().all()

    items = [MisdiagnosisReportListItem.model_validate(report) for report in reports]

    return MisdiagnosisReportListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get("/{report_id}", response_model=MisdiagnosisReportDetailResponse, dependencies=[Depends(require_role(["admin"]))])
async def get_misdiagnosis_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    查询单个报告详情

    权限: 仅管理员
    """
    stmt = select(ReportRecord).where(
        ReportRecord.id == report_id,
        ReportRecord.report_type == "diagnosis_monthly"
    )
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    return MisdiagnosisReportDetailResponse.model_validate(report)


@router.get("/{report_id}/download", dependencies=[Depends(require_role(["admin"]))])
async def download_misdiagnosis_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    下载报告 Markdown 文件

    权限: 仅管理员
    """
    stmt = select(ReportRecord).where(
        ReportRecord.id == report_id,
        ReportRecord.report_type == "diagnosis_monthly"
    )
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    if not report.file_path:
        raise HTTPException(status_code=404, detail="报告文件不存在")

    import os
    # 路径遍历防护：确保文件在允许的报告目录内
    reports_dir = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "reports"))
    real_path = os.path.realpath(report.file_path)
    if not real_path.startswith(reports_dir + os.sep) and real_path != reports_dir:
        raise HTTPException(status_code=403, detail="非法文件路径")

    if not os.path.exists(real_path):
        raise HTTPException(status_code=404, detail="报告文件已删除")

    # 生成文件名
    filename = f"{report.start_time.year}-{report.start_time.month:02d}-misdiagnosis.md"

    return FileResponse(
        path=real_path,
        media_type="text/markdown; charset=utf-8",
        filename=filename,
    )


@router.post("/generate")
async def generate_misdiagnosis_report(
    request: MisdiagnosisReportGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role(["admin"])),
):
    """
    手动触发报告生成（仅用于测试）

    权限: 仅管理员
    """
    # 转换日期为 datetime（UTC）
    start_datetime = datetime.combine(request.start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_datetime = datetime.combine(request.end_date, datetime.max.time()).replace(tzinfo=timezone.utc)

    if start_datetime > end_datetime:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")

    # 创建服务实例
    service = MisdiagnosisReportServiceV2(db)

    try:
        report_id = await service.generate_monthly_report_v2(
            start_date=start_datetime,
            end_date=end_datetime,
            generated_by=current_user.id,
        )

        return {
            "message": "报告生成任务已提交",
            "report_id": report_id,
        }

    except ValueError as e:
        # 报告已存在
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"报告生成失败: {e}")
        raise HTTPException(status_code=500, detail="报告生成失败，请稍后重试")
