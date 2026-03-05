"""默认负荷转移约束初始化测试"""

import pytest
from sqlalchemy import select

from app.models.load_shift import ShiftConstraint
from app.services.load_shift.shift_constraint_service import ShiftConstraintService


@pytest.mark.asyncio
async def test_ensure_default_constraints_idempotent(async_db):
    """重复执行初始化时应幂等，不重复插入。"""
    first = await ShiftConstraintService.ensure_default_constraints(async_db)
    second = await ShiftConstraintService.ensure_default_constraints(async_db)

    assert first["created"] >= 2
    assert second["created"] == 0

    result = await async_db.execute(
        select(ShiftConstraint).where(
            ShiftConstraint.constraint_type.in_(["datacenter_load", "ups_capacity"])
        )
    )
    rows = result.scalars().all()
    assert len(rows) == 2

    by_type = {r.constraint_type: r for r in rows}
    assert "datacenter_load" in by_type
    assert "ups_capacity" in by_type

    assert by_type["datacenter_load"].constraint_config.get("it_load_ratio_min") == 0.60
    assert by_type["ups_capacity"].constraint_config.get("safety_factor") == 0.80
