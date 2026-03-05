"""演示模块生命周期管理 — 供 main.py lifespan 调用"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import delete

logger = logging.getLogger(__name__)

# 模拟器后台任务句柄
_simulator_task: Optional[asyncio.Task] = None
# 清理任务句柄
_cleanup_task: Optional[asyncio.Task] = None


async def startup() -> None:
    """演示模块启动钩子 — 在 main.py lifespan 中条件调用

    职责:
    1. 执行配电/制冷种子数据初始化
    2. 启动数据模拟器后台任务
    """
    global _simulator_task

    from .config import is_demo_enabled

    if not is_demo_enabled():
        return

    logger.info("演示模块: 启动中...")

    # 注册 Demo 专用的 legacy 映射规则（必须在设备同步之前）
    from .data.legacy_mapping import register_demo_rules
    register_demo_rules()

    # 种子数据初始化（幂等，已存在则跳过）
    from .seeds.datacenter_seed import seed_datacenter
    from .seeds.power_seed import seed_power_devices
    from .seeds.cooling_seed import seed_cooling_devices

    await seed_datacenter()
    await seed_power_devices()
    await seed_cooling_devices()
    logger.info("演示模块: 种子数据已初始化")

    # 双向同步: 拓扑节点 ↔ 动环设备 (通过 device_code 匹配关联)
    from ..services.device_sync import DeviceSyncService
    from ..core.database import async_session

    async with async_session() as session:
        sync = DeviceSyncService(session)
        result = await sync.migrate_existing_data()
        logger.info(
            "演示模块: 设备同步完成 - 关联配电柜 %d, 关联用电设备 %d, 新建设备(配电柜) %d, 新建设备(用电) %d",
            result.get("linked_panels", 0),
            result.get("linked_power_devices", 0),
            result.get("created_devices_for_panels", 0),
            result.get("created_devices_for_power", 0),
        )

    # 启动数据模拟器（使用配置的间隔）
    from .engine import simulator
    from ..core.config import get_settings
    
    settings = get_settings()
    _simulator_task = asyncio.create_task(simulator.start(interval=settings.simulation_interval))
    logger.info(f"演示模块: 模拟器已启动 (interval={settings.simulation_interval}s)")

    # 启动历史数据清理任务
    global _cleanup_task
    _cleanup_task = asyncio.create_task(_cleanup_old_history())
    logger.info("演示模块: 历史数据清理任务已启动")

async def _cleanup_old_history():
    """定期清理过期历史数据（增强版：最多保疕60天）"""
    from ..core.config import get_settings
    from ..core.database import async_session
    from ..models import PointHistory
    import os
    
    settings = get_settings()
    max_retention_days = 60  # 硬限制：最多60天
    target_retention_days = min(settings.data_retention_days, max_retention_days)
    
    logger.info(f"历史数据清理任务已启动")
    logger.info(f"  配置保留天数: {settings.data_retention_days}")
    logger.info(f"  实际保留天数: {target_retention_days} (最多60天)")
    
    while True:
        try:
            # 每天凌晨2点执行清理
            now = datetime.now()
            next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            
            wait_seconds = (next_run - now).total_seconds()
            logger.info(f"下次清理时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            await asyncio.sleep(wait_seconds)
            
            # 执行清理
            cutoff = datetime.now() - timedelta(days=target_retention_days)
            logger.info(f"开始清理 {cutoff.strftime('%Y-%m-%d %H:%M:%S')} 之前的历史数据...")
            
            async with async_session() as session:
                # 清理过期历史
                result = await session.execute(
                    delete(PointHistory).where(PointHistory.recorded_at < cutoff)
                )
                deleted_count = result.rowcount
                await session.commit()
                
                # 检查数据库大小
                db_path = '../dcim.db'
                if os.path.exists(db_path):
                    size_mb = os.path.getsize(db_path) / 1024 / 1024
                    logger.info(f"历史数据清理完成")
                    logger.info(f"  删除记录: {deleted_count:,} 条")
                    logger.info(f"  数据库大小: {size_mb:.2f} MB")
                else:
                    logger.info(f"历史数据清理完成，删除 {deleted_count:,} 条记录")
                
        except asyncio.CancelledError:
            logger.info("历史数据清理任务已取消")
            break
        except Exception as e:
            logger.error(f"清理历史数据失败: {e}", exc_info=True)
            # 出错后等待1小时再重试
            await asyncio.sleep(3600)


async def shutdown() -> None:
    """演示模块关闭钩子"""
    global _simulator_task, _cleanup_task

    from .config import is_demo_enabled

    if not is_demo_enabled():
        return

    # 卸载 Demo 专用的 legacy 映射规则
    from .data.legacy_mapping import unregister_demo_rules
    unregister_demo_rules()

    # 停止模拟器
    try:
        from .engine import simulator

        simulator.stop()
    except Exception as e:
        logger.warning("演示模块: 停止模拟器异常: %s", e)

    if _simulator_task and not _simulator_task.done():
        _simulator_task.cancel()
        try:
            await _simulator_task
        except asyncio.CancelledError:
            pass

    _simulator_task = None
    
    # 停止清理任务
    if _cleanup_task and not _cleanup_task.done():
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass
    
    _cleanup_task = None
    logger.info("演示模块: 已关闭")
