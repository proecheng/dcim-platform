"""
Shift Constraint Service
负荷转移约束管理服务
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from app.models.load_shift import ShiftConstraint


class ShiftConstraintService:
    """约束管理服务"""
    
    @staticmethod
    async def get_constraints(db: AsyncSession) -> List[Dict[str, Any]]:
        """获取所有约束"""
        result = await db.execute(select(ShiftConstraint))
        constraints = result.scalars().all()
        
        return [
            {
                "id": c.id,
                "name": c.constraint_name,
                "type": c.constraint_type,
                "description": c.description,
                "params": c.constraint_params,
                "priority": c.priority,
                "enabled": c.is_active,
                "created_at": c.created_at.isoformat() if c.created_at else None
            }
            for c in constraints
        ]
    
    @staticmethod
    async def create_constraint(db: AsyncSession, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建约束"""
        constraint = ShiftConstraint(
            constraint_name=data.get("name"),
            constraint_type=data.get("type"),
            description=data.get("description"),
            constraint_params=data.get("params"),
            priority=data.get("priority", "medium"),
            is_active=data.get("enabled", True)
        )
        
        db.add(constraint)
        await db.commit()
        await db.refresh(constraint)
        
        return {
            "id": constraint.id,
            "name": constraint.constraint_name,
            "type": constraint.constraint_type,
            "description": constraint.description,
            "params": constraint.constraint_params,
            "priority": constraint.priority,
            "enabled": constraint.is_active
        }
    
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
            elif key == "params":
                constraint.constraint_params = value
            elif key == "priority":
                constraint.priority = value
            elif key == "enabled":
                constraint.is_active = value
        
        constraint.updated_at = datetime.now()
        await db.commit()
        await db.refresh(constraint)
        
        return {
            "id": constraint.id,
            "name": constraint.constraint_name,
            "type": constraint.constraint_type,
            "description": constraint.description,
            "params": constraint.constraint_params,
            "priority": constraint.priority,
            "enabled": constraint.is_active
        }
    
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
