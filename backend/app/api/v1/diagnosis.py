"""
智能诊断 API
Story 9-3: 智能故障诊断
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..deps import get_db, require_admin, require_operator, require_viewer
from ...models.user import User
from ...models.diagnosis import DiagnosisRule, DiagnosisResult
from ...schemas.diagnosis import (
    DiagnosisRuleCreate,
    DiagnosisRuleUpdate,
    DiagnosisRuleResponse,
    DiagnosisResultResponse,
    DiagnosisCategoryItem,
)
from ...engines.diagnosis_engine import diagnosis_engine

logger = logging.getLogger(__name__)

router = APIRouter()

# 分类映射
CATEGORY_MAP = {
    "temperature": "温度",
    "humidity": "湿度",
    "power": "电力",
    "communication": "通信",
    "security": "安防",
    "cooling": "制冷",
    "environment": "环境",
    "composite": "综合",
}


# ==================== 静态路由（必须在参数化路由之前）====================


@router.get("/categories", response_model=list)
async def get_categories(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取诊断规则分类列表"""
    result = await db.execute(
        select(DiagnosisRule.category, func.count(DiagnosisRule.id)).group_by(DiagnosisRule.category)
    )
    rows = result.all()
    return [
        DiagnosisCategoryItem(
            code=row[0],
            name=CATEGORY_MAP.get(row[0], row[0]),
            count=row[1],
        )
        for row in rows
    ]


# ==================== 规则管理 ====================


@router.get("/rules/reload", response_model=dict)
async def reload_rules_from_yaml(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """重载 YAML 诊断规则"""
    from ...services.diagnosis_loader import reload

    count = await reload(db)
    await diagnosis_engine.reload_rules()
    return {"message": f"诊断规则重载完成，共 {count} 条", "count": count}


@router.get("/rules", response_model=dict)
async def list_rules(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    category: Optional[str] = Query(None, description="分类筛选"),
    is_enabled: Optional[bool] = Query(None, description="启用状态"),
    is_system: Optional[bool] = Query(None, description="系统规则"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """诊断规则列表"""
    query = select(DiagnosisRule)
    if category is not None:
        query = query.where(DiagnosisRule.category == category)
    if is_enabled is not None:
        query = query.where(DiagnosisRule.is_enabled == is_enabled)
    if is_system is not None:
        query = query.where(DiagnosisRule.is_system == is_system)
    query = query.order_by(DiagnosisRule.priority.desc(), DiagnosisRule.id)

    # 总数
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # 分页
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rules = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [DiagnosisRuleResponse.model_validate(r) for r in rules],
    }


@router.get("/rules/{rule_id}", response_model=DiagnosisRuleResponse)
async def get_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """诊断规则详情"""
    result = await db.execute(select(DiagnosisRule).where(DiagnosisRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="规则不存在")
    return DiagnosisRuleResponse.model_validate(rule)


@router.post("/rules", response_model=DiagnosisRuleResponse)
async def create_rule(
    data: DiagnosisRuleCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """创建自定义诊断规则"""
    # 检查 rule_code 唯一性
    existing = await db.execute(select(DiagnosisRule).where(DiagnosisRule.rule_code == data.rule_code))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail=f"规则编码 {data.rule_code} 已存在")

    rule = DiagnosisRule(
        rule_code=data.rule_code,
        name=data.name,
        description=data.description,
        category=data.category,
        trigger_condition=data.trigger_condition,
        diagnosis_logic=data.diagnosis_logic,
        priority=data.priority,
        is_enabled=data.is_enabled,
        is_system=False,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    await diagnosis_engine.reload_rules()
    return DiagnosisRuleResponse.model_validate(rule)


@router.put("/rules/{rule_id}", response_model=DiagnosisRuleResponse)
async def update_rule(
    rule_id: int,
    data: DiagnosisRuleUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """更新诊断规则"""
    result = await db.execute(select(DiagnosisRule).where(DiagnosisRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="规则不存在")

    # is_system 规则禁止修改 trigger_condition
    if rule.is_system and data.trigger_condition is not None:
        raise HTTPException(status_code=403, detail="系统规则禁止修改触发条件")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)
    await db.commit()
    await db.refresh(rule)
    await diagnosis_engine.reload_rules()
    return DiagnosisRuleResponse.model_validate(rule)


@router.delete("/rules/{rule_id}", response_model=dict)
async def delete_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """删除诊断规则（系统规则禁止删除）"""
    result = await db.execute(select(DiagnosisRule).where(DiagnosisRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="规则不存在")
    if rule.is_system:
        raise HTTPException(status_code=403, detail="系统内置规则禁止删除")

    await db.delete(rule)
    await db.commit()
    await diagnosis_engine.reload_rules()
    return {"message": "规则已删除"}


@router.put("/rules/{rule_id}/toggle", response_model=DiagnosisRuleResponse)
async def toggle_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """启用/禁用诊断规则"""
    result = await db.execute(select(DiagnosisRule).where(DiagnosisRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="规则不存在")

    rule.is_enabled = not rule.is_enabled
    await db.commit()
    await db.refresh(rule)
    await diagnosis_engine.reload_rules()
    return DiagnosisRuleResponse.model_validate(rule)


# ==================== 诊断结果 ====================


@router.get("/results/by-alarm/{alarm_id}", response_model=list)
async def get_results_by_alarm(
    alarm_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """按告警ID查询诊断结果"""
    result = await db.execute(
        select(DiagnosisResult).where(DiagnosisResult.alarm_id == alarm_id).order_by(DiagnosisResult.created_at.desc())
    )
    results = result.scalars().all()
    return [DiagnosisResultResponse.model_validate(r) for r in results]


@router.get("/results", response_model=dict)
async def list_results(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    device_type: Optional[str] = Query(None),
    zone: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None, description="开始时间 ISO格式"),
    end_time: Optional[str] = Query(None, description="结束时间 ISO格式"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """诊断结果列表"""
    query = select(DiagnosisResult)
    if device_type is not None:
        query = query.where(DiagnosisResult.device_type == device_type)
    if zone is not None:
        query = query.where(DiagnosisResult.zone == zone)
    if start_time is not None:
        try:
            st = datetime.fromisoformat(start_time)
            query = query.where(DiagnosisResult.created_at >= st)
        except ValueError:
            pass
    if end_time is not None:
        try:
            et = datetime.fromisoformat(end_time)
            query = query.where(DiagnosisResult.created_at <= et)
        except ValueError:
            pass
    query = query.order_by(DiagnosisResult.created_at.desc())

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [DiagnosisResultResponse.model_validate(r) for r in items],
    }


@router.get("/results/{result_id}", response_model=DiagnosisResultResponse)
async def get_result(
    result_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """诊断结果详情"""
    result = await db.execute(select(DiagnosisResult).where(DiagnosisResult.id == result_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="诊断结果不存在")
    return DiagnosisResultResponse.model_validate(item)


@router.post("/analyze/{alarm_id}", response_model=dict)
async def manual_diagnose(
    alarm_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """手动触发诊断"""
    payload = await diagnosis_engine.manual_diagnose(alarm_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="告警不存在")
    return {"message": "诊断已触发", "alarm_id": alarm_id}
