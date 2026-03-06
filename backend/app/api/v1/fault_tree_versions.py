"""
故障树版本管理 API - Story 24.4
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
from app.core.database import get_db
from app.core.security import require_role, get_current_user
from app.services.diagnosis.version_manager import VersionManager
from app.models.fault_tree import FaultTreeVersion
from app.schemas.fault_tree_version import (
    FaultTreeVersionCreate,
    FaultTreeVersionResponse,
    FaultTreeVersionListResponse
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fault-trees/{tree_id}/versions", tags=["fault-tree-versions"])


@router.post("/", response_model=FaultTreeVersionResponse, dependencies=[Depends(require_role("admin"))])
async def create_version(
    tree_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    创建新版本

    - **tree_id**: 故障树 ID
    - **返回**: 新创建的版本信息
    - **错误**: 404 - 故障树不存在
    """
    try:
        version = await VersionManager.create_version(db, tree_id, current_user.id)
        return version
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{version_id}/review", response_model=FaultTreeVersionResponse, dependencies=[Depends(require_role("admin"))])
async def review_version(
    tree_id: int,
    version_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    审批版本

    - **tree_id**: 故障树 ID
    - **version_id**: 版本 ID
    - **返回**: 审批后的版本信息
    - **错误**:
        - 404 - 版本不存在
        - 400 - 版本状态不是 draft
        - 403 - 不能审批自己创建的版本
    """
    version = await db.get(FaultTreeVersion, version_id)
    if not version or version.tree_id != tree_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    if version.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only draft versions can be reviewed, current status: {version.status}"
        )

    # 验证审批者与创建者不同
    if version.created_by == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="不能审批自己创建的版本"
        )

    version.status = "reviewed"
    version.reviewed_by = current_user.id
    version.reviewed_at = func.now()
    await db.commit()
    await db.refresh(version)
    return version


@router.post("/{version_id}/activate", response_model=FaultTreeVersionResponse, dependencies=[Depends(require_role("admin"))])
async def activate_version(
    tree_id: int,
    version_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    激活版本

    - **tree_id**: 故障树 ID
    - **version_id**: 版本 ID
    - **返回**: 激活后的版本信息
    - **错误**:
        - 404 - 版本不存在
        - 400 - 版本状态不是 reviewed / DAG 验证失败 / 签名验证失败
    """
    # 先获取版本并验证 tree_id
    version = await db.get(FaultTreeVersion, version_id)
    if not version or version.tree_id != tree_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    try:
        version = await VersionManager.activate_version(db, version_id)
        return version
    except ValueError as e:
        logger.error(f"Failed to activate version {version_id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/rollback", response_model=FaultTreeVersionResponse, dependencies=[Depends(require_role("admin"))])
async def rollback_version(
    tree_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    回滚到上一个版本

    - **tree_id**: 故障树 ID
    - **返回**: 回滚后激活的版本信息
    - **错误**:
        - 404 - 没有可回滚的版本
        - 400 - 签名验证失败 / DAG 验证失败
    """
    try:
        version = await VersionManager.rollback_version(db, tree_id)
        return version
    except ValueError as e:
        logger.error(f"Failed to rollback tree {tree_id}: {e}")
        if "没有可回滚的版本" in str(e):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=List[FaultTreeVersionListResponse])
async def list_versions(
    tree_id: int,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    版本列表

    - **tree_id**: 故障树 ID
    - **status**: 可选，按状态过滤 (draft/reviewed/active/archived)
    - **返回**: 版本列表，按版本号降序排列
    """
    query = select(FaultTreeVersion).where(FaultTreeVersion.tree_id == tree_id)

    if status:
        query = query.where(FaultTreeVersion.status == status)

    query = query.order_by(FaultTreeVersion.version_number.desc())

    result = await db.execute(query)
    versions = result.scalars().all()
    return versions
