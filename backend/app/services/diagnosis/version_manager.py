"""
故障树版本管理器 - Story 24.4
"""
import json
import logging
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from app.models.fault_tree import (
    FaultTree,
    FaultTreeNode,
    FaultTreeEdge,
    FaultTreeDeviceMapping,
    FaultTreeVersion
)
from app.services.diagnosis.hmac_manager import HMACManager
from app.services.diagnosis.dag_validator import DAGValidator
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)


class VersionManager:
    """故障树版本管理器"""

    @staticmethod
    async def create_version(
        session: AsyncSession,
        tree_id: int,
        created_by: int
    ) -> FaultTreeVersion:
        """创建新版本"""
        # 查询故障树及其节点和边
        tree = await session.get(FaultTree, tree_id)
        if not tree:
            raise ValueError(f"Fault tree {tree_id} not found")

        nodes = await session.execute(
            select(FaultTreeNode).where(FaultTreeNode.tree_id == tree_id)
        )
        edges = await session.execute(
            select(FaultTreeEdge).where(FaultTreeEdge.tree_id == tree_id)
        )
        device_mappings = await session.execute(
            select(FaultTreeDeviceMapping).where(FaultTreeDeviceMapping.tree_id == tree_id)
        )

        # 构建完整快照（包含设备映射）
        snapshot = {
            "tree": {"id": tree.id, "name": tree.name, "description": tree.description},
            "nodes": [
                {
                    "id": n.id,
                    "node_type": n.node_type,
                    "gate_type": n.gate_type,
                    "name": n.name,
                    "description": n.description,
                    "prior_probability": n.prior_probability,
                    "evidence_point_id": n.evidence_point_id,
                    "config": n.config
                }
                for n in nodes.scalars()
            ],
            "edges": [
                {"parent_node_id": e.parent_node_id, "child_node_id": e.child_node_id}
                for e in edges.scalars()
            ],
            "device_mappings": [
                {
                    "device_type": dm.device_type,
                    "alarm_type": dm.alarm_type,
                    "priority": dm.priority
                }
                for dm in device_mappings.scalars()
            ]
        }
        snapshot_json = json.dumps(snapshot, sort_keys=True)

        # 使用 SELECT FOR UPDATE 获取下一个版本号（防止并发冲突）
        result = await session.execute(
            select(FaultTreeVersion.version_number)
            .where(FaultTreeVersion.tree_id == tree_id)
            .order_by(FaultTreeVersion.version_number.desc())
            .limit(1)
            .with_for_update()
        )
        last_version = result.scalar_one_or_none()
        next_version = (last_version or 0) + 1

        # 创建版本记录
        version = FaultTreeVersion(
            tree_id=tree_id,
            version_number=next_version,
            status="draft",
            snapshot=snapshot_json,
            created_by=created_by
        )
        session.add(version)
        await session.commit()
        await session.refresh(version)
        return version

    @staticmethod
    async def activate_version(
        session: AsyncSession,
        version_id: int
    ) -> FaultTreeVersion:
        """激活版本"""
        version = await session.get(FaultTreeVersion, version_id)
        if not version:
            raise ValueError(f"Version {version_id} not found")

        if version.status != "reviewed":
            raise ValueError(f"Only reviewed versions can be activated, current status: {version.status}")

        # 解析快照并验证 DAG
        try:
            snapshot_data = json.loads(version.snapshot)
            nodes = snapshot_data.get("nodes", [])
            edges = snapshot_data.get("edges", [])

            is_valid, error_msg = DAGValidator.validate(nodes, edges)
            if not is_valid:
                raise ValueError(f"DAG validation failed: {error_msg}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid snapshot JSON: {e}")

        # 如果版本已有签名（重新激活场景），先验证旧签名
        if version.hmac_signature:
            if not HMACManager.verify_signature(version.snapshot, version.hmac_signature):
                logger.error(f"HMAC signature verification failed for version {version_id}")
                raise ValueError("HMAC signature verification failed")

        # 生成新签名
        new_signature = HMACManager.generate_signature(version.snapshot)

        # 使用 SELECT FOR UPDATE 锁定同一 tree 的所有 active 版本（防止并发激活）
        await session.execute(
            select(FaultTreeVersion.id)
            .where(FaultTreeVersion.tree_id == version.tree_id)
            .where(FaultTreeVersion.status == "active")
            .with_for_update()
        )

        # 在单个事务中完成状态切换
        # 1. 归档同一 tree 的其他 active 版本
        await session.execute(
            update(FaultTreeVersion)
            .where(FaultTreeVersion.tree_id == version.tree_id)
            .where(FaultTreeVersion.status == "active")
            .values(status="archived")
        )

        # 2. 激活当前版本
        version.status = "active"
        version.hmac_signature = new_signature
        version.activated_at = func.now()
        await session.commit()
        await session.refresh(version)

        # 发布版本切换事件（失败不影响激活）
        try:
            redis = await get_redis()
            await redis.publish("diagnosis:tree_version_change", json.dumps({
                "tree_id": version.tree_id,
                "version_id": version.id,
                "version_number": version.version_number
            }))
        except Exception as e:
            logger.warning(f"Failed to publish version change event: {e}")

        return version

    @staticmethod
    async def rollback_version(
        session: AsyncSession,
        tree_id: int
    ) -> FaultTreeVersion:
        """回滚到上一个版本"""
        # 查找最近一个 archived 版本
        result = await session.execute(
            select(FaultTreeVersion)
            .where(FaultTreeVersion.tree_id == tree_id)
            .where(FaultTreeVersion.status == "archived")
            .order_by(FaultTreeVersion.activated_at.desc())
            .limit(1)
        )
        archived_version = result.scalar_one_or_none()

        if not archived_version:
            raise ValueError("没有可回滚的版本")

        # 验证签名
        if archived_version.hmac_signature:
            if not HMACManager.verify_signature(archived_version.snapshot, archived_version.hmac_signature):
                raise ValueError("版本签名验证失败，可能使用了已删除的旧密钥，请联系管理员")

        # 将状态改为 reviewed，然后激活
        archived_version.status = "reviewed"
        await session.flush()

        # 调用 activate_version 完成激活
        return await VersionManager.activate_version(session, archived_version.id)
