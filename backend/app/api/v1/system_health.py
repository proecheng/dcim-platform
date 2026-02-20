"""
系统健康状态 API — Story 4.5 优雅降级 + Story 13.4 数据备份
"""
import logging
import os
import shutil
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, update

from ..deps import get_db, require_viewer, require_admin
from ...models.user import User
from ...models.config import SystemConfig
from ...core.redis import redis_service
from ...core.config import get_settings
from ...services.websocket import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", summary="系统健康状态")
async def get_system_health(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """返回各组件健康状态：Redis、Database、WebSocket、MQTT"""
    settings = get_settings()

    # Redis 状态
    redis_status = "disconnected"
    if redis_service and redis_service.is_available:
        try:
            await redis_service.set("health_check", "ok", ttl=5)
            redis_status = "connected"
        except Exception:
            redis_status = "disconnected"

    # 数据库状态
    db_status = "disconnected"
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    # WebSocket 活跃连接数
    ws_connections = 0
    for conns in ws_manager.active_connections.values():
        ws_connections += len(conns)

    # MQTT 状态
    mqtt_status = "not_configured"
    if getattr(settings, "mqtt_enabled", False):
        mqtt_status = "unknown"

    # 存储使用率
    storage_info = {}
    try:
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "dcim.db")
        if os.path.exists(db_path):
            db_size_mb = os.path.getsize(db_path) / (1024 * 1024)
            storage_info["db_size_mb"] = round(db_size_mb, 2)
        total, used, free = shutil.disk_usage(os.path.dirname(db_path) if os.path.exists(db_path) else ".")
        storage_info["disk_total_gb"] = round(total / (1024**3), 2)
        storage_info["disk_used_gb"] = round(used / (1024**3), 2)
        storage_info["disk_free_gb"] = round(free / (1024**3), 2)
        storage_info["disk_usage_percent"] = round(used / total * 100, 1)
    except Exception:
        pass  # 磁盘信息获取失败不影响健康检查

    return {
        "redis": {"status": redis_status},
        "database": {"status": db_status},
        "websocket": {"active_connections": ws_connections},
        "mqtt": {"status": mqtt_status},
        "storage": storage_info,
    }


# ============================================================
# 数据备份管理 (Story 13-4)
# ============================================================

BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "backups")


@router.get("/backup/config", summary="获取备份配置")
async def get_backup_config(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """获取自动备份策略配置"""
    result = await db.execute(
        select(SystemConfig).where(
            SystemConfig.config_group == "backup"
        )
    )
    configs = result.scalars().all()
    config_dict = {c.config_key: c.config_value for c in configs}

    return {
        "auto_backup_enabled": config_dict.get("auto_backup_enabled", "false") == "true",
        "backup_time": config_dict.get("backup_time", "02:00"),
        "retention_count": int(config_dict.get("retention_count", "7")),
        "backup_dir": BACKUP_DIR,
    }


@router.put("/backup/config", summary="更新备份配置")
async def update_backup_config(
    auto_backup_enabled: Optional[bool] = None,
    backup_time: Optional[str] = None,
    retention_count: Optional[int] = Query(None, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """更新自动备份策略"""
    updates = {}
    if auto_backup_enabled is not None:
        updates["auto_backup_enabled"] = str(auto_backup_enabled).lower()
    if backup_time is not None:
        updates["backup_time"] = backup_time
    if retention_count is not None:
        updates["retention_count"] = str(retention_count)

    for key, value in updates.items():
        result = await db.execute(
            select(SystemConfig).where(
                SystemConfig.config_group == "backup",
                SystemConfig.config_key == key
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.config_value = value
        else:
            db.add(SystemConfig(
                config_group="backup",
                config_key=key,
                config_value=value,
                description=f"备份配置: {key}"
            ))

    await db.commit()
    return {"message": "备份配置已更新"}


@router.post("/backup/manual", summary="手动备份")
async def manual_backup(
    _: User = Depends(require_admin),
):
    """执行手动数据库备份"""
    os.makedirs(BACKUP_DIR, exist_ok=True)

    db_path = os.path.join(os.path.dirname(BACKUP_DIR), "dcim.db")
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="数据库文件不存在")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"dcim_backup_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    try:
        shutil.copy2(db_path, backup_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"备份失败: {str(e)}")

    return {
        "message": "备份成功",
        "backup_name": backup_name,
        "backup_path": backup_path,
        "size_mb": round(os.path.getsize(backup_path) / (1024 * 1024), 2),
        "created_at": datetime.now().isoformat(),
    }


@router.get("/backup/list", summary="获取备份列表")
async def list_backups(
    _: User = Depends(require_admin),
):
    """获取所有备份文件列表"""
    if not os.path.exists(BACKUP_DIR):
        return {"backups": []}

    backups = []
    for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if f.endswith(".db"):
            fpath = os.path.join(BACKUP_DIR, f)
            backups.append({
                "name": f,
                "size_mb": round(os.path.getsize(fpath) / (1024 * 1024), 2),
                "created_at": datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat(),
            })

    return {"backups": backups}


@router.post("/backup/restore", summary="恢复备份")
async def restore_backup(
    backup_name: str = Query(..., description="备份文件名"),
    _: User = Depends(require_admin),
):
    """从备份文件恢复数据库"""
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    if not os.path.exists(backup_path):
        raise HTTPException(status_code=404, detail="备份文件不存在")

    db_path = os.path.join(os.path.dirname(BACKUP_DIR), "dcim.db")

    try:
        # 先备份当前数据库
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pre_restore_backup = os.path.join(BACKUP_DIR, f"dcim_pre_restore_{timestamp}.db")
        if os.path.exists(db_path):
            shutil.copy2(db_path, pre_restore_backup)

        # 恢复
        shutil.copy2(backup_path, db_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"恢复失败: {str(e)}")

    return {
        "message": "恢复成功，请重启服务使更改生效",
        "restored_from": backup_name,
    }
