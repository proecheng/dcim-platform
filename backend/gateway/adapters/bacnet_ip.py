"""BACnet/IP 协议适配器 — 通过 BACnet/IP 采集楼宇自控设备 — Story 15.3

设计说明:
  BacnetIpAdapter 是拉模式适配器:
  - connect() 初始化/复用 BAC0 网络实例，验证设备可达
  - read_points() 优先使用 ReadPropertyMultiple 批量读取，fallback 逐点位读取
  - write_point() 通过 BAC0 写入 presentValue（支持双向通信）
  - 支持设备发现和对象列表浏览（扩展方法）
  - BAC0 基于 bacpypes3，原生 asyncio，无需 to_thread 包装

  BAC0 网络实例管理:
  - BAC0 绑定 UDP 47808 端口，全局只能有一个实例
  - 通过模块级单例 + 引用计数管理生命周期
  - 多个 BacnetIpAdapter 共享同一个 BAC0 网络实例
"""
import asyncio
import inspect
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

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

# ─── BACnet 对象类型映射 ─────────────────────────────────────

# 完整名称 → BAC0 对象类型字符串
OBJECT_TYPE_MAP: dict[str, str] = {
    "analogInput": "analogInput",
    "analogOutput": "analogOutput",
    "analogValue": "analogValue",
    "binaryInput": "binaryInput",
    "binaryOutput": "binaryOutput",
    "binaryValue": "binaryValue",
    "multiStateInput": "multiStateInput",
    "multiStateOutput": "multiStateOutput",
    "multiStateValue": "multiStateValue",
}

# 缩写 → 完整名称
OBJECT_TYPE_ALIASES: dict[str, str] = {
    "AI": "analogInput",
    "AO": "analogOutput",
    "AV": "analogValue",
    "BI": "binaryInput",
    "BO": "binaryOutput",
    "BV": "binaryValue",
    "MI": "multiStateInput",
    "MO": "multiStateOutput",
    "MV": "multiStateValue",
}

# 默认读取属性
DEFAULT_PROPERTY = "presentValue"


def parse_point_address(address: str) -> tuple[str, int, str]:
    """解析点位地址格式: {object_type}:{instance}[:{property}]

    Returns:
        (object_type, instance, property_name)

    Examples:
        "analogInput:1" → ("analogInput", 1, "presentValue")
        "AI:5:statusFlags" → ("analogInput", 5, "statusFlags")
        "binaryOutput:3" → ("binaryOutput", 3, "presentValue")
    """
    parts = address.split(":")
    if len(parts) < 2 or len(parts) > 3:
        raise ValueError(
            f"无效 BACnet 地址格式: {address}，"
            f"期望 {{object_type}}:{{instance}}[:{{property}}]"
        )

    raw_type = parts[0]
    # 支持缩写
    obj_type = OBJECT_TYPE_ALIASES.get(raw_type.upper(), raw_type)
    if obj_type not in OBJECT_TYPE_MAP:
        raise ValueError(
            f"未知 BACnet 对象类型: {raw_type}，"
            f"支持: {list(OBJECT_TYPE_MAP.keys())} 或缩写 {list(OBJECT_TYPE_ALIASES.keys())}"
        )

    try:
        instance = int(parts[1])
    except ValueError as e:
        raise ValueError(f"无效对象实例号: {parts[1]}") from e

    prop = parts[2] if len(parts) == 3 else DEFAULT_PROPERTY

    return obj_type, instance, prop


# ─── BAC0 网络实例单例管理 ───────────────────────────────────

class _BacnetNetworkManager:
    """BAC0 网络实例单例管理器 — 引用计数控制生命周期

    BAC0 绑定 UDP 端口，全局只能有一个活跃实例。
    多个 BacnetIpAdapter 通过此管理器共享同一个 BAC0 网络。
    """

    def __init__(self) -> None:
        self._network: Any = None
        self._ref_count: int = 0
        self._lock: Optional[asyncio.Lock] = None
        self._ip: Optional[str] = None
        self._port: int = 47808

    def _get_lock(self) -> asyncio.Lock:
        """延迟创建 Lock，确保绑定到当前事件循环"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock  # type: ignore[return-value]

    async def acquire(self, ip: str = "", port: int = 47808) -> Any:
        """获取 BAC0 网络实例（引用计数 +1）"""
        async with self._get_lock():
            if self._network is None:
                try:
                    import BAC0
                    self._ip = ip or None
                    self._port = port
                    # BAC0.start() 是 async context manager，但也可直接 await
                    self._network = await BAC0.start(ip=self._ip, port=self._port)
                    logger.info("BAC0 网络已启动: ip=%s, port=%d", self._ip, self._port)
                except ImportError:
                    raise ImportError("BAC0 未安装")
                except Exception as e:
                    raise RuntimeError(f"BAC0 网络启动失败: {e}") from e

            self._ref_count += 1
            logger.debug("BAC0 网络引用计数: %d", self._ref_count)
            return self._network

    async def release(self) -> None:
        """释放 BAC0 网络实例（引用计数 -1，归零时关闭）"""
        async with self._get_lock():
            if self._ref_count > 0:
                self._ref_count -= 1
                logger.debug("BAC0 网络引用计数: %d", self._ref_count)

            if self._ref_count <= 0 and self._network is not None:
                try:
                    result = self._network.disconnect()
                    if inspect.isawaitable(result):
                        await result
                    logger.info("BAC0 网络已关闭")
                except Exception as e:
                    logger.warning("BAC0 网络关闭异常: %s", e)
                finally:
                    self._network = None
                    self._ref_count = 0

    @property
    def is_active(self) -> bool:
        return self._network is not None


# 模块级单例
_network_manager = _BacnetNetworkManager()


# ─── BACnet/IP 适配器 ───────────────────────────────────────

@register_adapter("bacnet_ip")
class BacnetIpAdapter(BaseProtocolAdapter):
    """BACnet/IP 协议适配器 — 采集楼宇自控设备

    connection_config 示例:
    {
        "device_instance": 1234,            # 目标设备实例号
        "device_address": "192.168.1.100",  # 设备 IP（可选，自动发现时留空）
        "network_interface": "",            # 本机网卡 IP（可选）
        "port": 47808,                      # BACnet/IP 端口（默认 47808）
        "bbmd_address": "",                 # BBMD 地址（跨子网场景，可选）
        "bbmd_ttl": 900,                    # BBMD TTL 秒数（可选）
        "timeout": 10                       # 读取超时（秒）
    }

    DataSourcePoint.address 格式:
      {object_type}:{instance}[:{property}]
      如 "analogInput:1" 或 "AI:5" 或 "binaryOutput:3:statusFlags"
      默认读取 presentValue
    """

    def __init__(self) -> None:
        self._config: Optional[DataSourceConfig] = None
        self._state: AdapterState = AdapterState.DISCONNECTED
        self._connected_since: Optional[datetime] = None
        self._last_read_time: Optional[datetime] = None
        self._consecutive_failures: int = 0
        self._error_message: Optional[str] = None

        # BAC0 网络实例（由 _network_manager 管理）
        self._network: Any = None

        # 设备配置
        self._device_instance: int = 0
        self._device_address: str = ""
        self._timeout: float = 10.0

    async def connect(self, config: DataSourceConfig) -> bool:
        """连接 BACnet/IP 设备"""
        # 防止重复 connect 导致引用计数泄漏
        if self._network is not None:
            await self.disconnect()

        self._config = config
        params = config.connection_params

        # 解析配置
        self._device_instance = params.get("device_instance", 0)
        if not self._device_instance:
            self._state = AdapterState.CONFIG_ERROR
            self._error_message = "缺少 device_instance 配置"
            return False

        self._device_address = params.get("device_address", "")
        self._timeout = params.get("timeout", 10)
        network_ip = params.get("network_interface", "")
        port = params.get("port", 47808)

        # 验证点位地址格式
        for point in config.points:
            try:
                parse_point_address(point.address)
            except ValueError as e:
                self._state = AdapterState.CONFIG_ERROR
                self._error_message = f"点位 {point.point_id} 地址无效: {e}"
                return False

        # 获取 BAC0 网络实例
        try:
            self._network = await _network_manager.acquire(ip=network_ip, port=port)
        except ImportError:
            self._state = AdapterState.CONFIG_ERROR
            self._error_message = "BAC0 未安装"
            logger.error("BACnet/IP 适配器: BAC0 未安装")
            return False
        except Exception as e:
            self._state = AdapterState.DISCONNECTED
            self._error_message = str(e)
            logger.error("BACnet/IP 适配器连接失败: %s", e)
            return False

        self._state = AdapterState.CONNECTED
        self._connected_since = datetime.now(timezone.utc)
        self._consecutive_failures = 0
        self._error_message = None
        logger.info(
            "BACnet/IP 适配器已连接: device=%d, address=%s",
            self._device_instance, self._device_address or "(auto-discover)",
        )
        return True

    async def disconnect(self) -> None:
        """断开 BACnet/IP 连接"""
        if self._network is not None:
            await _network_manager.release()
            self._network = None
        self._state = AdapterState.DISCONNECTED
        self._connected_since = None
        logger.info("BACnet/IP 适配器已断开: device=%d", self._device_instance)

    async def read_points(self, points: list[PointConfig]) -> dict[str, PointValue]:
        """读取 BACnet 对象属性 — 优先 ReadPropertyMultiple，fallback 逐点位"""
        results: dict[str, PointValue] = {}

        if self._network is None:
            for point in points:
                results[point.point_id] = PointValue(
                    point_id=point.point_id,
                    value=None,
                    quality=DataQuality.ABNORMAL,
                    timestamp=datetime.now(timezone.utc),
                )
            return results

        # 构建设备地址字符串
        device_addr = self._device_address or str(self._device_instance)

        # 尝试 ReadPropertyMultiple 批量读取
        try:
            rpm_success = await self._read_property_multiple(device_addr, points, results)
            if rpm_success:
                self._consecutive_failures = 0
                self._error_message = None
                self._last_read_time = datetime.now(timezone.utc)
                return results
        except Exception as e:
            logger.debug("ReadPropertyMultiple 失败，回退逐点位读取: %s", e)

        # Fallback: 逐点位读取
        try:
            await self._read_points_individually(device_addr, points, results)
            self._consecutive_failures = 0
            self._error_message = None
        except Exception as e:
            self._consecutive_failures += 1
            self._error_message = str(e)
            logger.error("BACnet/IP 读取失败: %s", e)

            for point in points:
                if point.point_id not in results:
                    results[point.point_id] = PointValue(
                        point_id=point.point_id,
                        value=None,
                        quality=DataQuality.ABNORMAL,
                        timestamp=datetime.now(timezone.utc),
                    )

            if self._consecutive_failures >= (
                self._config.retry_max_failures if self._config else 5
            ):
                self._state = AdapterState.COMMUNICATION_INTERRUPTED

        self._last_read_time = datetime.now(timezone.utc)
        return results

    async def _read_property_multiple(
        self,
        device_addr: str,
        points: list[PointConfig],
        results: dict[str, PointValue],
    ) -> bool:
        """批量读取 — ReadPropertyMultiple"""
        # 构建 RPM 请求参数: {(obj_type, instance): [(point_id, property), ...]}
        rpm_map: dict[tuple[str, int], list[tuple[str, str]]] = {}
        for point in points:
            obj_type, instance, prop = parse_point_address(point.address)
            key = (obj_type, instance)
            if key not in rpm_map:
                rpm_map[key] = []
            rpm_map[key].append((point.point_id, prop))

        # 构建 BAC0 RPM 请求列表
        request_list = []
        for (obj_type, instance), props in rpm_map.items():
            prop_names = list({p[1] for p in props})
            request_list.append(f"{obj_type} {instance} {' '.join(prop_names)}")

        rpm_request = " ".join(request_list)

        # 执行 RPM
        rpm_result = await asyncio.wait_for(
            self._network.readMultiple(f"{device_addr} {rpm_request}"),
            timeout=self._timeout,
        )

        if rpm_result is None:
            return False

        # 解析 RPM 结果并填充 results
        # BAC0 readMultiple 返回值格式取决于版本，做容错处理
        if isinstance(rpm_result, dict):
            for point in points:
                obj_type, instance, prop = parse_point_address(point.address)
                key = f"{obj_type}:{instance}"
                value = rpm_result.get(key, {}).get(prop)
                quality = DataQuality.NORMAL if value is not None else DataQuality.UNRELIABLE
                results[point.point_id] = PointValue(
                    point_id=point.point_id,
                    value=value,
                    quality=quality,
                    timestamp=datetime.now(timezone.utc),
                )
        elif isinstance(rpm_result, list):
            # list 格式无法可靠地映射回点位（索引与请求顺序不一定对应），回退逐点位读取
            logger.debug("RPM 返回 list 格式，回退逐点位读取")
            return False
        else:
            return False

        return True

    async def _read_points_individually(
        self,
        device_addr: str,
        points: list[PointConfig],
        results: dict[str, PointValue],
    ) -> None:
        """逐点位读取 — ReadProperty fallback

        当所有点位均读取失败时抛出 RuntimeError，
        以便 read_points() 触发 consecutive_failures 递增。
        """
        failure_count = 0
        for point in points:
            try:
                obj_type, instance, prop = parse_point_address(point.address)
                read_request = f"{device_addr} {obj_type} {instance} {prop}"

                value = await asyncio.wait_for(
                    self._network.read(read_request),
                    timeout=self._timeout,
                )

                results[point.point_id] = PointValue(
                    point_id=point.point_id,
                    value=value,
                    quality=DataQuality.NORMAL,
                    timestamp=datetime.now(timezone.utc),
                )
            except asyncio.TimeoutError:
                failure_count += 1
                logger.warning("点位 %s 读取超时", point.point_id)
                results[point.point_id] = PointValue(
                    point_id=point.point_id,
                    value=None,
                    quality=DataQuality.ABNORMAL,
                    timestamp=datetime.now(timezone.utc),
                )
            except Exception as e:
                failure_count += 1
                logger.warning("点位 %s 读取失败: %s", point.point_id, e)
                results[point.point_id] = PointValue(
                    point_id=point.point_id,
                    value=None,
                    quality=DataQuality.ABNORMAL,
                    timestamp=datetime.now(timezone.utc),
                )
        # 全部失败时向上层传播，触发 consecutive_failures 逻辑
        if failure_count == len(points):
            raise RuntimeError(f"所有 {len(points)} 个点位读取均失败")

    async def write_point(self, point_id: str, value: Any) -> bool:
        """写入 BACnet 对象属性"""
        if not self._config or not self._config.write_enabled:
            logger.warning("写入被禁用，无法写入点位 %s", point_id)
            return False

        if self._network is None:
            logger.error("BACnet 网络未连接，无法写入点位 %s", point_id)
            return False

        # 查找点位配置
        point_cfg = None
        for p in self._config.points:
            if p.point_id == point_id:
                point_cfg = p
                break

        if point_cfg is None:
            logger.error("未找到点位配置: %s", point_id)
            return False

        if value is None:
            logger.error("写入值不能为 None: point_id=%s", point_id)
            return False

        try:
            obj_type, instance, prop = parse_point_address(point_cfg.address)
            device_addr = self._device_address or str(self._device_instance)
            write_request = f"{device_addr} {obj_type} {instance} {prop} {value}"

            await asyncio.wait_for(
                self._network.write(write_request),
                timeout=self._timeout,
            )

            logger.info("写入点位 %s 成功: %s", point_id, value)
            return True

        except asyncio.TimeoutError:
            logger.error("写入点位 %s 超时", point_id)
            return False
        except Exception as e:
            logger.error("写入点位 %s 失败: %s", point_id, e)
            return False

    async def test_connection(self) -> ConnectionResult:
        """测试 BACnet/IP 连接 — 读取设备 objectName"""
        if self._network is None:
            return ConnectionResult(
                success=False,
                message="BACnet 网络未初始化",
            )

        try:
            device_addr = self._device_address or str(self._device_instance)
            start = time.monotonic()

            # 读取设备对象名称验证连通性
            obj_name = await asyncio.wait_for(
                self._network.read(f"{device_addr} device {self._device_instance} objectName"),
                timeout=self._timeout,
            )

            latency = (time.monotonic() - start) * 1000

            return ConnectionResult(
                success=True,
                message=f"BACnet/IP 连接测试成功 (device={self._device_instance})",
                latency_ms=round(latency, 2),
                sample_data={
                    "device_instance": self._device_instance,
                    "object_name": str(obj_name) if obj_name else None,
                },
            )

        except asyncio.TimeoutError:
            return ConnectionResult(
                success=False,
                message=f"BACnet/IP 连接超时 ({self._timeout}s)",
            )
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

    # ─── 扩展方法: 设备发现与对象浏览 ────────────────────────

    async def discover_devices(self, timeout: float = 5.0) -> list[dict]:
        """发现 BACnet 网络上的设备

        Returns:
            [{"device_instance": 1234, "address": "192.168.1.100", "name": "AHU-01"}, ...]
        """
        if self._network is None:
            return []

        try:
            devices = await asyncio.wait_for(
                self._network.discover(),
                timeout=timeout,
            )
            result = []
            if devices:
                for dev in devices:
                    result.append({
                        "device_instance": getattr(dev, "device_id", None) or getattr(dev, "instance", None),
                        "address": str(getattr(dev, "address", "")),
                        "name": str(getattr(dev, "name", "")),
                    })
            return result
        except Exception as e:
            logger.warning("BACnet 设备发现失败: %s", e)
            return []

    async def browse_objects(self, device_address: str = "") -> list[dict]:
        """浏览设备的 BACnet 对象列表

        Returns:
            [{"object_type": "analogInput", "instance": 1, "name": "Room Temp"}, ...]
        """
        if self._network is None:
            return []

        addr = device_address or self._device_address or str(self._device_instance)

        try:
            # 读取设备的 objectList
            obj_list = await asyncio.wait_for(
                self._network.read(f"{addr} device {self._device_instance} objectList"),
                timeout=self._timeout,
            )

            result = []
            if obj_list:
                for obj_id in obj_list:
                    if hasattr(obj_id, "__iter__") and len(obj_id) >= 2:
                        obj_type_str = str(obj_id[0])
                        obj_instance = int(obj_id[1])
                        # 尝试读取对象名称
                        try:
                            name = await asyncio.wait_for(
                                self._network.read(
                                    f"{addr} {obj_type_str} {obj_instance} objectName"
                                ),
                                timeout=3.0,
                            )
                        except Exception:
                            name = ""
                        result.append({
                            "object_type": obj_type_str,
                            "instance": obj_instance,
                            "name": str(name) if name else "",
                        })
            return result
        except Exception as e:
            logger.warning("BACnet 对象浏览失败: %s", e)
            return []
