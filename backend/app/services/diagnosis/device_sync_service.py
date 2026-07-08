# backend/app/services/diagnosis/device_sync_service.py
import asyncio
import json
import logging
import redis.asyncio as redis
from app.core.config import get_settings
from app.services.diagnosis.power_topology_service import update_topology_node

logger = logging.getLogger(__name__)
settings = get_settings()

# 全局停止标志
_stop_listener = False


async def start_device_sync_listener():
    """监听设备拓扑变更事件（带 Redis 连接错误处理和降级策略）"""
    global _stop_listener
    retry_delay = 5  # 重连延迟（秒）
    max_retries = 3  # 最大重试次数

    for attempt in range(max_retries):
        if _stop_listener:
            break

        redis_client = None
        try:
            redis_client = redis.from_url(settings.effective_redis_url)
            pubsub = redis_client.pubsub()
            await pubsub.subscribe("device:topology_change")

            logger.info("设备拓扑变更监听器已启动")

            async for message in pubsub.listen():
                if _stop_listener:
                    break

                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        node_id = data["node_id"]
                        node_type = data["node_type"]
                        action = data["action"]  # add/update/delete

                        await update_topology_node(node_id, node_type, action)
                    except Exception as e:
                        logger.error(f"处理拓扑变更事件失败: {e}")

        except redis.ConnectionError as e:
            logger.error(f"Redis 连接失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                logger.warning("Redis 连接失败次数过多，降级为定期重建拓扑图模式")
                # 启动定期重建任务
                asyncio.create_task(_periodic_rebuild_topology())
                break

        except Exception as e:
            logger.error(f"设备拓扑变更监听器异常: {e}")
            break
        finally:
            if redis_client:
                try:
                    await redis_client.close()
                except Exception as e:
                    logger.warning(f"关闭 Redis 客户端失败: {e}")


async def stop_device_sync_listener() -> None:
    """停止监听器"""
    global _stop_listener
    _stop_listener = True


async def _periodic_rebuild_topology():
    """定期重建拓扑图（Redis 不可用时的降级策略）"""
    from app.services.diagnosis.power_topology_service import initialize_power_topology_graph

    rebuild_interval = 300  # 5 分钟

    while not _stop_listener:
        await asyncio.sleep(rebuild_interval)
        if _stop_listener:
            break

        try:
            logger.info("定期重建配电拓扑图...")
            await initialize_power_topology_graph()
        except Exception as e:
            logger.error(f"定期重建拓扑图失败: {e}")
