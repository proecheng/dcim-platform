"""
节能方案 API 端点
提供方案生成、查询、接受、执行和监控功能
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from decimal import Decimal

from app.api.deps import get_db
from app.schemas.proposal_schema import (
    ProposalCreate,
    ProposalResponse,
    MeasureAcceptRequest,
    ProposalMonitoringResponse,
    MeasureMonitoringResponse,
    ExecutionLogResponse,
    MLProposalCreate,
    MLAnalysisResponse,
    RLOptimizationRequest,
    RLOptimizationResponse,
    RLTrainingRequest,
    RLTrainingResponse,
    RLModelInfoResponse,
    RLOptimizationHistoryResponse,
    RLExplorationRateUpdateRequest,
)
from app.services.template_generator import TemplateGenerator
from app.services.proposal_executor import ProposalExecutor
from app.models.energy import EnergySavingProposal, ProposalMeasure, MeasureExecutionLog

router = APIRouter(prefix="/proposals", tags=["节能方案"])


# ==================== 0. 获取模板列表 ====================

@router.get("/templates", summary="获取模板列表")
async def get_templates():
    """
    获取所有可用的节能方案模板

    返回6种模板的基本信息：
    - A1-A5: 无需投资的优化方案
    - B1: 需要投资的改造方案
    """
    from app.services.template_generator import TemplateGenerator

    templates = []
    priority_map = {"A1": "high", "A2": "high", "A3": "medium", "A4": "medium", "A5": "low", "B1": "high"}
    category_map = {"A1": "peak_valley", "A2": "demand", "A3": "device", "A4": "vpp", "A5": "device", "B1": "device"}

    for template_id, config in TemplateGenerator.TEMPLATE_CONFIGS.items():
        templates.append({
            "id": template_id,
            "name": config["name"],
            "type": config["type"],
            "description": config["description"],
            "category": category_map.get(template_id, "other"),
            "priority": priority_map.get(template_id, "medium"),
            "is_enabled": True
        })

    return {
        "code": 0,
        "message": "success",
        "data": {
            "total": len(templates),
            "templates": templates
        }
    }


# ==================== 0.1 批量分析生成方案 ====================

@router.post("/analyze", summary="智能分析并生成方案")
async def analyze_and_generate(
    db: AsyncSession = Depends(get_db)
):
    """
    智能分析并批量生成节能方案

    为所有6种模板各生成一个方案，返回生成的方案数量
    """
    generator = TemplateGenerator(db)
    template_ids = list(TemplateGenerator.TEMPLATE_CONFIGS.keys())

    new_proposals = []
    for template_id in template_ids:
        try:
            # 检查是否已存在相同模板的待处理方案
            query = select(EnergySavingProposal).where(
                EnergySavingProposal.template_id == template_id,
                EnergySavingProposal.status == "pending"
            )
            result = await db.execute(query)
            existing = result.scalar_one_or_none()

            if not existing:
                proposal = generator.generate_proposal(template_id, analysis_days=30)
                db.add(proposal)
                new_proposals.append(proposal)
        except Exception as e:
            print(f"生成{template_id}方案失败: {str(e)}")
            continue

    await db.commit()

    return {
        "code": 0,
        "message": "success",
        "data": {
            "new_suggestions": len(new_proposals),
            "total": len(new_proposals)
        }
    }


# ==================== 0.2 兼容旧前端的建议格式API ====================

@router.get("/as-suggestions", summary="获取方案列表（建议格式）")
async def get_proposals_as_suggestions(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    将方案转换为前端期望的建议格式

    兼容旧的节能建议接口格式
    """
    query = select(EnergySavingProposal).options(selectinload(EnergySavingProposal.measures))

    # 状态映射: 前端的pending/accepted/rejected/completed -> 数据库的状态
    if status:
        query = query.where(EnergySavingProposal.status == status)

    query = query.order_by(EnergySavingProposal.created_at.desc())
    result = await db.execute(query)
    proposals = result.scalars().unique().all()

    suggestions = []
    priority_map = {"A1": "high", "A2": "high", "A3": "medium", "A4": "medium", "A5": "low", "B1": "high"}

    for proposal in proposals:
        # 转换为前端期望的格式
        suggestion = {
            "id": proposal.id,
            "rule_id": proposal.template_id,
            "rule_name": proposal.template_name,
            "suggestion": f"预计年度收益: {proposal.total_benefit:.2f}万元" if proposal.total_benefit else "点击查看详情",
            "priority": priority_map.get(proposal.template_id, "medium"),
            "status": proposal.status or "pending",
            "potential_saving": float(proposal.total_benefit * 10000 / 12) if proposal.total_benefit else 0,  # 换算为kWh/月
            "potential_cost_saving": float(proposal.total_benefit * 10000 / 12) if proposal.total_benefit else 0,  # 元/月
            "created_at": proposal.created_at.isoformat() if proposal.created_at else None,
            "updated_at": proposal.updated_at.isoformat() if proposal.updated_at else None,
            "completed_at": None,
            "actual_saving": None,
            "remark": None,
            # 额外字段供详情查看
            "proposal_code": proposal.proposal_code,
            "measures_count": len(proposal.measures) if proposal.measures else 0
        }
        suggestions.append(suggestion)

    return {
        "code": 0,
        "message": "success",
        "data": suggestions
    }


# ==================== 0.3 获取节能潜力统计 ====================

@router.get("/saving-potential", summary="获取节能潜力统计")
async def get_saving_potential(
    db: AsyncSession = Depends(get_db)
):
    """
    获取节能潜力统计数据

    兼容前端的节能潜力卡片
    """
    result = await db.execute(select(EnergySavingProposal))
    proposals = result.scalars().all()

    # 统计各状态数量
    pending_count = len([p for p in proposals if p.status == "pending"])
    accepted_count = len([p for p in proposals if p.status == "accepted"])
    completed_count = len([p for p in proposals if p.status == "completed"])

    # 计算总潜力
    total_benefit = sum(float(p.total_benefit or 0) for p in proposals)
    # 转换为月度数据 (万元/年 -> 元/月)
    monthly_saving = total_benefit * 10000 / 12

    priority_map = {"A1": "high", "A2": "high", "A3": "medium", "A4": "medium", "A5": "low", "B1": "high"}
    high_count = len([p for p in proposals if priority_map.get(p.template_id) == "high"])
    medium_count = len([p for p in proposals if priority_map.get(p.template_id) == "medium"])
    low_count = len([p for p in proposals if priority_map.get(p.template_id) == "low"])

    return {
        "code": 0,
        "message": "success",
        "data": {
            "total_potential_saving": monthly_saving,  # kWh/月 (这里简化为等同于金额)
            "total_cost_saving": monthly_saving,  # 元/月
            "pending_count": pending_count,
            "accepted_count": accepted_count,
            "completed_count": completed_count,
            "high_priority_count": high_count,
            "medium_priority_count": medium_count,
            "low_priority_count": low_count,
            "actual_saving_ytd": 0  # 年度实际节能，需要从执行日志统计
        }
    }


# ==================== 1. 生成方案 ====================

@router.post("/generate", response_model=ProposalResponse, summary="生成节能方案")
async def generate_proposal(
    request: ProposalCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    根据模板ID生成节能方案

    - **template_id**: A1/A2/A3/A4/A5/B1
    - **analysis_days**: 分析天数 (1-365，默认30)

    返回完整方案，包含多个措施
    """
    try:
        generator = TemplateGenerator(db)
        proposal = generator.generate_proposal(
            request.template_id,
            request.analysis_days
        )

        # 保存到数据库
        db.add(proposal)
        await db.commit()
        await db.refresh(proposal)

        return proposal
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"生成方案失败: {str(e)}")


# ==================== 1.1 ML 增强方案生成 (专利 S2) ====================

@router.post("/generate-ml-enhanced", response_model=ProposalResponse, summary="ML增强方案生成")
async def generate_ml_enhanced_proposal(
    request: MLProposalCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    使用深度学习增强的方案生成 (专利 S2)

    - **template_id**: A1/A2/A3/A4/A5/B1
    - **analysis_days**: 分析天数 (1-365，默认30)
    - **device_power_data**: 设备功率数据 (可选，用于 Transformer 分析)

    功能:
    - S2-TF: 使用 Transformer 识别可转移负荷 (A1 方案)
    - S2-GNN: 使用 GNN 分析措施冲突和收益耦合
    - 自动降级: ML 不可用时使用传统算法

    返回包含 ML 分析结果的完整方案
    """
    from app.services.ml_template_generator import MLTemplateGenerator

    try:
        generator = MLTemplateGenerator(db, enable_trace=True, enable_ml=True)

        # 转换 device_power_data 格式
        device_data = None
        if request.device_power_data:
            device_data = {
                device_id: {
                    "power": data.power,
                    "period_types": data.period_types,
                    "is_weekday": data.is_weekday,
                    "temperature": data.temperature
                }
                for device_id, data in request.device_power_data.items()
            }

        proposal = generator.generate_ml_enhanced_proposal(
            template_id=request.template_id,
            analysis_days=request.analysis_days,
            device_power_data=device_data
        )

        # 保存到数据库
        db.add(proposal)
        await db.commit()
        await db.refresh(proposal)

        return proposal
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"ML增强方案生成失败: {str(e)}")


# ==================== 1.2 获取 ML 分析详情 ====================

@router.get("/{proposal_id}/ml-analysis", response_model=MLAnalysisResponse, summary="获取ML分析详情")
async def get_ml_analysis(
    proposal_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    获取方案的 ML 分析详情

    返回:
    - Transformer 分析结果 (可转移负荷识别)
    - GNN 分析结果 (措施冲突和收益耦合)
    - RL 调整结果 (参数自适应)
    - 追溯汇总
    """
    from app.services.ml_template_generator import MLTemplateGenerator

    query = select(EnergySavingProposal).where(EnergySavingProposal.id == proposal_id)
    result = await db.execute(query)
    proposal = result.scalar_one_or_none()

    if not proposal:
        raise HTTPException(status_code=404, detail="方案不存在")

    # 获取 ML 状态
    generator = MLTemplateGenerator(db, enable_trace=True, enable_ml=True)
    ml_status = generator.get_ml_status()

    # 从 trace_summary 提取 ML 分析结果
    trace_summary = proposal.trace_summary or {}

    return MLAnalysisResponse(
        proposal_id=proposal.id,
        ml_enabled=ml_status.get("ml_enabled", False),
        ml_available=ml_status.get("ml_available", False),
        transformer_analysis=trace_summary.get("transformer_analysis"),
        gnn_analysis=trace_summary.get("gnn_analysis"),
        rl_adjustment=trace_summary.get("rl_adjustment"),
        trace_summary=trace_summary
    )


# ==================== 2. 获取方案详情 ====================

# 注意: enhanced 路由必须在 {proposal_id} 之前定义，否则 FastAPI 会把 "enhanced" 当成 proposal_id
@router.get("/{proposal_id}/enhanced", summary="获取方案增强详情（包含电价和设备数据）")
async def get_proposal_enhanced(
    proposal_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    获取方案详情并附加实时电价和设备数据
    用于前端详情抽屉展示
    """
    from app.services.pricing_service import PricingService
    from app.services.device_regulation_service import DeviceRegulationService

    # 获取方案基础信息
    query = select(EnergySavingProposal).options(selectinload(EnergySavingProposal.measures))\
        .where(EnergySavingProposal.id == proposal_id)
    result = await db.execute(query)
    proposal = result.scalar_one_or_none()

    if not proposal:
        raise HTTPException(status_code=404, detail="方案不存在")

    # 获取实时电价数据
    pricing_service = PricingService(db)
    device_service = DeviceRegulationService(db)

    pricing = await pricing_service.get_current_pricing()
    time_periods = await pricing_service.get_time_periods_for_display()
    shiftable_devices_data = await device_service.get_shiftable_devices()
    prices = await pricing_service.get_all_prices()

    # 计算总可转移功率
    total_shiftable_power = sum(d.get("shiftable_power", 0) for d in shiftable_devices_data)

    # 构建与前端期望的SuggestionDetail格式兼容的数据结构
    priority_map = {"A1": "high", "A2": "high", "A3": "medium", "A4": "medium", "A5": "low", "B1": "high"}

    enhanced_data = {
        "id": proposal.id,
        "rule_id": proposal.template_id,
        "rule_name": proposal.template_name,
        "template_id": proposal.template_id,
        "category": "peak_valley" if proposal.proposal_type == "A" else "other",
        "suggestion": f"预计年度收益: {proposal.total_benefit:.2f}万元" if proposal.total_benefit else "节能优化方案",
        "problem_description": f"方案编号: {proposal.proposal_code}\n方案类型: {'峰谷优化' if proposal.proposal_type == 'A' else '其他优化'}",
        "analysis_detail": None,  # 可根据 current_situation 生成
        "implementation_steps": [
            {"step": i+1, "description": m.regulation_description or m.regulation_object, "duration": None}
            for i, m in enumerate(proposal.measures or [])
        ] if proposal.measures else [],
        "expected_effect": {
            "description": f"年度收益: {proposal.total_benefit}万元" if proposal.total_benefit else "",
            "saving_kwh": float(proposal.total_benefit or 0) * 10000 / 0.6,  # 假设电价0.6元/kWh
            "saving_cost": float(proposal.total_benefit or 0) * 10000
        },
        "priority": priority_map.get(proposal.template_id, "medium"),
        "difficulty": None,
        "potential_saving": float(proposal.total_benefit or 0) * 10000 / 12,  # 月度节能
        "potential_cost_saving": float(proposal.total_benefit or 0) * 10000 / 12,  # 月度节省
        "status": proposal.status or "pending",
        "created_at": proposal.created_at.isoformat() if proposal.created_at else None,

        # 参数字段 - 包含可调整参数、设备列表、计算公式等
        "parameters": {
            "pricing_source": "electricity_pricing表",
            "device_source": "device_shift_configs表",
            "sharp_price": prices.get("sharp_price", 0),
            "peak_price": prices.get("peak_price", 0),
            "valley_price": prices.get("valley_price", 0),
            "price_diff": prices.get("sharp_price", 0) - prices.get("valley_price", 0),
            "total_shiftable_power": total_shiftable_power,

            # 可调整参数
            "adjustable_params": [
                {
                    "key": "shift_hours",
                    "name": "转移时长",
                    "type": "number",
                    "current_value": 2,
                    "min": 0.5,
                    "max": 8,
                    "step": 0.5,
                    "unit": "小时"
                },
                {
                    "key": "source_period",
                    "name": "转出时段",
                    "type": "period_select",
                    "current_value": "sharp",
                    "options": [p for p in time_periods if p["type"] in ["sharp", "peak"]]
                },
                {
                    "key": "target_period",
                    "name": "转入时段",
                    "type": "period_select",
                    "current_value": "valley",
                    "options": [p for p in time_periods if p["type"] in ["valley", "deep_valley", "normal"]]
                }
            ],

            # 设备列表
            "devices": [
                {
                    "device_id": d["device_id"],
                    "device_code": d["device_code"],
                    "device_name": d["device_name"],
                    "device_type": d["device_type"],
                    "rated_power": d["rated_power"],
                    "shiftable_power": d["shiftable_power"],
                    "regulation_method": d["regulation_method"],
                    "constraints": {
                        "allowed_hours": d.get("allowed_shift_hours", []),
                        "forbidden_hours": d.get("forbidden_shift_hours", []),
                        "min_runtime": d.get("min_continuous_runtime")
                    }
                }
                for d in shiftable_devices_data[:5]  # 取前5个设备
            ],

            # 计算公式
            "calculation_formula": {
                "formula": "日收益 = 转移功率 × 转移时长 × (转出电价 - 转入电价)",
                "variables_from_db": {
                    "尖峰电价": f"{prices.get('sharp_price', 0)} 元/kWh（来自系统设置-电价配置）",
                    "低谷电价": f"{prices.get('valley_price', 0)} 元/kWh（来自系统设置-电价配置）",
                    "峰谷价差": f"{prices.get('sharp_price', 0) - prices.get('valley_price', 0)} 元/kWh"
                },
                "steps": [
                    {"step": 1, "desc": "日转移电量 = 转移功率 × 转移时长"},
                    {"step": 2, "desc": "价差 = 转出电价 - 转入电价"},
                    {"step": 3, "desc": "日收益 = 日转移电量 × 价差"},
                    {"step": 4, "desc": "年收益 = 日收益 × 工作日数"}
                ]
            }
        },

        # 实时数据
        "current_pricing": pricing,
        "time_periods": time_periods,
        "shiftable_devices": shiftable_devices_data,
        "data_sources": {
            "pricing": "electricity_pricing表",
            "devices": "device_shift_configs表"
        }
    }

    return {
        "code": 0,
        "message": "success",
        "data": enhanced_data
    }


# ==================== RL 模型管理 (全局端点，无 proposal_id) ====================
# 重要：这些路由必须定义在 /{proposal_id} 路由之前，否则会被参数路由拦截

@router.post("/rl/train", response_model=RLTrainingResponse, summary="执行RL在线训练")
async def rl_train_step(
    request: RLTrainingRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    执行一步在线训练

    接收实际效果反馈并更新 RL 模型:
    - actual_saving: 实际节能收益
    - expected_saving: 预期节能收益
    - comfort_violation: 舒适度违反程度 (0-1)
    - safety_violation: 安全约束违反 (0-1)
    """
    from app.services.adaptive_optimization_service import AdaptiveOptimizationService

    optimization_service = AdaptiveOptimizationService(db)

    current_state = None
    if request.current_state:
        current_state = request.current_state.model_dump()

    result = optimization_service.train_step(
        actual_saving=request.actual_saving,
        expected_saving=request.expected_saving,
        comfort_violation=request.comfort_violation,
        safety_violation=request.safety_violation,
        current_state=current_state,
        proposal_id=request.proposal_id
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "训练失败"))

    return RLTrainingResponse(
        success=True,
        reward=result.get("reward", 0),
        achievement_rate=result.get("achievement_rate", 0),
        exploration_rate=result.get("exploration_rate", 0),
        step=result.get("step", 0),
        network_updated=result.get("network_updated", False),
        update_info=result.get("update_info"),
        training_log_id=result.get("training_log_id"),
    )


@router.get("/rl/model-info", response_model=RLModelInfoResponse, summary="获取RL模型信息")
async def get_rl_model_info(
    db: AsyncSession = Depends(get_db)
):
    """
    获取 RL 模型信息

    包含模型训练状态、探索率、统计指标等
    """
    from app.services.adaptive_optimization_service import AdaptiveOptimizationService

    optimization_service = AdaptiveOptimizationService(db)
    info = optimization_service.get_model_info()

    return RLModelInfoResponse(**info)


@router.put("/rl/exploration-rate", summary="更新探索率")
async def update_exploration_rate(
    request: RLExplorationRateUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    手动更新 RL 探索率 (S5f)

    用于干预自适应探索率调整机制
    """
    from app.services.adaptive_optimization_service import AdaptiveOptimizationService

    optimization_service = AdaptiveOptimizationService(db)
    result = optimization_service.update_exploration_rate(
        exploration_rate=request.exploration_rate,
        phase=request.phase
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "更新失败"))

    return {
        "code": 0,
        "message": "探索率已更新",
        "data": result
    }


@router.post("/rl/save-checkpoint", summary="保存模型检查点")
async def save_rl_checkpoint(
    db: AsyncSession = Depends(get_db)
):
    """
    保存 RL 模型检查点

    将当前模型参数保存到磁盘
    """
    from app.services.adaptive_optimization_service import AdaptiveOptimizationService

    optimization_service = AdaptiveOptimizationService(db)
    result = optimization_service.save_checkpoint()

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "保存失败"))

    return {
        "code": 0,
        "message": "检查点已保存",
        "data": result
    }


# ==================== 2. 获取方案详情 ====================

@router.get("/{proposal_id}", response_model=ProposalResponse, summary="获取方案详情")
async def get_proposal(
    proposal_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取指定方案的详细信息"""
    query = select(EnergySavingProposal).where(EnergySavingProposal.id == proposal_id)
    result = await db.execute(query)
    proposal = result.scalar_one_or_none()

    if not proposal:
        raise HTTPException(status_code=404, detail="方案不存在")

    return proposal


# ==================== 3. 获取方案列表 ====================

@router.get("/", summary="获取方案列表")
async def get_proposals(
    template_id: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    获取方案列表，支持过滤和分页

    - **template_id**: 按模板ID过滤
    - **status**: 按状态过滤
    - **skip**: 跳过记录数
    - **limit**: 返回记录数
    """
    query = select(EnergySavingProposal)

    if template_id:
        query = query.where(EnergySavingProposal.template_id == template_id)
    if status:
        query = query.where(EnergySavingProposal.status == status)

    query = query.order_by(EnergySavingProposal.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    proposals = result.scalars().all()

    # 统一响应格式
    return {
        "code": 0,
        "message": "success",
        "data": {
            "items": [ProposalResponse.model_validate(p) for p in proposals],
            "total": len(proposals),
            "skip": skip,
            "limit": limit
        }
    }


# ==================== 4. 接受方案（选择措施）====================

@router.post("/{proposal_id}/accept", response_model=ProposalResponse, summary="接受方案")
async def accept_proposal(
    proposal_id: int,
    request: MeasureAcceptRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    接受方案并选择要实施的措施

    - **selected_measure_ids**: 选中的措施ID列表

    会更新措施的 is_selected 状态，并将方案状态改为 accepted
    """
    query = select(EnergySavingProposal).options(selectinload(EnergySavingProposal.measures)).where(
        EnergySavingProposal.id == proposal_id
    )
    result = await db.execute(query)
    proposal = result.scalar_one_or_none()

    if not proposal:
        raise HTTPException(status_code=404, detail="方案不存在")

    # 更新措施选择状态
    for measure in proposal.measures:
        measure.is_selected = measure.id in request.selected_measure_ids

    # 更新方案状态
    proposal.status = "accepted"

    # 重新计算总收益（仅计算选中的措施）
    proposal.total_benefit = sum(
        m.annual_benefit for m in proposal.measures if m.is_selected
    )

    await db.commit()
    await db.refresh(proposal)

    return proposal


# ==================== 5. 执行方案 ====================

@router.post("/{proposal_id}/execute", summary="执行方案")
async def execute_proposal(
    proposal_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    执行已接受的方案（启动自动控制）

    执行所有选中的措施，并记录执行日志
    """
    query = select(EnergySavingProposal).where(EnergySavingProposal.id == proposal_id)
    result = await db.execute(query)
    proposal = result.scalar_one_or_none()

    if not proposal:
        raise HTTPException(status_code=404, detail="方案不存在")

    if proposal.status != "accepted":
        raise HTTPException(status_code=400, detail="方案未接受，无法执行")

    try:
        # 使用 ProposalExecutor 执行方案
        executor = ProposalExecutor(db)
        result = await executor.execute_proposal(proposal)

        # 统一响应格式
        return {
            "code": 0,
            "message": "方案执行完成",
            "data": {
                "proposal_id": proposal_id,
                "executed_count": result["executed_count"],
                "success_count": result["success_count"],
                "monitoring_started": result.get("monitoring_started", False),
                "baselines_captured": result.get("baselines_captured", 0),
                "results": result["results"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行方案失败: {str(e)}")


# ==================== 5.1 获取执行摘要 ====================

@router.get("/{proposal_id}/execution-summary", summary="获取执行摘要")
async def get_execution_summary(
    proposal_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    获取方案执行的摘要统计

    包括：
    - 总执行次数和成功次数
    - 成功率
    - 总节省功率
    - 预估年度节省
    """
    executor = ProposalExecutor(db)
    summary = await executor.get_execution_summary(proposal_id)

    if summary is None:
        raise HTTPException(status_code=404, detail="方案不存在")

    # 统一响应格式
    return {
        "code": 0,
        "message": "success",
        "data": summary
    }


# ==================== 6. 获取方案监控数据 ====================

@router.get("/{proposal_id}/monitoring", response_model=ProposalMonitoringResponse, summary="获取监控数据")
async def get_proposal_monitoring(
    proposal_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    获取方案执行的监控数据

    包括：
    - 每个措施的执行次数、成功率
    - 实际收益 vs 预期收益
    - 最新执行日志
    """
    query = select(EnergySavingProposal).options(selectinload(EnergySavingProposal.measures)).where(
        EnergySavingProposal.id == proposal_id
    )
    result = await db.execute(query)
    proposal = result.scalar_one_or_none()

    if not proposal:
        raise HTTPException(status_code=404, detail="方案不存在")

    # 构建监控响应
    measure_monitorings = []
    total_actual_benefit = Decimal("0")

    for measure in proposal.measures:
        if not measure.is_selected:
            continue

        # 统计执行日志
        logs_query = select(MeasureExecutionLog).where(
            MeasureExecutionLog.measure_id == measure.id
        )
        logs_result = await db.execute(logs_query)
        logs = logs_result.scalars().all()

        execution_count = len(logs)
        success_count = len([log for log in logs if log.result == "success"])

        # 计算实际收益（从日志）
        total_saved = sum(log.power_saved or Decimal("0") for log in logs)
        # 简化计算：假设平均电价0.5元/kWh
        actual_benefit = total_saved * Decimal("0.5") / Decimal("10000")  # 转万元
        total_actual_benefit += actual_benefit

        # 获取最新日志
        latest_log = logs[-1] if logs else None
        latest_execution = ExecutionLogResponse.from_orm(latest_log) if latest_log else None

        measure_monitoring = MeasureMonitoringResponse(
            measure_id=measure.id,
            measure_code=measure.measure_code,
            regulation_object=measure.regulation_object,
            expected_benefit=measure.annual_benefit,
            actual_benefit=actual_benefit,
            execution_count=execution_count,
            success_count=success_count,
            latest_execution=latest_execution
        )
        measure_monitorings.append(measure_monitoring)

    return ProposalMonitoringResponse(
        proposal_id=proposal.id,
        proposal_code=proposal.proposal_code,
        template_name=proposal.template_name,
        total_expected_benefit=proposal.total_benefit,
        total_actual_benefit=total_actual_benefit,
        measures=measure_monitorings
    )


# ==================== 7. 删除方案 ====================

@router.delete("/{proposal_id}", summary="删除方案")
async def delete_proposal(
    proposal_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除指定方案"""
    query = select(EnergySavingProposal).where(EnergySavingProposal.id == proposal_id)
    result = await db.execute(query)
    proposal = result.scalar_one_or_none()

    if not proposal:
        raise HTTPException(status_code=404, detail="方案不存在")

    await db.delete(proposal)
    await db.commit()

    # 统一响应格式
    return {
        "code": 0,
        "message": "方案已删除",
        "data": {"proposal_id": proposal_id}
    }


# ==================== 8. 措施详情增强 (专利 S3) ====================

@router.get("/{proposal_id}/measures/{measure_id}/detail", summary="获取措施详情（含ML和追溯）")
async def get_measure_detail(
    proposal_id: int,
    measure_id: int,
    include_trace: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """
    获取措施详情，包含 ML 预测置信度和数据追溯链

    专利 S3 对应接口:
    - 措施基本信息和状态
    - ML 预测信息 (可转移性置信度等)
    - 数据追溯链 (可展开查看计算路径)
    - 当前状态和目标状态对比
    """
    from app.services.data_trace_service import DataTraceService
    from app.models.trace import TraceRecord

    # 查询措施
    query = select(ProposalMeasure).where(
        ProposalMeasure.id == measure_id,
        ProposalMeasure.proposal_id == proposal_id
    )
    result = await db.execute(query)
    measure = result.scalar_one_or_none()

    if not measure:
        raise HTTPException(status_code=404, detail="措施不存在")

    # 构建基本信息
    detail = {
        "id": measure.id,
        "measure_code": measure.measure_code,
        "regulation_object": measure.regulation_object,
        "regulation_description": measure.regulation_description,
        "current_state": measure.current_state,
        "target_state": measure.target_state,
        "state_comparison": _build_state_comparison(measure.current_state, measure.target_state),
        "calculation_formula": measure.calculation_formula,
        "calculation_basis": measure.calculation_basis,
        "annual_benefit": float(measure.annual_benefit) if measure.annual_benefit else None,
        "investment": float(measure.investment) if measure.investment else 0,
        "is_selected": measure.is_selected,
        "execution_status": measure.execution_status or "pending",
        "created_at": measure.created_at.isoformat() if measure.created_at else None,
        "updated_at": measure.updated_at.isoformat() if measure.updated_at else None,
    }

    # 查询 ML 预测信息
    ml_query = select(TraceRecord).where(
        TraceRecord.measure_id == measure_id,
        TraceRecord.mapping_type == "ml_prediction"
    )
    ml_result = await db.execute(ml_query)
    ml_traces = ml_result.scalars().all()

    if ml_traces:
        # 找到置信度最高的预测
        best_trace = max(ml_traces, key=lambda t: t.ml_confidence or 0)
        detail["ml_prediction"] = {
            "has_ml_prediction": True,
            "model_type": best_trace.ml_model_type,
            "confidence": best_trace.ml_confidence,
            "prediction_details": {
                "param_name": best_trace.param_name,
                "value": float(best_trace.raw_value) if best_trace.raw_value else None,
                "unit": best_trace.value_unit,
                "input_features": best_trace.ml_input_features,
                "output_raw": best_trace.ml_output_raw
            }
        }
    else:
        detail["ml_prediction"] = {
            "has_ml_prediction": False,
            "model_type": None,
            "confidence": None,
            "prediction_details": None
        }

    # 查询追溯信息
    if include_trace:
        trace_service = DataTraceService(db)
        traces = await trace_service.get_traces_by_measure(measure_id)
        detail["trace_info"] = {
            "trace_count": len(traces),
            "trace_tree_available": any(t.child_trace_ids for t in traces),
            "key_traces": [
                {
                    "trace_id": t.trace_id,
                    "param_name": t.param_name,
                    "mapping_type": t.mapping_type,
                    "value": float(t.raw_value) if t.raw_value else None,
                    "unit": t.value_unit,
                    "formula_display": t.formula_display
                }
                for t in traces[:5]  # 只返回前5个关键追溯
            ]
        }

    return {
        "code": 0,
        "message": "success",
        "data": detail
    }


# ==================== 9. 措施状态更新 (专利 S3) ====================

@router.patch("/{proposal_id}/measures/{measure_id}/status", summary="更新措施状态")
async def update_measure_status(
    proposal_id: int,
    measure_id: int,
    status: str,
    reason: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    更新单个措施的选择状态

    专利 S3 对应接口:
    - accepted: 接受执行该措施
    - rejected: 拒绝执行该措施
    - deferred: 暂缓决定
    """
    valid_statuses = ["accepted", "rejected", "deferred", "pending"]
    if status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"无效状态，可选值: {valid_statuses}"
        )

    # 查询措施
    query = select(ProposalMeasure).where(
        ProposalMeasure.id == measure_id,
        ProposalMeasure.proposal_id == proposal_id
    )
    result = await db.execute(query)
    measure = result.scalar_one_or_none()

    if not measure:
        raise HTTPException(status_code=404, detail="措施不存在")

    old_status = "accepted" if measure.is_selected else "pending"

    # 更新状态
    measure.is_selected = (status == "accepted")

    # 重新计算方案总收益
    proposal_query = select(EnergySavingProposal).options(
        selectinload(EnergySavingProposal.measures)
    ).where(EnergySavingProposal.id == proposal_id)
    proposal_result = await db.execute(proposal_query)
    proposal = proposal_result.scalar_one_or_none()

    if proposal:
        proposal.total_benefit = sum(
            m.annual_benefit or Decimal("0")
            for m in proposal.measures
            if m.is_selected
        )

    await db.commit()

    return {
        "code": 0,
        "message": "状态更新成功",
        "data": {
            "measure_id": measure_id,
            "old_status": old_status,
            "new_status": status,
            "proposal_total_benefit": float(proposal.total_benefit) if proposal else None
        }
    }


@router.post("/{proposal_id}/measures/batch-status", summary="批量更新措施状态")
async def batch_update_measure_status(
    proposal_id: int,
    updates: List[dict],
    db: AsyncSession = Depends(get_db)
):
    """
    批量更新措施状态

    请求体格式:
    [
        {"measure_id": 1, "status": "accepted"},
        {"measure_id": 2, "status": "rejected"}
    ]
    """
    valid_statuses = ["accepted", "rejected", "deferred", "pending"]

    # 获取方案和所有措施
    proposal_query = select(EnergySavingProposal).options(
        selectinload(EnergySavingProposal.measures)
    ).where(EnergySavingProposal.id == proposal_id)
    result = await db.execute(proposal_query)
    proposal = result.scalar_one_or_none()

    if not proposal:
        raise HTTPException(status_code=404, detail="方案不存在")

    # 构建措施ID到措施的映射
    measure_map = {m.id: m for m in proposal.measures}

    results = []
    for update in updates:
        measure_id = update.get("measure_id")
        new_status = update.get("status")

        if measure_id not in measure_map:
            results.append({
                "measure_id": measure_id,
                "success": False,
                "message": "措施不存在"
            })
            continue

        if new_status not in valid_statuses:
            results.append({
                "measure_id": measure_id,
                "success": False,
                "message": f"无效状态: {new_status}"
            })
            continue

        measure = measure_map[measure_id]
        measure.is_selected = (new_status == "accepted")
        results.append({
            "measure_id": measure_id,
            "success": True,
            "new_status": new_status
        })

    # 重新计算总收益
    proposal.total_benefit = sum(
        m.annual_benefit or Decimal("0")
        for m in proposal.measures
        if m.is_selected
    )

    await db.commit()

    return {
        "code": 0,
        "message": "批量更新完成",
        "data": {
            "updated_count": sum(1 for r in results if r.get("success")),
            "results": results,
            "proposal_total_benefit": float(proposal.total_benefit)
        }
    }


# ==================== 10. 效果监测 (专利 S4) ====================

@router.post("/{proposal_id}/monitoring/start", summary="启动效果监测")
async def start_monitoring(
    proposal_id: int,
    interval_minutes: int = 15,
    report_interval: str = "daily",
    db: AsyncSession = Depends(get_db)
):
    """
    启动方案的持续效果监测 (S4b)

    - interval_minutes: 监测间隔 (分钟)
    - report_interval: 报告周期 (hourly/daily/weekly)
    """
    from app.services.effect_monitoring_service import EffectMonitoringService

    query = select(EnergySavingProposal).where(EnergySavingProposal.id == proposal_id)
    result = await db.execute(query)
    proposal = result.scalar_one_or_none()

    if not proposal:
        raise HTTPException(status_code=404, detail="方案不存在")

    if proposal.status not in ["executing", "accepted"]:
        raise HTTPException(status_code=400, detail="方案未在执行状态")

    monitoring_service = EffectMonitoringService(db)
    session = monitoring_service.start_monitoring(
        proposal,
        interval_minutes=interval_minutes,
        report_interval=report_interval
    )

    return {
        "code": 0,
        "message": "监测已启动",
        "data": {
            "session_id": session.id,
            "proposal_id": proposal_id,
            "interval_minutes": interval_minutes,
            "report_interval": report_interval,
            "started_at": session.started_at.isoformat()
        }
    }


@router.post("/{proposal_id}/monitoring/stop", summary="停止效果监测")
async def stop_monitoring(
    proposal_id: int,
    db: AsyncSession = Depends(get_db)
):
    """停止方案的效果监测"""
    from app.services.effect_monitoring_service import EffectMonitoringService
    from app.models.energy import MonitoringSession

    # 查找活跃会话
    query = select(MonitoringSession).where(
        MonitoringSession.proposal_id == proposal_id,
        MonitoringSession.status == "active"
    )
    result = await db.execute(query)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="未找到活跃的监测会话")

    monitoring_service = EffectMonitoringService(db)
    monitoring_service.stop_monitoring(session.id)

    return {
        "code": 0,
        "message": "监测已停止",
        "data": {
            "session_id": session.id,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None
        }
    }


@router.get("/{proposal_id}/monitoring/status", summary="获取监测状态")
async def get_monitoring_status(
    proposal_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取方案的监测状态"""
    from app.services.effect_monitoring_service import EffectMonitoringService

    monitoring_service = EffectMonitoringService(db)
    status = monitoring_service.get_monitoring_status(proposal_id)

    return {
        "code": 0,
        "message": "success",
        "data": status
    }


@router.get("/{proposal_id}/effect-report", summary="获取效果达成率报告")
async def get_effect_report(
    proposal_id: int,
    report_type: str = "daily",
    db: AsyncSession = Depends(get_db)
):
    """
    获取效果达成率报告 (S4d)

    返回:
    - 预期收益 vs 实际收益
    - 效果达成率
    - RL 反馈状态
    """
    from app.services.effect_monitoring_service import EffectMonitoringService

    query = select(EnergySavingProposal).where(EnergySavingProposal.id == proposal_id)
    result = await db.execute(query)
    proposal = result.scalar_one_or_none()

    if not proposal:
        raise HTTPException(status_code=404, detail="方案不存在")

    monitoring_service = EffectMonitoringService(db)

    # 生成或获取报告
    if report_type == "daily":
        report = monitoring_service.generate_daily_report(proposal_id)
    else:
        from datetime import datetime, timedelta
        now = datetime.now()
        if report_type == "weekly":
            start = now - timedelta(days=7)
        else:  # monthly
            start = now - timedelta(days=30)
        report = monitoring_service.calculate_achievement_rate(proposal_id, start, now)

    return {
        "code": 0,
        "message": "success",
        "data": {
            "report_id": report.id,
            "proposal_id": proposal_id,
            "report_type": report.report_type,
            "period": {
                "start": report.period_start.isoformat(),
                "end": report.period_end.isoformat()
            },
            "expected": {
                "energy_saved": float(report.expected_energy_saved or 0),
                "cost_saved": float(report.expected_cost_saved or 0)
            },
            "actual": {
                "energy_saved": float(report.actual_energy_saved or 0),
                "cost_saved": float(report.actual_cost_saved or 0)
            },
            "achievement_rate": float(report.achievement_rate or 0),
            "rl_feedback": {
                "sent": report.rl_feedback_sent,
                "sent_at": report.rl_feedback_at.isoformat() if report.rl_feedback_at else None,
                "action": report.rl_adjustment_action
            },
            "data_quality": float(report.data_quality or 0)
        }
    }


@router.get("/{proposal_id}/effect-summary", summary="获取效果汇总")
async def get_effect_summary(
    proposal_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取方案的效果汇总统计"""
    from app.services.effect_monitoring_service import EffectMonitoringService

    monitoring_service = EffectMonitoringService(db)
    summary = monitoring_service.get_effect_summary(proposal_id)

    return {
        "code": 0,
        "message": "success",
        "data": summary
    }


@router.post("/{proposal_id}/rl-feedback", summary="触发RL反馈")
async def trigger_rl_feedback(
    proposal_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    手动触发 RL 反馈 (S4e)

    计算当前效果达成率并推送到 RL 模块
    """
    from app.services.effect_monitoring_service import EffectMonitoringService

    query = select(EnergySavingProposal).where(EnergySavingProposal.id == proposal_id)
    result = await db.execute(query)
    proposal = result.scalar_one_or_none()

    if not proposal:
        raise HTTPException(status_code=404, detail="方案不存在")

    monitoring_service = EffectMonitoringService(db)

    # 生成报告并推送 RL
    report = monitoring_service.generate_daily_report(proposal_id)
    rl_result = monitoring_service.feed_to_rl(report)

    return {
        "code": 0,
        "message": "RL 反馈已触发",
        "data": {
            "report_id": report.id,
            "achievement_rate": float(report.achievement_rate or 0),
            "rl_feedback": rl_result
        }
    }


# ==================== 11. RL 自适应优化 (专利 S5) ====================

@router.post("/{proposal_id}/rl/optimize", response_model=RLOptimizationResponse, summary="执行RL优化")
async def rl_optimize(
    proposal_id: int,
    request: RLOptimizationRequest = None,
    db: AsyncSession = Depends(get_db)
):
    """
    执行 RL 优化 (S5e)

    基于当前系统状态，使用深度强化学习输出方案参数调整建议

    - 调整措施优先级权重
    - 推荐转移负荷目标时段
    - 调整需量安全系数
    - 建议温度设定值
    """
    from app.services.adaptive_optimization_service import AdaptiveOptimizationService

    optimization_service = AdaptiveOptimizationService(db)

    current_state = None
    if request and request.current_state:
        current_state = request.current_state.model_dump()

    result = optimization_service.optimize(proposal_id, current_state)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "RL 优化失败"))

    return RLOptimizationResponse(
        proposal_id=proposal_id,
        success=True,
        adjustments={k: {"value": v.get("value"), "description": v.get("description", ""), "unit": v.get("unit"), "index": v.get("index")}
                     for k, v in result.get("adjustments", {}).items()},
        raw_actions=result.get("raw_actions"),
        exploration=result.get("exploration", False),
        exploration_rate=result.get("exploration_rate", 0),
        confidence=result.get("confidence", 0),
        state_value=result.get("state_value"),
        optimization_id=result.get("optimization_id"),
    )


@router.get("/{proposal_id}/rl/status", summary="获取方案RL优化状态")
async def get_rl_optimization_status(
    proposal_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    获取方案的 RL 优化状态

    包含优化历史统计和最近一次优化结果
    """
    from app.services.adaptive_optimization_service import AdaptiveOptimizationService

    # 验证方案存在
    query = select(EnergySavingProposal).where(EnergySavingProposal.id == proposal_id)
    result = await db.execute(query)
    proposal = result.scalar_one_or_none()

    if not proposal:
        raise HTTPException(status_code=404, detail="方案不存在")

    optimization_service = AdaptiveOptimizationService(db)
    history = optimization_service.get_optimization_history(proposal_id, limit=1)

    return {
        "code": 0,
        "data": {
            "proposal_id": proposal_id,
            "total_optimizations": history.get("total", 0),
            "latest_optimization": history.get("items", [None])[0],
        }
    }


@router.get("/{proposal_id}/rl/history", response_model=RLOptimizationHistoryResponse, summary="获取RL优化历史")
async def get_rl_optimization_history(
    proposal_id: int,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """
    获取方案的 RL 优化历史记录
    """
    from app.services.adaptive_optimization_service import AdaptiveOptimizationService

    # 验证方案存在
    query = select(EnergySavingProposal).where(EnergySavingProposal.id == proposal_id)
    result = await db.execute(query)
    proposal = result.scalar_one_or_none()

    if not proposal:
        raise HTTPException(status_code=404, detail="方案不存在")

    optimization_service = AdaptiveOptimizationService(db)
    history = optimization_service.get_optimization_history(proposal_id, limit=limit, offset=offset)

    return RLOptimizationHistoryResponse(
        total=history.get("total", 0),
        items=history.get("items", [])
    )


@router.post("/{proposal_id}/rl/apply/{optimization_id}", summary="应用RL优化建议")
async def apply_rl_optimization(
    proposal_id: int,
    optimization_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    标记 RL 优化建议为已应用

    用于跟踪哪些优化建议被实际采纳
    """
    from app.services.adaptive_optimization_service import AdaptiveOptimizationService

    optimization_service = AdaptiveOptimizationService(db)
    result = optimization_service.apply_optimization(optimization_id)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "应用失败"))

    return {
        "code": 0,
        "message": "优化建议已标记为已应用",
        "data": result
    }


# ==================== 12. 从监测数据训练 ====================

@router.post("/{proposal_id}/rl/train-from-monitoring", summary="从监测数据训练")
async def rl_train_from_monitoring(
    proposal_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    从监测数据自动训练 (S4e → S5 闭环)

    读取方案的效果监测报告，自动计算达成率并执行训练步骤
    """
    from app.services.adaptive_optimization_service import AdaptiveOptimizationService

    # 验证方案存在
    query = select(EnergySavingProposal).where(EnergySavingProposal.id == proposal_id)
    result = await db.execute(query)
    proposal = result.scalar_one_or_none()

    if not proposal:
        raise HTTPException(status_code=404, detail="方案不存在")

    optimization_service = AdaptiveOptimizationService(db)
    train_result = optimization_service.train_from_monitoring(proposal_id)

    if not train_result.get("success"):
        raise HTTPException(status_code=400, detail=train_result.get("error", "训练失败"))

    return {
        "code": 0,
        "message": "从监测数据训练成功",
        "data": train_result
    }


# ==================== 辅助函数 ====================

def _build_state_comparison(current_state: dict, target_state: dict) -> dict:
    """构建当前状态和目标状态的对比"""
    if not current_state or not target_state:
        return None

    comparison = {
        "changes": [],
        "summary": ""
    }

    all_keys = set(current_state.keys()) | set(target_state.keys())
    for key in all_keys:
        current_val = current_state.get(key)
        target_val = target_state.get(key)
        if current_val != target_val:
            comparison["changes"].append({
                "field": key,
                "from": current_val,
                "to": target_val
            })

    if comparison["changes"]:
        comparison["summary"] = f"共 {len(comparison['changes'])} 项参数变更"

    return comparison



