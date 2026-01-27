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
    ExecutionLogResponse
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

@router.get("/", response_model=List[ProposalResponse], summary="获取方案列表")
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

    return proposals


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
        result = executor.execute_proposal(proposal)

        return {
            "message": "方案执行完成",
            "proposal_id": proposal_id,
            "executed_count": result["executed_count"],
            "success_count": result["success_count"],
            "results": result["results"]
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
    summary = executor.get_execution_summary(proposal_id)

    if summary is None:
        raise HTTPException(status_code=404, detail="方案不存在")

    return summary


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

    return {"message": "方案已删除", "proposal_id": proposal_id}



