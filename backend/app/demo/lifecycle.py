"""演示模块生命周期管理 — 供 main.py lifespan 调用"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 模拟器后台任务句柄
_simulator_task: Optional[asyncio.Task] = None


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

    # 种子数据初始化（幂等，已存在则跳过）
    from .seeds.datacenter_seed import seed_datacenter
    from .seeds.power_seed import seed_power_devices
    from .seeds.cooling_seed import seed_cooling_devices

    await seed_datacenter()
    await seed_power_devices()
    await seed_cooling_devices()
    logger.info("演示模块: 种子数据已初始化")

    # 启动数据模拟器
    from .engine import simulator

    _simulator_task = asyncio.create_task(simulator.start(interval=5))
    logger.info("演示模块: 模拟器已启动 (interval=5s)")


async def shutdown() -> None:
    """演示模块关闭钩子"""
    global _simulator_task

    from .config import is_demo_enabled

    if not is_demo_enabled():
        return

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
    logger.info("演示模块: 已关闭")
