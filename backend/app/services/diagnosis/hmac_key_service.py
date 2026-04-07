"""HMAC 密钥管理服务 — Story 26.10

提供 HMAC 密钥状态查询、密钥轮换（重签名）、批量签名验证、轮换历史查询。
"""

import logging
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import async_session
from app.models.diagnosis import HMACKeyRotationLog
from app.models.fault_tree import FaultTreeVersion
from app.services.diagnosis.hmac_manager import HMACManager

logger = logging.getLogger(__name__)


class HMACKeyManagementService:
    """HMAC 密钥管理服务"""

    async def get_key_status(self) -> dict:
        """查询当前 HMAC 密钥配置状态和活跃版本统计。"""
        settings = get_settings()
        current_key = settings.FAULT_TREE_HMAC_KEY
        previous_key = settings.FAULT_TREE_HMAC_KEY_PREVIOUS

        async with async_session() as session:
            # 统计 active 版本数
            result = await session.execute(
                select(func.count()).select_from(FaultTreeVersion).where(FaultTreeVersion.status == "active")
            )
            active_count = result.scalar() or 0

            # 查询最近一次轮换记录
            result = await session.execute(
                select(HMACKeyRotationLog)
                .where(HMACKeyRotationLog.status == "success")
                .order_by(HMACKeyRotationLog.rotated_at.desc())
                .limit(1)
            )
            last_rotation = result.scalar_one_or_none()

            return {
                "key_configured": bool(current_key),
                "key_length": len(current_key) if current_key else 0,
                "key_prefix": (current_key[:4] + "****") if current_key and len(current_key) >= 4 else None,
                "previous_key_configured": bool(previous_key),
                "active_versions_count": active_count,
                "last_rotation_at": last_rotation.rotated_at.isoformat() if last_rotation else None,
            }

    async def rotate_key(self, new_key: str, operator_id: int) -> dict:
        """执行密钥轮换：用新密钥对所有 active/reviewed 版本重新签名。"""
        if len(new_key.strip()) < 32:
            raise ValueError("新密钥长度必须 >= 32 字符（不能为空白字符）")

        settings = get_settings()
        old_key = settings.FAULT_TREE_HMAC_KEY

        async with async_session() as session:
            # FOR UPDATE 锁定版本（PostgreSQL 生效，SQLite 静默忽略）
            query = (
                select(FaultTreeVersion).where(FaultTreeVersion.status.in_(["active", "reviewed"])).with_for_update()
            )
            result = await session.execute(query)
            versions = result.scalars().all()

            if not versions:
                # 无版本需要重签名，记录日志并返回
                old_prefix = old_key[:4] if old_key and len(old_key) >= 4 else "(空)"
                await self._save_rotation_log(session, operator_id, 0, [], new_key[:4], old_prefix, "success")
                return {
                    "versions_resigned": 0,
                    "resigned_version_ids": [],
                    "rotated_at": datetime.now().isoformat(),
                }

            # 前置验证：检查所有 active 版本的现有签名
            for v in versions:
                if v.snapshot is None:
                    continue
                if v.status == "active" and v.hmac_signature:
                    if not HMACManager.verify_signature(v.snapshot, v.hmac_signature):
                        error_msg = f"版本 {v.id} (tree_id={v.tree_id}) 现有签名验证失败，中止轮换"
                        logger.error(error_msg)
                        await self._save_rotation_log(
                            session,
                            operator_id,
                            0,
                            [],
                            new_key[:4],
                            old_key[:4] if old_key else None,
                            "failed",
                            error_msg,
                        )
                        raise ValueError(error_msg)

            # 用新密钥重签名所有 active/reviewed 版本
            resigned_ids = []
            try:
                for v in versions:
                    new_sig = HMACManager.generate_signature_with_key(v.snapshot, new_key)
                    v.hmac_signature = new_sig
                    resigned_ids.append(v.id)

                # 记录审计日志
                await self._save_rotation_log(
                    session,
                    operator_id,
                    len(resigned_ids),
                    resigned_ids,
                    new_key[:4],
                    old_key[:4] if old_key else None,
                    "success",
                )
                await session.commit()

            except Exception as e:
                await session.rollback()
                error_msg = f"重签名失败: {e}"
                logger.error(error_msg, exc_info=True)
                # 记录失败日志（新事务）
                async with async_session() as log_session:
                    await self._save_rotation_log(
                        log_session,
                        operator_id,
                        0,
                        [],
                        new_key[:4],
                        old_key[:4] if old_key else None,
                        "failed",
                        error_msg,
                    )
                raise ValueError(error_msg)

            logger.info(f"HMAC 密钥轮换完成: 重签名 {len(resigned_ids)} 个版本, 操作者 ID={operator_id}")

            return {
                "versions_resigned": len(resigned_ids),
                "resigned_version_ids": resigned_ids,
                "rotated_at": datetime.now().isoformat(),
            }

    async def verify_all_signatures(self) -> dict:
        """批量验证所有 active/reviewed 版本的签名完整性。"""
        async with async_session() as session:
            result = await session.execute(
                select(FaultTreeVersion).where(FaultTreeVersion.status.in_(["active", "reviewed"]))
            )
            versions = result.scalars().all()

            results = []
            valid_count = 0
            invalid_count = 0

            for v in versions:
                if not v.hmac_signature:
                    results.append(
                        {
                            "version_id": v.id,
                            "tree_id": v.tree_id,
                            "version_number": v.version_number,
                            "status": v.status,
                            "verification": "no_signature",
                        }
                    )
                    invalid_count += 1
                elif HMACManager.verify_signature(v.snapshot, v.hmac_signature):
                    results.append(
                        {
                            "version_id": v.id,
                            "tree_id": v.tree_id,
                            "version_number": v.version_number,
                            "status": v.status,
                            "verification": "valid",
                        }
                    )
                    valid_count += 1
                else:
                    results.append(
                        {
                            "version_id": v.id,
                            "tree_id": v.tree_id,
                            "version_number": v.version_number,
                            "status": v.status,
                            "verification": "invalid",
                        }
                    )
                    invalid_count += 1

            return {
                "total_versions": len(versions),
                "valid_count": valid_count,
                "invalid_count": invalid_count,
                "results": results,
            }

    async def list_rotation_logs(self, page: int = 1, page_size: int = 20) -> dict:
        """分页查询轮换历史记录。"""
        async with async_session() as session:
            count_result = await session.execute(select(func.count()).select_from(HMACKeyRotationLog))
            total = count_result.scalar() or 0

            query = (
                select(HMACKeyRotationLog)
                .order_by(HMACKeyRotationLog.rotated_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(query)
            logs = result.scalars().all()

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [
                    {
                        "id": log.id,
                        "rotated_at": log.rotated_at.isoformat() if log.rotated_at else None,
                        "rotated_by": log.rotated_by,
                        "versions_resigned": log.versions_resigned,
                        "resigned_version_ids": log.resigned_version_ids,
                        "new_key_prefix": log.new_key_prefix,
                        "old_key_prefix": log.old_key_prefix,
                        "status": log.status,
                        "error_detail": log.error_detail,
                    }
                    for log in logs
                ],
            }

    async def _save_rotation_log(
        self,
        session: AsyncSession,
        operator_id: int,
        versions_resigned: int,
        resigned_ids: list,
        new_prefix: str,
        old_prefix: str | None,
        status: str,
        error_detail: str | None = None,
    ):
        """保存轮换审计日志。"""
        log = HMACKeyRotationLog(
            rotated_at=datetime.now(),
            rotated_by=operator_id,
            versions_resigned=versions_resigned,
            resigned_version_ids=resigned_ids if resigned_ids else None,
            new_key_prefix=new_prefix,
            old_key_prefix=old_prefix,
            status=status,
            error_detail=error_detail,
        )
        session.add(log)
        await session.commit()


# 单例
hmac_key_service = HMACKeyManagementService()
