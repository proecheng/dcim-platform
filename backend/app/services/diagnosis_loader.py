"""
诊断规则 YAML 加载服务
Story 9-3: 智能故障诊断
"""

import logging
from pathlib import Path
from typing import List

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.diagnosis import DiagnosisRule

logger = logging.getLogger(__name__)

# YAML 文件路径
_YAML_PATH = Path(__file__).parent.parent / "config" / "diagnosis_rules.yaml"


def load_yaml_rules() -> List[dict]:
    """从 YAML 文件读取诊断规则"""
    if not _YAML_PATH.exists():
        logger.warning("诊断规则 YAML 文件不存在: %s", _YAML_PATH)
        return []
    try:
        with open(_YAML_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        rules = data.get("rules", [])
        logger.info("诊断规则 YAML: 读取 %d 条规则", len(rules))
        return rules
    except Exception as e:
        logger.error("诊断规则 YAML 加载失败: %s", e)
        return []


async def sync_to_database(db: AsyncSession) -> int:
    """同步 YAML 规则到数据库（已存在则跳过）"""
    rules = load_yaml_rules()
    if not rules:
        return 0

    created = 0
    for rule_data in rules:
        rule_code = rule_data.get("rule_code")
        if not rule_code:
            continue

        # 检查是否已存在
        result = await db.execute(select(DiagnosisRule).where(DiagnosisRule.rule_code == rule_code))
        existing = result.scalar_one_or_none()
        if existing is not None:
            continue

        # 创建新规则
        rule = DiagnosisRule(
            rule_code=rule_code,
            name=rule_data.get("name", rule_code),
            description=rule_data.get("description"),
            category=rule_data.get("category", "composite"),
            trigger_condition=rule_data.get("trigger_condition"),
            diagnosis_logic=rule_data.get("diagnosis_logic"),
            priority=rule_data.get("priority", 0),
            is_enabled=True,
            is_system=True,
        )
        db.add(rule)
        created += 1

    if created > 0:
        await db.commit()
        logger.info("诊断规则同步: 新增 %d 条系统规则", created)
    return created


async def reload(db: AsyncSession) -> int:
    """重载 YAML 规则（删除所有系统规则后重新创建）"""
    # 删除所有系统规则
    result = await db.execute(
        select(DiagnosisRule).where(DiagnosisRule.is_system == True)  # noqa: E712
    )
    system_rules = result.scalars().all()
    for rule in system_rules:
        await db.delete(rule)
    await db.commit()
    logger.info("诊断规则重载: 已删除 %d 条系统规则", len(system_rules))

    # 重新加载
    rules = load_yaml_rules()
    created = 0
    for rule_data in rules:
        rule_code = rule_data.get("rule_code")
        if not rule_code:
            continue
        rule = DiagnosisRule(
            rule_code=rule_code,
            name=rule_data.get("name", rule_code),
            description=rule_data.get("description"),
            category=rule_data.get("category", "composite"),
            trigger_condition=rule_data.get("trigger_condition"),
            diagnosis_logic=rule_data.get("diagnosis_logic"),
            priority=rule_data.get("priority", 0),
            is_enabled=True,
            is_system=True,
        )
        db.add(rule)
        created += 1

    if created > 0:
        await db.commit()
    logger.info("诊断规则重载: 重新创建 %d 条系统规则", created)
    return created
