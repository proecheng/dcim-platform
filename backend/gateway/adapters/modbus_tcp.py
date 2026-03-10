"""Modbus TCP 协议适配器 — 基于 pymodbus 3.x 异步 API"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.framer import FramerType
from pymodbus.pdu import ExceptionResponse

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

# Modbus 异常码: ILLEGAL_ADDRESS
_ILLEGAL_ADDRESS = 0x02

# 寄存器类型 → pymodbus 读方法名
_READ_METHODS = {
    "HR": "read_holding_registers",
    "IR": "read_input_registers",
    "CO": "read_coils",
    "DI": "read_discrete_inputs",
}

# 数据类型 → 默认寄存器数量
_DEFAULT_COUNT: dict[str, int] = {
    "int16": 1,
    "uint16": 1,
    "int32": 2,
    "uint32": 2,
    "float32": 2,
    "bool": 1,
}


def _parse_address(address: str, data_type: str) -> tuple[str, int, int]:
    """解析点位地址格式: {type}:{address} 或 {type}:{address}:{count}

    Returns:
        (reg_type, address, count)
    """
    parts = address.split(":")
    if len(parts) < 2 or len(parts) > 3:
        raise ValueError(f"无效地址格式: {address}，期望 {{type}}:{{address}}[:{{count}}]")

    reg_type = parts[0].upper()
    if reg_type not in _READ_METHODS:
        raise ValueError(f"未知寄存器类型: {reg_type}，支持: {list(_READ_METHODS.keys())}")

    try:
        addr = int(parts[1])
    except ValueError as e:
        raise ValueError(f"无效寄存器地址: {parts[1]}") from e

    if len(parts) == 3:
        try:
            count = int(parts[2])
        except ValueError as e:
            raise ValueError(f"无效寄存器数量: {parts[2]}") from e
    else:
        if data_type == "string":
            raise ValueError(f"string 类型必须显式指定寄存器数量，如 {reg_type}:{addr}:4")
        count = _DEFAULT_COUNT.get(data_type, 1)

    return reg_type, addr, count


def _convert_value(registers_or_bits: list, data_type: str, word_order: str = "big") -> Any:
    """将寄存器/位值转换为目标数据类型"""
    DATATYPE = AsyncModbusTcpClient.DATATYPE

    if data_type == "bool":
        return bool(registers_or_bits[0])

    if data_type == "int16":
        val = registers_or_bits[0]
        return val - 65536 if val > 32767 else val

    if data_type == "uint16":
        return registers_or_bits[0]

    if data_type == "int32":
        return AsyncModbusTcpClient.convert_from_registers(registers_or_bits, DATATYPE.INT32, word_order=word_order)

    if data_type == "uint32":
        return AsyncModbusTcpClient.convert_from_registers(registers_or_bits, DATATYPE.UINT32, word_order=word_order)

    if data_type == "float32":
        return AsyncModbusTcpClient.convert_from_registers(registers_or_bits, DATATYPE.FLOAT32, word_order=word_order)

    if data_type == "string":
        return AsyncModbusTcpClient.convert_from_registers(registers_or_bits, DATATYPE.STRING, string_encoding="utf-8")

    raise ValueError(f"不支持的数据类型: {data_type}")


@register_adapter("modbus_tcp")
class ModbusTcpAdapter(BaseProtocolAdapter):
    """Modbus TCP 协议适配器"""

    def __init__(self) -> None:
        self._client: Optional[AsyncModbusTcpClient] = None
        self._config: Optional[DataSourceConfig] = None
        self._device_id: int = 1
        self._word_order: str = "big"
        self._state: AdapterState = AdapterState.DISCONNECTED
        self._connected_since: Optional[datetime] = None
        self._last_read_time: Optional[datetime] = None
        self._consecutive_failures: int = 0
        self._error_message: Optional[str] = None

    async def connect(self, config: DataSourceConfig) -> bool:
        """连接 Modbus TCP 设备"""
        # 清理已有连接
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

        self._config = config
        params = config.connection_params

        host = params.get("host")
        if not host:
            self._state = AdapterState.CONFIG_ERROR
            self._error_message = "缺少 host 参数"
            logger.error("Modbus TCP 连接失败: 缺少 host 参数")
            return False

        port = params.get("port", 502)
        self._device_id = params.get("device_id", 1)
        timeout = params.get("timeout", 3)
        self._word_order = params.get("word_order", "big")

        try:
            self._client = AsyncModbusTcpClient(
                host=host,
                port=port,
                framer=FramerType.SOCKET,
                timeout=timeout,
                reconnect_delay=0,
            )
            await self._client.connect()

            if self._client.connected:
                self._state = AdapterState.CONNECTED
                self._connected_since = datetime.now(timezone.utc)
                self._consecutive_failures = 0
                self._error_message = None
                logger.info("Modbus TCP 已连接: %s:%s", host, port)
                return True
            else:
                self._state = AdapterState.DISCONNECTED
                self._error_message = f"无法连接到 {host}:{port}"
                logger.warning("Modbus TCP 无法连接: %s:%s", host, port)
                return False
        except Exception as e:
            self._state = AdapterState.DISCONNECTED
            self._error_message = str(e)
            logger.error("Modbus TCP 连接异常: %s", e)
            return False

    async def disconnect(self) -> None:
        """断开连接"""
        if self._client is not None:
            try:
                await self._client.close()
            except Exception as e:
                logger.warning("Modbus TCP 断开连接时出错: %s", e)
            self._client = None
        self._state = AdapterState.DISCONNECTED
        self._connected_since = None
        logger.info("Modbus TCP 已断开")

    async def read_points(self, points: list[PointConfig]) -> dict[str, PointValue]:
        """读取多个点位，单点失败不影响其他点位"""
        results: dict[str, PointValue] = {}

        for point in points:
            try:
                reg_type, addr, count = _parse_address(point.address, point.data_type)
                read_method = getattr(self._client, _READ_METHODS[reg_type])
                response = await read_method(addr, count=count, slave=self._device_id)

                # 检查错误响应
                if isinstance(response, ExceptionResponse):
                    if response.exception_code == _ILLEGAL_ADDRESS:
                        logger.warning("点位 %s 地址越界 (ILLEGAL_ADDRESS): addr=%s", point.point_id, point.address)
                    else:
                        logger.warning("点位 %s Modbus 异常: code=0x%02X", point.point_id, response.exception_code)
                    results[point.point_id] = PointValue(
                        point_id=point.point_id,
                        value=None,
                        quality=DataQuality.ABNORMAL,
                        timestamp=datetime.now(timezone.utc),
                    )
                    continue

                if response.isError():
                    logger.warning("点位 %s 读取错误: %s", point.point_id, response)
                    results[point.point_id] = PointValue(
                        point_id=point.point_id,
                        value=None,
                        quality=DataQuality.ABNORMAL,
                        timestamp=datetime.now(timezone.utc),
                    )
                    continue

                # 提取原始值
                if reg_type in ("CO", "DI"):
                    raw_values = response.bits[:count]
                else:
                    raw_values = response.registers[:count]

                # 类型转换
                quality = DataQuality.NORMAL
                try:
                    value = _convert_value(raw_values, point.data_type, self._word_order)
                except Exception:
                    # 自动转换尝试: 原始值 → float（精度可能有损，标记为 UNRELIABLE）
                    try:
                        value = float(raw_values[0])
                        quality = DataQuality.UNRELIABLE
                        logger.warning("点位 %s 类型转换失败，自动转为 float: %s", point.point_id, value)
                    except Exception:
                        results[point.point_id] = PointValue(
                            point_id=point.point_id,
                            value=None,
                            quality=DataQuality.ABNORMAL,
                            timestamp=datetime.now(timezone.utc),
                        )
                        continue

                results[point.point_id] = PointValue(
                    point_id=point.point_id,
                    value=value,
                    quality=quality,
                    timestamp=datetime.now(timezone.utc),
                )
                self._consecutive_failures = 0

            except Exception as e:
                logger.error("点位 %s 读取异常: %s", point.point_id, e)
                results[point.point_id] = PointValue(
                    point_id=point.point_id,
                    value=None,
                    quality=DataQuality.ABNORMAL,
                    timestamp=datetime.now(timezone.utc),
                )

        self._last_read_time = datetime.now(timezone.utc)
        return results

    async def write_point(self, point_id: str, value: Any) -> bool:
        """写入单个点位"""
        if not self._config or not self._config.write_enabled:
            logger.warning("写入被禁用，无法写入点位 %s", point_id)
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

        try:
            reg_type, addr, count = _parse_address(point_cfg.address, point_cfg.data_type)

            if reg_type == "CO":
                response = await self._client.write_coil(addr, bool(value), slave=self._device_id)
            elif reg_type == "HR":
                if count == 1:
                    response = await self._client.write_register(addr, int(value), slave=self._device_id)
                else:
                    DATATYPE = AsyncModbusTcpClient.DATATYPE
                    dt_map = {
                        "int32": DATATYPE.INT32,
                        "uint32": DATATYPE.UINT32,
                        "float32": DATATYPE.FLOAT32,
                    }
                    dt = dt_map.get(point_cfg.data_type)
                    if dt is None:
                        logger.error("不支持的多寄存器写入类型: %s", point_cfg.data_type)
                        return False
                    regs = AsyncModbusTcpClient.convert_to_registers(value, dt, word_order=self._word_order)
                    response = await self._client.write_registers(addr, regs, slave=self._device_id)
            else:
                logger.error("不支持写入 %s 类型寄存器", reg_type)
                return False

            if response.isError():
                logger.error("写入点位 %s 失败: %s", point_id, response)
                return False

            logger.info("写入点位 %s 成功: %s", point_id, value)
            return True

        except Exception as e:
            logger.error("写入点位 %s 异常: %s", point_id, e)
            return False

    async def test_connection(self) -> ConnectionResult:
        """测试连接 — 读取保持寄存器 0，超时 10 秒"""
        try:

            async def _test() -> ConnectionResult:
                # 如果未连接，先尝试连接
                if self._client is None or not self._client.connected:
                    if self._config:
                        connected = await self.connect(self._config)
                        if not connected:
                            return ConnectionResult(
                                success=False,
                                message=self._error_message or "连接失败",
                            )
                    else:
                        return ConnectionResult(
                            success=False,
                            message="未配置连接参数",
                        )

                start = time.monotonic()
                response = await self._client.read_holding_registers(0, count=1, slave=self._device_id)
                latency = (time.monotonic() - start) * 1000

                if response.isError():
                    return ConnectionResult(
                        success=False,
                        message=f"读取测试失败: {response}",
                    )

                return ConnectionResult(
                    success=True,
                    message="连接测试成功",
                    latency_ms=round(latency, 2),
                    sample_data={"register_0": response.registers[0]},
                )

            return await asyncio.wait_for(_test(), timeout=10.0)

        except asyncio.TimeoutError:
            return ConnectionResult(
                success=False,
                message="连接测试超时 (10s)",
            )
        except Exception as e:
            return ConnectionResult(
                success=False,
                message=str(e),
            )

    def get_status(self) -> AdapterStatus:
        """获取适配器当前状态"""
        return AdapterStatus(
            state=self._state,
            connected_since=self._connected_since,
            last_read_time=self._last_read_time,
            consecutive_failures=self._consecutive_failures,
            error_message=self._error_message,
        )
