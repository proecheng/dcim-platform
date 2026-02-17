"""
系统健康状态 API — Story 4.5 优雅降级
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..deps import get_db, require_viewer
from ...models.user import User
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

    return {
        "redis": {"status": redis_status},
        "database": {"status": db_status},
        "websocket": {"active_connections": ws_connections},
        "mqtt": {"status": mqtt_status},
    }
