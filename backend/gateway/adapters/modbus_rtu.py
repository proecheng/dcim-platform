"""Modbus RTU 串口协议适配器 — 基于 pymodbus 3.x AsyncModbusSerialClient"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from pymodbus.client import AsyncModbusSerialClient
from pymodbus.framer import FramerType
from pymodbus.pdu import ExceptionResponse
from pymodbus.exceptions import ModbusException
from serial import SerialException

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
from .modbus_tcp import _parse_address_spec, _convert_value, _extract_bit_value, _READ_METHODS, _ILLEGAL_ADDRESS

logger = logging.getLogger(__name__)


@register_adapter("modbus_rtu")
class ModbusRtuAdapter(BaseProtocolAdapter):
    """Modbus RTU 串口协议适配器"""

    def __init__(self) -> None:
        self._client: Optional[AsyncModbusSerialClient] = None
        self._config: Optional[DataSourceConfig] = None
        self._device_id: int = 1
        self._word_order: str = "big"
        self._crc_failure_count: int = 0
        self._state: AdapterState = AdapterState.DISCONNECTED
        self._connected_since: Optional[datetime] = None
        self._last_read_time: Optional[datetime] = None
        self._consecutive_failures: int = 0
        self._error_message: Optional[str] = None

    async def connect(self, config: DataSourceConfig) -> bool:
        """连接 Modbus RTU 串口设备"""
        # 清理已有连接
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

        self._config = config
        params = config.connection_params

        port = params.get("port")
        if not port:
            self._state = AdapterState.CONFIG_ERROR
            self._error_message = "缺少 port 参数"
            logger.error("Modbus RTU 连接失败: 缺少 port 参数")
            return False

        baudrate = params.get("baudrate", 9600)
        bytesize = params.get("bytesize", 8)
        parity = params.get("parity", "N")
        stopbits = params.get("stopbits", 1)
        self._device_id = params.get("device_id", 1)
        timeout = params.get("timeout", 3)
        self._word_order = params.get("word_order", "big")

        try:
            self._client = AsyncModbusSerialClient(
                port=port,
                framer=FramerType.RTU,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                timeout=timeout,
                handle_local_echo=False,
                reconnect_delay=0,
            )
            await self._client.connect()

            if self._client.connected:
                self._state = AdapterState.CONNECTED
                self._connected_since = datetime.now(timezone.utc)
                self._consecutive_failures = 0
                self._crc_failure_count = 0
                self._error_message = None
                logger.info("Modbus RTU 已连接: %s @ %s baud", port, baudrate)
                return True
            else:
                self._state = AdapterState.DISCONNECTED
                self._error_message = "无法连接到 %s" % port
                logger.warning("Modbus RTU 无法连接: %s", port)
                return False

        except (SerialException, PermissionError) as e:
            self._state = AdapterState.CONFIG_ERROR
            self._error_message = str(e)
            logger.error("串口被占用或不存在: %s — %s", port, e)
            return False
        except Exception as e:
            self._state = AdapterState.DISCONNECTED
            self._error_message = str(e)
            logger.error("Modbus RTU 连接异常: %s", e)
            return False

    async def disconnect(self) -> None:
        """断开连接"""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        self._state = AdapterState.DISCONNECTED
        self._connected_since = None
        logger.info("Modbus RTU 已断开")

    async def _read_with_retry(self, read_method: Any, addr: int, count: int) -> tuple[Any, DataQuality]:
        """带重试的读取，检测 CRC 错误

        Returns:
            (response_or_None, quality)
            - ExceptionResponse 返回 (None, ABNORMAL)
            - CRC 错误重试后仍失败返回 (None, UNRELIABLE)
            - 成功返回 (response, NORMAL)
        """
        try:
            response = await read_method(addr, count=count, slave=self._device_id)
        except (asyncio.TimeoutError, ModbusException) as e:
            # 超时/Modbus异常 → 重试一次
            logger.warning("Modbus RTU 读取超时/异常，重试: addr=%s, err=%s", addr, e)
            try:
                response = await read_method(addr, count=count, slave=self._device_id)
            except Exception:
                return None, DataQuality.ABNORMAL
        except Exception:
            # 其他异常不重试
            return None, DataQuality.ABNORMAL

        # ExceptionResponse → ABNORMAL，不重试
        if isinstance(response, ExceptionResponse):
            if response.exception_code == _ILLEGAL_ADDRESS:
                logger.warning("地址越界 (ILLEGAL_ADDRESS): addr=%s", addr)
            else:
                logger.warning("Modbus 异常: addr=%s, code=0x%02X", addr, response.exception_code)
            return None, DataQuality.ABNORMAL

        # isError() 但非 ExceptionResponse → 可能是 CRC 错误
        if response.isError():
            logger.warning("Modbus RTU 非异常错误（可能 CRC），重试: addr=%s", addr)
            # 重试一次
            try:
                response = await read_method(addr, count=count, slave=self._device_id)
            except Exception:
                self._crc_failure_count += 1
                if self._crc_failure_count >= 3:
                    logger.error("连续 CRC 失败 >= 3 次，请检查串口参数（波特率、校验位）")
                return None, DataQuality.UNRELIABLE

            if response.isError() or isinstance(response, ExceptionResponse):
                self._crc_failure_count += 1
                if self._crc_failure_count >= 3:
                    logger.error("连续 CRC 失败 >= 3 次，请检查串口参数（波特率、校验位）")
                return None, DataQuality.UNRELIABLE

        # 成功 → 重置 CRC 计数
        self._crc_failure_count = 0
        return response, DataQuality.NORMAL

    async def read_points(self, points: list[PointConfig]) -> dict[str, PointValue]:
        """读取多个点位，单点失败不影响其他点位"""
        results: dict[str, PointValue] = {}

        for point in points:
            try:
                spec = _parse_address_spec(point.address, point.data_type)
                read_method = getattr(self._client, _READ_METHODS[spec.reg_type])

                response, quality = await self._read_with_retry(read_method, spec.address, spec.count)

                if response is None:
                    results[point.point_id] = PointValue(
                        point_id=point.point_id,
                        value=None,
                        quality=quality,
                        timestamp=datetime.now(timezone.utc),
                    )
                    continue

                # 提取原始值
                if spec.reg_type in ("CO", "DI"):
                    raw_values = response.bits[: spec.count]
                else:
                    raw_values = response.registers[: spec.count]

                # 类型转换
                try:
                    if spec.has_bit_selector:
                        value = _extract_bit_value(raw_values[0], spec, point.data_type)
                    else:
                        value = _convert_value(raw_values, point.data_type, self._word_order)
                except Exception:
                    # 自动转换尝试: 原始值 → float
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
        """写入单个点位 — 仅支持 HR 和 CO"""
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
            spec = _parse_address_spec(point_cfg.address, point_cfg.data_type)

            if spec.has_bit_selector:
                logger.error("不支持写入寄存器位段地址: %s", point_cfg.address)
                return False

            if spec.reg_type in ("IR", "DI"):
                logger.error("不支持写入 %s 类型寄存器（只读）", spec.reg_type)
                return False

            if spec.reg_type == "CO":
                response = await self._client.write_coil(spec.address, bool(value), slave=self._device_id)
            elif spec.reg_type == "HR":
                if spec.count == 1:
                    response = await self._client.write_register(spec.address, int(value), slave=self._device_id)
                else:
                    DATATYPE = AsyncModbusSerialClient.DATATYPE
                    dt_map = {
                        "int32": DATATYPE.INT32,
                        "uint32": DATATYPE.UINT32,
                        "float32": DATATYPE.FLOAT32,
                    }
                    dt = dt_map.get(point_cfg.data_type)
                    if dt is None:
                        logger.error("不支持的多寄存器写入类型: %s", point_cfg.data_type)
                        return False
                    regs = AsyncModbusSerialClient.convert_to_registers(value, dt, word_order=self._word_order)
                    response = await self._client.write_registers(spec.address, regs, slave=self._device_id)
            else:
                logger.error("不支持写入 %s 类型寄存器", spec.reg_type)
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
                        message="读取测试失败: %s" % response,
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
