"""
智能诊断 API
Story 9-3: 智能故障诊断
Story 24.6: 诊断会话、审计日志、历史查询
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from ..deps import get_db, require_admin, require_operator, require_viewer, require_diagnosis_advanced
from ...models.user import User
from ...models.diagnosis import DiagnosisRule, DiagnosisResult, DiagnosisSession, DiagnosisAuditLog, BreakerProfile
from ...models.fault_tree import FaultTree
from ...schemas.diagnosis import (
    DiagnosisRuleCreate,
    DiagnosisRuleUpdate,
    DiagnosisRuleResponse,
    DiagnosisResultResponse,
    DiagnosisCategoryItem,
    DiagnosisSessionResponse,
    DiagnosisAuditLogResponse,
    DiagnosisAnnotationCreate,
    DiagnosisAnnotationResponse,
    DiagnosisAnnotationListQuery,
    DiagnosisAnnotationStatsResponse,
    SOHWeightsConfig,
    BreakerProfileCreate,
    BreakerProfileUpdate,
    BreakerProfileResponse,
    TrendWarningListResponse,
    TrendWarningResponse,
    TrendWarningAcknowledge,
    SensorFusionRecordListResponse,
    SensorFusionRecordResponse,
    TrendConfigUpdate,
    TrendConfigResponse,
    CounterfactualAnalysisResponse,
    CounterfactualAnalysisListResponse,
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


@router.get("/fault-trees", response_model=list)
async def get_fault_trees(
    device_type: Optional[str] = Query(None, description="设备类型筛选"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取故障树列表（供概率调参页面筛选用）"""
    query = select(FaultTree.id, FaultTree.name, FaultTree.description, FaultTree.status)
    if device_type:
        query = query.where(FaultTree.name.ilike(f"%{device_type}%"))
    query = query.order_by(FaultTree.id).offset(skip).limit(limit)
    result = await db.execute(query)
    rows = result.all()
    return [{"id": row.id, "name": row.name, "description": row.description, "status": row.status} for row in rows]


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


# ==================== 健康检查 (Story 24.7) ====================


@router.get("/health")
async def diagnosis_health(_: User = Depends(require_viewer)):
    """诊断引擎健康检查（熔断器状态）"""
    try:
        from ...services.diagnosis.scheduler import get_scheduler

        scheduler = await get_scheduler()
        breaker = scheduler.circuit_breaker
        return {
            "state": breaker.state.value,
            "error_rate": round(breaker.error_rate, 4),
            "last_trip_time": breaker.last_trip_time_iso,
            "consecutive_failures": breaker.consecutive_failures,
            "total_requests_in_window": breaker.total_in_window,
            "failed_requests_in_window": breaker.failed_in_window,
            "degraded_since": breaker.degraded_since_iso,
        }
    except Exception:
        return {"state": "UNKNOWN", "error_rate": 0, "message": "Scheduler not running"}


# ==================== 诊断会话 (Story 24.6) ====================


@router.get("/sessions", response_model=dict)
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    device_id: Optional[int] = Query(None, description="设备ID"),
    engine_level: Optional[str] = Query(None, description="推理级别: L1/L2/L3"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="最低置信度"),
    start_date: Optional[str] = Query(None, description="开始时间 ISO格式"),
    end_date: Optional[str] = Query(None, description="结束时间 ISO格式"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """诊断会话列表（分页查询）"""
    query = select(DiagnosisSession)
    if device_id is not None:
        query = query.where(DiagnosisSession.device_id == device_id)
    if engine_level is not None:
        query = query.where(DiagnosisSession.engine_level == engine_level)
    if min_confidence is not None:
        query = query.where(DiagnosisSession.max_confidence >= min_confidence)
    if start_date is not None:
        try:
            sd = datetime.fromisoformat(start_date)
            query = query.where(DiagnosisSession.created_at >= sd)
        except ValueError:
            pass
    if end_date is not None:
        try:
            ed = datetime.fromisoformat(end_date)
            query = query.where(DiagnosisSession.created_at <= ed)
        except ValueError:
            pass
    query = query.order_by(DiagnosisSession.created_at.desc())

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    sessions = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [DiagnosisSessionResponse.model_validate(s) for s in sessions],
    }


@router.get("/sessions/{session_id}", response_model=DiagnosisSessionResponse)
async def get_session_detail(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """诊断会话详情（含关联的诊断结果）"""
    result = await db.execute(select(DiagnosisSession).where(DiagnosisSession.id == session_id))
    session_obj = result.scalar_one_or_none()
    if session_obj is None:
        raise HTTPException(status_code=404, detail="诊断会话不存在")

    # 查询关联的诊断结果
    result_query = await db.execute(select(DiagnosisResult).where(DiagnosisResult.session_id == session_id))
    diagnosis_result = result_query.scalar_one_or_none()

    response = DiagnosisSessionResponse.model_validate(session_obj)
    if diagnosis_result is not None:
        response.result = DiagnosisResultResponse.model_validate(diagnosis_result)
    return response


@router.get("/sessions/{session_id}/audit-log", response_model=list)
async def get_session_audit_log(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """诊断会话审计日志（需 admin 角色）"""
    # 验证会话存在
    session_result = await db.execute(select(DiagnosisSession).where(DiagnosisSession.id == session_id))
    if session_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="诊断会话不存在")

    result = await db.execute(
        select(DiagnosisAuditLog)
        .where(DiagnosisAuditLog.session_id == session_id)
        .order_by(DiagnosisAuditLog.created_at.desc())
    )
    logs = result.scalars().all()
    return [DiagnosisAuditLogResponse.model_validate(log) for log in logs]


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
    session_id: Optional[int] = Query(None, description="诊断会话ID"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="最低置信度"),
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
    if session_id is not None:
        query = query.where(DiagnosisResult.session_id == session_id)
    if min_confidence is not None:
        query = query.where(DiagnosisResult.confidence >= min_confidence)
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


# ==================== 标注管理 (Story 24.8) ====================


@router.post("/annotations", response_model=DiagnosisAnnotationResponse)
async def create_annotation(
    data: DiagnosisAnnotationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """创建诊断标注（operator+）"""
    from ...services.diagnosis.annotation_service import DiagnosisAnnotationService

    try:
        annotation = await DiagnosisAnnotationService.create_annotation(
            db=db,
            data=data,
            annotator_id=current_user.id,
        )
        return annotation
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/annotations", response_model=dict)
async def list_annotations(
    query: DiagnosisAnnotationListQuery = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """获取标注列表（operator 只能查看自己的，admin 可查看所有）"""
    from ...services.diagnosis.annotation_service import DiagnosisAnnotationService

    try:
        annotations, total = await DiagnosisAnnotationService.get_annotations(
            db=db,
            query=query,
            user_id=current_user.id,
            user_role=current_user.role,
        )
        return {
            "items": annotations,
            "total": total,
            "page": query.page,
            "page_size": query.page_size,
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.delete("/annotations/{annotation_id}", response_model=dict)
async def delete_annotation(
    annotation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """删除标注（operator 只能删除自己的，admin 可删除任何）"""
    from ...services.diagnosis.annotation_service import DiagnosisAnnotationService

    try:
        await DiagnosisAnnotationService.delete_annotation(
            db=db,
            annotation_id=annotation_id,
            user_id=current_user.id,
            user_role=current_user.role,
        )
        return {"message": "标注已删除"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/annotations/stats", response_model=DiagnosisAnnotationStatsResponse)
async def get_annotation_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
    top_n: int = Query(10, ge=1, le=50, description="Top N 标注者数量"),
):
    """获取标注统计（仅 admin）"""
    from ...services.diagnosis.annotation_service import DiagnosisAnnotationService

    stats = await DiagnosisAnnotationService.get_annotation_stats(db=db, top_n=top_n)
    return stats


# ==================== Battery SOH Endpoints (Story 25.3) ====================


@router.get("/battery-soh/{device_id}", response_model=dict)
async def get_device_soh_history(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    limit: int = Query(30, ge=1, le=100, description="返回记录数量"),
):
    """查询设备 SOH 历史记录（分页）"""
    from sqlalchemy import select, desc
    from ...models.diagnosis import BatterySOHRecord
    from ...schemas.diagnosis import BatterySOHRecordResponse

    result = await db.execute(
        select(BatterySOHRecord)
        .where(BatterySOHRecord.device_id == device_id)
        .order_by(desc(BatterySOHRecord.calculated_at))
        .limit(limit)
    )
    records = result.scalars().all()

    return {
        "device_id": device_id,
        "total": len(records),
        "records": [BatterySOHRecordResponse.model_validate(r) for r in records],
    }


@router.get("/battery-soh/latest", response_model=dict)
async def get_all_latest_soh(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """查询所有 UPS 设备最新 SOH（使用窗口函数优化）"""
    from sqlalchemy import text

    # 使用窗口函数获取每台设备最新的 SOH 记录
    query = text("""
        WITH ranked_soh AS (
            SELECT
                device_id,
                soh_percent,
                resistance_mohm,
                cycle_count,
                weights_version,
                calculated_at,
                ROW_NUMBER() OVER (PARTITION BY device_id ORDER BY calculated_at DESC) AS rn
            FROM battery_soh_records
        )
        SELECT
            device_id,
            soh_percent,
            resistance_mohm,
            cycle_count,
            weights_version,
            calculated_at
        FROM ranked_soh
        WHERE rn = 1
        ORDER BY device_id
    """)

    result = await db.execute(query)
    rows = result.fetchall()

    records = [
        {
            "device_id": row[0],
            "soh_percent": row[1],
            "resistance_mohm": row[2],
            "cycle_count": row[3],
            "weights_version": row[4],
            "calculated_at": row[5],
        }
        for row in rows
    ]

    return {"total": len(records), "records": records}


@router.post("/battery-soh/calculate/{device_id}", response_model=dict)
async def trigger_soh_calculation(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """手动触发 SOH 计算（operator/admin）"""
    from ...services.diagnosis.battery_soh_service import calculate_soh

    soh = await calculate_soh(device_id)

    if soh is None:
        raise HTTPException(
            status_code=400,
            detail=f"设备 {device_id} SOH 计算失败，请检查设备配置和点位数据",
        )

    return {"device_id": device_id, "soh_percent": soh, "message": "SOH 计算完成"}


@router.get("/config/soh-weights", response_model=SOHWeightsConfig)
async def get_soh_weights_config(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取 SOH 权重配置"""
    from ...services.diagnosis.battery_soh_service import get_soh_weights

    weights = await get_soh_weights()
    return SOHWeightsConfig(**weights)


@router.put("/config/soh-weights", response_model=dict)
async def update_soh_weights_config(
    config: SOHWeightsConfig,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """更新 SOH 权重配置（仅 admin）"""
    from sqlalchemy import select, update
    from ...models.config import SystemConfig
    import json

    # 查询现有配置
    result = await db.execute(
        select(SystemConfig)
        .where(SystemConfig.config_group == "diagnosis")
        .where(SystemConfig.config_key == "soh_weights")
    )
    existing_config = result.scalar_one_or_none()

    if not existing_config:
        raise HTTPException(status_code=404, detail="SOH 权重配置不存在")

    # 更新配置
    new_value = config.model_dump()
    await db.execute(
        update(SystemConfig).where(SystemConfig.id == existing_config.id).values(config_value=json.dumps(new_value))
    )
    await db.commit()

    return {"message": "SOH 权重配置已更新", "config": new_value}


# ==================== 断路器配置管理 - Story 25.4 ====================


@router.post("/breaker-profiles", response_model=dict, status_code=201)
async def create_breaker_profile(
    profile: BreakerProfileCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """创建断路器配置"""
    from ...models.diagnosis import BreakerProfile
    from ...models.energy import PowerDevice

    # 验证设备存在
    device = await db.get(PowerDevice, profile.breaker_device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"设备 {profile.breaker_device_id} 不存在")

    # 检查是否已存在配置
    result = await db.execute(
        select(BreakerProfile).where(BreakerProfile.breaker_device_id == profile.breaker_device_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail=f"设备 {profile.breaker_device_id} 已存在断路器配置")

    # 创建配置
    new_profile = BreakerProfile(
        breaker_device_id=profile.breaker_device_id,
        trip_curve_type=profile.trip_curve_type,
        rated_current=profile.rated_current,
    )
    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    return {"message": "断路器配置创建成功", "id": new_profile.id}


@router.get("/breaker-profiles", response_model=dict)
async def list_breaker_profiles(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """断路器配置列表"""
    # 查询总数
    count_result = await db.execute(select(func.count(BreakerProfile.id)))
    total = count_result.scalar()

    # 分页查询
    result = await db.execute(select(BreakerProfile).offset((page - 1) * page_size).limit(page_size))
    profiles = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [BreakerProfileResponse.model_validate(p) for p in profiles],
    }


@router.get("/breaker-profiles/{profile_id}", response_model=BreakerProfileResponse)
async def get_breaker_profile(
    profile_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取断路器配置详情"""
    profile = await db.get(BreakerProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="断路器配置不存在")

    return BreakerProfileResponse.model_validate(profile)


@router.put("/breaker-profiles/{profile_id}", response_model=dict)
async def update_breaker_profile(
    profile_id: int,
    profile_update: BreakerProfileUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """更新断路器配置"""
    from ...models.diagnosis import BreakerProfile

    profile = await db.get(BreakerProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="断路器配置不存在")

    # 更新字段
    update_data = profile_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)

    return {"message": "断路器配置更新成功"}


@router.delete("/breaker-profiles/{profile_id}", response_model=dict)
async def delete_breaker_profile(
    profile_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """删除断路器配置"""
    from ...models.diagnosis import BreakerProfile

    profile = await db.get(BreakerProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="断路器配置不存在")

    await db.delete(profile)
    await db.commit()

    return {"message": "断路器配置删除成功"}


# ==================== Story 25.7: 趋势分析与多传感器融合 API ====================


@router.get("/trend-warnings", response_model=TrendWarningListResponse)
async def get_trend_warnings(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    point_id: Optional[int] = Query(None, description="点位ID过滤"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    acknowledged: Optional[bool] = Query(None, description="是否已确认"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """查询趋势预警列表（分页）"""
    from ...models.diagnosis import TrendWarning
    from ...schemas.diagnosis import TrendWarningListResponse, TrendWarningResponse

    # 构建查询
    query = select(TrendWarning)

    # 应用过滤条件
    if point_id:
        query = query.where(TrendWarning.point_id == point_id)
    if start_time:
        query = query.where(TrendWarning.detected_at >= start_time)
    if end_time:
        query = query.where(TrendWarning.detected_at <= end_time)
    if acknowledged is not None:
        query = query.where(TrendWarning.acknowledged == acknowledged)

    # 计算总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 分页查询
    query = query.order_by(TrendWarning.detected_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    warnings = result.scalars().all()

    return TrendWarningListResponse(
        total=total, page=page, page_size=page_size, items=[TrendWarningResponse.model_validate(w) for w in warnings]
    )


@router.post("/trend-warnings/{warning_id}/acknowledge", response_model=dict)
async def acknowledge_trend_warning(
    warning_id: int,
    request: TrendWarningAcknowledge,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """确认趋势预警"""
    from ...models.diagnosis import TrendWarning
    from ...schemas.diagnosis import TrendWarningAcknowledge

    warning = await db.get(TrendWarning, warning_id)
    if not warning:
        raise HTTPException(status_code=404, detail="趋势预警不存在")

    if warning.acknowledged:
        raise HTTPException(status_code=400, detail="趋势预警已确认")

    warning.acknowledged = True
    warning.acknowledged_by = request.acknowledged_by
    warning.acknowledged_at = datetime.now()

    await db.commit()

    return {"message": "趋势预警确认成功", "warning_id": warning_id}


@router.get("/sensor-fusion", response_model=SensorFusionRecordListResponse)
async def get_sensor_fusion_records(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    zone_id: Optional[int] = Query(None, description="区域ID过滤"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """查询多传感器融合记录列表（分页）"""
    from ...models.diagnosis import SensorFusionRecord
    from ...schemas.diagnosis import SensorFusionRecordListResponse, SensorFusionRecordResponse

    # 构建查询
    query = select(SensorFusionRecord)

    # 应用过滤条件
    if zone_id:
        query = query.where(SensorFusionRecord.zone_id == zone_id)
    if start_time:
        query = query.where(SensorFusionRecord.created_at >= start_time)
    if end_time:
        query = query.where(SensorFusionRecord.created_at <= end_time)

    # 计算总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 分页查询
    query = query.order_by(SensorFusionRecord.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    records = result.scalars().all()

    return SensorFusionRecordListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[SensorFusionRecordResponse.model_validate(r) for r in records],
    )


@router.get("/trend-config", response_model=TrendConfigResponse)
async def get_trend_config(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取趋势阈值配置"""
    from ...models import SystemConfig
    from ...schemas.diagnosis import TrendConfigResponse

    # 查询配置
    result = await db.execute(
        select(SystemConfig).where(
            SystemConfig.config_group == "diagnosis",
            SystemConfig.config_key.in_(
                [
                    "trend_threshold_temperature",
                    "trend_threshold_humidity",
                    "airflow_variance_threshold",
                    "trend_analysis_enabled",
                    "sensor_fusion_enabled",
                ]
            ),
        )
    )
    configs = {c.config_key: c.config_value for c in result.scalars().all()}

    return TrendConfigResponse(
        trend_threshold_temperature=float(configs.get("trend_threshold_temperature", "0.5")),
        trend_threshold_humidity=float(configs.get("trend_threshold_humidity", "3.0")),
        airflow_variance_threshold=float(configs.get("airflow_variance_threshold", "5.0")),
        trend_analysis_enabled=configs.get("trend_analysis_enabled", "true").lower() == "true",
        sensor_fusion_enabled=configs.get("sensor_fusion_enabled", "true").lower() == "true",
    )


@router.put("/trend-config", response_model=dict)
async def update_trend_config(
    request: TrendConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """更新趋势阈值配置"""
    from ...models import SystemConfig
    from ...schemas.diagnosis import TrendConfigUpdate

    # 更新配置
    updates = {}
    if request.trend_threshold_temperature is not None:
        updates["trend_threshold_temperature"] = str(request.trend_threshold_temperature)
    if request.trend_threshold_humidity is not None:
        updates["trend_threshold_humidity"] = str(request.trend_threshold_humidity)
    if request.airflow_variance_threshold is not None:
        updates["airflow_variance_threshold"] = str(request.airflow_variance_threshold)
    if request.trend_analysis_enabled is not None:
        updates["trend_analysis_enabled"] = "true" if request.trend_analysis_enabled else "false"
    if request.sensor_fusion_enabled is not None:
        updates["sensor_fusion_enabled"] = "true" if request.sensor_fusion_enabled else "false"

    for key, value in updates.items():
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.config_group == "diagnosis", SystemConfig.config_key == key)
        )
        config = result.scalar_one_or_none()

        if config:
            config.config_value = value
        else:
            # 如果配置不存在，创建新配置
            config = SystemConfig(
                config_group="diagnosis",
                config_key=key,
                config_value=value,
                value_type="number" if key.endswith("threshold") else "boolean",
                description=f"趋势分析配置: {key}",
            )
            db.add(config)

    await db.commit()

    return {"message": "趋势阈值配置更新成功", "updated_keys": list(updates.keys())}


# ==================== Counterfactual Analysis Endpoints - Story 26.1 ====================


@router.post("/counterfactual/{session_id}", response_model=dict)
async def trigger_counterfactual_analysis(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
    top_n: int = Query(5, ge=1, le=10, description="分析Top N证据"),
):
    """手动触发反事实分析（operator/admin）"""
    from ...services.diagnosis.counterfactual_service import analyze_counterfactual

    # 检查会话是否存在
    from ...models.diagnosis import DiagnosisSession

    session_result = await db.execute(select(DiagnosisSession).where(DiagnosisSession.id == session_id))
    if not session_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="诊断会话不存在")

    # 触发分析
    analysis = await analyze_counterfactual(session_id, top_n, db)

    if not analysis:
        raise HTTPException(status_code=400, detail=f"会话 {session_id} 反事实分析失败，请检查会话状态和证据数据")

    return {
        "message": "反事实分析完成",
        "session_id": session_id,
        "analysis_id": analysis.id,
        "analysis_time_ms": analysis.analysis_time_ms,
    }


@router.get("/counterfactual/{session_id}", response_model=CounterfactualAnalysisResponse)
async def get_counterfactual_analysis(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_diagnosis_advanced),
):
    """
    获取反事实分析结果

    权限要求: diagnosis:view_advanced (admin, operator)
    """
    from ...services.diagnosis.counterfactual_service import get_counterfactual_analysis as get_analysis
    from ...models.diagnosis import CounterfactualAnalysis

    analysis = await get_analysis(session_id, db)

    if not analysis:
        raise HTTPException(status_code=404, detail="反事实分析不存在")

    return CounterfactualAnalysisResponse.model_validate(analysis)


@router.get("/counterfactual/{session_id}/progress")
async def get_counterfactual_progress(
    session_id: int,
    _: User = Depends(require_diagnosis_advanced),
):
    """
    SSE 进度推送端点

    返回反事实分析的实时进度

    权限要求: diagnosis:view_advanced (admin)
    """
    from fastapi.responses import StreamingResponse
    from ...services.diagnosis.counterfactual_service import stream_counterfactual_progress

    return StreamingResponse(
        stream_counterfactual_progress(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )


@router.get("/counterfactual", response_model=CounterfactualAnalysisListResponse)
async def list_counterfactual_analyses(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="最低原始置信度"),
    start_date: Optional[str] = Query(None, description="开始时间 ISO格式"),
    end_date: Optional[str] = Query(None, description="结束时间 ISO格式"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """反事实分析列表（分页查询）"""
    from ...models.diagnosis import CounterfactualAnalysis

    query = select(CounterfactualAnalysis).where(CounterfactualAnalysis.deleted_at.is_(None))

    if min_confidence is not None:
        query = query.where(CounterfactualAnalysis.original_confidence >= min_confidence)
    if start_date is not None:
        try:
            sd = datetime.fromisoformat(start_date)
            query = query.where(CounterfactualAnalysis.created_at >= sd)
        except ValueError:
            pass
    if end_date is not None:
        try:
            ed = datetime.fromisoformat(end_date)
            query = query.where(CounterfactualAnalysis.created_at <= ed)
        except ValueError:
            pass

    query = query.order_by(CounterfactualAnalysis.created_at.desc())

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    analyses = result.scalars().all()

    return CounterfactualAnalysisListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[CounterfactualAnalysisResponse.model_validate(a) for a in analyses],
    )


@router.delete("/counterfactual/{session_id}", response_model=dict)
async def delete_counterfactual_analysis(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """软删除反事实分析（仅 admin）"""
    from ...services.diagnosis.counterfactual_service import get_counterfactual_analysis as get_analysis

    analysis = await get_analysis(session_id, db)

    if not analysis:
        raise HTTPException(status_code=404, detail="反事实分析不存在")

    # 软删除
    analysis.deleted_at = datetime.now()
    await db.commit()

    return {"message": "反事实分析已删除", "session_id": session_id}


# ==================== Misdiagnosis Report Endpoints - Story 26.2 ====================


@router.get("/reports/misdiagnosis", response_model=dict)
async def get_misdiagnosis_report(
    period: Optional[str] = Query(None, description="报告周期 YYYY-MM，默认为上月"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    查询误诊分析报告

    权限要求: diagnosis:view_reports (仅 admin)
    """
    from ...models.diagnosis import SystemReport
    from ...schemas.system_report import SystemReportInfo

    # 如果未指定周期，默认为上月
    if not period:
        now = datetime.now()
        if now.month == 1:
            period = f"{now.year - 1}-12"
        else:
            period = f"{now.year}-{now.month - 1:02d}"

    # 查询报告
    result = await db.execute(
        select(SystemReport).where(
            SystemReport.report_type == "misdiagnosis_monthly",
            SystemReport.report_period == period,
            SystemReport.deleted_at.is_(None),
        )
    )
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail=f"报告不存在: period={period}，请先生成报告")

    return SystemReportInfo.model_validate(report).model_dump()


@router.post("/reports/misdiagnosis/generate", response_model=dict)
async def generate_misdiagnosis_report(
    period: str = Query(..., description="报告周期 YYYY-MM"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    手动生成误诊分析报告

    权限要求: diagnosis:manage_reports (仅 admin)
    """
    from ...services.diagnosis.misdiagnosis_report_service import MisdiagnosisReportService

    # 生成报告
    report = await MisdiagnosisReportService.generate_monthly_report(period, db)

    if not report:
        raise HTTPException(status_code=400, detail=f"报告生成失败: period={period}，可能是数据不足或获取锁失败")

    return {
        "status": "success",
        "message": "报告生成任务已完成",
        "report_id": report.id,
        "note": "如果报告已存在，将返回已存在报告的ID",
    }


@router.get("/reports/misdiagnosis/export")
async def export_misdiagnosis_report(
    period: str = Query(..., description="报告周期 YYYY-MM"),
    format: str = Query("pdf", description="导出格式: pdf"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    导出误诊分析报告为 PDF

    权限要求: diagnosis:view_reports (仅 admin)
    """
    from ...models.diagnosis import SystemReport
    from fastapi.responses import Response

    # 查询报告
    result = await db.execute(
        select(SystemReport).where(
            SystemReport.report_type == "misdiagnosis_monthly",
            SystemReport.report_period == period,
            SystemReport.deleted_at.is_(None),
        )
    )
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail=f"报告不存在: period={period}")

    if format == "pdf":
        try:
            from weasyprint import HTML
            import io

            # 将 Markdown 转换为 HTML
            import markdown

            html_content = markdown.markdown(report.content, extensions=["tables"])

            # 添加 CSS 样式
            styled_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                    h1 {{ color: #333; }}
                    h2 {{ color: #666; margin-top: 30px; }}
                </style>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """

            # 生成 PDF
            pdf_buffer = io.BytesIO()
            HTML(string=styled_html).write_pdf(pdf_buffer)
            pdf_buffer.seek(0)

            return Response(
                content=pdf_buffer.read(),
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=误诊分析报告-{period}.pdf"},
            )
        except ImportError:
            raise HTTPException(status_code=500, detail="PDF 导出功能未安装，请安装 weasyprint 和 markdown 库")
        except Exception as e:
            logger.error("PDF 导出失败: %s", e)
            raise HTTPException(status_code=500, detail=f"PDF 导出失败: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail=f"不支持的导出格式: {format}")


# ============================================================
# 概率调参 API - Story 26.3
# 注意: 完整实现已迁移至 probability_tuning.py（含乐观锁、版本管理、WebSocket 通知）
# ============================================================


# ============================================================
# 时间窗口调参 API - Story 26.4
# ============================================================


@router.post("/time-window-tuning/analyze", dependencies=[Depends(require_admin)])
async def analyze_time_window_tuning(
    device_type: Optional[str] = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)
):
    """
    手动触发时间窗口调参分析

    权限: admin
    """
    from ...services.diagnosis.time_window_tuning_service import TimeWindowTuningService

    tuning_service = TimeWindowTuningService()

    try:
        result = await tuning_service.analyze_all_device_types(device_type)
        logger.info(f"时间窗口调参分析完成: {result}, 用户: {current_user.username}")
        return result
    except Exception as e:
        logger.error(f"时间窗口调参分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"调参分析失败: {str(e)}")


@router.get("/time-window-tuning/adjustments", dependencies=[Depends(require_admin)])
async def get_time_window_adjustments(
    device_type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    查询时间窗口调参记录列表

    权限: admin
    """
    from ...models.diagnosis import TimeWindowAdjustmentLog

    # 构建查询条件
    conditions = []
    if device_type:
        conditions.append(TimeWindowAdjustmentLog.device_type == device_type)
    if status:
        conditions.append(TimeWindowAdjustmentLog.status == status)

    # 查询总数
    count_query = select(func.count(TimeWindowAdjustmentLog.id))
    if conditions:
        count_query = count_query.where(*conditions)
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 查询记录
    query = select(TimeWindowAdjustmentLog)
    if conditions:
        query = query.where(*conditions)
    query = query.order_by(TimeWindowAdjustmentLog.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    adjustments = result.scalars().all()

    return {"items": adjustments, "total": total, "page": page, "page_size": page_size}


@router.post("/time-window-tuning/adjustments/{adjustment_id}/approve", dependencies=[Depends(require_admin)])
async def approve_time_window_adjustment(
    adjustment_id: int,
    body: Optional[dict] = Body(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    审批时间窗口调参建议

    权限: admin
    """
    from ...models.diagnosis import TimeWindowAdjustmentLog
    from ...models.config import SystemConfig
    import json

    reason = body.get("reason") if body else None

    # 查询调参记录
    result = await db.execute(select(TimeWindowAdjustmentLog).where(TimeWindowAdjustmentLog.id == adjustment_id))
    adjustment = result.scalar_one_or_none()

    if not adjustment:
        raise HTTPException(status_code=404, detail="调参记录不存在")

    if adjustment.status != "pending":
        raise HTTPException(status_code=409, detail=f"调参记录已被其他管理员处理，当前状态为 {adjustment.status}")

    # 使用数据库事务确保原子性
    try:
        # 更新调参记录状态（使用乐观锁）
        update_result = await db.execute(
            select(TimeWindowAdjustmentLog)
            .where(
                and_(
                    TimeWindowAdjustmentLog.id == adjustment_id,
                    TimeWindowAdjustmentLog.version == adjustment.version,
                    TimeWindowAdjustmentLog.status == "pending",
                )
            )
            .with_for_update()
        )
        locked_adjustment = update_result.scalar_one_or_none()

        if not locked_adjustment:
            raise HTTPException(status_code=409, detail="调参记录已被其他用户修改，请刷新后重试")

        # 更新状态
        locked_adjustment.status = "approved"
        locked_adjustment.reason = reason
        locked_adjustment.approved_by = current_user.id
        locked_adjustment.approved_at = datetime.now()

        # 更新 system_configs 表中的时间窗口配置
        config_result = await db.execute(
            select(SystemConfig).where(SystemConfig.config_key == "diagnosis_time_windows")
        )
        config = config_result.scalar_one_or_none()

        if config:
            # 更新现有配置
            time_windows = (
                json.loads(config.config_value) if isinstance(config.config_value, str) else config.config_value
            )
            time_windows[locked_adjustment.device_type] = locked_adjustment.proposed_window_minutes
            config.config_value = json.dumps(time_windows)
        else:
            # 创建新配置
            config = SystemConfig(
                config_key="diagnosis_time_windows",
                config_value=json.dumps({locked_adjustment.device_type: locked_adjustment.proposed_window_minutes}),
                description="诊断时间窗口配置（分钟）",
            )
            db.add(config)

        # 记录审计日志（在同一事务中）
        from ...models.diagnosis import AuditLog

        audit_log = AuditLog(
            user_id=current_user.id,
            action="approve_time_window_adjustment",
            resource_type="time_window_adjustment",
            resource_id=adjustment_id,
            details=f"审批时间窗口调参: {locked_adjustment.device_type}, {locked_adjustment.current_window_minutes} -> {locked_adjustment.proposed_window_minutes} 分钟",
        )
        db.add(audit_log)

        await db.commit()

        logger.info(f"时间窗口调参已审批: {adjustment_id}, 用户: {current_user.username}")

        # 发送 WebSocket 通知给所有管理员
        try:
            from ...services.websocket import ws_manager

            await ws_manager.broadcast_diagnosis(
                msg_type="time_window_adjustment_updated",
                data={
                    "adjustment_id": adjustment_id,
                    "device_type": locked_adjustment.device_type,
                    "status": "approved",
                    "approved_by": current_user.username,
                },
                target_roles=["admin"],
            )
        except Exception as ws_error:
            logger.error(f"发送 WebSocket 通知失败: {ws_error}", exc_info=True)

        return {
            "message": "时间窗口调整已审批，配置已更新",
            "adjustment_id": adjustment_id,
            "device_type": locked_adjustment.device_type,
            "new_window_minutes": locked_adjustment.proposed_window_minutes,
        }

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"审批时间窗口调参失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"审批失败: {str(e)}")


@router.post("/time-window-tuning/adjustments/{adjustment_id}/reject", dependencies=[Depends(require_admin)])
async def reject_time_window_adjustment(
    adjustment_id: int, body: dict = Body(...), db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)
):
    """
    拒绝时间窗口调参建议

    权限: admin
    """
    from ...models.diagnosis import TimeWindowAdjustmentLog

    reason = body.get("reason") if body else None

    # 查询调参记录
    result = await db.execute(select(TimeWindowAdjustmentLog).where(TimeWindowAdjustmentLog.id == adjustment_id))
    adjustment = result.scalar_one_or_none()

    if not adjustment:
        raise HTTPException(status_code=404, detail="调参记录不存在")

    if adjustment.status != "pending":
        raise HTTPException(status_code=409, detail=f"调参记录已被其他管理员处理，当前状态为 {adjustment.status}")

    # 更新状态
    adjustment.status = "rejected"
    adjustment.reason = reason
    adjustment.approved_by = current_user.id
    adjustment.approved_at = datetime.now()

    await db.commit()

    logger.info(f"时间窗口调参记录 {adjustment_id} 已拒绝，用户: {current_user.username}")

    # 发送 WebSocket 通知给所有管理员
    try:
        from ...services.websocket import ws_manager

        await ws_manager.broadcast_diagnosis(
            msg_type="time_window_adjustment_updated",
            data={
                "adjustment_id": adjustment_id,
                "device_type": adjustment.device_type,
                "status": "rejected",
                "rejected_by": current_user.username,
            },
            target_roles=["admin"],
        )
    except Exception as ws_error:
        logger.error(f"发送 WebSocket 通知失败: {ws_error}", exc_info=True)

    return {"message": "时间窗口调整已拒绝", "adjustment_id": adjustment_id}


@router.get("/time-window-tuning/config", dependencies=[Depends(require_admin)])
async def get_time_window_config(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
    """
    查询当前时间窗口配置

    权限: admin
    """
    from ...models.config import SystemConfig
    import json

    result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == "diagnosis_time_windows"))
    config = result.scalar_one_or_none()

    if config and config.config_value:
        try:
            time_windows = (
                json.loads(config.config_value) if isinstance(config.config_value, str) else config.config_value
            )
            return {"time_windows": time_windows}
        except json.JSONDecodeError:
            return {"time_windows": {}}

    return {"time_windows": {}}


@router.put("/time-window-tuning/config", dependencies=[Depends(require_admin)])
async def update_time_window_config(
    device_type: str,
    time_window_minutes: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    手动更新时间窗口配置

    权限: admin
    """
    from ...models.config import SystemConfig
    import json

    if time_window_minutes < 1 or time_window_minutes > 120:
        raise HTTPException(status_code=400, detail="时间窗口必须在 1-120 分钟之间")

    # 查询配置
    result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == "diagnosis_time_windows"))
    config = result.scalar_one_or_none()

    if config:
        # 更新现有配置
        time_windows = json.loads(config.config_value) if isinstance(config.config_value, str) else config.config_value
        time_windows[device_type] = time_window_minutes
        config.config_value = json.dumps(time_windows)
    else:
        # 创建新配置
        config = SystemConfig(
            config_key="diagnosis_time_windows",
            config_value=json.dumps({device_type: time_window_minutes}),
            description="诊断时间窗口配置（分钟）",
        )
        db.add(config)

    await db.commit()

    # 记录审计日志
    from ...models.diagnosis import AuditLog

    audit_log = AuditLog(
        user_id=current_user.id,
        action="update_time_window_config",
        resource_type="time_window_config",
        resource_id=None,
        details=f"手动更新时间窗口配置: {device_type} = {time_window_minutes} 分钟",
    )
    db.add(audit_log)
    await db.commit()

    logger.info(f"时间窗口配置已更新: {device_type} = {time_window_minutes} 分钟, 用户: {current_user.username}")

    return {"message": "配置已更新", "device_type": device_type, "time_window_minutes": time_window_minutes}


# ============================================================
# 训练数据异常检测 API - Story 26.9
# ============================================================


@router.get("/training-audit", summary="查询训练数据异常检测历史")
async def list_training_audits(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(require_admin),
):
    """查询训练数据异常检测历史报告（仅管理员可访问）"""
    try:
        from app.services.diagnosis.training_data_audit_service import training_data_audit_service

        result = await training_data_audit_service.list_audits(page, page_size)
        return {"code": 200, "message": "success", "data": result}
    except Exception as e:
        logger.error(f"查询训练数据审计历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {e}")


# ============================================================
# HMAC 密钥管理 API - Story 26.10
# ============================================================


@router.get("/hmac-key/status", summary="查询 HMAC 密钥状态")
async def get_hmac_key_status(
    _: User = Depends(require_admin),
):
    """查询当前 HMAC 密钥配置状态和活跃版本统计（仅管理员可访问）"""
    try:
        from app.services.diagnosis.hmac_key_service import hmac_key_service

        result = await hmac_key_service.get_key_status()
        return {"code": 200, "message": "success", "data": result}
    except Exception as e:
        logger.error(f"查询 HMAC 密钥状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {e}")


@router.post("/hmac-key/rotate", summary="执行 HMAC 密钥轮换")
async def rotate_hmac_key(
    body: dict,
    current_user: User = Depends(require_admin),
):
    """用新密钥对所有活跃/已审核版本重新签名（仅管理员可访问）"""
    new_key = body.get("new_key")
    if not new_key or not isinstance(new_key, str):
        raise HTTPException(status_code=400, detail="请提供 new_key 参数")
    if len(new_key) < 32:
        raise HTTPException(status_code=400, detail="新密钥长度必须 >= 32 字符")

    try:
        from app.services.diagnosis.hmac_key_service import hmac_key_service

        result = await hmac_key_service.rotate_key(new_key, current_user.id)
        return {"code": 200, "message": "密钥轮换成功", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"HMAC 密钥轮换失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"轮换失败: {e}")


@router.post("/hmac-key/verify-all", summary="批量验证签名完整性")
async def verify_all_signatures(
    _: User = Depends(require_admin),
):
    """验证所有活跃/已审核故障树版本的 HMAC 签名（仅管理员可访问）"""
    try:
        from app.services.diagnosis.hmac_key_service import hmac_key_service

        result = await hmac_key_service.verify_all_signatures()
        return {"code": 200, "message": "success", "data": result}
    except Exception as e:
        logger.error(f"批量验证签名失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"验证失败: {e}")


@router.get("/hmac-key/rotation-logs", summary="查询密钥轮换历史")
async def list_rotation_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(require_admin),
):
    """查询 HMAC 密钥轮换历史记录（仅管理员可访问）"""
    try:
        from app.services.diagnosis.hmac_key_service import hmac_key_service

        result = await hmac_key_service.list_rotation_logs(page, page_size)
        return {"code": 200, "message": "success", "data": result}
    except Exception as e:
        logger.error(f"查询密钥轮换历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {e}")
