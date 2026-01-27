"""
负荷调节API V2.3
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...services.load_regulation import LoadRegulationService
from ...schemas.energy import (
    LoadRegulationConfigCreate,
    LoadRegulationConfigUpdate,
    LoadRegulationConfigResponse,
    RegulationSimulateRequest,
    RegulationSimulateResponse,
    RegulationApplyRequest,
    RegulationHistoryResponse,
    RegulationRecommendation
)

router = APIRouter()


@router.get("/configs", response_model=List[LoadRegulationConfigResponse])
async def get_regulation_configs(
    device_id: Optional[int] = Query(None, description="设备ID"),
    regulation_type: Optional[str] = Query(None, description="调节类型"),
    is_enabled: bool = Query(True, description="是否启用"),
    db: AsyncSession = Depends(get_db)
):
    """获取负荷调节配置列表"""
    service = LoadRegulationService(db)
    return await service.get_configs(device_id, regulation_type, is_enabled)


@router.get("/configs/{config_id}", response_model=LoadRegulationConfigResponse)
async def get_regulation_config(
    config_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取单个调节配置"""
    service = LoadRegulationService(db)
    config = await service.get_config_by_id(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    return config


@router.post("/configs", response_model=LoadRegulationConfigResponse)
async def create_regulation_config(
    data: LoadRegulationConfigCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建负荷调节配置"""
    service = LoadRegulationService(db)
    config = await service.create_config(data)
    return await service.get_config_by_id(config.id)


@router.put("/configs/{config_id}", response_model=LoadRegulationConfigResponse)
async def update_regulation_config(
    config_id: int,
    data: LoadRegulationConfigUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新负荷调节配置"""
    service = LoadRegulationService(db)
    config = await service.update_config(config_id, data)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    return await service.get_config_by_id(config_id)


@router.delete("/configs/{config_id}")
async def delete_regulation_config(
    config_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除负荷调节配置"""
    service = LoadRegulationService(db)
    success = await service.delete_config(config_id)
    if not success:
        raise HTTPException(status_code=404, detail="配置不存在")
    return {"message": "删除成功"}


@router.post("/simulate", response_model=RegulationSimulateResponse)
async def simulate_regulation(
    data: RegulationSimulateRequest,
    db: AsyncSession = Depends(get_db)
):
    """模拟调节效果"""
    service = LoadRegulationService(db)
    result = await service.simulate_regulation(data.config_id, data.target_value)
    if not result:
        raise HTTPException(status_code=404, detail="配置不存在")
    return result


@router.post("/apply", response_model=RegulationHistoryResponse)
async def apply_regulation(
    data: RegulationApplyRequest,
    db: AsyncSession = Depends(get_db)
):
    """应用调节方案"""
    service = LoadRegulationService(db)
    result = await service.apply_regulation(
        data.config_id,
        data.target_value,
        data.reason,
        remark=data.remark
    )
    if not result:
        raise HTTPException(status_code=404, detail="配置不存在")
    return result


@router.get("/history", response_model=List[RegulationHistoryResponse])
async def get_regulation_history(
    device_id: Optional[int] = Query(None),
    config_id: Optional[int] = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db)
):
    """获取调节历史"""
    service = LoadRegulationService(db)
    return await service.get_history(device_id, config_id, limit)


@router.get("/recommendations", response_model=List[RegulationRecommendation])
async def get_regulation_recommendations(
    current_demand: Optional[float] = Query(None),
    declared_demand: Optional[float] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """获取调节建议"""
    service = LoadRegulationService(db)
    return await service.get_recommendations(current_demand, declared_demand)
