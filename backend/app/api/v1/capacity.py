"""
容量管理 API - v1
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, update

from ..deps import get_db, require_viewer, require_operator
from ...models.user import User
from ...models.capacity import (
    SpaceCapacity, PowerCapacity, CoolingCapacity, WeightCapacity,
    CapacityPlan, CapacityStatus
)
from ...schemas.capacity import (
    SpaceCapacityCreate, SpaceCapacityUpdate, SpaceCapacityResponse,
    PowerCapacityCreate, PowerCapacityUpdate, PowerCapacityResponse,
    CoolingCapacityCreate, CoolingCapacityUpdate, CoolingCapacityResponse,
    WeightCapacityCreate, WeightCapacityUpdate, WeightCapacityResponse,
    CapacityPlanCreate, CapacityPlanResponse,
    CapacityStatistics
)

router = APIRouter(prefix="/capacity", tags=["容量管理"])


# ==================== 辅助函数 ====================

def _calculate_usage_rate(used: Optional[float], total: Optional[float]) -> Optional[float]:
    """
    计算使用率

    Args:
        used: 已用量
        total: 总量

    Returns:
        使用率(%)，保留两位小数
    """
    if total is None or total <= 0:
        return None
    if used is None:
        return 0.0
    return round(used / total * 100, 2)


def _calculate_status(
    used: float,
    total: float,
    warning: float,
    critical: float
) -> CapacityStatus:
    """
    根据使用率计算容量状态

    Args:
        used: 已用量
        total: 总量
        warning: 警告阈值(%)
        critical: 严重阈值(%)

    Returns:
        容量状态枚举值
    """
    if total <= 0:
        return CapacityStatus.normal

    rate = used / total * 100

    if rate >= 100:
        return CapacityStatus.full
    elif rate >= critical:
        return CapacityStatus.critical
    elif rate >= warning:
        return CapacityStatus.warning

    return CapacityStatus.normal


# ==================== 空间容量管理 ====================

@router.get("/space", response_model=List[SpaceCapacityResponse], summary="获取空间容量列表")
async def get_space_capacities(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取空间容量列表（分页）
    """
    query = select(SpaceCapacity).offset(skip).limit(limit)
    result = await db.execute(query)
    capacities = result.scalars().all()

    response_list = []
    for capacity in capacities:
        capacity_data = SpaceCapacityResponse.model_validate(capacity)
        # 计算使用率
        capacity_data.usage_rate = _calculate_usage_rate(
            capacity.used_u_positions,
            capacity.total_u_positions
        )
        response_list.append(capacity_data)

    return response_list


@router.post("/space", response_model=SpaceCapacityResponse, summary="创建空间容量")
async def create_space_capacity(
    data: SpaceCapacityCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    创建空间容量
    """
    capacity = SpaceCapacity(**data.model_dump())

    # 计算状态 - 基于U位使用率
    used = data.used_u_positions or 0
    total = data.total_u_positions or 0
    warning = data.warning_threshold or 80
    critical = data.critical_threshold or 95
    capacity.status = _calculate_status(used, total, warning, critical)

    db.add(capacity)
    await db.commit()
    await db.refresh(capacity)

    capacity_data = SpaceCapacityResponse.model_validate(capacity)
    capacity_data.usage_rate = _calculate_usage_rate(
        capacity.used_u_positions,
        capacity.total_u_positions
    )
    return capacity_data


@router.get("/space/{id}", response_model=SpaceCapacityResponse, summary="获取空间容量详情")
async def get_space_capacity(
    id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    根据ID获取空间容量详情
    """
    result = await db.execute(select(SpaceCapacity).where(SpaceCapacity.id == id))
    capacity = result.scalar_one_or_none()

    if not capacity:
        raise HTTPException(status_code=404, detail="空间容量不存在")

    capacity_data = SpaceCapacityResponse.model_validate(capacity)
    capacity_data.usage_rate = _calculate_usage_rate(
        capacity.used_u_positions,
        capacity.total_u_positions
    )
    return capacity_data


@router.put("/space/{id}", response_model=SpaceCapacityResponse, summary="更新空间容量")
async def update_space_capacity(
    id: int,
    data: SpaceCapacityUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    更新空间容量信息
    """
    result = await db.execute(select(SpaceCapacity).where(SpaceCapacity.id == id))
    capacity = result.scalar_one_or_none()

    if not capacity:
        raise HTTPException(status_code=404, detail="空间容量不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(capacity, key, value)

    # 重新计算状态
    used = capacity.used_u_positions or 0
    total = capacity.total_u_positions or 0
    warning = capacity.warning_threshold or 80
    critical = capacity.critical_threshold or 95
    capacity.status = _calculate_status(used, total, warning, critical)

    capacity.updated_at = datetime.now()
    await db.commit()
    await db.refresh(capacity)

    capacity_data = SpaceCapacityResponse.model_validate(capacity)
    capacity_data.usage_rate = _calculate_usage_rate(
        capacity.used_u_positions,
        capacity.total_u_positions
    )
    return capacity_data


@router.delete("/space/{id}", summary="删除空间容量")
async def delete_space_capacity(
    id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    删除空间容量
    """
    result = await db.execute(select(SpaceCapacity).where(SpaceCapacity.id == id))
    capacity = result.scalar_one_or_none()

    if not capacity:
        raise HTTPException(status_code=404, detail="空间容量不存在")

    await db.delete(capacity)
    await db.commit()

    return {"message": "删除成功"}


# ==================== 电力容量管理 ====================

@router.get("/power", response_model=List[PowerCapacityResponse], summary="获取电力容量列表")
async def get_power_capacities(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取电力容量列表（分页）
    """
    query = select(PowerCapacity).offset(skip).limit(limit)
    result = await db.execute(query)
    capacities = result.scalars().all()

    response_list = []
    for capacity in capacities:
        capacity_data = PowerCapacityResponse.model_validate(capacity)
        # 计算使用率
        capacity_data.usage_rate = _calculate_usage_rate(
            capacity.used_capacity_kw,
            capacity.total_capacity_kw
        )
        response_list.append(capacity_data)

    return response_list


@router.post("/power", response_model=PowerCapacityResponse, summary="创建电力容量")
async def create_power_capacity(
    data: PowerCapacityCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    创建电力容量
    """
    capacity = PowerCapacity(**data.model_dump())

    # 计算状态 - 基于kW使用率
    used = data.used_capacity_kw or 0
    total = data.total_capacity_kw or 0
    warning = data.warning_threshold or 70
    critical = data.critical_threshold or 85
    capacity.status = _calculate_status(used, total, warning, critical)

    db.add(capacity)
    await db.commit()
    await db.refresh(capacity)

    capacity_data = PowerCapacityResponse.model_validate(capacity)
    capacity_data.usage_rate = _calculate_usage_rate(
        capacity.used_capacity_kw,
        capacity.total_capacity_kw
    )
    return capacity_data


@router.get("/power/{id}", response_model=PowerCapacityResponse, summary="获取电力容量详情")
async def get_power_capacity(
    id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    根据ID获取电力容量详情
    """
    result = await db.execute(select(PowerCapacity).where(PowerCapacity.id == id))
    capacity = result.scalar_one_or_none()

    if not capacity:
        raise HTTPException(status_code=404, detail="电力容量不存在")

    capacity_data = PowerCapacityResponse.model_validate(capacity)
    capacity_data.usage_rate = _calculate_usage_rate(
        capacity.used_capacity_kw,
        capacity.total_capacity_kw
    )
    return capacity_data


@router.put("/power/{id}", response_model=PowerCapacityResponse, summary="更新电力容量")
async def update_power_capacity(
    id: int,
    data: PowerCapacityUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    更新电力容量信息
    """
    result = await db.execute(select(PowerCapacity).where(PowerCapacity.id == id))
    capacity = result.scalar_one_or_none()

    if not capacity:
        raise HTTPException(status_code=404, detail="电力容量不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(capacity, key, value)

    # 重新计算状态
    used = capacity.used_capacity_kw or 0
    total = capacity.total_capacity_kw or 0
    warning = capacity.warning_threshold or 70
    critical = capacity.critical_threshold or 85
    capacity.status = _calculate_status(used, total, warning, critical)

    capacity.updated_at = datetime.now()
    await db.commit()
    await db.refresh(capacity)

    capacity_data = PowerCapacityResponse.model_validate(capacity)
    capacity_data.usage_rate = _calculate_usage_rate(
        capacity.used_capacity_kw,
        capacity.total_capacity_kw
    )
    return capacity_data


@router.delete("/power/{id}", summary="删除电力容量")
async def delete_power_capacity(
    id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    删除电力容量
    """
    result = await db.execute(select(PowerCapacity).where(PowerCapacity.id == id))
    capacity = result.scalar_one_or_none()

    if not capacity:
        raise HTTPException(status_code=404, detail="电力容量不存在")

    await db.delete(capacity)
    await db.commit()

    return {"message": "删除成功"}


# ==================== 制冷容量管理 ====================

@router.get("/cooling", response_model=List[CoolingCapacityResponse], summary="获取制冷容量列表")
async def get_cooling_capacities(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取制冷容量列表（分页）
    """
    query = select(CoolingCapacity).offset(skip).limit(limit)
    result = await db.execute(query)
    capacities = result.scalars().all()

    response_list = []
    for capacity in capacities:
        capacity_data = CoolingCapacityResponse.model_validate(capacity)
        # 计算使用率
        capacity_data.usage_rate = _calculate_usage_rate(
            capacity.used_cooling_kw,
            capacity.total_cooling_kw
        )
        response_list.append(capacity_data)

    return response_list


@router.post("/cooling", response_model=CoolingCapacityResponse, summary="创建制冷容量")
async def create_cooling_capacity(
    data: CoolingCapacityCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    创建制冷容量
    """
    capacity = CoolingCapacity(**data.model_dump())

    # 计算状态 - 基于制冷量使用率
    used = data.used_cooling_kw or 0
    total = data.total_cooling_kw or 0
    warning = data.warning_threshold or 75
    critical = data.critical_threshold or 90
    capacity.status = _calculate_status(used, total, warning, critical)

    db.add(capacity)
    await db.commit()
    await db.refresh(capacity)

    capacity_data = CoolingCapacityResponse.model_validate(capacity)
    capacity_data.usage_rate = _calculate_usage_rate(
        capacity.used_cooling_kw,
        capacity.total_cooling_kw
    )
    return capacity_data


@router.get("/cooling/{id}", response_model=CoolingCapacityResponse, summary="获取制冷容量详情")
async def get_cooling_capacity(
    id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    根据ID获取制冷容量详情
    """
    result = await db.execute(select(CoolingCapacity).where(CoolingCapacity.id == id))
    capacity = result.scalar_one_or_none()

    if not capacity:
        raise HTTPException(status_code=404, detail="制冷容量不存在")

    capacity_data = CoolingCapacityResponse.model_validate(capacity)
    capacity_data.usage_rate = _calculate_usage_rate(
        capacity.used_cooling_kw,
        capacity.total_cooling_kw
    )
    return capacity_data


@router.put("/cooling/{id}", response_model=CoolingCapacityResponse, summary="更新制冷容量")
async def update_cooling_capacity(
    id: int,
    data: CoolingCapacityUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    更新制冷容量信息
    """
    result = await db.execute(select(CoolingCapacity).where(CoolingCapacity.id == id))
    capacity = result.scalar_one_or_none()

    if not capacity:
        raise HTTPException(status_code=404, detail="制冷容量不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(capacity, key, value)

    # 重新计算状态
    used = capacity.used_cooling_kw or 0
    total = capacity.total_cooling_kw or 0
    warning = capacity.warning_threshold or 75
    critical = capacity.critical_threshold or 90
    capacity.status = _calculate_status(used, total, warning, critical)

    capacity.updated_at = datetime.now()
    await db.commit()
    await db.refresh(capacity)

    capacity_data = CoolingCapacityResponse.model_validate(capacity)
    capacity_data.usage_rate = _calculate_usage_rate(
        capacity.used_cooling_kw,
        capacity.total_cooling_kw
    )
    return capacity_data


@router.delete("/cooling/{id}", summary="删除制冷容量")
async def delete_cooling_capacity(
    id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    删除制冷容量
    """
    result = await db.execute(select(CoolingCapacity).where(CoolingCapacity.id == id))
    capacity = result.scalar_one_or_none()

    if not capacity:
        raise HTTPException(status_code=404, detail="制冷容量不存在")

    await db.delete(capacity)
    await db.commit()

    return {"message": "删除成功"}


# ==================== 承重容量管理 ====================

@router.get("/weight", response_model=List[WeightCapacityResponse], summary="获取承重容量列表")
async def get_weight_capacities(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取承重容量列表（分页）
    """
    query = select(WeightCapacity).offset(skip).limit(limit)
    result = await db.execute(query)
    capacities = result.scalars().all()

    response_list = []
    for capacity in capacities:
        capacity_data = WeightCapacityResponse.model_validate(capacity)
        # 计算使用率
        capacity_data.usage_rate = _calculate_usage_rate(
            capacity.used_weight_kg,
            capacity.total_weight_kg
        )
        response_list.append(capacity_data)

    return response_list


@router.post("/weight", response_model=WeightCapacityResponse, summary="创建承重容量")
async def create_weight_capacity(
    data: WeightCapacityCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    创建承重容量
    """
    capacity = WeightCapacity(**data.model_dump())

    # 计算状态 - 基于承重使用率
    used = data.used_weight_kg or 0
    total = data.total_weight_kg or 0
    warning = data.warning_threshold or 80
    critical = data.critical_threshold or 95
    capacity.status = _calculate_status(used, total, warning, critical)

    db.add(capacity)
    await db.commit()
    await db.refresh(capacity)

    capacity_data = WeightCapacityResponse.model_validate(capacity)
    capacity_data.usage_rate = _calculate_usage_rate(
        capacity.used_weight_kg,
        capacity.total_weight_kg
    )
    return capacity_data


@router.get("/weight/{id}", response_model=WeightCapacityResponse, summary="获取承重容量详情")
async def get_weight_capacity(
    id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    根据ID获取承重容量详情
    """
    result = await db.execute(select(WeightCapacity).where(WeightCapacity.id == id))
    capacity = result.scalar_one_or_none()

    if not capacity:
        raise HTTPException(status_code=404, detail="承重容量不存在")

    capacity_data = WeightCapacityResponse.model_validate(capacity)
    capacity_data.usage_rate = _calculate_usage_rate(
        capacity.used_weight_kg,
        capacity.total_weight_kg
    )
    return capacity_data


@router.put("/weight/{id}", response_model=WeightCapacityResponse, summary="更新承重容量")
async def update_weight_capacity(
    id: int,
    data: WeightCapacityUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    更新承重容量信息
    """
    result = await db.execute(select(WeightCapacity).where(WeightCapacity.id == id))
    capacity = result.scalar_one_or_none()

    if not capacity:
        raise HTTPException(status_code=404, detail="承重容量不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(capacity, key, value)

    # 重新计算状态
    used = capacity.used_weight_kg or 0
    total = capacity.total_weight_kg or 0
    warning = capacity.warning_threshold or 80
    critical = capacity.critical_threshold or 95
    capacity.status = _calculate_status(used, total, warning, critical)

    capacity.updated_at = datetime.now()
    await db.commit()
    await db.refresh(capacity)

    capacity_data = WeightCapacityResponse.model_validate(capacity)
    capacity_data.usage_rate = _calculate_usage_rate(
        capacity.used_weight_kg,
        capacity.total_weight_kg
    )
    return capacity_data


@router.delete("/weight/{id}", summary="删除承重容量")
async def delete_weight_capacity(
    id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    删除承重容量
    """
    result = await db.execute(select(WeightCapacity).where(WeightCapacity.id == id))
    capacity = result.scalar_one_or_none()

    if not capacity:
        raise HTTPException(status_code=404, detail="承重容量不存在")

    await db.delete(capacity)
    await db.commit()

    return {"message": "删除成功"}


# ==================== 容量规划管理 ====================

@router.get("/plans", response_model=List[CapacityPlanResponse], summary="获取容量规划列表")
async def get_capacity_plans(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取容量规划列表（分页）
    """
    query = select(CapacityPlan).order_by(CapacityPlan.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    plans = result.scalars().all()

    return [CapacityPlanResponse.model_validate(plan) for plan in plans]


@router.post("/plans", response_model=CapacityPlanResponse, summary="创建容量规划")
async def create_capacity_plan(
    data: CapacityPlanCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    创建容量规划（自动评估可行性）
    """
    plan = CapacityPlan(**data.model_dump())
    db.add(plan)
    await db.flush()  # 获取ID但不提交

    # 评估可行性
    notes = []
    is_feasible = True

    # 检查空间容量（U位）
    if plan.required_u:
        space_result = await db.execute(select(SpaceCapacity))
        space_capacities = space_result.scalars().all()
        total_available_u = sum(
            (sc.total_u_positions or 0) - (sc.used_u_positions or 0)
            for sc in space_capacities
        )
        if total_available_u >= plan.required_u:
            notes.append(f"空间容量检查通过: 可用U位 {total_available_u}U >= 所需 {plan.required_u}U")
        else:
            notes.append(f"空间容量不足: 可用U位 {total_available_u}U < 所需 {plan.required_u}U")
            is_feasible = False

    # 检查电力容量
    if plan.required_power_kw:
        power_result = await db.execute(select(PowerCapacity))
        power_capacities = power_result.scalars().all()
        total_available_power = sum(
            (pc.total_capacity_kw or 0) - (pc.used_capacity_kw or 0)
            for pc in power_capacities
        )
        if total_available_power >= plan.required_power_kw:
            notes.append(f"电力容量检查通过: 可用电力 {total_available_power:.2f}kW >= 所需 {plan.required_power_kw:.2f}kW")
        else:
            notes.append(f"电力容量不足: 可用电力 {total_available_power:.2f}kW < 所需 {plan.required_power_kw:.2f}kW")
            is_feasible = False

    # 检查制冷容量
    if plan.required_cooling_kw:
        cooling_result = await db.execute(select(CoolingCapacity))
        cooling_capacities = cooling_result.scalars().all()
        total_available_cooling = sum(
            (cc.total_cooling_kw or 0) - (cc.used_cooling_kw or 0)
            for cc in cooling_capacities
        )
        if total_available_cooling >= plan.required_cooling_kw:
            notes.append(f"制冷容量检查通过: 可用制冷 {total_available_cooling:.2f}kW >= 所需 {plan.required_cooling_kw:.2f}kW")
        else:
            notes.append(f"制冷容量不足: 可用制冷 {total_available_cooling:.2f}kW < 所需 {plan.required_cooling_kw:.2f}kW")
            is_feasible = False

    # 检查承重容量
    if plan.required_weight_kg:
        weight_result = await db.execute(select(WeightCapacity))
        weight_capacities = weight_result.scalars().all()
        total_available_weight = sum(
            (wc.total_weight_kg or 0) - (wc.used_weight_kg or 0)
            for wc in weight_capacities
        )
        if total_available_weight >= plan.required_weight_kg:
            notes.append(f"承重容量检查通过: 可用承重 {total_available_weight:.2f}kg >= 所需 {plan.required_weight_kg:.2f}kg")
        else:
            notes.append(f"承重容量不足: 可用承重 {total_available_weight:.2f}kg < 所需 {plan.required_weight_kg:.2f}kg")
            is_feasible = False

    if not notes:
        notes.append("无容量需求，规划可行")

    plan.is_feasible = is_feasible
    plan.feasibility_notes = "\n".join(notes)

    await db.commit()
    await db.refresh(plan)

    return CapacityPlanResponse.model_validate(plan)


@router.get("/plans/{id}", response_model=CapacityPlanResponse, summary="获取容量规划详情")
async def get_capacity_plan(
    id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    根据ID获取容量规划详情
    """
    result = await db.execute(select(CapacityPlan).where(CapacityPlan.id == id))
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="容量规划不存在")

    return CapacityPlanResponse.model_validate(plan)


@router.delete("/plans/{id}", summary="删除容量规划")
async def delete_capacity_plan(
    id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    删除容量规划
    """
    result = await db.execute(select(CapacityPlan).where(CapacityPlan.id == id))
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="容量规划不存在")

    await db.delete(plan)
    await db.commit()

    return {"message": "删除成功"}


# ==================== 容量统计 ====================

@router.get("/statistics", response_model=Dict[str, Any], summary="获取容量统计信息")
async def get_capacity_statistics(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取所有类型容量的统计信息
    """
    # 空间容量统计
    space_result = await db.execute(select(SpaceCapacity))
    space_capacities = space_result.scalars().all()
    total_u = sum(sc.total_u_positions or 0 for sc in space_capacities)
    used_u = sum(sc.used_u_positions or 0 for sc in space_capacities)
    space_stats = {
        "total_u_positions": total_u,
        "used_u_positions": used_u,
        "available_u_positions": total_u - used_u,
        "usage_rate": round(used_u / total_u * 100, 2) if total_u > 0 else 0,
        "count": len(space_capacities)
    }

    # 电力容量统计
    power_result = await db.execute(select(PowerCapacity))
    power_capacities = power_result.scalars().all()
    total_power = sum(pc.total_capacity_kw or 0 for pc in power_capacities)
    used_power = sum(pc.used_capacity_kw or 0 for pc in power_capacities)
    power_stats = {
        "total_capacity_kw": total_power,
        "used_capacity_kw": used_power,
        "available_capacity_kw": total_power - used_power,
        "usage_rate": round(used_power / total_power * 100, 2) if total_power > 0 else 0,
        "count": len(power_capacities)
    }

    # 制冷容量统计
    cooling_result = await db.execute(select(CoolingCapacity))
    cooling_capacities = cooling_result.scalars().all()
    total_cooling = sum(cc.total_cooling_kw or 0 for cc in cooling_capacities)
    used_cooling = sum(cc.used_cooling_kw or 0 for cc in cooling_capacities)
    cooling_stats = {
        "total_cooling_kw": total_cooling,
        "used_cooling_kw": used_cooling,
        "available_cooling_kw": total_cooling - used_cooling,
        "usage_rate": round(used_cooling / total_cooling * 100, 2) if total_cooling > 0 else 0,
        "count": len(cooling_capacities)
    }

    # 承重容量统计
    weight_result = await db.execute(select(WeightCapacity))
    weight_capacities = weight_result.scalars().all()
    total_weight = sum(wc.total_weight_kg or 0 for wc in weight_capacities)
    used_weight = sum(wc.used_weight_kg or 0 for wc in weight_capacities)
    weight_stats = {
        "total_weight_kg": total_weight,
        "used_weight_kg": used_weight,
        "available_weight_kg": total_weight - used_weight,
        "usage_rate": round(used_weight / total_weight * 100, 2) if total_weight > 0 else 0,
        "count": len(weight_capacities)
    }

    # 状态统计
    status_counts = {
        "normal": 0,
        "warning": 0,
        "critical": 0,
        "full": 0
    }

    for sc in space_capacities:
        if sc.status:
            status_counts[sc.status.value] = status_counts.get(sc.status.value, 0) + 1
    for pc in power_capacities:
        if pc.status:
            status_counts[pc.status.value] = status_counts.get(pc.status.value, 0) + 1
    for cc in cooling_capacities:
        if cc.status:
            status_counts[cc.status.value] = status_counts.get(cc.status.value, 0) + 1
    for wc in weight_capacities:
        if wc.status:
            status_counts[wc.status.value] = status_counts.get(wc.status.value, 0) + 1

    return {
        "space": space_stats,
        "power": power_stats,
        "cooling": cooling_stats,
        "weight": weight_stats,
        "status_summary": status_counts,
        "total_capacity_records": (
            len(space_capacities) + len(power_capacities) +
            len(cooling_capacities) + len(weight_capacities)
        )
    }
