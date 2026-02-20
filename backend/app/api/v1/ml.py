"""
深度学习节能优化API端点

提供REST API访问深度学习模块的功能
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime

from ..services.ml_service import get_ml_service

router = APIRouter(prefix="/ml", tags=["深度学习节能优化"])


# ========== 请求/响应模型 ==========


class LoadAnalysisRequest(BaseModel):
    """负荷分析请求"""

    power_data: List[List[float]] = Field(..., description="功率时序数据")
    period_types: List[List[int]] = Field(..., description="时段类型 (0-4)")
    is_weekday: List[List[int]] = Field(..., description="工作日标志 (0/1)")
    temperature: List[List[float]] = Field(..., description="温度数据")


class PeakValleySavingRequest(BaseModel):
    """峰谷收益计算请求"""

    predictions: List[Dict[str, Any]] = Field(..., description="负荷分析结果")
    price_diff: float = Field(..., description="峰谷电价差 (元/kWh)")
    shift_hours: float = Field(2.0, description="每日转移时长")
    working_days: int = Field(250, description="年工作日数")


class MeasureConflictRequest(BaseModel):
    """措施冲突分析请求"""

    measures: List[Dict[str, Any]] = Field(..., description="候选措施列表")


class RLUpdateRequest(BaseModel):
    """RL更新请求"""

    actual_saving: float = Field(..., description="实际节能收益")
    expected_saving: float = Field(..., description="预期节能收益")
    comfort_violation: float = Field(0.0, description="舒适度违反程度")
    safety_violation: float = Field(0.0, description="安全约束违反")
    current_state: Optional[Dict[str, Any]] = Field(None, description="当前状态")


class IntelligentSchemeRequest(BaseModel):
    """智能方案生成请求"""

    power_data: List[List[float]]
    period_types: List[List[int]]
    is_weekday: List[List[int]]
    temperature: List[List[float]]
    candidate_measures: List[Dict[str, Any]]
    price_diff: float
    current_state: Optional[Dict[str, Any]] = None


class TrainRequest(BaseModel):
    """模型训练请求"""

    transformer_epochs: int = Field(50, ge=1, le=500)
    gnn_epochs: int = Field(30, ge=1, le=200)
    rl_steps: int = Field(1000, ge=100, le=10000)


# ========== API端点 ==========


@router.get("/status")
async def get_status():
    """
    获取深度学习模块状态

    返回各模型的加载和训练状态
    """
    try:
        service = get_ml_service()
        return {"success": True, "data": service.get_model_status()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/loads")
async def analyze_loads(request: LoadAnalysisRequest):
    """
    分析可转移负荷 (时序Transformer)

    使用Transformer模型识别可转移负荷，输出:
    - 可转移性概率
    - 最优转移时段
    - 可转移容量
    """
    try:
        service = get_ml_service()
        result = service.analyze_transferable_loads(
            request.power_data, request.period_types, request.is_weekday, request.temperature
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calculate/peak-valley-saving")
async def calculate_saving(request: PeakValleySavingRequest):
    """
    计算峰谷套利收益

    基于可转移负荷分析结果计算潜在节能收益
    """
    try:
        service = get_ml_service()
        result = service.calculate_peak_valley_saving(
            request.predictions, request.price_diff, request.shift_hours, request.working_days
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/conflicts")
async def analyze_conflicts(request: MeasureConflictRequest):
    """
    分析措施冲突 (图神经网络)

    使用GNN分析措施间的冲突和耦合关系:
    - 冲突概率矩阵
    - 耦合系数矩阵
    - 推荐措施组合
    """
    try:
        service = get_ml_service()
        result = service.analyze_measure_conflicts(request.measures)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize/actions")
async def get_optimization_actions(current_state: Optional[Dict[str, Any]] = None):
    """
    获取优化动作建议 (强化学习)

    使用RL代理输出参数调整建议:
    - 措施优先级权重
    - 目标转移时段
    - 需量安全系数
    - 温度设定值
    """
    try:
        service = get_ml_service()
        result = service.get_optimization_actions(current_state)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rl/update")
async def update_rl_agent(request: RLUpdateRequest):
    """
    更新强化学习代理

    根据实际效果反馈进行在线学习
    """
    try:
        service = get_ml_service()
        result = service.update_rl_agent(
            request.actual_saving,
            request.expected_saving,
            request.comfort_violation,
            request.safety_violation,
            request.current_state,
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheme/generate")
async def generate_scheme(request: IntelligentSchemeRequest):
    """
    智能生成节能方案

    整合Transformer、GNN、RL三个模块，生成完整的智能节能方案
    """
    try:
        service = get_ml_service()
        result = service.generate_intelligent_scheme(
            request.power_data,
            request.period_types,
            request.is_weekday,
            request.temperature,
            request.candidate_measures,
            request.price_diff,
            request.current_state,
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train")
async def train_models(request: TrainRequest):
    """
    训练深度学习模型

    使用合成数据进行初始训练
    """
    try:
        service = get_ml_service()
        result = service.train_models(request.transformer_epochs, request.gnn_epochs, request.rl_steps)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== 与现有系统集成 ==========


@router.post("/integrate/opportunity-engine")
async def integrate_with_opportunity_engine(
    opportunities: List[Dict[str, Any]],
    power_data: Optional[List[List[float]]] = None,
    period_types: Optional[List[List[int]]] = None,
):
    """
    与现有机会分析引擎集成

    增强现有opportunity_engine的分析能力:
    1. 对可转移负荷进行深度学习识别
    2. 对候选措施进行冲突分析
    3. 输出优化后的收益估算
    """
    try:
        service = get_ml_service()

        result = {
            "original_opportunities": opportunities,
            "ml_enhancements": {},
            "timestamp": datetime.now().isoformat(),
        }

        # 如果提供了负荷数据，进行深度分析
        if power_data and period_types:
            # 生成模拟的时序数据
            is_weekday = [[1] * len(p) for p in power_data]
            temperature = [[25.0] * len(p) for p in power_data]

            load_analysis = service.analyze_transferable_loads(power_data, period_types, is_weekday, temperature)
            result["ml_enhancements"]["load_analysis"] = load_analysis

        # 将机会转换为措施格式进行冲突分析
        measures = []
        for opp in opportunities:
            measures.append(
                {
                    "measure_type": opp.get("category", 0),
                    "device_ids": opp.get("device_ids", []),
                    "execution_hours": list(range(8, 18)),  # 默认工作时间
                    "power_direction": 1 if "reduction" in str(opp.get("title", "")).lower() else 0,
                    "expected_benefit": opp.get("potential_saving", 0),
                }
            )

        if measures:
            conflict_analysis = service.analyze_measure_conflicts(measures)
            result["ml_enhancements"]["conflict_analysis"] = conflict_analysis

            # 计算调整后收益
            adjusted = service.calculate_adjusted_benefit(measures, conflict_analysis)
            result["ml_enhancements"]["adjusted_benefit"] = adjusted

        # 获取RL优化建议
        rl_advice = service.get_optimization_actions()
        result["ml_enhancements"]["optimization_advice"] = rl_advice

        return {"success": True, "data": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
