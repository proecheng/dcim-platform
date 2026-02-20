"""
容量管理 API - v1
"""

import re
import numpy as np
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..deps import get_db, require_viewer, require_operator
from ...models.user import User
from ...models.asset import Cabinet, Asset
from ...models.capacity import (
    SpaceCapacity,
    PowerCapacity,
    CoolingCapacity,
    WeightCapacity,
    CapacityPlan,
    CapacityStatus,
    CapacityHistory,
)
from ...schemas.capacity import (
    SpaceCapacityCreate,
    SpaceCapacityUpdate,
    SpaceCapacityResponse,
    PowerCapacityCreate,
    PowerCapacityUpdate,
    PowerCapacityResponse,
    CoolingCapacityCreate,
    CoolingCapacityUpdate,
    CoolingCapacityResponse,
    WeightCapacityCreate,
    WeightCapacityUpdate,
    WeightCapacityResponse,
    CapacityPlanCreate,
    CapacityPlanResponse,
    RackingRecommendationRequest,
    CabinetScore,
    RackingRecommendationResponse,
    CapacityTrendResponse,
    CapacityForecastResponse,
    ExpansionSuggestion,
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


def _calculate_status(used: float, total: float, warning: float, critical: float) -> CapacityStatus:
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
    _: User = Depends(require_viewer),
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
        capacity_data.usage_rate = _calculate_usage_rate(capacity.used_u_positions, capacity.total_u_positions)
        response_list.append(capacity_data)

    return response_list


@router.post("/space", response_model=SpaceCapacityResponse, summary="创建空间容量")
async def create_space_capacity(
    data: SpaceCapacityCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
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
    capacity_data.usage_rate = _calculate_usage_rate(capacity.used_u_positions, capacity.total_u_positions)
    return capacity_data


@router.get("/space/{id}", response_model=SpaceCapacityResponse, summary="获取空间容量详情")
async def get_space_capacity(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)):
    """
    根据ID获取空间容量详情
    """
    result = await db.execute(select(SpaceCapacity).where(SpaceCapacity.id == id))
    capacity = result.scalar_one_or_none()

    if not capacity:
        raise HTTPException(status_code=404, detail="空间容量不存在")

    capacity_data = SpaceCapacityResponse.model_validate(capacity)
    capacity_data.usage_rate = _calculate_usage_rate(capacity.used_u_positions, capacity.total_u_positions)
    return capacity_data


@router.put("/space/{id}", response_model=SpaceCapacityResponse, summary="更新空间容量")
async def update_space_capacity(
    id: int, data: SpaceCapacityUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
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
    capacity_data.usage_rate = _calculate_usage_rate(capacity.used_u_positions, capacity.total_u_positions)
    return capacity_data


@router.delete("/space/{id}", summary="删除空间容量")
async def delete_space_capacity(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)):
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
    _: User = Depends(require_viewer),
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
        capacity_data.usage_rate = _calculate_usage_rate(capacity.used_capacity_kw, capacity.total_capacity_kw)
        response_list.append(capacity_data)

    return response_list


@router.post("/power", response_model=PowerCapacityResponse, summary="创建电力容量")
async def create_power_capacity(
    data: PowerCapacityCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
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
    capacity_data.usage_rate = _calculate_usage_rate(capacity.used_capacity_kw, capacity.total_capacity_kw)
    return capacity_data


@router.get("/power/{id}", response_model=PowerCapacityResponse, summary="获取电力容量详情")
async def get_power_capacity(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)):
    """
    根据ID获取电力容量详情
    """
    result = await db.execute(select(PowerCapacity).where(PowerCapacity.id == id))
    capacity = result.scalar_one_or_none()

    if not capacity:
        raise HTTPException(status_code=404, detail="电力容量不存在")

    capacity_data = PowerCapacityResponse.model_validate(capacity)
    capacity_data.usage_rate = _calculate_usage_rate(capacity.used_capacity_kw, capacity.total_capacity_kw)
    return capacity_data


@router.put("/power/{id}", response_model=PowerCapacityResponse, summary="更新电力容量")
async def update_power_capacity(
    id: int, data: PowerCapacityUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
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
    capacity_data.usage_rate = _calculate_usage_rate(capacity.used_capacity_kw, capacity.total_capacity_kw)
    return capacity_data


@router.delete("/power/{id}", summary="删除电力容量")
async def delete_power_capacity(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)):
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
    _: User = Depends(require_viewer),
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
        capacity_data.usage_rate = _calculate_usage_rate(capacity.used_cooling_kw, capacity.total_cooling_kw)
        response_list.append(capacity_data)

    return response_list


@router.post("/cooling", response_model=CoolingCapacityResponse, summary="创建制冷容量")
async def create_cooling_capacity(
    data: CoolingCapacityCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
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
    capacity_data.usage_rate = _calculate_usage_rate(capacity.used_cooling_kw, capacity.total_cooling_kw)
    return capacity_data


@router.get("/cooling/{id}", response_model=CoolingCapacityResponse, summary="获取制冷容量详情")
async def get_cooling_capacity(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)):
    """
    根据ID获取制冷容量详情
    """
    result = await db.execute(select(CoolingCapacity).where(CoolingCapacity.id == id))
    capacity = result.scalar_one_or_none()

    if not capacity:
        raise HTTPException(status_code=404, detail="制冷容量不存在")

    capacity_data = CoolingCapacityResponse.model_validate(capacity)
    capacity_data.usage_rate = _calculate_usage_rate(capacity.used_cooling_kw, capacity.total_cooling_kw)
    return capacity_data


@router.put("/cooling/{id}", response_model=CoolingCapacityResponse, summary="更新制冷容量")
async def update_cooling_capacity(
    id: int, data: CoolingCapacityUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
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
    capacity_data.usage_rate = _calculate_usage_rate(capacity.used_cooling_kw, capacity.total_cooling_kw)
    return capacity_data


@router.delete("/cooling/{id}", summary="删除制冷容量")
async def delete_cooling_capacity(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)):
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
    _: User = Depends(require_viewer),
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
        capacity_data.usage_rate = _calculate_usage_rate(capacity.used_weight_kg, capacity.total_weight_kg)
        response_list.append(capacity_data)

    return response_list


@router.post("/weight", response_model=WeightCapacityResponse, summary="创建承重容量")
async def create_weight_capacity(
    data: WeightCapacityCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
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
    capacity_data.usage_rate = _calculate_usage_rate(capacity.used_weight_kg, capacity.total_weight_kg)
    return capacity_data


@router.get("/weight/{id}", response_model=WeightCapacityResponse, summary="获取承重容量详情")
async def get_weight_capacity(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)):
    """
    根据ID获取承重容量详情
    """
    result = await db.execute(select(WeightCapacity).where(WeightCapacity.id == id))
    capacity = result.scalar_one_or_none()

    if not capacity:
        raise HTTPException(status_code=404, detail="承重容量不存在")

    capacity_data = WeightCapacityResponse.model_validate(capacity)
    capacity_data.usage_rate = _calculate_usage_rate(capacity.used_weight_kg, capacity.total_weight_kg)
    return capacity_data


@router.put("/weight/{id}", response_model=WeightCapacityResponse, summary="更新承重容量")
async def update_weight_capacity(
    id: int, data: WeightCapacityUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
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
    capacity_data.usage_rate = _calculate_usage_rate(capacity.used_weight_kg, capacity.total_weight_kg)
    return capacity_data


@router.delete("/weight/{id}", summary="删除承重容量")
async def delete_weight_capacity(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)):
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


@router.post("/recommend", response_model=RackingRecommendationResponse, summary="智能上架推荐")
async def get_racking_recommendation(
    data: RackingRecommendationRequest, db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)
):
    """
    基于设备需求推荐最优上架位置（FR60简化版）
    """
    # 1. 单次聚合查询所有机柜的 used_u（避免 N+1）
    used_u_query = (
        select(Asset.cabinet_id, func.coalesce(func.sum(Asset.u_height), 0).label("used_u"))
        .where(Asset.u_height.isnot(None))
        .group_by(Asset.cabinet_id)
    )
    used_u_result = await db.execute(used_u_query)
    used_u_map = {row.cabinet_id: int(row.used_u) for row in used_u_result}

    # 2. 查询所有 Cabinet
    cabinet_result = await db.execute(select(Cabinet))
    cabinets = cabinet_result.scalars().all()
    total_evaluated = len(cabinets)

    # 3. 查询所有 CoolingCapacity（用于制冷评分）
    cooling_result = await db.execute(select(CoolingCapacity))
    cooling_capacities = cooling_result.scalars().all()

    # 4. 评分函数
    def calc_scores(cabinet, available_u, strict=True):
        # 空间评分
        space_score = min(100, (available_u / data.required_u) * 50)

        # 电力评分
        if data.required_power_kw is None:
            power_score = 100.0
        elif cabinet.max_power is None:
            power_score = 50.0
        else:
            if strict and cabinet.max_power < data.required_power_kw:
                return None  # 严格模式下排除
            power_score = (
                min(100, (cabinet.max_power / data.required_power_kw) * 50) if data.required_power_kw > 0 else 100.0
            )

        # 制冷评分
        best_match = None
        available_cooling = 0.0
        if data.required_cooling_kw is None or data.required_cooling_kw == 0:
            cooling_score = 100.0
        else:
            cab_loc = cabinet.location or ""
            best_len = -1
            for cc in cooling_capacities:
                cc_loc = cc.location or ""
                if cc_loc and (cab_loc == cc_loc or cab_loc.startswith(cc_loc + "/")) and len(cc_loc) > best_len:
                    best_match = cc
                    best_len = len(cc_loc)
            if best_match is None:
                cooling_score = 50.0
            else:
                available_cooling = (best_match.total_cooling_kw or 0) - (best_match.used_cooling_kw or 0)
                cooling_score = min(100, (available_cooling / data.required_cooling_kw) * 50)

        # 承重评分
        if data.required_weight_kg is None:
            weight_score = 100.0
        elif cabinet.max_weight is None:
            weight_score = 50.0
        else:
            if strict and cabinet.max_weight < data.required_weight_kg:
                return None  # 严格模式下排除
            weight_score = (
                min(100, (cabinet.max_weight / data.required_weight_kg) * 50) if data.required_weight_kg > 0 else 100.0
            )

        # 综合评分
        total_score = space_score * 0.4 + power_score * 0.2 + cooling_score * 0.2 + weight_score * 0.2

        # 生成 notes
        notes_parts = []
        # 空间
        if available_u >= data.required_u * 2:
            notes_parts.append(f"空间充裕(可用{available_u}U)")
        elif available_u >= data.required_u:
            notes_parts.append(f"空间满足(可用{available_u}U)")
        else:
            notes_parts.append(f"空间不足(可用{available_u}U)")
        # 电力
        if data.required_power_kw is not None:
            if cabinet.max_power is None:
                notes_parts.append("电力未配置")
            elif cabinet.max_power >= data.required_power_kw * 2:
                notes_parts.append(f"电力充裕({cabinet.max_power}kW)")
            elif cabinet.max_power >= data.required_power_kw:
                notes_parts.append(f"电力满足({cabinet.max_power}kW)")
            else:
                notes_parts.append(f"电力不足({cabinet.max_power}kW)")
        # 制冷
        if data.required_cooling_kw is not None and data.required_cooling_kw > 0:
            if best_match is None:
                notes_parts.append("制冷数据未知")
            elif available_cooling >= data.required_cooling_kw * 2:
                notes_parts.append("制冷充裕")
            elif available_cooling >= data.required_cooling_kw:
                notes_parts.append("制冷满足")
            else:
                notes_parts.append("制冷不足")
        # 承重
        if data.required_weight_kg is not None:
            if cabinet.max_weight is None:
                notes_parts.append("承重未配置")
            elif cabinet.max_weight >= data.required_weight_kg * 2:
                notes_parts.append(f"承重充裕({cabinet.max_weight}kg)")
            elif cabinet.max_weight >= data.required_weight_kg:
                notes_parts.append(f"承重满足({cabinet.max_weight}kg)")
            else:
                notes_parts.append(f"承重不足({cabinet.max_weight}kg)")

        return CabinetScore(
            cabinet_id=cabinet.id,
            cabinet_code=cabinet.cabinet_code,
            cabinet_name=cabinet.cabinet_name,
            location=cabinet.location,
            space_score=round(space_score, 1),
            power_score=round(power_score, 1),
            cooling_score=round(cooling_score, 1),
            weight_score=round(weight_score, 1),
            total_score=round(total_score, 1),
            available_u=available_u,
            max_power=cabinet.max_power,
            max_weight=cabinet.max_weight,
            notes="，".join(notes_parts),
        )

    # 5. 第一轮：严格筛选
    candidates = []
    for cab in cabinets:
        used_u = used_u_map.get(cab.id, 0)
        available_u = (cab.total_u or 42) - used_u
        if available_u < data.required_u:
            continue  # 空间硬性条件
        score = calc_scores(cab, available_u, strict=True)
        if score is not None:
            candidates.append(score)

    # 6. 如果候选不足3个，放宽筛选（仅保留空间硬性条件）
    if len(candidates) < 3:
        candidates = []
        for cab in cabinets:
            used_u = used_u_map.get(cab.id, 0)
            available_u = (cab.total_u or 42) - used_u
            if available_u < data.required_u:
                continue
            score = calc_scores(cab, available_u, strict=False)
            if score is not None:
                candidates.append(score)

    # 7. 按综合评分降序排列
    candidates.sort(key=lambda x: x.total_score, reverse=True)
    qualified_count = len(candidates)

    return RackingRecommendationResponse(
        request=data,
        candidates=candidates[: data.limit],
        total_cabinets_evaluated=total_evaluated,
        qualified_count=qualified_count,
    )


@router.get("/plans", response_model=List[CapacityPlanResponse], summary="获取容量规划列表")
async def get_capacity_plans(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
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
    data: CapacityPlanCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
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
        total_available_u = sum((sc.total_u_positions or 0) - (sc.used_u_positions or 0) for sc in space_capacities)
        if total_available_u >= plan.required_u:
            notes.append(f"空间容量检查通过: 可用U位 {total_available_u}U >= 所需 {plan.required_u}U")
        else:
            notes.append(f"空间容量不足: 可用U位 {total_available_u}U < 所需 {plan.required_u}U")
            is_feasible = False

    # 检查电力容量
    if plan.required_power_kw:
        power_result = await db.execute(select(PowerCapacity))
        power_capacities = power_result.scalars().all()
        total_available_power = sum((pc.total_capacity_kw or 0) - (pc.used_capacity_kw or 0) for pc in power_capacities)
        if total_available_power >= plan.required_power_kw:
            notes.append(
                f"电力容量检查通过: 可用电力 {total_available_power:.2f}kW >= 所需 {plan.required_power_kw:.2f}kW"
            )
        else:
            notes.append(f"电力容量不足: 可用电力 {total_available_power:.2f}kW < 所需 {plan.required_power_kw:.2f}kW")
            is_feasible = False

    # 检查制冷容量
    if plan.required_cooling_kw:
        cooling_result = await db.execute(select(CoolingCapacity))
        cooling_capacities = cooling_result.scalars().all()
        total_available_cooling = sum(
            (cc.total_cooling_kw or 0) - (cc.used_cooling_kw or 0) for cc in cooling_capacities
        )
        if total_available_cooling >= plan.required_cooling_kw:
            notes.append(
                f"制冷容量检查通过: 可用制冷 {total_available_cooling:.2f}kW >= 所需 {plan.required_cooling_kw:.2f}kW"
            )
        else:
            notes.append(
                f"制冷容量不足: 可用制冷 {total_available_cooling:.2f}kW < 所需 {plan.required_cooling_kw:.2f}kW"
            )
            is_feasible = False

    # 检查承重容量
    if plan.required_weight_kg:
        weight_result = await db.execute(select(WeightCapacity))
        weight_capacities = weight_result.scalars().all()
        total_available_weight = sum((wc.total_weight_kg or 0) - (wc.used_weight_kg or 0) for wc in weight_capacities)
        if total_available_weight >= plan.required_weight_kg:
            notes.append(
                f"承重容量检查通过: 可用承重 {total_available_weight:.2f}kg >= 所需 {plan.required_weight_kg:.2f}kg"
            )
        else:
            notes.append(
                f"承重容量不足: 可用承重 {total_available_weight:.2f}kg < 所需 {plan.required_weight_kg:.2f}kg"
            )
            is_feasible = False

    if not notes:
        notes.append("无容量需求，规划可行")

    plan.is_feasible = is_feasible
    plan.feasibility_notes = "\n".join(notes)

    await db.commit()
    await db.refresh(plan)

    return CapacityPlanResponse.model_validate(plan)


@router.get("/plans/{id}", response_model=CapacityPlanResponse, summary="获取容量规划详情")
async def get_capacity_plan(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)):
    """
    根据ID获取容量规划详情
    """
    result = await db.execute(select(CapacityPlan).where(CapacityPlan.id == id))
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="容量规划不存在")

    return CapacityPlanResponse.model_validate(plan)


@router.put("/plans/{id}/override-cabinet", response_model=CapacityPlanResponse, summary="覆盖推荐机柜")
async def override_plan_cabinet(
    id: int,
    cabinet_id: int = Body(..., embed=True, alias="target_cabinet_id"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """
    人工覆盖推荐机柜（基于目标机柜重新评估可行性）
    """
    # 查找 plan
    result = await db.execute(select(CapacityPlan).where(CapacityPlan.id == id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="容量规划不存在")

    # 查找 cabinet
    cab_result = await db.execute(select(Cabinet).where(Cabinet.id == cabinet_id))
    cabinet = cab_result.scalar_one_or_none()
    if not cabinet:
        raise HTTPException(status_code=404, detail="机柜不存在")

    # 计算该机柜的 used_u
    used_u_result = await db.execute(
        select(func.coalesce(func.sum(Asset.u_height), 0)).where(
            Asset.cabinet_id == cabinet_id, Asset.u_height.isnot(None)
        )
    )
    used_u = int(used_u_result.scalar() or 0)
    available_u = (cabinet.total_u or 42) - used_u

    # 基于目标机柜重新评估可行性
    notes = [f"已覆盖为机柜 {cabinet.cabinet_name}({cabinet.cabinet_code})"]
    is_feasible = True

    if plan.required_u and available_u < plan.required_u:
        notes.append(f"空间不足: 可用{available_u}U < 所需{plan.required_u}U")
        is_feasible = False
    elif plan.required_u:
        notes.append(f"空间满足: 可用{available_u}U >= 所需{plan.required_u}U")

    if plan.required_power_kw is not None:
        if cabinet.max_power is None:
            notes.append("电力: 机柜未配置最大功率")
        elif cabinet.max_power < plan.required_power_kw:
            notes.append(f"电力不足: 最大{cabinet.max_power}kW < 所需{plan.required_power_kw}kW")
            is_feasible = False
        else:
            notes.append(f"电力满足: 最大{cabinet.max_power}kW >= 所需{plan.required_power_kw}kW")

    if plan.required_weight_kg is not None:
        if cabinet.max_weight is None:
            notes.append("承重: 机柜未配置最大承重")
        elif cabinet.max_weight < plan.required_weight_kg:
            notes.append(f"承重不足: 最大{cabinet.max_weight}kg < 所需{plan.required_weight_kg}kg")
            is_feasible = False
        else:
            notes.append(f"承重满足: 最大{cabinet.max_weight}kg >= 所需{plan.required_weight_kg}kg")

    # 制冷评估（简化版：标注需人工确认）
    if plan.required_cooling_kw is not None and plan.required_cooling_kw > 0:
        notes.append("制冷: 需人工确认覆盖机柜的制冷容量")

    plan.target_cabinet_id = cabinet_id
    plan.is_feasible = is_feasible
    plan.feasibility_notes = "\n".join(notes)

    await db.commit()
    await db.refresh(plan)

    return CapacityPlanResponse.model_validate(plan)


@router.delete("/plans/{id}", summary="删除容量规划")
async def delete_capacity_plan(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)):
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


# ==================== 容量趋势预测 ====================

_VALID_CAP_TYPES = ("space", "power", "cooling", "weight")


def _auto_interval(start: datetime, end: datetime) -> str:
    """根据时间跨度自动选择聚合粒度"""
    span = (end - start).days
    if span <= 2:
        return "hour"
    elif span <= 30:
        return "day"
    elif span <= 180:
        return "week"
    return "month"


def _bucket_key(dt: datetime, interval: str) -> str:
    """根据聚合粒度生成时间桶 key"""
    if interval == "hour":
        return dt.strftime("%Y-%m-%d %H:00")
    elif interval == "day":
        return dt.strftime("%Y-%m-%d")
    elif interval == "week":
        iso = dt.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    else:  # month
        return dt.strftime("%Y-%m")


@router.get("/trend", response_model=CapacityTrendResponse, summary="获取容量趋势数据")
async def get_capacity_trend(
    cap_type: Optional[str] = Query("space", alias="type", description="容量类型: space/power/cooling/weight"),
    start_time: Optional[str] = Query(None, description="开始时间 ISO格式"),
    end_time: Optional[str] = Query(None, description="结束时间 ISO格式"),
    interval: Optional[str] = Query(None, description="聚合粒度: hour/day/week/month"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取容量趋势数据"""
    if cap_type not in _VALID_CAP_TYPES:
        raise HTTPException(status_code=400, detail=f"无效的容量类型: {cap_type}")

    now = datetime.now()
    try:
        end_dt = datetime.fromisoformat(end_time) if end_time else now
        start_dt = datetime.fromisoformat(start_time) if start_time else end_dt - timedelta(days=30)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="无效的时间格式，请使用 ISO 8601 格式")

    if start_dt > end_dt:
        raise HTTPException(status_code=400, detail="start_time 不能晚于 end_time")

    if interval is None:
        interval = _auto_interval(start_dt, end_dt)

    query = (
        select(CapacityHistory)
        .where(
            CapacityHistory.capacity_type == cap_type,
            CapacityHistory.reference_id == 0,
            CapacityHistory.recorded_at >= start_dt,
            CapacityHistory.recorded_at <= end_dt,
        )
        .order_by(CapacityHistory.recorded_at)
    )
    rows = (await db.execute(query)).scalars().all()

    if not rows:
        return CapacityTrendResponse()

    # 按时间桶聚合
    buckets: Dict[str, Dict[str, list]] = defaultdict(lambda: {"total": [], "used": [], "rate": []})
    for r in rows:
        key = _bucket_key(r.recorded_at, interval)
        buckets[key]["total"].append(r.total_value or 0)
        buckets[key]["used"].append(r.used_value or 0)
        buckets[key]["rate"].append(r.usage_rate or 0)

    timestamps = []
    total_list = []
    used_list = []
    rate_list = []
    for ts in sorted(buckets.keys()):
        b = buckets[ts]
        timestamps.append(ts)
        total_list.append(round(sum(b["total"]) / len(b["total"]), 2))
        used_list.append(round(sum(b["used"]) / len(b["used"]), 2))
        rate_list.append(round(sum(b["rate"]) / len(b["rate"]), 2))

    return CapacityTrendResponse(
        timestamps=timestamps,
        total=total_list,
        used=used_list,
        usage_rate=rate_list,
    )


@router.get("/forecast", response_model=CapacityForecastResponse, summary="获取容量预测数据")
async def get_capacity_forecast(
    cap_type: Optional[str] = Query("space", alias="type", description="容量类型"),
    days: int = Query(90, ge=30, le=365, description="预测天数(30-365)"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取容量预测数据"""
    if cap_type not in _VALID_CAP_TYPES:
        raise HTTPException(status_code=400, detail=f"无效的容量类型: {cap_type}")

    now = datetime.now()
    history_start = now - timedelta(days=180)

    query = (
        select(CapacityHistory)
        .where(
            CapacityHistory.capacity_type == cap_type,
            CapacityHistory.reference_id == 0,
            CapacityHistory.recorded_at >= history_start,
        )
        .order_by(CapacityHistory.recorded_at)
    )
    rows = (await db.execute(query)).scalars().all()

    # 按日聚合
    daily: Dict[str, list] = defaultdict(list)
    for r in rows:
        day_key = r.recorded_at.strftime("%Y-%m-%d")
        daily[day_key].append(r.usage_rate or 0)

    day_keys = sorted(daily.keys())
    day_rates = [sum(daily[k]) / len(daily[k]) for k in day_keys]

    if len(day_rates) >= 30:
        # 真实预测 — 线性回归
        x = np.arange(len(day_rates), dtype=float)
        y = np.array(day_rates, dtype=float)
        slope, intercept = np.polyfit(x, y, 1)
        residual_std = float(np.std(y - (slope * x + intercept)))

        timestamps = []
        predicted_usage = []
        confidence_upper = []
        confidence_lower = []
        suggestions = []

        base_idx = len(day_rates)
        current_rate = day_rates[-1]
        first_exceed_idx = None

        for i in range(days):
            future_day = now + timedelta(days=i + 1)
            ts = future_day.strftime("%Y-%m-%d")
            pred = float(slope * (base_idx + i) + intercept)
            pred_clamped = min(100.0, max(0.0, round(pred, 2)))
            upper = min(100.0, round(pred_clamped + 1.96 * residual_std, 2))
            lower = max(0.0, round(pred_clamped - 1.96 * residual_std, 2))

            timestamps.append(ts)
            predicted_usage.append(pred_clamped)
            confidence_upper.append(upper)
            confidence_lower.append(lower)

            if pred_clamped > 80 and first_exceed_idx is None:
                first_exceed_idx = i

        # 扩容建议
        if current_rate > 80:
            suggestions.append(
                ExpansionSuggestion(
                    capacity_type=cap_type,
                    current_usage_rate=round(current_rate, 2),
                    predicted_exceed_date="当前",
                    predicted_usage_rate=round(current_rate, 2),
                    resource_gap=f"当前使用率已达 {round(current_rate, 2)}%",
                    suggestion=f"{cap_type} 容量当前已超过80%阈值，建议立即扩容",
                )
            )
        elif first_exceed_idx is not None:
            exceed_date = (now + timedelta(days=first_exceed_idx + 1)).strftime("%Y-%m-%d")
            exceed_rate = predicted_usage[first_exceed_idx]
            suggestions.append(
                ExpansionSuggestion(
                    capacity_type=cap_type,
                    current_usage_rate=round(current_rate, 2),
                    predicted_exceed_date=exceed_date,
                    predicted_usage_rate=exceed_rate,
                    resource_gap=f"预计 {exceed_date} 使用率将达 {exceed_rate}%",
                    suggestion=f"{cap_type} 容量预计在 {exceed_date} 超过80%阈值，建议提前规划扩容",
                )
            )

        return CapacityForecastResponse(
            timestamps=timestamps,
            predicted_usage=predicted_usage,
            confidence_upper=confidence_upper,
            confidence_lower=confidence_lower,
            is_demo=False,
            expansion_suggestions=suggestions,
        )
    else:
        # Demo 数据 — 数据不足
        defaults = {
            "space": (1000.0, 400.0),
            "power": (500.0, 200.0),
            "cooling": (300.0, 120.0),
            "weight": (5000.0, 2000.0),
        }
        # 尝试从容量表获取当前值
        table_map = {
            "space": (SpaceCapacity, "total_u_positions", "used_u_positions"),
            "power": (PowerCapacity, "total_capacity_kw", "used_capacity_kw"),
            "cooling": (CoolingCapacity, "total_cooling_kw", "used_cooling_kw"),
            "weight": (WeightCapacity, "total_weight_kg", "used_weight_kg"),
        }
        model, total_field, used_field = table_map[cap_type]
        cap_rows = (await db.execute(select(model))).scalars().all()
        if cap_rows:
            total_val = sum(getattr(r, total_field) or 0 for r in cap_rows)
            used_val = sum(getattr(r, used_field) or 0 for r in cap_rows)
            if total_val > 0:
                base_rate = used_val / total_val * 100
            else:
                t, u = defaults[cap_type]
                base_rate = u / t * 100
        else:
            t, u = defaults[cap_type]
            base_rate = u / t * 100

        timestamps = []
        predicted_usage = []
        confidence_upper = []
        confidence_lower = []
        suggestions = []

        monthly_growth = 2.0  # 每月增长2%
        daily_growth = monthly_growth / 30.0

        for i in range(days):
            future_day = now + timedelta(days=i + 1)
            ts = future_day.strftime("%Y-%m-%d")
            pred = min(100.0, max(0.0, round(base_rate + daily_growth * i, 2)))
            upper = min(100.0, round(pred + 5.0, 2))
            lower = max(0.0, round(pred - 5.0, 2))

            timestamps.append(ts)
            predicted_usage.append(pred)
            confidence_upper.append(upper)
            confidence_lower.append(lower)

        # 扩容建议（demo模式下也检查）
        first_exceed_idx = None
        for i, pred_val in enumerate(predicted_usage):
            if pred_val > 80:
                first_exceed_idx = i
                break

        if base_rate > 80:
            suggestions.append(
                ExpansionSuggestion(
                    capacity_type=cap_type,
                    current_usage_rate=round(base_rate, 2),
                    predicted_exceed_date="当前",
                    predicted_usage_rate=round(base_rate, 2),
                    resource_gap=f"当前使用率已达 {round(base_rate, 2)}%",
                    suggestion=f"{cap_type} 容量当前已超过80%阈值，建议立即扩容",
                )
            )
        elif first_exceed_idx is not None:
            exceed_date = (now + timedelta(days=first_exceed_idx + 1)).strftime("%Y-%m-%d")
            exceed_rate = predicted_usage[first_exceed_idx]
            suggestions.append(
                ExpansionSuggestion(
                    capacity_type=cap_type,
                    current_usage_rate=round(base_rate, 2),
                    predicted_exceed_date=exceed_date,
                    predicted_usage_rate=exceed_rate,
                    resource_gap=f"预计 {exceed_date} 使用率将达 {exceed_rate}%",
                    suggestion=f"{cap_type} 容量预计在 {exceed_date} 超过80%阈值，建议提前规划扩容",
                )
            )

        return CapacityForecastResponse(
            timestamps=timestamps,
            predicted_usage=predicted_usage,
            confidence_upper=confidence_upper,
            confidence_lower=confidence_lower,
            is_demo=True,
            expansion_suggestions=suggestions,
        )


# ==================== 容量统计 ====================


@router.get("/statistics", response_model=Dict[str, Any], summary="获取容量统计信息")
async def get_capacity_statistics(db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)):
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
        "count": len(space_capacities),
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
        "count": len(power_capacities),
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
        "count": len(cooling_capacities),
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
        "count": len(weight_capacities),
    }

    # 状态统计
    status_counts = {"normal": 0, "warning": 0, "critical": 0, "full": 0}

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
            len(space_capacities) + len(power_capacities) + len(cooling_capacities) + len(weight_capacities)
        ),
    }


def _parse_location_key(location: Optional[str], dimension: str) -> str:
    """根据维度解析 location 分组键"""
    if not location or not location.strip():
        return "未分类"
    parts = re.split(r"[/\-\s]+", location.strip())
    parts = [p for p in parts if p]
    if not parts:
        return "未分类"
    if dimension == "area":
        return parts[0]
    elif dimension == "floor":
        return "-".join(parts[:2]) if len(parts) >= 2 else parts[0]
    else:  # room — 完整 location
        return location.strip()


@router.get("/statistics/by-location", summary="按区域维度聚合容量统计")
async def get_capacity_statistics_by_location(
    dimension: str = Query("area", description="聚合维度: area/floor/room"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """按区域维度聚合四维容量统计"""
    # 查询四维容量表
    space_rows = (await db.execute(select(SpaceCapacity))).scalars().all()
    power_rows = (await db.execute(select(PowerCapacity))).scalars().all()
    cooling_rows = (await db.execute(select(CoolingCapacity))).scalars().all()
    weight_rows = (await db.execute(select(WeightCapacity))).scalars().all()

    groups: Dict[str, Dict[str, Any]] = {}

    def _ensure(loc_key: str):
        if loc_key not in groups:
            groups[loc_key] = {
                "location": loc_key,
                "space": {"total_u_positions": 0, "used_u_positions": 0},
                "power": {"total_capacity_kw": 0.0, "used_capacity_kw": 0.0},
                "cooling": {"total_cooling_kw": 0.0, "used_cooling_kw": 0.0},
                "weight": {"total_weight_kg": 0.0, "used_weight_kg": 0.0},
            }

    for r in space_rows:
        key = _parse_location_key(r.location, dimension)
        _ensure(key)
        groups[key]["space"]["total_u_positions"] += r.total_u_positions or 0
        groups[key]["space"]["used_u_positions"] += r.used_u_positions or 0

    for r in power_rows:
        key = _parse_location_key(r.location, dimension)
        _ensure(key)
        groups[key]["power"]["total_capacity_kw"] += r.total_capacity_kw or 0
        groups[key]["power"]["used_capacity_kw"] += r.used_capacity_kw or 0

    for r in cooling_rows:
        key = _parse_location_key(r.location, dimension)
        _ensure(key)
        groups[key]["cooling"]["total_cooling_kw"] += r.total_cooling_kw or 0
        groups[key]["cooling"]["used_cooling_kw"] += r.used_cooling_kw or 0

    for r in weight_rows:
        key = _parse_location_key(r.location, dimension)
        _ensure(key)
        groups[key]["weight"]["total_weight_kg"] += r.total_weight_kg or 0
        groups[key]["weight"]["used_weight_kg"] += r.used_weight_kg or 0

    # 计算 usage_rate
    for g in groups.values():
        for dim_key, used_field, total_field in [
            ("space", "used_u_positions", "total_u_positions"),
            ("power", "used_capacity_kw", "total_capacity_kw"),
            ("cooling", "used_cooling_kw", "total_cooling_kw"),
            ("weight", "used_weight_kg", "total_weight_kg"),
        ]:
            g[dim_key]["usage_rate"] = _calculate_usage_rate(g[dim_key][used_field], g[dim_key][total_field]) or 0.0

    return {"items": list(groups.values())}


@router.get("/alerts", summary="获取容量预警列表")
async def get_capacity_alerts(
    cap_type: Optional[str] = Query(None, alias="type", description="容量类型: space/power/cooling/weight"),
    status: Optional[str] = Query(None, description="状态: warning/critical/full"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取容量预警列表（status 为 warning/critical/full 的记录）"""
    alert_statuses = [CapacityStatus.warning, CapacityStatus.critical, CapacityStatus.full]
    if status:
        alert_statuses = [CapacityStatus(status)]

    table_map: Dict[str, Any] = {
        "space": SpaceCapacity,
        "power": PowerCapacity,
        "cooling": CoolingCapacity,
        "weight": WeightCapacity,
    }

    if cap_type:
        if cap_type not in table_map:
            raise HTTPException(status_code=400, detail=f"无效的容量类型: {cap_type}")
        tables_to_query = {cap_type: table_map[cap_type]}
    else:
        tables_to_query = table_map

    def _get_used_total(cap_type: str, record):
        if cap_type == "space":
            return record.used_u_positions, record.total_u_positions
        elif cap_type == "power":
            return record.used_capacity_kw, record.total_capacity_kw
        elif cap_type == "cooling":
            return record.used_cooling_kw, record.total_cooling_kw
        else:
            return record.used_weight_kg, record.total_weight_kg

    alerts = []
    for cap_type, model in tables_to_query.items():
        query = select(model).where(model.status.in_(alert_statuses))
        rows = (await db.execute(query)).scalars().all()
        for record in rows:
            used, total = _get_used_total(cap_type, record)
            alerts.append(
                {
                    "type": cap_type,
                    "name": record.name,
                    "location": record.location or "",
                    "status": record.status.value if record.status else "warning",
                    "usage_rate": _calculate_usage_rate(used, total) or 0.0,
                    "threshold": record.warning_threshold,
                    "created_at": record.created_at.isoformat() if record.created_at else None,
                }
            )

    return alerts
