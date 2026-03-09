"""
A/B 测试 API 路由 - Story 26.5
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.user import User
from app.schemas.ab_testing import (
    ABTestCreateRequest,
    ABTestUpdateRequest,
    ABTestCompleteRequest,
    ABTestResponse,
    ABTestReportResponse,
)
from app.services.diagnosis.ab_testing_service import ABTestingService
from app.models.ab_test_config import ABTestConfig
from sqlalchemy import select

router = APIRouter(prefix="/diagnosis/ab-tests", tags=["A/B Testing"])


@router.post("", response_model=ABTestResponse, status_code=status.HTTP_201_CREATED)
async def create_ab_test(
    request: ABTestCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """创建 A/B 测试配置"""
    service = ABTestingService(db)
    try:
        ab_test = await service.create_ab_test(
            name=request.name,
            fault_tree_id=request.fault_tree_id,
            version_a_id=request.version_a_id,
            version_b_id=request.version_b_id,
            strategy=request.strategy,
            strategy_params=request.strategy_params.model_dump(),
            min_duration_hours=request.min_duration_hours,
            min_sample_size=request.min_sample_size,
            created_by=current_user.id,
        )
        return ABTestResponse.model_validate(ab_test)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=List[ABTestResponse])
async def list_ab_tests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """列出所有 A/B 测试"""
    stmt = select(ABTestConfig).order_by(ABTestConfig.created_at.desc())
    result = await db.execute(stmt)
    ab_tests = result.scalars().all()
    return [ABTestResponse.model_validate(ab_test) for ab_test in ab_tests]


@router.get("/{ab_test_id}", response_model=ABTestResponse)
async def get_ab_test(
    ab_test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """查询单个 A/B 测试"""
    stmt = select(ABTestConfig).where(ABTestConfig.id == ab_test_id)
    result = await db.execute(stmt)
    ab_test = result.scalar_one_or_none()
    if not ab_test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="A/B 测试不存在")
    return ABTestResponse.model_validate(ab_test)


@router.get("/{ab_test_id}/report", response_model=ABTestReportResponse)
async def get_ab_test_report(
    ab_test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """查询 A/B 测试效果报告"""
    service = ABTestingService(db)
    try:
        report = await service.get_ab_test_report(ab_test_id)
        return ABTestReportResponse(**report)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{ab_test_id}", response_model=ABTestResponse)
async def update_ab_test(
    ab_test_id: int,
    request: ABTestUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """更新 A/B 测试配置（扩大灰度）"""
    service = ABTestingService(db)
    try:
        ab_test = await service.update_ab_test(
            ab_test_id=ab_test_id,
            strategy_params=request.strategy_params.model_dump(),
            version=request.version,
        )
        return ABTestResponse.model_validate(ab_test)
    except ValueError as e:
        if "版本冲突" in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{ab_test_id}/complete")
async def complete_ab_test(
    ab_test_id: int,
    request: ABTestCompleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """完成 A/B 测试（全量切换或回滚）"""
    service = ABTestingService(db)
    try:
        result = await service.complete_ab_test(
            ab_test_id=ab_test_id,
            action=request.action,
            version=request.version,
            archived_by=current_user.id,
        )
        return result
    except ValueError as e:
        if "版本冲突" in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{ab_test_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ab_test(
    ab_test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """删除 A/B 测试（仅 paused 状态可删除）"""
    stmt = select(ABTestConfig).where(ABTestConfig.id == ab_test_id)
    result = await db.execute(stmt)
    ab_test = result.scalar_one_or_none()
    if not ab_test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="A/B 测试不存在")
    if ab_test.status != "paused":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"只能删除 paused 状态的 A/B 测试（当前状态: {ab_test.status}）"
        )
    await db.delete(ab_test)
    await db.commit()
