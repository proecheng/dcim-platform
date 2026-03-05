"""
Shift Constraint Service
负荷转移约束管理服务
"""
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.load_shift import ShiftConstraint


class ShiftConstraintService:
    """约束管理服务"""

    @staticmethod
    async def ensure_default_constraints(db: AsyncSession) -> Dict[str, int]:
        """确保算力中心特殊约束默认存在（幂等）。

        Returns:
            {"created": x, "existing": y}
        """
        defaults: List[Dict[str, Any]] = [
            {
                "name": "算力中心负载占比约束(默认)",
                "type": "datacenter_load",
                "description": "默认 IT/制冷/配电/其他占比约束与可转移功率公式参数",
                "constraint_config": {
                    "it_load_ratio_min": 0.60,
                    "it_load_ratio_max": 0.80,
                    "cooling_ratio": 0.20,
                    "distribution_ratio": 0.04,
                    "other_ratio": 0.06,
                    "cooling_transferable_ratio": 0.40,
                    "other_transferable_ratio": 0.60,
                },
                "priority": 2,
                "enabled": True,
            },
            {
                "name": "UPS容量约束(默认)",
                "type": "ups_capacity",
                "description": "默认 UPS 容量安全系数约束（超限拒绝并给出建议值）",
                "constraint_config": {
                    "safety_factor": 0.80,
                    "auto_adjust": True,
                    "reject_on_exceed": True,
                },
                "priority": 1,
                "enabled": True,
            },
        ]

        created = 0
        existing = 0

        for item in defaults:
            exists = await db.execute(
                select(ShiftConstraint).where(ShiftConstraint.constraint_type == item["type"])
            )
            if exists.scalar_one_or_none() is not None:
                existing += 1
                continue

            obj = ShiftConstraint(
                constraint_name=item["name"],
                constraint_type=item["type"],
                description=item["description"],
                constraint_config=item["constraint_config"],
            )
            setattr(obj, "priority", int(item["priority"]))
            setattr(obj, "is_enabled", bool(item["enabled"]))
            db.add(obj)
            created += 1

        if created > 0:
            await db.commit()

        return {"created": created, "existing": existing}

    @staticmethod
    def _extract_config(data: Dict[str, Any]) -> Dict[str, Any]:
        """兼容前后端不同字段名：constraint_config / params / constraint_params。"""
        config = data.get("constraint_config")
        if config is None:
            config = data.get("params")
        if config is None:
            config = data.get("constraint_params")
        return config or {}

    @staticmethod
    def _extract_enabled(data: Dict[str, Any], default: bool = True) -> bool:
        """兼容 enabled / is_enabled / is_active。"""
        if "enabled" in data:
            return bool(data["enabled"])
        if "is_enabled" in data:
            return bool(data["is_enabled"])
        if "is_active" in data:
            return bool(data["is_active"])
        return default

    @staticmethod
    def _to_response(c: ShiftConstraint) -> Dict[str, Any]:
        created_value = getattr(c, "created_at", None)
        updated_value = getattr(c, "updated_at", None)
        created_at = str(created_value) if created_value is not None else None
        updated_at = str(updated_value) if updated_value is not None else None
        return {
            "id": c.id,
            "name": c.constraint_name,
            "type": c.constraint_type,
            "description": c.description,
            "constraint_config": c.constraint_config,
            "params": c.constraint_config,
            "priority": c.priority,
            "enabled": c.is_enabled,
            "created_at": created_at,
            "updated_at": updated_at,
        }

    @staticmethod
    async def get_constraints(db: AsyncSession) -> List[Dict[str, Any]]:
        """获取所有约束"""
        result = await db.execute(select(ShiftConstraint))
        constraints = result.scalars().all()

        return [ShiftConstraintService._to_response(c) for c in constraints]

    @staticmethod
    async def create_constraint(db: AsyncSession, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建约束"""
        constraint = ShiftConstraint(
            constraint_name=data.get("name"),
            constraint_type=data.get("type"),
            description=data.get("description"),
            constraint_config=ShiftConstraintService._extract_config(data),
        )
        setattr(constraint, "priority", int(data.get("priority", 5)))
        setattr(constraint, "is_enabled", ShiftConstraintService._extract_enabled(data, True))

        db.add(constraint)
        await db.commit()
        await db.refresh(constraint)

        return ShiftConstraintService._to_response(constraint)

    @staticmethod
    async def update_constraint(db: AsyncSession, constraint_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """更新约束"""
        result = await db.execute(
            select(ShiftConstraint).where(ShiftConstraint.id == constraint_id)
        )
        constraint = result.scalar_one_or_none()

        if not constraint:
            raise ValueError(f"Constraint {constraint_id} not found")

        for key, value in data.items():
            if key == "name":
                constraint.constraint_name = value
            elif key == "type":
                constraint.constraint_type = value
            elif key == "description":
                constraint.description = value
            elif key in {"params", "constraint_params", "constraint_config"}:
                constraint.constraint_config = value
            elif key == "priority":
                setattr(constraint, "priority", int(value))
            elif key in {"enabled", "is_enabled", "is_active"}:
                setattr(constraint, "is_enabled", bool(value))

        # 兼容批量更新：如果没走到循环分支，也按统一提取规则覆盖
        if any(k in data for k in ("params", "constraint_params", "constraint_config")):
            constraint.constraint_config = ShiftConstraintService._extract_config(data)
        if any(k in data for k in ("enabled", "is_enabled", "is_active")):
            setattr(constraint, "is_enabled", ShiftConstraintService._extract_enabled(data, default=True))

        await db.commit()
        await db.refresh(constraint)

        return ShiftConstraintService._to_response(constraint)

    @staticmethod
    async def delete_constraint(db: AsyncSession, constraint_id: int) -> bool:
        """删除约束"""
        result = await db.execute(
            select(ShiftConstraint).where(ShiftConstraint.id == constraint_id)
        )
        constraint = result.scalar_one_or_none()

        if not constraint:
            return False

        await db.delete(constraint)
        await db.commit()
        return True
