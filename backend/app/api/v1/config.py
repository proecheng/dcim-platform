"""
系统配置 API - v1
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import json
import io

from ..deps import get_db, require_viewer, require_admin
from ...models.user import User
from ...models.config import SystemConfig, Dictionary, License
from ...schemas.config import (
    SystemConfigInfo, SystemConfigUpdate,
    DictionaryInfo, LicenseInfo, LicenseActivate
)

router = APIRouter()


@router.get("", summary="获取系统配置")
async def get_configs(
    group: Optional[str] = Query(None, description="配置分组"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
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
    data: list[SystemConfigUpdate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    批量更新系统配置
    """
    updated_count = 0
    for item in data:
        result = await db.execute(
            select(SystemConfig).where(
                SystemConfig.config_group == item.config_group,
                SystemConfig.config_key == item.config_key
            )
        )
        config = result.scalar_one_or_none()

        if config:
            if not config.is_editable:
                continue

            await db.execute(
                update(SystemConfig).where(SystemConfig.id == config.id).values(
                    config_value=item.config_value,
                    updated_by=current_user.id,
                    updated_at=datetime.now()
                )
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
                updated_by=current_user.id
            )
            db.add(new_config)
            updated_count += 1

    await db.commit()
    return {"message": f"已更新 {updated_count} 项配置"}


@router.get("/dictionaries", summary="获取数据字典")
async def get_dictionaries(
    dict_type: Optional[str] = Query(None, description="字典类型"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
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

    return grouped


@router.get("/license", response_model=LicenseInfo, summary="获取授权信息")
async def get_license(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取当前授权信息
    """
    result = await db.execute(
        select(License).where(License.is_active == True).order_by(License.activated_at.desc())
    )
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
            status="trial"
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
        status=status
    )


@router.post("/license/activate", summary="激活授权")
async def activate_license(
    data: LicenseActivate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    激活授权许可
    """
    # 简单的许可证验证逻辑（实际应该对接许可证服务器）
    license_key = data.license_key.strip().upper()

    # 检查许可证格式
    if len(license_key) < 16:
        raise HTTPException(status_code=400, detail="无效的许可证密钥")

    # 检查是否已使用
    result = await db.execute(
        select(License).where(License.license_key == license_key)
    )
    existing = result.scalar_one_or_none()
    if existing:
        if existing.is_active:
            raise HTTPException(status_code=400, detail="该许可证已激活")
        else:
            # 重新激活
            await db.execute(
                update(License).where(License.id == existing.id).values(
                    is_active=True,
                    activated_at=datetime.now()
                )
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
    await db.execute(
        update(License).values(is_active=False)
    )

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
        activated_at=datetime.now()
    )
    db.add(new_license)
    await db.commit()

    return {
        "message": "许可证激活成功",
        "license_type": license_type,
        "max_points": max_points,
        "expire_date": new_license.expire_date.isoformat()
    }


@router.get("/backup", summary="导出系统配置")
async def backup_configs(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
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
                "description": c.description
            } for c in configs
        ],
        "dictionaries": [
            {
                "type": d.dict_type,
                "code": d.dict_code,
                "name": d.dict_name,
                "value": d.dict_value,
                "sort": d.sort_order
            } for d in dicts
        ]
    }

    content = json.dumps(backup_data, ensure_ascii=False, indent=2)
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=system_backup.json"}
    )


@router.post("/restore", summary="导入系统配置")
async def restore_configs(
    backup_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
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
                SystemConfig.config_group == config["group"],
                SystemConfig.config_key == config["key"]
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            await db.execute(
                update(SystemConfig).where(SystemConfig.id == existing.id).values(
                    config_value=config["value"],
                    updated_by=current_user.id,
                    updated_at=datetime.now()
                )
            )
        else:
            new_config = SystemConfig(
                config_group=config["group"],
                config_key=config["key"],
                config_value=config["value"],
                value_type=config.get("type", "string"),
                description=config.get("description"),
                updated_by=current_user.id
            )
            db.add(new_config)
        restored_configs += 1

    # 恢复字典
    for d in backup_data.get("dictionaries", []):
        result = await db.execute(
            select(Dictionary).where(
                Dictionary.dict_type == d["type"],
                Dictionary.dict_code == d["code"]
            )
        )
        existing = result.scalar_one_or_none()

        if not existing:
            new_dict = Dictionary(
                dict_type=d["type"],
                dict_code=d["code"],
                dict_name=d["name"],
                dict_value=d.get("value"),
                sort_order=d.get("sort", 0)
            )
            db.add(new_dict)
            restored_dicts += 1

    await db.commit()

    return {
        "message": "配置恢复成功",
        "restored_configs": restored_configs,
        "restored_dictionaries": restored_dicts
    }
