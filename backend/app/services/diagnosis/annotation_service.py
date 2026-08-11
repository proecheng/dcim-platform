"""
诊断结果标注服务 - Story 24.8
"""

import logging
from datetime import datetime
from typing import Optional, List, Tuple

from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diagnosis import DiagnosisAnnotation, DiagnosisSession
from app.models.user import User
from app.schemas.diagnosis import (
    DiagnosisAnnotationCreate,
    DiagnosisAnnotationResponse,
    DiagnosisAnnotationListQuery,
    DiagnosisAnnotationStatsResponse,
)

logger = logging.getLogger(__name__)


class DiagnosisAnnotationService:
    """诊断标注服务"""

    @staticmethod
    async def create_annotation(
        db: AsyncSession,
        data: DiagnosisAnnotationCreate,
        annotator_id: int,
    ) -> DiagnosisAnnotationResponse:
        """
        创建诊断标注

        Args:
            db: 数据库会话
            data: 标注数据
            annotator_id: 标注者ID

        Returns:
            DiagnosisAnnotationResponse: 标注响应

        Raises:
            ValueError: 验证失败
        """
        # 验证 annotation 值
        if data.annotation not in ("accurate", "inaccurate", "unknown"):
            raise ValueError(f"Invalid annotation value: {data.annotation}")

        # 验证 inaccurate 时必须提供 actual_root_cause
        if data.annotation == "inaccurate" and not data.actual_root_cause:
            raise ValueError("actual_root_cause is required when annotation is 'inaccurate'")

        # 验证会话是否存在
        session_result = await db.execute(select(DiagnosisSession).where(DiagnosisSession.id == data.session_id))
        session = session_result.scalar_one_or_none()
        if not session:
            raise ValueError(f"Diagnosis session {data.session_id} not found")

        # 创建标注记录
        annotation = DiagnosisAnnotation(
            session_id=data.session_id,
            annotator_id=annotator_id,
            annotation=data.annotation,
            actual_root_cause=data.actual_root_cause,
            notes=data.notes,
            annotated_at=datetime.now(),
        )

        db.add(annotation)
        await db.commit()
        await db.refresh(annotation)

        logger.info(f"Created annotation {annotation.id} for session {data.session_id} by user {annotator_id}")

        return DiagnosisAnnotationResponse.model_validate(annotation)

    @staticmethod
    async def get_annotations(
        db: AsyncSession,
        query: DiagnosisAnnotationListQuery,
        user_id: Optional[int] = None,
        user_role: Optional[str] = None,
        allowed_session_ids=None,
    ) -> Tuple[List[DiagnosisAnnotationResponse], int]:
        """
        获取标注列表（分页）

        Args:
            db: 数据库会话
            query: 查询参数
            user_id: 当前用户ID（用于权限过滤）
            user_role: 当前用户角色

        Returns:
            Tuple[List[DiagnosisAnnotationResponse], int]: (标注列表, 总数)
        """
        # 构建查询条件
        conditions = []

        if query.session_id:
            conditions.append(DiagnosisAnnotation.session_id == query.session_id)

        if query.annotation:
            conditions.append(DiagnosisAnnotation.annotation == query.annotation)

        if allowed_session_ids is not None:
            conditions.append(DiagnosisAnnotation.session_id.in_(allowed_session_ids))

        # RBAC 权限过滤
        if user_role == "operator" and user_id:
            # operator 只能查看自己的标注
            if query.annotator_id and query.annotator_id != user_id:
                raise PermissionError("Operator can only view their own annotations")
            conditions.append(DiagnosisAnnotation.annotator_id == user_id)
        elif query.annotator_id:
            # admin 可以查看指定用户的标注
            conditions.append(DiagnosisAnnotation.annotator_id == query.annotator_id)

        # 查询总数
        count_stmt = select(func.count()).select_from(DiagnosisAnnotation)
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))

        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0

        # 查询数据
        stmt = select(DiagnosisAnnotation).where(and_(*conditions)) if conditions else select(DiagnosisAnnotation)
        stmt = stmt.order_by(DiagnosisAnnotation.annotated_at.desc())
        stmt = stmt.offset((query.page - 1) * query.page_size).limit(query.page_size)

        result = await db.execute(stmt)
        annotations = result.scalars().all()

        return (
            [DiagnosisAnnotationResponse.model_validate(a) for a in annotations],
            total,
        )

    @staticmethod
    async def delete_annotation(
        db: AsyncSession,
        annotation_id: int,
        user_id: int,
        user_role: str,
    ) -> None:
        """
        删除标注

        Args:
            db: 数据库会话
            annotation_id: 标注ID
            user_id: 当前用户ID
            user_role: 当前用户角色

        Raises:
            ValueError: 标注不存在
            PermissionError: 权限不足
        """
        # 查询标注
        result = await db.execute(select(DiagnosisAnnotation).where(DiagnosisAnnotation.id == annotation_id))
        annotation = result.scalar_one_or_none()

        if not annotation:
            raise ValueError(f"Annotation {annotation_id} not found")

        # 权限检查
        if user_role == "operator" and annotation.annotator_id != user_id:
            raise PermissionError("Operator can only delete their own annotations")

        # 删除标注
        await db.delete(annotation)
        await db.commit()

        logger.info(f"Deleted annotation {annotation_id} by user {user_id}")

    @staticmethod
    async def get_annotation_stats(
        db: AsyncSession,
        top_n: int = 10,
    ) -> DiagnosisAnnotationStatsResponse:
        """
        获取标注统计

        Args:
            db: 数据库会话
            top_n: Top N 标注者数量

        Returns:
            DiagnosisAnnotationStatsResponse: 统计响应
        """
        # 总标注数和分类统计
        stats_stmt = select(
            func.count(DiagnosisAnnotation.id).label("total"),
            func.sum(case((DiagnosisAnnotation.annotation == "accurate", 1), else_=0)).label("accurate"),
            func.sum(case((DiagnosisAnnotation.annotation == "inaccurate", 1), else_=0)).label("inaccurate"),
            func.sum(case((DiagnosisAnnotation.annotation == "unknown", 1), else_=0)).label("unknown"),
        )

        stats_result = await db.execute(stats_stmt)
        stats = stats_result.one()

        total_annotations = stats.total or 0
        accurate_count = stats.accurate or 0
        inaccurate_count = stats.inaccurate or 0
        unknown_count = stats.unknown or 0
        accurate_rate = (accurate_count / total_annotations * 100) if total_annotations > 0 else 0.0

        # 用户标注统计
        user_stats_stmt = (
            select(
                DiagnosisAnnotation.annotator_id,
                User.username,
                func.count(DiagnosisAnnotation.id).label("count"),
            )
            .join(User, DiagnosisAnnotation.annotator_id == User.id, isouter=True)
            .group_by(DiagnosisAnnotation.annotator_id, User.username)
        )

        user_stats_result = await db.execute(user_stats_stmt)
        user_stats_rows = user_stats_result.all()

        user_stats = [
            {
                "user_id": row.annotator_id,
                "username": row.username or "Unknown",
                "annotation_count": row.count,
            }
            for row in user_stats_rows
        ]

        # Top N 标注者
        top_annotators = sorted(user_stats, key=lambda x: x["annotation_count"], reverse=True)[:top_n]

        return DiagnosisAnnotationStatsResponse(
            total_annotations=total_annotations,
            accurate_count=accurate_count,
            inaccurate_count=inaccurate_count,
            unknown_count=unknown_count,
            accurate_rate=round(accurate_rate, 2),
            user_stats=user_stats,
            top_annotators=top_annotators,
        )
