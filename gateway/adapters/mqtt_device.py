"""MQTT 设备适配器 — 通过 MQTT 订阅接入 IoT 传感器 — Story 15.1

设计说明:
  BaseProtocolAdapter 是拉模式 (read_points 主动读取)，而 MQTT 是推模式 (subscribe 被动接收)。
  本适配器通过内部缓冲区桥接两种模式:
  - connect() 时订阅指定 Topic，收到消息后按解析规则提取点位数据存入缓冲区
  - read_points() 返回缓冲区中的最新值（不清空，保留最后已知值）
  - 支持 JSON 和自定义分隔符两种消息格式
"""
import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .base import (
    AdapterState,
    AdapterStatus,
    BaseProtocolAdapter,
    ConnectionResult,
    DataQuality,
    DataSourceConfig,
    PointConfig,
    PointValue,
)
from .registry import register_adapter

logger = logging.getLogger(__name__)


def _build_json_extractor(path: str) -> Callable[[dict], Any]:
    """构建 JSON 路径提取器

    支持点分路径: "data.temperature" → payload["data"]["temperature"]
    支持数组索引: "sensors[0].value" → payload["sensors"][0]["value"]
    """
    parts: list[str | int] = []
    for segment in path.split("."):
        # 处理数组索引: sensors[0]
        match = re.match(r"^(\w+)\[(\d+)\]$", segment)
        if match:
            parts.append(match.group(1))
            parts.append(int(match.group(2)))
        else:
            parts.append(segment)

    def extract(payload: dict) -> Any:
        current: Any = payload
        for part in parts:
            if isinstance(part, int):
                current = current[part]
            else:
                current = current[part]
        return current

    return extract


def _parse_custom_format(raw: str, delimiter: str, index: int) -> str:
    """自定义分隔符格式解析: 按分隔符拆分，取指定索引"""
    parts = raw.split(delimiter)
    if index >= len(parts):
        raise IndexError(f"索引 {index} 超出范围，消息仅有 {len(parts)} 段")
    return parts[index].strip()


@register_adapter("mqtt")
class MqttDeviceAdapter(BaseProtocolAdapter):
    """MQTT 设备适配器 — 订阅 Topic 接收 IoT 传感器数据

    connection_config 示例:
    {
        "broker_host": "emqx",          # MQTT Broker 地址（可选，复用网关 MQTT 时留空）
        "broker_port": 1883,            # MQTT Broker 端口
        "topics": ["sensor/+/data"],    # 订阅 Topic 列表（支持通配符）
        "username": "",                 # 认证用户名（可选）
        "password": "",                 # 认证密码（可选）
        "client_id": "dcim-mqtt-ds-1",  # 客户端 ID
        "qos": 1,                       # 订阅 QoS
        "message_format": "json",       # 消息格式: json / custom
        "parse_rules": {                # 解析规则（JSON 格式时）
            "point_id_path": "id",      # 点位 ID 的 JSON 路径
            "value_path": "value",      # 值的 JSON 路径
            "timestamp_path": "ts",     # 时间戳的 JSON 路径（可选）
            "quality_path": "quality"   # 质量码的 JSON 路径（可选）
        },
        "custom_delimiter": ",",        # 自定义格式分隔符
        "custom_mapping": {             # 自定义格式字段映射: 字段名 → 索引
            "point_id": 0,
            "value": 1,
            "timestamp": 2
        }
    }

    DataSourcePoint.address 格式:
      JSON 模式: JSON 路径，如 "data.temperature" 或 "sensors[0].value"
      自定义模式: 字段索引，如 "1"（取分隔后第 2 段）
    """

    def __init__(self) -> None:
        self._config: Optional[DataSourceConfig] = None
        self._state: AdapterState = AdapterState.DISCONNECTED
        self._connected_since: Optional[datetime] = None
        self._last_read_time: Optional[datetime] = None
        self._consecutive_failures: int = 0
        self._error_message: Optional[str] = None

        # 消息缓冲区: point_id → PointValue
        self._buffer: dict[str, PointValue] = {}
        self._buffer_lock = asyncio.Lock()

        # MQTT 连接（由外部 MqttService 注入，或自行连接）
        self._client: Any = None
        self._subscribe_task: Optional[asyncio.Task] = None
        self._message_count: int = 0

        # 解析配置缓存
        self._message_format: str = "json"
        self._parse_rules: dict = {}
        self._custom_delimiter: str = ","
        self._custom_mapping: dict = {}
        self._topics: list[str] = []
        self._qos: int = 1

        # 点位地址 → 提取器缓存
        self._extractors: dict[str, Callable] = {}

    async def connect(self, config: DataSourceConfig) -> bool:
        """连接 MQTT Broker 并订阅 Topic"""
        self._config = config
        params = config.connection_params

        # 解析配置
        self._topics = params.get("topics", [])
        if not self._topics:
            self._state = AdapterState.CONFIG_ERROR
            self._error_message = "缺少 topics 配置"
            return False

        self._qos = params.get("qos", 1)
        self._message_format = params.get("message_format", "json")
        self._parse_rules = params.get("parse_rules", {})
        self._custom_delimiter = params.get("custom_delimiter", ",")
        self._custom_mapping = params.get("custom_mapping", {})

        # 预编译点位提取器
        self._extractors.clear()
        for point in config.points:
            if self._message_format == "json":
                self._extractors[point.point_id] = _build_json_extractor(point.address)

        broker_host = params.get("broker_host", "")
        broker_port = params.get("broker_port", 1883)

        if broker_host:
            # 独立连接模式 — 自行连接 Broker
            try:
                import aiomqtt
                client_id = params.get("client_id", f"dcim-mqtt-{config.datasource_id}")
                username = params.get("username") or None
                password = params.get("password") or None

                self._client = aiomqtt.Client(
                    hostname=broker_host,
                    port=broker_port,
                    username=username,
                    password=password,
                    identifier=client_id,
                )
                # aiomqtt 需要 async context manager，启动后台订阅任务
                self._subscribe_task = asyncio.create_task(
                    self._subscribe_loop(broker_host, broker_port, username, password, client_id)
                )
                self._state = AdapterState.CONNECTED
                self._connected_since = datetime.now(timezone.utc)
                self._consecutive_failures = 0
                self._error_message = None
                logger.info("MQTT 适配器已启动: broker=%s:%d, topics=%s", broker_host, broker_port, self._topics)
                return True

            except ImportError:
                self._state = AdapterState.CONFIG_ERROR
                self._error_message = "aiomqtt 未安装"
                logger.error("MQTT 适配器: aiomqtt 未安装")
                return False
            except Exception as e:
                self._state = AdapterState.DISCONNECTED
                self._error_message = str(e)
                logger.error("MQTT 适配器连接失败: %s", e)
                return False
        else:
            # 复用网关 MQTT 模式 — 由 MqttService 注入消息
            self._state = AdapterState.CONNECTED
            self._connected_since = datetime.now(timezone.utc)
            self._error_message = None
            logger.info("MQTT 适配器已启动（复用网关 MQTT）: topics=%s", self._topics)
            return True

    async def disconnect(self) -> None:
        """断开 MQTT 连接"""
        if self._subscribe_task:
            self._subscribe_task.cancel()
            try:
                await self._subscribe_task
            except asyncio.CancelledError:
                pass
            self._subscribe_task = None

        self._client = None
        self._state = AdapterState.DISCONNECTED
        self._connected_since = None
        self._buffer.clear()
        logger.info("MQTT 适配器已断开")

    async def read_points(self, points: list[PointConfig]) -> dict[str, PointValue]:
        """读取缓冲区中的最新点位值

        MQTT 是推模式，数据通过 on_message 写入缓冲区。
        read_points 返回缓冲区中匹配的点位最新值。
        """
        results: dict[str, PointValue] = {}
        async with self._buffer_lock:
            for point in points:
                if point.point_id in self._buffer:
                    results[point.point_id] = self._buffer[point.point_id]
                else:
                    # 尚未收到该点位数据
                    results[point.point_id] = PointValue(
                        point_id=point.point_id,
                        value=None,
                        quality=DataQuality.UNRELIABLE,
                        timestamp=datetime.now(timezone.utc),
                    )
        self._last_read_time = datetime.now(timezone.utc)
        return results

    async def write_point(self, point_id: str, value: Any) -> bool:
        """MQTT 适配器不支持写入（IoT 传感器通常为只读）"""
        logger.warning("MQTT 适配器不支持写入: point_id=%s", point_id)
        return False

    async def test_connection(self) -> ConnectionResult:
        """测试 MQTT 连接"""
        params = self._config.connection_params if self._config else {}
        broker_host = params.get("broker_host", "")

        if not broker_host:
            # 复用网关 MQTT 模式 — 检查是否有缓冲数据
            return ConnectionResult(
                success=True,
                message="复用网关 MQTT 连接（无独立 Broker）",
                sample_data={"buffered_points": len(self._buffer), "message_count": self._message_count},
            )

        try:
            import aiomqtt
            start = time.monotonic()
            client_id = params.get("client_id", "dcim-mqtt-test")

            async with aiomqtt.Client(
                hostname=broker_host,
                port=params.get("broker_port", 1883),
                username=params.get("username") or None,
                password=params.get("password") or None,
                identifier=f"{client_id}-test",
            ) as client:
                latency = (time.monotonic() - start) * 1000
                # 尝试订阅第一个 topic
                if self._topics:
                    await client.subscribe(self._topics[0], qos=self._qos)

                return ConnectionResult(
                    success=True,
                    message="MQTT 连接测试成功",
                    latency_ms=round(latency, 2),
                    sample_data={"topics": self._topics},
                )

        except ImportError:
            return ConnectionResult(success=False, message="aiomqtt 未安装")
        except asyncio.TimeoutError:
            return ConnectionResult(success=False, message="MQTT 连接超时")
        except Exception as e:
            return ConnectionResult(success=False, message=str(e))

    def get_status(self) -> AdapterStatus:
        """获取适配器状态"""
        return AdapterStatus(
            state=self._state,
            connected_since=self._connected_since,
            last_read_time=self._last_read_time,
            consecutive_failures=self._consecutive_failures,
            error_message=self._error_message,
        )

    # ─── 消息处理 ─────────────────────────────────────────────

    async def on_message(self, topic: str, payload: bytes) -> None:
        """处理收到的 MQTT 消息 — 由 MqttService 或自身订阅循环调用

        Args:
            topic: MQTT topic
            payload: 原始消息字节
        """
        try:
            self._message_count += 1

            if self._message_format == "json":
                await self._parse_json_message(topic, payload)
            elif self._message_format == "custom":
                await self._parse_custom_message(topic, payload)
            else:
                logger.warning("未知消息格式: %s", self._message_format)

            self._consecutive_failures = 0

        except Exception as e:
            self._consecutive_failures += 1
            logger.warning("MQTT 消息解析失败: topic=%s, error=%s", topic, e)

    async def _parse_json_message(self, topic: str, payload: bytes) -> None:
        """解析 JSON 格式消息"""
        data = json.loads(payload.decode("utf-8"))

        # 方式1: 消息包含单个点位数据（有 point_id_path）
        point_id_path = self._parse_rules.get("point_id_path")
        value_path = self._parse_rules.get("value_path", "value")
        ts_path = self._parse_rules.get("timestamp_path")
        quality_path = self._parse_rules.get("quality_path")

        if point_id_path:
            # 单点位消息: {"id": "temp_01", "value": 25.3, "ts": 1700000000}
            try:
                extractor = _build_json_extractor(point_id_path)
                point_id = str(extractor(data))
                val_extractor = _build_json_extractor(value_path)
                value = val_extractor(data)

                timestamp = datetime.now(timezone.utc)
                if ts_path:
                    try:
                        ts_val = _build_json_extractor(ts_path)(data)
                        if isinstance(ts_val, (int, float)):
                            timestamp = datetime.fromtimestamp(ts_val, tz=timezone.utc)
                    except Exception:
                        pass

                quality = DataQuality.NORMAL
                if quality_path:
                    try:
                        q_val = _build_json_extractor(quality_path)(data)
                        if q_val in (1, "unreliable"):
                            quality = DataQuality.UNRELIABLE
                        elif q_val in (2, "abnormal"):
                            quality = DataQuality.ABNORMAL
                    except Exception:
                        pass

                async with self._buffer_lock:
                    self._buffer[point_id] = PointValue(
                        point_id=point_id,
                        value=value,
                        quality=quality,
                        timestamp=timestamp,
                    )
            except (KeyError, IndexError, TypeError) as e:
                logger.debug("JSON 单点位解析失败: %s", e)
        else:
            # 方式2: 消息包含多个字段，每个点位通过 address (JSON path) 提取
            # 适用于: {"temperature": 25.3, "humidity": 60.1}
            # 点位 address 配置为 "temperature", "humidity"
            if self._config:
                for point in self._config.points:
                    try:
                        extractor = self._extractors.get(point.point_id)
                        if extractor is None:
                            extractor = _build_json_extractor(point.address)
                            self._extractors[point.point_id] = extractor

                        value = extractor(data)
                        async with self._buffer_lock:
                            self._buffer[point.point_id] = PointValue(
                                point_id=point.point_id,
                                value=value,
                                quality=DataQuality.NORMAL,
                                timestamp=datetime.now(timezone.utc),
                            )
                    except (KeyError, IndexError, TypeError):
                        # 该消息不包含此点位数据，跳过
                        pass

    async def _parse_custom_message(self, topic: str, payload: bytes) -> None:
        """解析自定义分隔符格式消息"""
        raw = payload.decode("utf-8").strip()
        mapping = self._custom_mapping

        point_id_idx = mapping.get("point_id")
        value_idx = mapping.get("value")

        if point_id_idx is not None and value_idx is not None:
            # 消息自带点位 ID: "temp_01,25.3,1700000000"
            point_id = _parse_custom_format(raw, self._custom_delimiter, int(point_id_idx))
            value_str = _parse_custom_format(raw, self._custom_delimiter, int(value_idx))

            try:
                value: Any = float(value_str)
            except ValueError:
                value = value_str

            timestamp = datetime.now(timezone.utc)
            ts_idx = mapping.get("timestamp")
            if ts_idx is not None:
                try:
                    ts_str = _parse_custom_format(raw, self._custom_delimiter, int(ts_idx))
                    timestamp = datetime.fromtimestamp(float(ts_str), tz=timezone.utc)
                except Exception:
                    pass

            async with self._buffer_lock:
                self._buffer[point_id] = PointValue(
                    point_id=point_id,
                    value=value,
                    quality=DataQuality.NORMAL,
                    timestamp=timestamp,
                )
        else:
            # 无点位 ID 映射 — 按点位 address 索引提取
            if self._config:
                for point in self._config.points:
                    try:
                        idx = int(point.address)
                        value_str = _parse_custom_format(raw, self._custom_delimiter, idx)
                        try:
                            value = float(value_str)
                        except ValueError:
                            value = value_str

                        async with self._buffer_lock:
                            self._buffer[point.point_id] = PointValue(
                                point_id=point.point_id,
                                value=value,
                                quality=DataQuality.NORMAL,
                                timestamp=datetime.now(timezone.utc),
                            )
                    except (ValueError, IndexError):
                        pass

    # ─── 独立连接模式的订阅循环 ──────────────────────────────

    async def _subscribe_loop(
        self,
        broker_host: str,
        broker_port: int,
        username: Optional[str],
        password: Optional[str],
        client_id: str,
    ) -> None:
        """独立 MQTT 订阅循环（断线重连 + 指数退避）"""
        retry_delay = 1.0

        while True:
            try:
                import aiomqtt
                async with aiomqtt.Client(
                    hostname=broker_host,
                    port=broker_port,
                    username=username,
                    password=password,
                    identifier=client_id,
                ) as client:
                    self._state = AdapterState.CONNECTED
                    self._connected_since = datetime.now(timezone.utc)
                    self._error_message = None
                    retry_delay = 1.0

                    for topic in self._topics:
                        await client.subscribe(topic, qos=self._qos)
                        logger.info("MQTT 适配器已订阅: %s", topic)

                    async for message in client.messages:
                        await self.on_message(str(message.topic), message.payload)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._state = AdapterState.COMMUNICATION_INTERRUPTED
                self._error_message = str(e)
                logger.warning("MQTT 适配器连接断开: %s (%.1fs 后重试)", e, retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60.0)
