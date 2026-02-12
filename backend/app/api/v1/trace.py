"""
数据追溯链 API 端点
提供追溯记录查询、追溯树展开、数据源映射管理功能

专利 S1 对应接口:
- 每个数值结果关联其追溯标识
- 支持逐层展开查看完整计算路径
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import List, Optional

from app.api.deps import get_db
from app.schemas.trace import (
    TraceTreeResponse, TraceTreeNode, TraceRecordResponse,
    TraceListResponse, DataSourceMappingResponse, DataSourceMappingCreate,
    MappingListResponse, ProposalTraceSummary, TemplateParameterResponse,
    TemplateParameterCreate
)
from app.models.trace import (
    DataSourceMapping, TraceRecord, TraceTree, TemplateParameter
)
from app.services.data_trace_service import DataTraceService

router = APIRouter(prefix="/trace", tags=["数据追溯链"])


# ==================== 追溯记录查询 ====================

@router.get("/{trace_id}", summary="获取追溯记录详情", response_model=None)
async def get_trace_detail(
    trace_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    根据追溯ID获取追溯记录详情

    支持查看数据来源、计算公式和中间结果
    """
    service = DataTraceService(db)
    trace = await service.get_trace_by_id(trace_id)

    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"追溯记录不存在: {trace_id}"
        )

    return {
        "code": 0,
        "message": "success",
        "data": _trace_to_dict(trace)
    }


@router.get("/{trace_id}/tree", summary="获取追溯树", response_model=None)
async def get_trace_tree(
    trace_id: str,
    expand_depth: int = Query(10, description="展开深度, -1表示全部"),
    include_sql: bool = Query(False, description="是否包含SQL语句"),
    db: AsyncSession = Depends(get_db)
):
    """
    获取完整追溯树

    逐层展开查看完整计算路径:
    - 复合参数: 展示计算公式和子参数
    - 聚合参数: 展示聚合函数和数据源
    - 直接参数: 展示数据库表和字段
    """
    service = DataTraceService(db)
    tree = await service.get_trace_tree(trace_id)

    if not tree:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"追溯记录不存在: {trace_id}"
        )

    # 计算统计信息
    total_nodes, max_depth, data_sources = _analyze_tree(tree)

    if not include_sql:
        _strip_sql(tree)

    return {
        "code": 0,
        "message": "success",
        "data": {
            "root_trace_id": trace_id,
            "tree": tree,
            "total_nodes": total_nodes,
            "max_depth": max_depth,
            "data_sources": data_sources
        }
    }


# ==================== 方案/措施追溯查询 ====================

@router.get("/proposal/{proposal_id}", summary="获取方案追溯汇总", response_model=None)
async def get_proposal_traces(
    proposal_id: int,
    include_measures: bool = Query(True, description="是否包含措施追溯"),
    db: AsyncSession = Depends(get_db)
):
    """
    获取方案的所有追溯记录汇总

    包含方案内所有措施的追溯链信息
    """
    service = DataTraceService(db)
    traces = await service.get_traces_by_proposal(proposal_id)

    if not traces:
        return {
            "code": 0,
            "message": "success",
            "data": {
                "total_traces": 0,
                "data_sources": [],
                "root_trace_ids": [],
                "traces": []
            }
        }

    # 汇总数据源
    data_sources = set()
    root_trace_ids = []

    for trace in traces:
        if trace.source_table:
            data_sources.add(trace.source_table)
        if trace.parent_trace_id is None:
            root_trace_ids.append(trace.trace_id)

    result = {
        "total_traces": len(traces),
        "data_sources": list(data_sources),
        "root_trace_ids": root_trace_ids,
    }

    if include_measures:
        # 按措施分组
        measure_traces = {}
        for trace in traces:
            mid = trace.measure_id or 0
            if mid not in measure_traces:
                measure_traces[mid] = []
            measure_traces[mid].append(_trace_to_dict(trace))
        result["measure_traces"] = measure_traces
    else:
        result["traces"] = [_trace_to_dict(t) for t in traces]

    return {
        "code": 0,
        "message": "success",
        "data": result
    }


@router.get("/measure/{measure_id}", summary="获取措施追溯记录", response_model=None)
async def get_measure_traces(
    measure_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    获取某个措施的所有追溯记录

    每个措施的数值结果都关联追溯标识，可展开查看计算路径
    """
    service = DataTraceService(db)
    traces = await service.get_traces_by_measure(measure_id)

    return {
        "code": 0,
        "message": "success",
        "data": {
            "measure_id": measure_id,
            "total": len(traces),
            "traces": [_trace_to_dict(t) for t in traces]
        }
    }


# ==================== ML 预测追溯查询 (专利 S2) ====================

@router.get("/proposal/{proposal_id}/ml", summary="获取方案ML预测追溯", response_model=None)
async def get_proposal_ml_traces(
    proposal_id: int,
    model_type: Optional[str] = Query(None, description="ML模型类型过滤: transformer/gnn/rl"),
    db: AsyncSession = Depends(get_db)
):
    """
    获取方案的 ML 预测追溯记录

    专利 S2 对应接口:
    - Transformer 可转移负荷识别追溯
    - GNN 措施冲突分析追溯
    - RL 自适应优化追溯
    """
    query = select(TraceRecord).where(
        and_(
            TraceRecord.proposal_id == proposal_id,
            TraceRecord.mapping_type == "ml_prediction"
        )
    )

    if model_type:
        query = query.where(TraceRecord.ml_model_type == model_type)

    result = await db.execute(query)
    traces = result.scalars().all()

    # 按模型类型分组
    grouped = {
        "transformer": [],
        "gnn": [],
        "rl": []
    }

    for trace in traces:
        mt = trace.ml_model_type
        if mt in grouped:
            grouped[mt].append(_trace_to_dict(trace))

    # 统计信息
    summary = {
        "total_ml_traces": len(traces),
        "transformer_count": len(grouped["transformer"]),
        "gnn_count": len(grouped["gnn"]),
        "rl_count": len(grouped["rl"]),
        "avg_confidence": sum(t.ml_confidence or 0 for t in traces) / len(traces) if traces else 0
    }

    return {
        "code": 0,
        "message": "success",
        "data": {
            "proposal_id": proposal_id,
            "summary": summary,
            "traces_by_model": grouped
        }
    }


@router.get("/measure/{measure_id}/ml", summary="获取措施ML预测追溯", response_model=None)
async def get_measure_ml_traces(
    measure_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    获取措施的 ML 预测追溯记录

    包含该措施相关的所有 ML 模型预测信息和置信度
    """
    query = select(TraceRecord).where(
        and_(
            TraceRecord.measure_id == measure_id,
            TraceRecord.mapping_type == "ml_prediction"
        )
    )
    result = await db.execute(query)
    traces = result.scalars().all()

    ml_predictions = []
    for trace in traces:
        ml_predictions.append({
            "trace_id": trace.trace_id,
            "param_name": trace.param_name,
            "model_type": trace.ml_model_type,
            "model_version": trace.ml_model_version,
            "confidence": trace.ml_confidence,
            "value": float(trace.raw_value) if trace.raw_value else None,
            "unit": trace.value_unit,
            "input_features": trace.ml_input_features,
            "output_raw": trace.ml_output_raw,
            "calculated_at": trace.calculated_at.isoformat() if trace.calculated_at else None
        })

    return {
        "code": 0,
        "message": "success",
        "data": {
            "measure_id": measure_id,
            "has_ml_predictions": len(ml_predictions) > 0,
            "ml_predictions": ml_predictions
        }
    }


# ==================== 数据源映射管理 ====================

@router.get("/mappings/list", summary="获取数据源映射列表", response_model=None)
async def list_mappings(
    mapping_type: Optional[str] = Query(None, description="映射类型过滤"),
    template_id: Optional[str] = Query(None, description="模板ID过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """获取数据源映射配置列表"""
    query = select(DataSourceMapping).where(DataSourceMapping.is_enabled == True)

    if mapping_type:
        query = query.where(DataSourceMapping.mapping_type == mapping_type)

    # 统计总数
    count_query = select(func.count()).select_from(DataSourceMapping).where(
        DataSourceMapping.is_enabled == True
    )
    if mapping_type:
        count_query = count_query.where(DataSourceMapping.mapping_type == mapping_type)

    count_result = await db.execute(count_query)
    total = count_result.scalar()

    # 分页查询
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    mappings = result.scalars().all()

    return {
        "code": 0,
        "message": "success",
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_mapping_to_dict(m) for m in mappings]
        }
    }


@router.post("/mappings", summary="创建数据源映射", response_model=None)
async def create_mapping(
    data: DataSourceMappingCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建新的数据源映射配置"""
    # 检查是否已存在
    existing = await db.execute(
        select(DataSourceMapping).where(DataSourceMapping.param_code == data.param_code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"参数编码已存在: {data.param_code}"
        )

    mapping = DataSourceMapping(
        param_code=data.param_code,
        param_name=data.param_name,
        param_unit=data.param_unit,
        mapping_type=data.mapping_type,
        source_table=data.source_table,
        source_field=data.source_field,
        aggregation_type=data.aggregation_type,
        aggregation_params=data.aggregation_params,
        filter_condition=data.filter_condition,
        time_range_type=data.time_range_type,
        formula=data.formula,
        child_params=data.child_params,
        template_ids=data.template_ids,
        description=data.description,
    )
    db.add(mapping)
    await db.commit()
    await db.refresh(mapping)

    return {
        "code": 0,
        "message": "创建成功",
        "data": _mapping_to_dict(mapping)
    }


# ==================== 模板参数管理 ====================

@router.get("/templates/{template_id}/params", summary="获取模板参数列表", response_model=None)
async def get_template_params(
    template_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取模板的占位符参数及映射配置"""
    service = DataTraceService(db)
    params = await service.get_template_parameters(template_id)

    return {
        "code": 0,
        "message": "success",
        "data": {
            "template_id": template_id,
            "total": len(params),
            "parameters": [_template_param_to_dict(p) for p in params]
        }
    }


@router.post("/templates/params", summary="创建模板参数配置", response_model=None)
async def create_template_param(
    data: TemplateParameterCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建模板参数配置"""
    param = TemplateParameter(
        template_id=data.template_id,
        param_code=data.param_code,
        param_name=data.param_name,
        param_description=data.param_description,
        mapping_id=data.mapping_id,
        default_value=data.default_value,
        min_value=data.min_value,
        max_value=data.max_value,
        is_required=data.is_required,
        sort_order=data.sort_order,
    )
    db.add(param)
    await db.commit()
    await db.refresh(param)

    return {
        "code": 0,
        "message": "创建成功",
        "data": _template_param_to_dict(param)
    }


# ==================== 初始化默认映射 ====================

@router.post("/mappings/init", summary="初始化默认数据源映射", response_model=None)
async def init_default_mappings(
    db: AsyncSession = Depends(get_db)
):
    """
    初始化系统默认的数据源映射配置

    创建所有模板所需的基础参数映射
    """
    created = await _create_default_mappings(db)

    return {
        "code": 0,
        "message": f"初始化完成，创建了 {created} 个映射配置",
        "data": {"created_count": created}
    }


# ==================== 辅助函数 ====================

def _trace_to_dict(trace: TraceRecord) -> dict:
    """TraceRecord 转字典"""
    d = {
        "id": trace.id,
        "trace_id": trace.trace_id,
        "param_code": trace.param_code,
        "param_name": trace.param_name,
        "mapping_type": trace.mapping_type,
        "value": float(trace.raw_value) if trace.raw_value else None,
        "formatted_value": trace.formatted_value,
        "unit": trace.value_unit,
        "depth": trace.depth,
        "parent_trace_id": trace.parent_trace_id,
        "child_trace_ids": trace.child_trace_ids,
        "calculated_at": trace.calculated_at.isoformat() if trace.calculated_at else None,
        "created_at": trace.created_at.isoformat() if trace.created_at else None,
    }

    if trace.mapping_type == "direct":
        d["source"] = {
            "table": trace.source_table,
            "field": trace.source_field,
            "filter": trace.filter_condition,
        }
    elif trace.mapping_type == "aggregate":
        d["source"] = {
            "table": trace.source_table,
            "field": trace.source_field,
            "aggregation": trace.aggregation_type,
            "params": trace.aggregation_params,
            "filter": trace.filter_condition,
            "time_range": {
                "start": trace.time_range_start.isoformat() if trace.time_range_start else None,
                "end": trace.time_range_end.isoformat() if trace.time_range_end else None,
            }
        }
        d["query_sql"] = trace.query_sql
    elif trace.mapping_type == "composite":
        d["formula"] = trace.formula
        d["formula_display"] = trace.formula_display
    elif trace.mapping_type == "ml_prediction":
        # ML 预测追溯 (专利 S2)
        d["ml_prediction"] = {
            "model_type": trace.ml_model_type,
            "model_version": trace.ml_model_version,
            "confidence": trace.ml_confidence,
            "input_features": trace.ml_input_features,
            "output_raw": trace.ml_output_raw,
        }

    return d


def _mapping_to_dict(m: DataSourceMapping) -> dict:
    """DataSourceMapping 转字典"""
    return {
        "id": m.id,
        "param_code": m.param_code,
        "param_name": m.param_name,
        "param_unit": m.param_unit,
        "mapping_type": m.mapping_type,
        "source_table": m.source_table,
        "source_field": m.source_field,
        "aggregation_type": m.aggregation_type,
        "aggregation_params": m.aggregation_params,
        "filter_condition": m.filter_condition,
        "time_range_type": m.time_range_type,
        "formula": m.formula,
        "child_params": m.child_params,
        "template_ids": m.template_ids,
        "description": m.description,
        "is_enabled": m.is_enabled,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


def _template_param_to_dict(p: TemplateParameter) -> dict:
    """TemplateParameter 转字典"""
    return {
        "id": p.id,
        "template_id": p.template_id,
        "template_name": p.template_name,
        "param_code": p.param_code,
        "param_name": p.param_name,
        "param_description": p.param_description,
        "mapping_id": p.mapping_id,
        "default_value": float(p.default_value) if p.default_value else None,
        "min_value": float(p.min_value) if p.min_value else None,
        "max_value": float(p.max_value) if p.max_value else None,
        "is_required": p.is_required,
        "sort_order": p.sort_order,
        "is_enabled": p.is_enabled,
    }


def _analyze_tree(tree: dict) -> tuple:
    """分析追溯树统计信息"""
    total_nodes = 0
    max_depth = 0
    data_sources = set()

    def walk(node: dict, depth: int):
        nonlocal total_nodes, max_depth
        total_nodes += 1
        max_depth = max(max_depth, depth)

        source = node.get("source", {})
        if source and source.get("table"):
            data_sources.add(source["table"])

        for child in node.get("children", []):
            walk(child, depth + 1)

    walk(tree, 0)
    return total_nodes, max_depth, list(data_sources)


def _strip_sql(tree: dict):
    """从追溯树中移除SQL信息"""
    tree.pop("query_sql", None)
    for child in tree.get("children", []):
        _strip_sql(child)


# ==================== 默认映射配置 ====================

async def _create_default_mappings(db: AsyncSession) -> int:
    """创建系统默认的数据源映射"""
    default_mappings = [
        # ====== 第一层: 直接映射 ======
        {
            "param_code": "declared_demand",
            "param_name": "当前申报需量",
            "param_unit": "kW",
            "mapping_type": "direct",
            "source_table": "transformers",
            "source_field": "declared_demand",
            "template_ids": ["A2"],
            "description": "从变压器配置表获取当前申报需量"
        },
        {
            "param_code": "demand_price",
            "param_name": "需量电价",
            "param_unit": "元/kW·月",
            "mapping_type": "direct",
            "source_table": "pricing_configs",
            "source_field": "demand_price",
            "template_ids": ["A2"],
            "description": "从电价配置表获取需量电价"
        },
        {
            "param_code": "transformer_capacity",
            "param_name": "变压器额定容量",
            "param_unit": "kVA",
            "mapping_type": "direct",
            "source_table": "transformers",
            "source_field": "rated_capacity",
            "template_ids": ["A2", "A3"],
            "description": "从变压器表获取额定容量"
        },

        # ====== 第二层: 聚合映射 ======
        {
            "param_code": "annual_energy",
            "param_name": "年用电量",
            "param_unit": "kWh",
            "mapping_type": "aggregate",
            "source_table": "energy_monthly",
            "source_field": "total_energy",
            "aggregation_type": "sum",
            "time_range_type": "year",
            "template_ids": ["A1", "A2", "A3"],
            "description": "统计近12个月总用电量"
        },
        {
            "param_code": "max_demand",
            "param_name": "最大需量",
            "param_unit": "kW",
            "mapping_type": "aggregate",
            "source_table": "demand_history",
            "source_field": "max_demand",
            "aggregation_type": "max",
            "time_range_type": "year",
            "template_ids": ["A2"],
            "description": "统计近12个月最大需量"
        },
        {
            "param_code": "demand_95th",
            "param_name": "95分位需量",
            "param_unit": "kW",
            "mapping_type": "aggregate",
            "source_table": "demand_history",
            "source_field": "max_demand",
            "aggregation_type": "percentile",
            "aggregation_params": {"percentile": 95},
            "time_range_type": "year",
            "template_ids": ["A2"],
            "description": "统计近12个月95分位数需量"
        },
        {
            "param_code": "avg_power",
            "param_name": "平均负荷",
            "param_unit": "kW",
            "mapping_type": "aggregate",
            "source_table": "energy_daily",
            "source_field": "avg_power",
            "aggregation_type": "avg",
            "time_range_type": "year",
            "template_ids": ["A1", "A2"],
            "description": "统计日均平均负荷"
        },
        {
            "param_code": "annual_energy_cost",
            "param_name": "年电费",
            "param_unit": "元",
            "mapping_type": "aggregate",
            "source_table": "energy_monthly",
            "source_field": "energy_cost",
            "aggregation_type": "sum",
            "time_range_type": "year",
            "template_ids": ["A1", "A2"],
            "description": "统计近12个月总电费"
        },
        {
            "param_code": "peak_energy_ratio",
            "param_name": "峰时电量占比",
            "param_unit": "%",
            "mapping_type": "aggregate",
            "source_table": "energy_daily",
            "source_field": "peak_energy",
            "aggregation_type": "sum",
            "time_range_type": "year",
            "template_ids": ["A1"],
            "description": "峰时电量占总电量比例"
        },
        {
            "param_code": "valley_energy_ratio",
            "param_name": "谷时电量占比",
            "param_unit": "%",
            "mapping_type": "aggregate",
            "source_table": "energy_daily",
            "source_field": "valley_energy",
            "aggregation_type": "sum",
            "time_range_type": "year",
            "template_ids": ["A1"],
            "description": "谷时电量占总电量比例"
        },
        {
            "param_code": "shiftable_power",
            "param_name": "可转移功率",
            "param_unit": "kW",
            "mapping_type": "aggregate",
            "source_table": "device_shift_configs",
            "source_field": "shiftable_power_ratio",
            "aggregation_type": "sum",
            "template_ids": ["A1"],
            "description": "所有可转移设备的可转移功率总和"
        },

        # ====== 第三层: 复合映射 ======
        {
            "param_code": "load_rate",
            "param_name": "负荷率",
            "param_unit": "%",
            "mapping_type": "composite",
            "formula": "{avg_power} / {max_demand} * 100",
            "child_params": ["avg_power", "max_demand"],
            "template_ids": ["A2"],
            "description": "负荷率 = 平均负荷 / 最大需量 × 100%"
        },
        {
            "param_code": "avg_electricity_price",
            "param_name": "平均电价",
            "param_unit": "元/kWh",
            "mapping_type": "composite",
            "formula": "{annual_energy_cost} / {annual_energy}",
            "child_params": ["annual_energy_cost", "annual_energy"],
            "template_ids": ["A1", "A2", "A3"],
            "description": "平均电价 = 年电费 / 年用电量"
        },
        {
            "param_code": "demand_saving",
            "param_name": "需量优化收益",
            "param_unit": "元/年",
            "mapping_type": "composite",
            "formula": "({declared_demand} - {recommended_demand}) * {demand_price} * 12",
            "child_params": ["declared_demand", "recommended_demand", "demand_price"],
            "template_ids": ["A2"],
            "description": "需量优化收益 = (当前申报需量 - 建议需量) × 需量电价 × 12月"
        },
        {
            "param_code": "recommended_demand",
            "param_name": "建议申报需量",
            "param_unit": "kW",
            "mapping_type": "composite",
            "formula": "{demand_95th} * {safety_factor}",
            "child_params": ["demand_95th", "safety_factor"],
            "template_ids": ["A2"],
            "description": "建议申报需量 = 95分位需量 × 安全系数"
        },
        {
            "param_code": "peak_valley_saving",
            "param_name": "峰谷套利收益",
            "param_unit": "元/年",
            "mapping_type": "composite",
            "formula": "{shiftable_power} * {shift_hours} * {price_diff} * {working_days}",
            "child_params": ["shiftable_power", "shift_hours", "price_diff", "working_days"],
            "template_ids": ["A1"],
            "description": "峰谷收益 = 可转移功率 × 转移时长 × 电价差 × 年运行天数"
        },
    ]

    created = 0
    for mapping_data in default_mappings:
        # 检查是否已存在
        existing = await db.execute(
            select(DataSourceMapping).where(
                DataSourceMapping.param_code == mapping_data["param_code"]
            )
        )
        if existing.scalar_one_or_none():
            continue

        mapping = DataSourceMapping(**mapping_data)
        db.add(mapping)
        created += 1

    await db.commit()
    return created
