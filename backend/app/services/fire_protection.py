"""
消防分级联动策略 — YAML 加载服务
Story 9-2: 消防分级联动策略
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.linkage import LinkagePolicy, LinkageAction

logger = logging.getLogger(__name__)

# YAML 配置文件路径
_CONFIG_DIR = Path(__file__).parent.parent / "config"
_FIRE_POLICY_FILE = _CONFIG_DIR / "fire_protection_policies.yaml"

# 加载状态
_last_sync_time: Optional[datetime] = None
_synced_count: int = 0


def load_yaml_policies() -> List[dict]:
    """读取 YAML 消防策略定义文件，返回策略列表"""
    if not _FIRE_POLICY_FILE.exists():
        logger.warning("消防策略 YAML 文件不存在: %s", _FIRE_POLICY_FILE)
        return []

    try:
        import yaml

        with open(_FIRE_POLICY_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            logger.warning("消防策略 YAML 文件为空")
            return []

        policies = data.get("fire_protection_policies", [])
        logger.info("消防策略 YAML: 读取到 %d 条策略定义", len(policies))
        return policies
    except Exception as e:
        logger.error("消防策略 YAML 加载失败: %s", e)
        return []


async def sync_to_database(db: AsyncSession) -> int:
    """将 YAML 策略同步到数据库（已存在则跳过）"""
    global _last_sync_time, _synced_count

    policies = load_yaml_policies()
    if not policies:
        return 0

    created_count = 0
    for policy_def in policies:
        name = policy_def.get("name", "")
        if not name:
            continue

        # 检查是否已存在
        result = await db.execute(select(LinkagePolicy).where(LinkagePolicy.name == name))
        existing = result.scalar_one_or_none()
        if existing is not None:
            logger.debug("消防策略已存在，跳过: %s", name)
            continue

        # 创建策略
        policy = LinkagePolicy(
            name=name,
            description=policy_def.get("description", ""),
            trigger_type=policy_def.get("trigger_type", "alarm.triggered"),
            trigger_condition=policy_def.get("trigger_condition", {}),
            priority=policy_def.get("priority", "normal"),
            is_enabled=True,
            is_system=True,
        )
        db.add(policy)
        await db.flush()

        # 创建动作
        actions = policy_def.get("actions", [])
        for action_def in actions:
            action = LinkageAction(
                policy_id=policy.id,
                action_type=action_def.get("action_type", ""),
                action_config=action_def.get("action_config", {}),
                sort_order=action_def.get("sort_order", 0),
                timeout_seconds=action_def.get("timeout_seconds", 3),
                retry_count=action_def.get("retry_count", 0),
            )
            db.add(action)

        created_count += 1
        logger.info("消防策略已创建: %s（%d 个动作）", name, len(actions))

    if created_count > 0:
        await db.commit()

    _last_sync_time = datetime.now()
    _synced_count = created_count
    logger.info("消防策略同步完成: 新建 %d 条", created_count)
    return created_count


async def reload(db: AsyncSession) -> int:
    """重载消防策略（删除旧的系统消防策略 + 重新创建）"""
    global _last_sync_time, _synced_count

    # 查找所有 is_system=True 且 trigger_condition 中包含 fire_level 的策略
    result = await db.execute(
        select(LinkagePolicy).where(
            LinkagePolicy.is_system == True  # noqa: E712
        )
    )
    system_policies = result.scalars().all()

    deleted_count = 0
    for policy in system_policies:
        condition = policy.trigger_condition
        if isinstance(condition, dict) and "fire_level" in condition:
            # 先删除动作
            await db.execute(delete(LinkageAction).where(LinkageAction.policy_id == policy.id))
            await db.delete(policy)
            deleted_count += 1

    if deleted_count > 0:
        await db.commit()
    logger.info("消防策略重载: 删除 %d 条旧策略", deleted_count)

    # 重新同步
    created_count = await sync_to_database(db)
    _last_sync_time = datetime.now()
    _synced_count = created_count
    return created_count


def get_fire_level(policy_or_condition: dict) -> Optional[str]:
    """从策略或 trigger_condition 中获取消防分级标识"""
    if "trigger_condition" in policy_or_condition:
        condition = policy_or_condition.get("trigger_condition", {})
    else:
        condition = policy_or_condition

    if isinstance(condition, dict):
        return condition.get("fire_level")
    return None


def get_status() -> dict:
    """获取消防策略加载状态"""
    return {
        "last_sync_time": _last_sync_time.isoformat() if _last_sync_time is not None else None,
        "synced_count": _synced_count,
        "yaml_file": str(_FIRE_POLICY_FILE),
        "yaml_exists": _FIRE_POLICY_FILE.exists(),
    }
