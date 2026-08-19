"""后端 MQTT 客户端 — Story 2.1 + Story 15.1 动态订阅"""

import asyncio
import json
import logging
from typing import Callable, Optional

from ..core.config import get_settings
from ..core.database import async_session
from ..services.gateway_registration import handle_gateway_status, check_gateway_heartbeats
from ..services.point_data import handle_point_data

logger = logging.getLogger(__name__)

# 动态订阅回调类型: async def handler(topic: str, payload: bytes) -> None
MessageHandler = Callable[[str, bytes], object]


class MqttService:
    """后端 MQTT 客户端 — 订阅网关状态、数据上报 + 动态 Topic 订阅"""

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False
        self._connected = False
        self._client = None
        # 动态订阅: topic_pattern → handler
        self._dynamic_subscriptions: dict[str, MessageHandler] = {}
        self._pending_subscriptions: list[tuple[str, int]] = []

    async def start(self) -> None:
        """启动 MQTT 客户端（优雅降级：连接失败不阻塞）"""
        settings = get_settings()
        if not settings.mqtt_enabled:
            logger.info("MQTT 已禁用")
            return

        self._running = True
        self._task = asyncio.create_task(self._connect_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_check_loop())
        logger.info("MQTT 服务已启动")

    async def stop(self) -> None:
        """停止 MQTT 客户端"""
        self._running = False
        self._connected = False
        self._client = None
        for task in [self._task, self._heartbeat_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        logger.info("MQTT 服务已停止")

    async def publish(self, topic: str, payload: str, qos: int = 2) -> None:
        """发布 MQTT 消息"""
        if self._client is None:
            raise RuntimeError("MQTT 未连接")
        await self._client.publish(topic, payload, qos=qos)
        logger.debug("MQTT 消息已发布: topic=%s, qos=%d", topic, qos)

    def register_subscription(self, topic_pattern: str, handler: MessageHandler, qos: int = 1) -> None:
        """注册动态 Topic 订阅 — 由 MqttDeviceAdapter 调用

        Args:
            topic_pattern: MQTT topic（支持 +/# 通配符）
            handler: 消息回调 async def handler(topic, payload)
            qos: 订阅 QoS
        """
        self._dynamic_subscriptions[topic_pattern] = handler
        self._pending_subscriptions.append((topic_pattern, qos))
        logger.info("注册动态订阅: %s", topic_pattern)

    def unregister_subscription(self, topic_pattern: str) -> None:
        """取消动态 Topic 订阅"""
        self._dynamic_subscriptions.pop(topic_pattern, None)
        logger.info("取消动态订阅: %s", topic_pattern)

    async def _connect_loop(self) -> None:
        """MQTT 连接循环（断线重连 + 指数退避）"""
        settings = get_settings()
        retry_delay = 1.0

        while self._running:
            try:
                import aiomqtt

                async with aiomqtt.Client(
                    hostname=settings.mqtt_host,
                    port=settings.mqtt_port,
                    username=settings.mqtt_username or None,
                    password=settings.mqtt_password or None,
                    identifier=settings.mqtt_client_id,
                ) as client:
                    logger.info("MQTT 已连接: %s:%d", settings.mqtt_host, settings.mqtt_port)
                    self._client = client
                    self._connected = True
                    retry_delay = 1.0  # 重置退避

                    # 订阅网关状态 topic
                    await client.subscribe("dcim/+/gw/+/status")
                    logger.info("已订阅: dcim/+/gw/+/status")
                    await client.subscribe("dcim/+/gw/+/data", qos=1)
                    logger.info("已订阅: dcim/+/gw/+/data")
                    await client.subscribe("dcim/+/gw/+/ota/status", qos=1)
                    logger.info("已订阅: dcim/+/gw/+/ota/status")

                    # 订阅已注册的动态 topic
                    for topic_pattern, qos in list(self._pending_subscriptions):
                        await client.subscribe(topic_pattern, qos=qos)
                        logger.info("已订阅动态 topic: %s (qos=%d)", topic_pattern, qos)
                    self._pending_subscriptions.clear()

                    async for message in client.messages:
                        # 检查是否有新的待订阅 topic
                        if self._pending_subscriptions:
                            for tp, q in list(self._pending_subscriptions):
                                await client.subscribe(tp, qos=q)
                                logger.info("已订阅动态 topic: %s (qos=%d)", tp, q)
                            self._pending_subscriptions.clear()

                        await self._handle_message(message)

            except asyncio.CancelledError:
                self._connected = False
                self._client = None
                raise
            except ImportError:
                self._connected = False
                self._client = None
                logger.error("aiomqtt 未安装，MQTT 功能不可用")
                return
            except Exception as e:
                self._connected = False
                self._client = None
                logger.warning("MQTT 连接失败: %s (%.1fs 后重试)", e, retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60.0)
            finally:
                self._connected = False
                self._client = None

    @property
    def is_connected(self) -> bool:
        return self._running and self._connected and self._client is not None

    async def _handle_message(self, message) -> None:  # type: ignore[no-untyped-def]
        """处理收到的 MQTT 消息"""
        topic = str(message.topic)

        # 先检查动态订阅是否匹配
        for pattern, handler in self._dynamic_subscriptions.items():
            if self._topic_matches(topic, pattern):
                try:
                    result = handler(topic, message.payload)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    logger.exception("动态订阅处理异常: topic=%s, pattern=%s", topic, pattern)

        # 原有网关消息处理
        try:
            payload = json.loads(message.payload.decode())
            parts = topic.split("/")
            # OTA 状态上报: dcim/{site_id}/gw/{gw_id}/ota/status (6段)
            if len(parts) == 6 and parts[0] == "dcim" and parts[4] == "ota" and parts[5] == "status":
                from ..services.ota_service import ota_service

                async with async_session() as db:
                    await ota_service.handle_ota_status(payload, db)
            # 原有网关消息: dcim/{site_id}/gw/{gw_id}/{type} (5段)
            elif len(parts) == 5 and parts[0] == "dcim":
                site_id_str = parts[1]  # 从 topic 提取 site_id
                msg_type = parts[4]
                if msg_type == "status":
                    async with async_session() as db:
                        await handle_gateway_status(payload, db, site_id=site_id_str)
                elif msg_type == "data":
                    async with async_session() as db:
                        await handle_point_data(payload, db, site_id=site_id_str)
        except json.JSONDecodeError:
            pass  # 非 JSON 消息可能是动态订阅的自定义格式，已在上面处理
        except Exception:
            logger.exception("MQTT 消息处理异常: topic=%s", topic)

    @staticmethod
    def _topic_matches(topic: str, pattern: str) -> bool:
        """检查 MQTT topic 是否匹配订阅 pattern

        支持 MQTT 通配符:
          + 匹配单层: sensor/+/data 匹配 sensor/room1/data
          # 匹配多层: sensor/# 匹配 sensor/room1/data
        """
        # 将 MQTT 通配符转换为 fnmatch 模式
        pattern.replace("+", "*").replace("#", "**")
        # fnmatch 不支持 **，手动处理 # 通配符
        if "#" in pattern:
            prefix = pattern.split("#")[0]
            return topic.startswith(prefix)
        # + 通配符: 逐层匹配
        topic_parts = topic.split("/")
        pattern_parts = pattern.split("/")
        if len(topic_parts) != len(pattern_parts):
            return False
        return all(pp == "+" or pp == tp for tp, pp in zip(topic_parts, pattern_parts))

    async def _heartbeat_check_loop(self) -> None:
        """定时检查网关心跳超时"""
        while self._running:
            try:
                await asyncio.sleep(30)
                async with async_session() as db:
                    count = await check_gateway_heartbeats(db)
                    if count:
                        logger.info("心跳检查: %d 个网关标记为离线", count)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("心跳检查异常")

    @staticmethod
    def parse_topic(topic: str) -> Optional[dict]:
        """解析 MQTT topic，提取 site_id 和 gw_id"""
        parts = topic.split("/")
        if len(parts) >= 5 and parts[0] == "dcim":
            return {
                "site_id": parts[1],
                "gw_id": parts[3],
                "type": parts[4],
            }
        return None
