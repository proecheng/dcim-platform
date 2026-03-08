"""
系统配置 API - v1
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import json
import io

from ..deps import get_db, require_viewer, require_admin
from ...models.user import User
from ...models.config import SystemConfig, Dictionary, License
from ...schemas.config import SystemConfigInfo, SystemConfigUpdate, DictionaryInfo, LicenseInfo, LicenseActivate
from ...core.cache_headers import set_cache_headers, CACHE_LONG

router = APIRouter()


@router.get("", summary="获取系统配置")
async def get_configs(
    group: Optional[str] = Query(None, description="配置分组"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    获取系统配置列表
    """
    query = select(SystemConfig)
    if group:
        query = query.where(SystemConfig.config_group == group)

    result = await db.execute(query.order_by(SystemConfig.config_group, SystemConfig.config_key))
    configs = result.scalars().all()

    # 按分组整理
    grouped = {}
    for config in configs:
        if config.config_group not in grouped:
            grouped[config.config_group] = []
        grouped[config.config_group].append(SystemConfigInfo.model_validate(config))

    return grouped


@router.put("", summary="更新系统配置")
async def update_configs(
    data: list[SystemConfigUpdate], db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)
):
    """
    批量更新系统配置
    """
    updated_count = 0
    for item in data:
        result = await db.execute(
            select(SystemConfig).where(
                SystemConfig.config_group == item.config_group, SystemConfig.config_key == item.config_key
            )
        )
        config = result.scalar_one_or_none()

        if config:
            if not config.is_editable:
                continue

            await db.execute(
                update(SystemConfig)
                .where(SystemConfig.id == config.id)
                .values(config_value=item.config_value, updated_by=current_user.id, updated_at=datetime.now())
            )
            updated_count += 1
        else:
            # 新建配置
            new_config = SystemConfig(
                config_group=item.config_group,
                config_key=item.config_key,
                config_value=item.config_value,
                value_type=item.value_type or "string",
                description=item.description,
                updated_by=current_user.id,
            )
            db.add(new_config)
            updated_count += 1

    await db.commit()
    return {"message": f"已更新 {updated_count} 项配置"}


@router.get("/dictionaries", summary="获取数据字典")
async def get_dictionaries(
    response: Response,
    dict_type: Optional[str] = Query(None, description="字典类型"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """
    获取数据字典
    """
    query = select(Dictionary).where(Dictionary.is_enabled == True)
    if dict_type:
        query = query.where(Dictionary.dict_type == dict_type)

    result = await db.execute(query.order_by(Dictionary.dict_type, Dictionary.sort_order))
    dictionaries = result.scalars().all()

    # 按类型分组
    grouped = {}
    for d in dictionaries:
        if d.dict_type not in grouped:
            grouped[d.dict_type] = []
        grouped[d.dict_type].append(DictionaryInfo.model_validate(d))

    set_cache_headers(response, CACHE_LONG)
    return grouped


@router.get("/license", response_model=LicenseInfo, summary="获取授权信息")
async def get_license(db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)):
    """
    获取当前授权信息
    """
    result = await db.execute(select(License).where(License.is_active == True).order_by(License.activated_at.desc()))
    license = result.scalars().first()

    if not license:
        # 返回默认试用授权
        return LicenseInfo(
            id=0,
            license_key="TRIAL",
            license_type="trial",
            max_points=50,
            features=["basic"],
            issue_date=None,
            expire_date=None,
            is_active=True,
            status="trial",
        )

    # 检查是否过期
    status = "active"
    if license.expire_date and license.expire_date < datetime.now().date():
        status = "expired"

    return LicenseInfo(
        id=license.id,
        license_key=license.license_key[:8] + "****",  # 隐藏部分密钥
        license_type=license.license_type,
        max_points=license.max_points,
        features=json.loads(license.features) if license.features else [],
        issue_date=license.issue_date,
        expire_date=license.expire_date,
        is_active=license.is_active,
        activated_at=license.activated_at,
        status=status,
    )


@router.post("/license/activate", summary="激活授权")
async def activate_license(data: LicenseActivate, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    """
    激活授权许可
    """
    # 简单的许可证验证逻辑（实际应该对接许可证服务器）
    license_key = data.license_key.strip().upper()

    # 检查许可证格式
    if len(license_key) < 16:
        raise HTTPException(status_code=400, detail="无效的许可证密钥")

    # 检查是否已使用
    result = await db.execute(select(License).where(License.license_key == license_key))
    existing = result.scalar_one_or_none()
    if existing:
        if existing.is_active:
            raise HTTPException(status_code=400, detail="该许可证已激活")
        else:
            # 重新激活
            await db.execute(
                update(License).where(License.id == existing.id).values(is_active=True, activated_at=datetime.now())
            )
            await db.commit()
            return {"message": "许可证已重新激活", "license_type": existing.license_type}

    # 根据密钥前缀判断类型（简化逻辑）
    if license_key.startswith("ENT"):
        license_type = "enterprise"
        max_points = 500
        features = ["all", "api", "multi_user"]
    elif license_key.startswith("STD"):
        license_type = "standard"
        max_points = 100
        features = ["all"]
    elif license_key.startswith("BSC"):
        license_type = "basic"
        max_points = 50
        features = ["basic"]
    else:
        license_type = "standard"
        max_points = 100
        features = ["all"]

    # 禁用旧的许可证
    await db.execute(update(License).values(is_active=False))

    # 创建新许可证
    from datetime import date

    new_license = License(
        license_key=license_key,
        license_type=license_type,
        max_points=max_points,
        features=json.dumps(features),
        issue_date=date.today(),
        expire_date=date(date.today().year + 1, date.today().month, date.today().day),  # 一年有效期
        hardware_id=data.hardware_id,
        is_active=True,
        activated_at=datetime.now(),
    )
    db.add(new_license)
    await db.commit()

    return {
        "message": "许可证激活成功",
        "license_type": license_type,
        "max_points": max_points,
        "expire_date": new_license.expire_date.isoformat(),
    }


@router.get("/backup", summary="导出系统配置")
async def backup_configs(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    """
    导出系统配置备份
    """
    # 导出配置
    configs_result = await db.execute(select(SystemConfig))
    configs = configs_result.scalars().all()

    # 导出字典
    dicts_result = await db.execute(select(Dictionary))
    dicts = dicts_result.scalars().all()

    backup_data = {
        "backup_time": datetime.now().isoformat(),
        "version": "2.0",
        "configs": [
            {
                "group": c.config_group,
                "key": c.config_key,
                "value": c.config_value,
                "type": c.value_type,
                "description": c.description,
            }
            for c in configs
        ],
        "dictionaries": [
            {"type": d.dict_type, "code": d.dict_code, "name": d.dict_name, "value": d.dict_value, "sort": d.sort_order}
            for d in dicts
        ],
    }

    content = json.dumps(backup_data, ensure_ascii=False, indent=2)
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=system_backup.json"},
    )


@router.post("/restore", summary="导入系统配置")
async def restore_configs(
    backup_data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)
):
    """
    从备份恢复系统配置
    """
    restored_configs = 0
    restored_dicts = 0

    # 恢复配置
    for config in backup_data.get("configs", []):
        result = await db.execute(
            select(SystemConfig).where(
                SystemConfig.config_group == config["group"], SystemConfig.config_key == config["key"]
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            await db.execute(
                update(SystemConfig)
                .where(SystemConfig.id == existing.id)
                .values(config_value=config["value"], updated_by=current_user.id, updated_at=datetime.now())
            )
        else:
            new_config = SystemConfig(
                config_group=config["group"],
                config_key=config["key"],
                config_value=config["value"],
                value_type=config.get("type", "string"),
                description=config.get("description"),
                updated_by=current_user.id,
            )
            db.add(new_config)
        restored_configs += 1

    # 恢复字典
    for d in backup_data.get("dictionaries", []):
        result = await db.execute(
            select(Dictionary).where(Dictionary.dict_type == d["type"], Dictionary.dict_code == d["code"])
        )
        existing = result.scalar_one_or_none()

        if not existing:
            new_dict = Dictionary(
                dict_type=d["type"],
                dict_code=d["code"],
                dict_name=d["name"],
                dict_value=d.get("value"),
                sort_order=d.get("sort", 0),
            )
            db.add(new_dict)
            restored_dicts += 1

    await db.commit()

    return {"message": "配置恢复成功", "restored_configs": restored_configs, "restored_dictionaries": restored_dicts}


# ============================================================
# 动态阈值规则管理 API (Story 25.6)
# ============================================================

@router.get("/dynamic-threshold-rules", summary="查询动态阈值规则")
async def get_dynamic_threshold_rules(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """
    查询动态阈值规则配置

    Returns:
        - rules: 规则列表
        - version: 规则版本号
        - updated_at: 最后更新时间
    """
    result = await db.execute(
        select(SystemConfig).where(
            SystemConfig.config_group == "alarm",
            SystemConfig.config_key == "dynamic_threshold_rules"
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        return {"rules": [], "version": 0, "updated_at": None}

    try:
        rules = json.loads(config.config_value)
    except json.JSONDecodeError:
        rules = []

    return {
        "rules": rules,
        "version": config.version or 1,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None
    }


@router.put("/dynamic-threshold-rules", summary="更新动态阈值规则")
async def update_dynamic_threshold_rules(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    更新动态阈值规则配置（含乐观锁）

    Request Body:
        - rules: 规则列表
        - expected_version: 期望的版本号（用于乐观锁）

    Returns:
        - message: 操作结果
        - new_version: 新版本号
    """
    rules = data.get("rules", [])
    expected_version = data.get("expected_version")

    # 验证规则格式
    for rule in rules:
        if "condition" not in rule or "adjustment" not in rule or "description" not in rule:
            raise HTTPException(
                status_code=400,
                detail="规则格式错误：每条规则必须包含 condition, adjustment, description"
            )

        # 验证 condition 表达式
        try:
            from ...services.diagnosis.condition_parser import parse_and_evaluate
            # 测试解析（使用空上下文）
            parse_and_evaluate(rule["condition"], {})
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"规则条件表达式无效: {rule['condition']} - {str(e)}"
            )

        # 验证 adjustment 格式
        try:
            float(rule["adjustment"])
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail=f"调整值格式错误: {rule['adjustment']}，必须是数字或带 +/- 前缀的字符串"
            )

        # 验证 priority
        priority = rule.get("priority", 0)
        if not isinstance(priority, int) or priority < 0:
            raise HTTPException(
                status_code=400,
                detail=f"优先级必须是非负整数: {priority}"
            )

    # 查询当前配置
    result = await db.execute(
        select(SystemConfig).where(
            SystemConfig.config_group == "alarm",
            SystemConfig.config_key == "dynamic_threshold_rules"
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="动态阈值规则配置不存在")

    # 乐观锁检查
    current_version = config.version or 1
    if expected_version is not None and expected_version != current_version:
        raise HTTPException(
            status_code=409,
            detail=f"版本冲突：期望版本 {expected_version}，当前版本 {current_version}。请刷新后重试。"
        )

    # 保存旧值到历史表（如果存在）
    try:
        from ...models.config import ConfigHistory
        history = ConfigHistory(
            config_id=config.id,
            old_value=config.config_value,
            new_value=json.dumps(rules, ensure_ascii=False),
            version=current_version,
            updated_by=current_user.id,
            updated_at=datetime.now()
        )
        db.add(history)
    except Exception as e:
        logger.warning(f"保存配置历史失败: {e}")

    # 更新配置
    new_version = current_version + 1
    await db.execute(
        update(SystemConfig)
        .where(SystemConfig.id == config.id)
        .values(
            config_value=json.dumps(rules, ensure_ascii=False),
            version=new_version,
            updated_by=current_user.id,
            updated_at=datetime.now()
        )
    )
    await db.commit()

    # 触发缓存重新加载
    try:
        from ...services.diagnosis.dynamic_threshold_service import DynamicThresholdService
        await DynamicThresholdService.clear_cache()
    except Exception as e:
        logger.warning(f"清除动态阈值缓存失败: {e}")

    return {"message": "规则更新成功", "new_version": new_version}


@router.get("/dynamic-threshold-status", summary="查询动态阈值特性状态")
async def get_dynamic_threshold_status(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """
    查询动态阈值特性状态

    Returns:
        - is_enabled: 特性是否启用
        - rule_count: 规则数量
        - rule_version: 规则版本号
        - updated_at: 最后更新时间
    """
    # 查询特性开关
    enabled_result = await db.execute(
        select(SystemConfig).where(
            SystemConfig.config_group == "alarm",
            SystemConfig.config_key == "DYNAMIC_THRESHOLDS_ENABLED"
        )
    )
    enabled_config = enabled_result.scalar_one_or_none()
    is_enabled = enabled_config and enabled_config.config_value.lower() == "true"

    # 查询规则配置
    rules_result = await db.execute(
        select(SystemConfig).where(
            SystemConfig.config_group == "alarm",
            SystemConfig.config_key == "dynamic_threshold_rules"
        )
    )
    rules_config = rules_result.scalar_one_or_none()

    rule_count = 0
    rule_version = 0
    updated_at = None

    if rules_config:
        try:
            rules = json.loads(rules_config.config_value)
            rule_count = len(rules)
        except json.JSONDecodeError:
            pass
        rule_version = rules_config.version or 1
        updated_at = rules_config.updated_at.isoformat() if rules_config.updated_at else None

    return {
        "is_enabled": is_enabled,
        "rule_count": rule_count,
        "rule_version": rule_version,
        "updated_at": updated_at
    }


@router.post("/dynamic-threshold-toggle", summary="切换动态阈值特性开关")
async def toggle_dynamic_threshold(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    切换动态阈值特性开关

    Request Body:
        - enabled: true/false

    Returns:
        - message: 操作结果
        - is_enabled: 新状态
    """
    enabled = data.get("enabled", False)

    result = await db.execute(
        select(SystemConfig).where(
            SystemConfig.config_group == "alarm",
            SystemConfig.config_key == "DYNAMIC_THRESHOLDS_ENABLED"
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="动态阈值特性开关配置不存在")

    await db.execute(
        update(SystemConfig)
        .where(SystemConfig.id == config.id)
        .values(
            config_value="true" if enabled else "false",
            updated_by=current_user.id,
            updated_at=datetime.now()
        )
    )
    await db.commit()

    # 记录操作日志
    logger.info(f"用户 {current_user.username} {'启用' if enabled else '禁用'}了动态阈值特性")

    return {"message": f"动态阈值特性已{'启用' if enabled else '禁用'}", "is_enabled": enabled}


@router.post("/dynamic-threshold-rules/test", summary="测试动态阈值规则")
async def test_dynamic_threshold_rules(
    data: dict,
    _: User = Depends(require_admin),
):
    """
    测试动态阈值规则（不修改数据库）

    Request Body:
        - rules: 规则列表
        - context: 环境上下文 (outdoor_temp, it_load_percent, season)
        - sample_thresholds: 示例阈值列表 [{name, value, direction}]

    Returns:
        - matched_rules: 匹配的规则列表
        - total_adjustment: 总调整值
        - sample_results: 示例阈值调整结果
    """
    rules = data.get("rules", [])
    context = data.get("context", {})
    sample_thresholds = data.get("sample_thresholds", [])

    from ...services.diagnosis.condition_parser import parse_and_evaluate

    # 评估规则
    matched_rules = []
    total_adjustment = 0.0

    for rule in rules:
        try:
            if parse_and_evaluate(rule["condition"], context):
                adjustment = float(rule["adjustment"])
                total_adjustment += adjustment
                matched_rules.append({
                    "condition": rule["condition"],
                    "adjustment": adjustment,
                    "description": rule["description"],
                    "priority": rule.get("priority", 0)
                })
        except Exception as e:
            logger.warning(f"规则评估失败: {rule['condition']} - {e}")

    # 计算示例阈值调整结果
    sample_results = []
    for threshold in sample_thresholds:
        name = threshold.get("name", "")
        value = float(threshold.get("value", 0))
        direction = threshold.get("direction", "high")

        if direction == "high":
            adjusted = value + total_adjustment
        else:
            adjusted = value - total_adjustment

        sample_results.append({
            "name": name,
            "original": value,
            "adjusted": adjusted,
            "adjustment": total_adjustment
        })

    return {
        "matched_rules": matched_rules,
        "total_adjustment": total_adjustment,
        "sample_results": sample_results
    }


@router.get("/dynamic-threshold-rules/history", summary="查询规则修改历史")
async def get_dynamic_threshold_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    查询动态阈值规则修改历史（分页）

    Returns:
        - items: 历史记录列表
        - total: 总记录数
        - page: 当前页码
        - page_size: 每页大小
    """
    try:
        from ...models.config import ConfigHistory

        # 查询配置 ID
        config_result = await db.execute(
            select(SystemConfig.id).where(
                SystemConfig.config_group == "alarm",
                SystemConfig.config_key == "dynamic_threshold_rules"
            )
        )
        config_id = config_result.scalar_one_or_none()

        if not config_id:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}

        # 查询历史记录
        from sqlalchemy import func, desc
        count_result = await db.execute(
            select(func.count(ConfigHistory.id)).where(ConfigHistory.config_id == config_id)
        )
        total = count_result.scalar()

        history_result = await db.execute(
            select(ConfigHistory)
            .where(ConfigHistory.config_id == config_id)
            .order_by(desc(ConfigHistory.updated_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        history_records = history_result.scalars().all()

        items = []
        for record in history_records:
            # 查询操作人
            user_result = await db.execute(select(User.username).where(User.id == record.updated_by))
            username = user_result.scalar_one_or_none() or "Unknown"

            items.append({
                "id": record.id,
                "version": record.version,
                "updated_by": username,
                "updated_at": record.updated_at.isoformat() if record.updated_at else None,
                "old_value": record.old_value,
                "new_value": record.new_value
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size
        }

    except Exception as e:
        logger.error(f"查询规则历史失败: {e}")
        return {"items": [], "total": 0, "page": page, "page_size": page_size}


@router.post("/dynamic-threshold-rules/rollback", summary="回滚到历史版本")
async def rollback_dynamic_threshold_rules(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    回滚动态阈值规则到指定历史版本

    Request Body:
        - version: 目标版本号

    Returns:
        - message: 操作结果
        - new_version: 新版本号
    """
    target_version = data.get("version")
    if target_version is None:
        raise HTTPException(status_code=400, detail="必须指定目标版本号")

    try:
        from ...models.config import ConfigHistory

        # 查询配置
        config_result = await db.execute(
            select(SystemConfig).where(
                SystemConfig.config_group == "alarm",
                SystemConfig.config_key == "dynamic_threshold_rules"
            )
        )
        config = config_result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="动态阈值规则配置不存在")

        # 查询目标版本的历史记录
        history_result = await db.execute(
            select(ConfigHistory)
            .where(
                ConfigHistory.config_id == config.id,
                ConfigHistory.version == target_version
            )
            .order_by(ConfigHistory.updated_at.desc())
        )
        history = history_result.scalars().first()

        if not history:
            raise HTTPException(status_code=404, detail=f"未找到版本 {target_version} 的历史记录")

        # 保存当前值到历史
        current_version = config.version or 1
        current_history = ConfigHistory(
            config_id=config.id,
            old_value=config.config_value,
            new_value=history.new_value,  # 回滚到的值
            version=current_version,
            updated_by=current_user.id,
            updated_at=datetime.now()
        )
        db.add(current_history)

        # 回滚配置
        new_version = current_version + 1
        await db.execute(
            update(SystemConfig)
            .where(SystemConfig.id == config.id)
            .values(
                config_value=history.new_value,
                version=new_version,
                updated_by=current_user.id,
                updated_at=datetime.now()
            )
        )
        await db.commit()

        # 清除缓存
        try:
            from ...services.diagnosis.dynamic_threshold_service import DynamicThresholdService
            await DynamicThresholdService.clear_cache()
        except Exception as e:
            logger.warning(f"清除动态阈值缓存失败: {e}")

        logger.info(f"用户 {current_user.username} 将动态阈值规则回滚到版本 {target_version}")

        return {"message": f"已回滚到版本 {target_version}", "new_version": new_version}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"回滚规则失败: {e}")
        raise HTTPException(status_code=500, detail=f"回滚失败: {str(e)}")


@router.get("/dynamic-threshold-metrics", summary="查询动态阈值监控指标")
async def get_dynamic_threshold_metrics(
    point_id: Optional[int] = Query(None, description="点位 ID（可选，不传则返回全局统计）"),
    time_range: int = Query(3600, description="时间范围（秒），默认 1 小时"),
    _: User = Depends(require_admin),
):
    """
    查询动态阈值监控指标

    Returns:
        - adjustment_count: 调整次数统计 (adjusted/skipped/degraded)
        - adjustment_distribution: 调整幅度分布 (P50/P95/P99)
        - rule_match_stats: 规则匹配统计 (top 10 规则)
        - performance_stats: 性能统计 (平均耗时)
        - degradation_count: 降级次数
    """
    try:
        from ...core.redis import redis_service
        import time

        now = int(time.time())
        start_time = now - time_range

        # 1. 调整次数统计
        adjustment_count = {"adjusted": 0, "skipped": 0, "degraded": 0}

        # 扫描 Redis keys
        if point_id:
            # 单点位统计
            for status in ["adjusted", "skipped", "degraded"]:
                pattern = f"dynamic_threshold:count:{point_id}:{status}"
                keys = []
                if redis_service.is_available:
                    cursor = 0
                    while True:
                        cursor, batch = await redis_service._pool.scan(cursor, match=pattern, count=100)
                        keys.extend(batch)
                        if cursor == 0:
                            break
                adjustment_count[status] = len(keys)
        else:
            # 全局统计
            for status in ["adjusted", "skipped", "degraded"]:
                pattern = f"dynamic_threshold:count:*:{status}"
                keys = []
                if redis_service.is_available:
                    cursor = 0
                    while True:
                        cursor, batch = await redis_service._pool.scan(cursor, match=pattern, count=100)
                        keys.extend(batch)
                        if cursor == 0:
                            break
                adjustment_count[status] = len(keys)

        # 2. 调整幅度分布（仅 adjusted 状态）
        adjustment_values = []
        if redis_service.is_available:
            pattern = f"dynamic_threshold:adjustment:{point_id or '*'}:*"
            cursor = 0
            while True:
                cursor, keys = await redis_service._pool.scan(cursor, match=pattern, count=100)
                for key in keys:
                    # 检查时间戳是否在范围内
                    timestamp = int(key.decode().split(":")[-1])
                    if timestamp >= start_time:
                        value_str = await redis_service.get(key.decode())
                        if value_str:
                            try:
                                adjustment_values.append(float(value_str))
                            except ValueError:
                                pass
                if cursor == 0:
                    break

        # 计算分位数
        adjustment_distribution = {}
        if adjustment_values:
            adjustment_values.sort()
            n = len(adjustment_values)
            adjustment_distribution = {
                "p50": adjustment_values[int(n * 0.5)],
                "p95": adjustment_values[int(n * 0.95)],
                "p99": adjustment_values[int(n * 0.99)],
                "count": n,
            }

        # 3. 规则匹配统计（Top 10）
        rule_match_stats = []
        if redis_service.is_available:
            pattern = "dynamic_threshold:rule_match:*"
            cursor = 0
            rule_counts = {}
            while True:
                cursor, keys = await redis_service._pool.scan(cursor, match=pattern, count=100)
                for key in keys:
                    count = await redis_service._pool.get(key)
                    if count:
                        rule_hash = key.decode().split(":")[-1]
                        rule_counts[rule_hash] = int(count)
                if cursor == 0:
                    break

            # 排序并取 Top 10
            sorted_rules = sorted(rule_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            rule_match_stats = [{"rule_hash": rule, "match_count": count} for rule, count in sorted_rules]

        # 4. 性能统计
        perf_data_list = []
        if redis_service.is_available:
            pattern = "dynamic_threshold:perf:*"
            cursor = 0
            while True:
                cursor, keys = await redis_service._pool.scan(cursor, match=pattern, count=100)
                for key in keys:
                    # 检查时间戳是否在范围内
                    timestamp = int(key.decode().split(":")[-1])
                    if timestamp >= start_time:
                        perf_json = await redis_service.get_json(key.decode())
                        if perf_json:
                            perf_data_list.append(perf_json)
                if cursor == 0:
                    break

        performance_stats = {}
        if perf_data_list:
            avg_total_time = sum(p["total_time"] for p in perf_data_list) / len(perf_data_list)
            avg_context_time = sum(p["context_time"] for p in perf_data_list) / len(perf_data_list)
            avg_eval_time = sum(p["eval_time"] for p in perf_data_list) / len(perf_data_list)
            avg_matched_count = sum(p["matched_count"] for p in perf_data_list) / len(perf_data_list)

            performance_stats = {
                "avg_total_time_ms": round(avg_total_time * 1000, 2),
                "avg_context_time_ms": round(avg_context_time * 1000, 2),
                "avg_eval_time_ms": round(avg_eval_time * 1000, 2),
                "avg_matched_count": round(avg_matched_count, 2),
                "sample_count": len(perf_data_list),
            }

        # 5. 降级次数
        degradation_count = 0
        if redis_service.is_available:
            pattern = "dynamic_threshold:degraded:*"
            cursor = 0
            while True:
                cursor, keys = await redis_service._pool.scan(cursor, match=pattern, count=100)
                for key in keys:
                    # 检查时间戳是否在范围内
                    timestamp = int(key.decode().split(":")[-1])
                    if timestamp >= start_time:
                        degradation_count += 1
                if cursor == 0:
                    break

        return {
            "time_range_seconds": time_range,
            "point_id": point_id,
            "adjustment_count": adjustment_count,
            "adjustment_distribution": adjustment_distribution,
            "rule_match_stats": rule_match_stats,
            "performance_stats": performance_stats,
            "degradation_count": degradation_count,
        }

    except Exception as e:
        logger.error(f"查询监控指标失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")

