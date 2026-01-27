"""
电价配置 API - v1
提供完整电价配置的查询、更新和电费计算功能
"""
from typing import Optional, Dict
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_db, require_viewer, require_admin
from ...models.user import User
from ...services.pricing_service import PricingService
from ...schemas.energy import (
    PricingConfigCreate, PricingConfigUpdate, PricingConfigResponse
)

router = APIRouter()


# ========== 请求/响应模型 ==========

class CalculateBillRequest(BaseModel):
    """电费计算请求"""
    energy_by_period: Dict[str, float] = Field(
        ...,
        description="各时段用电量 kWh",
        examples=[{"sharp": 100, "peak": 500, "normal": 800, "valley": 300, "deep_valley": 100}]
    )
    max_demand: float = Field(0.0, description="当月最大需量 kW")
    avg_power_factor: float = Field(0.9, description="平均功率因数", ge=0, le=1)
    include_fixed_fees: bool = Field(True, description="是否包含固定费用")


class EstimateSavingsRequest(BaseModel):
    """节省估算请求"""
    current_energy_by_period: Dict[str, float] = Field(
        ..., description="当前各时段用电量 kWh"
    )
    current_max_demand: float = Field(..., description="当前最大需量 kW")
    optimized_energy_by_period: Dict[str, float] = Field(
        ..., description="优化后各时段用电量 kWh"
    )
    optimized_max_demand: float = Field(..., description="优化后最大需量 kW")
    avg_power_factor: float = Field(0.9, description="平均功率因数", ge=0, le=1)


# ========== 完整电价配置 ==========

@router.get("/full-config", summary="获取完整电价配置")
async def get_full_pricing_config(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取完整的电价配置，包括：
    - 时段电价（尖峰/高峰/平段/低谷/深谷）
    - 全局配置（基本电费、功率因数调整、固定费用）
    - 配置摘要
    """
    service = PricingService(db)
    return await service.get_full_pricing_config()


# ========== 全局配置 CRUD ==========

@router.get("/global-config", summary="获取全局电价配置")
async def get_global_config(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取当前有效的全局电价配置（基本电费、功率因数、固定费用）"""
    service = PricingService(db)
    config = await service.get_current_global_config()
    if not config:
        return {"message": "暂无全局电价配置", "config": None}
    return {"config": PricingConfigResponse.model_validate(config)}


@router.post("/global-config", summary="创建全局电价配置")
async def create_global_config(
    data: PricingConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """创建新的全局电价配置"""
    service = PricingService(db)
    config = await service.update_pricing_config(
        config_id=None,
        config_data=data.model_dump()
    )
    return {
        "message": "创建成功",
        "config": PricingConfigResponse.model_validate(config)
    }


@router.put("/global-config/{config_id}", summary="更新全局电价配置")
async def update_global_config(
    config_id: int,
    data: PricingConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """更新指定的全局电价配置"""
    service = PricingService(db)
    try:
        config = await service.update_pricing_config(
            config_id=config_id,
            config_data=data.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "message": "更新成功",
        "config": PricingConfigResponse.model_validate(config)
    }


# ========== 电费计算 ==========

@router.post("/calculate-bill", summary="计算电费账单")
async def calculate_bill(
    request: CalculateBillRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    计算完整电费账单，包括：
    - 电度电费（按时段电价计算）
    - 基本电费（按需量或容量计算）
    - 功率因数调整
    - 固定费用（输配电费、政府基金、辅助服务费等）
    """
    service = PricingService(db)
    return await service.calculate_electricity_bill(
        energy_by_period=request.energy_by_period,
        max_demand=request.max_demand,
        avg_power_factor=request.avg_power_factor,
        include_fixed_fees=request.include_fixed_fees
    )


@router.post("/estimate-savings", summary="估算优化节省")
async def estimate_savings(
    request: EstimateSavingsRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    比较当前用能模式和优化后用能模式的电费差异，
    估算可节省的金额和比例。
    """
    service = PricingService(db)
    return await service.estimate_savings(
        current_energy_by_period=request.current_energy_by_period,
        current_max_demand=request.current_max_demand,
        optimized_energy_by_period=request.optimized_energy_by_period,
        optimized_max_demand=request.optimized_max_demand,
        avg_power_factor=request.avg_power_factor
    )


# ========== 时段电价查询（兼容旧接口）==========

@router.get("/time-periods", summary="获取时段电价")
async def get_time_period_prices(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取所有时段电价配置"""
    service = PricingService(db)
    return await service.get_current_pricing()


@router.get("/peak-valley-spread", summary="获取峰谷电价差")
async def get_peak_valley_spread(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取峰谷电价差分析"""
    service = PricingService(db)
    return await service.get_peak_valley_spread()
