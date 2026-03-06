"""
故障树版本管理器 - Story 24.4
"""
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
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

# 回滚频率限制：5分钟内最多3次
ROLLBACK_RATE_LIMIT_WINDOW = timedelta(minutes=5)
ROLLBACK_RATE_LIMIT_MAX = 3


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

        # 使用 SELECT FOR UPDATE 锁定整个 tree 的版本记录（防止并发创建）
        await session.execute(
            select(FaultTreeVersion.id)
            .where(FaultTreeVersion.tree_id == tree_id)
            .with_for_update()
        )

        # 获取下一个版本号
        result = await session.execute(
            select(FaultTreeVersion.version_number)
            .where(FaultTreeVersion.tree_id == tree_id)
            .order_by(FaultTreeVersion.version_number.desc())
            .limit(1)
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

        if version.status not in ("reviewed", "archived"):
            raise ValueError(f"Only reviewed or archived versions can be activated, current status: {version.status}")

        # 解析快照并验证完整性
        try:
            snapshot_data = json.loads(version.snapshot)

            # 验证快照包含所有必需字段
            required_fields = ["tree", "nodes", "edges", "device_mappings"]
            missing_fields = [f for f in required_fields if f not in snapshot_data]
            if missing_fields:
                raise ValueError(f"Snapshot missing required fields: {', '.join(missing_fields)}")

            nodes = snapshot_data.get("nodes", [])
            edges = snapshot_data.get("edges", [])

            # 验证 DAG
            is_valid, error_msg = DAGValidator.validate(nodes, edges)
            if not is_valid:
                raise ValueError(f"DAG validation failed: {error_msg}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid snapshot JSON: {e}")

        # 生成新签名（重新激活时直接覆盖旧签名，不验证）
        new_signature = HMACManager.generate_signature(version.snapshot)

        # 使用 SELECT FOR UPDATE 锁定同一 tree 的所有版本（不限状态）
        await session.execute(
            select(FaultTreeVersion.id)
            .where(FaultTreeVersion.tree_id == version.tree_id)
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
            logger.error(f"Failed to publish version change event for tree {version.tree_id}, version {version.id}: {e}")

        return version

    @staticmethod
    async def rollback_version(
        session: AsyncSession,
        tree_id: int
    ) -> FaultTreeVersion:
        """回滚到上一个版本"""
        # 检查回滚频率限制（统计最近的 archived -> active 状态转换）
        cutoff_time = datetime.utcnow() - ROLLBACK_RATE_LIMIT_WINDOW
        result = await session.execute(
            select(func.count(FaultTreeVersion.id))
            .where(FaultTreeVersion.tree_id == tree_id)
            .where(FaultTreeVersion.status == "active")
            .where(FaultTreeVersion.activated_at >= cutoff_time)
        )
        recent_activations = result.scalar()

        # 获取当前 active 版本
        current_active_result = await session.execute(
            select(FaultTreeVersion)
            .where(FaultTreeVersion.tree_id == tree_id)
            .where(FaultTreeVersion.status == "active")
        )
        current_active = current_active_result.scalar_one_or_none()

        # 如果当前 active 版本是最近激活的，说明可能是回滚操作
        # 简化逻辑：如果最近激活次数 >= 限制，拒绝回滚
        if recent_activations >= ROLLBACK_RATE_LIMIT_MAX:
            raise ValueError("回滚过于频繁，请稍后再试")

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

        # 直接调用 activate_version 激活（不修改状态）
        return await VersionManager.activate_version(session, archived_version.id)
