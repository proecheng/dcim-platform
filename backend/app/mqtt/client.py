"""后端 MQTT 客户端 — Story 2.1"""
import asyncio
import json
import logging
from typing import Optional

from ..core.config import get_settings
from ..core.database import async_session
from ..services.gateway_registration import handle_gateway_status, check_gateway_heartbeats
from ..services.point_data import handle_point_data

logger = logging.getLogger(__name__)


class MqttService:
    """后端 MQTT 客户端 — 订阅网关状态、数据上报"""

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False
        self._client = None

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
                    retry_delay = 1.0  # 重置退避

                    # 订阅网关状态 topic
                    await client.subscribe("dcim/+/gw/+/status")
                    logger.info("已订阅: dcim/+/gw/+/status")
                    await client.subscribe("dcim/+/gw/+/data", qos=1)
                    logger.info("已订阅: dcim/+/gw/+/data")

                    async for message in client.messages:
                        await self._handle_message(message)

            except asyncio.CancelledError:
                raise
            except ImportError:
                self._client = None
                logger.error("aiomqtt 未安装，MQTT 功能不可用")
                return
            except Exception as e:
                self._client = None
                logger.warning("MQTT 连接失败: %s (%.1fs 后重试)", e, retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60.0)

    async def _handle_message(self, message) -> None:  # type: ignore[no-untyped-def]
        """处理收到的 MQTT 消息"""
        try:
            topic = str(message.topic)
            payload = json.loads(message.payload.decode())

            # 解析 topic: dcim/{site_id}/gw/{gw_id}/{type}
            parts = topic.split("/")
            if len(parts) == 5:
                msg_type = parts[4]
                if msg_type == "status":
                    async with async_session() as db:
                        await handle_gateway_status(payload, db)
                elif msg_type == "data":
                    async with async_session() as db:
                        await handle_point_data(payload, db)
        except json.JSONDecodeError:
            logger.warning("MQTT 消息 JSON 解析失败: topic=%s", message.topic)
        except Exception:
            logger.exception("MQTT 消息处理异常: topic=%s", message.topic)

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
