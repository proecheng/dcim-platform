"""
规则管理器 - Story 24.1
负责规则热更新监听
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


class RuleManager:
    """规则管理器 - 监听规则更新事件"""

    def __init__(self, l1_engine: 'L1RuleEngine', redis_service):
        """
        初始化规则管理器

        Args:
            l1_engine: L1RuleEngine 实例
            redis_service: RedisService 实例
        """
        self.l1_engine = l1_engine
        self.redis_service = redis_service
        self._listener_task = None

    async def start_listener(self):
        """订阅 Redis Pub/Sub 监听规则更新事件"""
        if not self.redis_service.is_available:
            logger.warning("Redis 不可用，规则热更新功能禁用")
            return

        try:
            # 获取 Redis 连接池
            redis_client = self.redis_service._pool
            pubsub = redis_client.pubsub()
            await pubsub.subscribe("diagnosis:rule_update")

            logger.info("规则管理器已启动，监听 diagnosis:rule_update 事件")

            async for message in pubsub.listen():
                if message["type"] == "message":
                    # 重新加载规则
                    await self.l1_engine.load_rules()
                    logger.info("诊断规则已热更新")
        except asyncio.CancelledError:
            logger.info("规则管理器监听器已停止")
            raise
        except Exception as e:
            logger.error(f"规则管理器监听器异常: {e}")

    def start(self):
        """启动监听器（非阻塞）"""
        self._listener_task = asyncio.create_task(self.start_listener())

    async def stop(self):
        """停止监听器"""
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
