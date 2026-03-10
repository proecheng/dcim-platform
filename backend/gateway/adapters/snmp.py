"""SNMP v2c/v3 协议适配器 — 基于 pysnmp 7.x asyncio API"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    NoSuchInstance,
    NoSuchObject,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    bulk_walk_cmd,
    get_cmd,
    usmAesCfb128Protocol,
    usmDESPrivProtocol,
    usmHMACMD5AuthProtocol,
    usmHMACSHAAuthProtocol,
)

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

# sysDescr OID — 用于连接验证
_SYS_DESCR_OID = ".1.3.6.1.2.1.1.1.0"

# 认证协议映射
AUTH_PROTOCOLS: dict[str, tuple] = {
    "MD5": usmHMACMD5AuthProtocol,
    "SHA": usmHMACSHAAuthProtocol,
}

# 加密协议映射
PRIV_PROTOCOLS: dict[str, tuple] = {
    "DES": usmDESPrivProtocol,
    "AES": usmAesCfb128Protocol,
}

# v3 认证失败关键词
_V3_AUTH_FAILURE_KEYWORDS = ("unknownUserName", "wrongDigest", "decryptionError")


def _parse_oid(address: str) -> tuple[str, str]:
    """解析点位地址格式，返回 (operation, oid)

    支持格式:
        "get:.1.3.6.1.2.1.1.1.0"  → ("get", ".1.3.6.1.2.1.1.1.0")
        ".1.3.6.1.2.1.1.1.0"      → ("get", ".1.3.6.1.2.1.1.1.0")
        "walk:.1.3.6.1.2.1.1"     → ("walk", ".1.3.6.1.2.1.1")
    """
    if address.startswith("walk:"):
        return "walk", address[5:]
    if address.startswith("get:"):
        return "get", address[4:]
    # 无前缀默认 GET
    return "get", address


def _normalize_value(raw_value: Any, point: PointConfig) -> tuple[Any, DataQuality]:
    """将 SNMP 原始值转换为工程值"""
    # 1. 提取原始 Python 值
    if hasattr(raw_value, "prettyPrint"):
        str_val = raw_value.prettyPrint()
    else:
        str_val = str(raw_value)

    # 2. 尝试转为数值
    try:
        numeric_val = float(str_val)
    except (ValueError, TypeError):
        # 非数值类型（字符串），尝试枚举映射
        if point.enum_mapping and str_val in point.enum_mapping:
            return point.enum_mapping[str_val], DataQuality.NORMAL
        return str_val, DataQuality.NORMAL

    # 3. 枚举映射（仅对整数值做映射，避免浮点截断）
    if point.enum_mapping and numeric_val == int(numeric_val):
        str_key = str(int(numeric_val))
        if str_key in point.enum_mapping:
            return point.enum_mapping[str_key], DataQuality.NORMAL

    # 4. 应用 scale + offset
    result = numeric_val * point.scale + point.offset
    return result, DataQuality.NORMAL


def _is_auth_failure_v3(error_indication: Any) -> bool:
    """检测 v3 认证失败"""
    if error_indication is None:
        return False
    err_str = str(error_indication)
    return any(kw in err_str for kw in _V3_AUTH_FAILURE_KEYWORDS)


def _is_timeout(error_indication: Any) -> bool:
    """检测超时错误"""
    if error_indication is None:
        return False
    return "requestTimedOut" in str(error_indication)


@register_adapter("snmp_v3")
@register_adapter("snmp_v2c")
class SnmpAdapter(BaseProtocolAdapter):
    """SNMP v2c/v3 协议适配器 — 统一类，双注册"""

    def __init__(self) -> None:
        self._engine: Optional[SnmpEngine] = None
        self._auth_data: Optional[Any] = None
        self._transport: Optional[UdpTransportTarget] = None
        self._config: Optional[DataSourceConfig] = None
        self._state: AdapterState = AdapterState.DISCONNECTED
        self._connected_since: Optional[datetime] = None
        self._last_read_time: Optional[datetime] = None
        self._consecutive_failures: int = 0
        self._error_message: Optional[str] = None

    async def connect(self, config: DataSourceConfig) -> bool:
        """连接 SNMP 设备 — 根据 protocol_type 区分 v2c/v3"""
        # 清理已有连接
        if self._engine is not None:
            self._engine = None

        self._config = config
        params = config.connection_params

        host = params.get("host")
        if not host:
            self._state = AdapterState.CONFIG_ERROR
            self._error_message = "缺少 host 参数"
            logger.error("SNMP 连接失败: 缺少 host 参数")
            return False

        port = params.get("port", 161)
        timeout = params.get("timeout", 5)

        # 创建引擎和传输目标
        self._engine = SnmpEngine()
        self._transport = await UdpTransportTarget.create((host, port), timeout=timeout, retries=0)

        # 根据协议类型构建认证数据
        if config.protocol_type == "snmp_v3":
            try:
                self._auth_data = self._build_v3_auth(params)
            except ValueError as e:
                self._state = AdapterState.CONFIG_ERROR
                self._error_message = str(e)
                self._engine = None
                logger.error("SNMP v3 配置错误: %s", e)
                return False
        else:
            # v2c
            community = params.get("community", "public")
            self._auth_data = CommunityData(community)

        # 验证连通性 — 读取 sysDescr
        try:
            error_indication, error_status, error_index, var_binds = await get_cmd(
                self._engine,
                self._auth_data,
                self._transport,
                ContextData(),
                ObjectType(ObjectIdentity(_SYS_DESCR_OID)),
            )

            if error_indication:
                if _is_timeout(error_indication):
                    if config.protocol_type == "snmp_v3":
                        self._error_message = "连接超时，请检查目标地址"
                    else:
                        self._error_message = "连接超时，请检查目标地址和团体名"
                    self._state = AdapterState.DISCONNECTED
                    self._engine = None
                    logger.warning("SNMP 连接超时: %s:%s", host, port)
                    return False

                if config.protocol_type == "snmp_v3" and _is_auth_failure_v3(error_indication):
                    self._error_message = "认证失败，请检查团体名/认证参数"
                    self._state = AdapterState.CONFIG_ERROR
                    self._engine = None
                    logger.warning("SNMP v3 认证失败: %s", error_indication)
                    return False

                # 其他传输层错误
                self._error_message = str(error_indication)
                self._state = AdapterState.DISCONNECTED
                self._engine = None
                logger.error("SNMP 连接错误: %s", error_indication)
                return False

            if error_status:
                idx_info = "?"
                if error_index and var_binds:
                    try:
                        idx_info = str(var_binds[int(error_index) - 1][0])
                    except (IndexError, TypeError):
                        idx_info = "?"
                self._error_message = "SNMP 协议错误: %s at %s" % (
                    error_status.prettyPrint(),
                    idx_info,
                )
                self._state = AdapterState.DISCONNECTED
                self._engine = None
                logger.error("SNMP 协议错误: %s", self._error_message)
                return False

            # 连接成功
            self._state = AdapterState.CONNECTED
            self._connected_since = datetime.now(timezone.utc)
            self._consecutive_failures = 0
            self._error_message = None
            sys_descr = var_binds[0][1].prettyPrint() if var_binds else "unknown"
            logger.info("SNMP 已连接: %s:%s — %s", host, port, sys_descr)
            return True

        except Exception as e:
            self._state = AdapterState.DISCONNECTED
            self._error_message = str(e)
            self._engine = None
            logger.error("SNMP 连接异常: %s", e)
            return False

    def _build_v3_auth(self, params: dict) -> UsmUserData:
        """构建 v3 认证数据"""
        username = params.get("username")
        if not username:
            raise ValueError("SNMP v3 缺少 username 参数")

        auth_protocol_name = params.get("auth_protocol")
        auth_key = params.get("auth_key")
        priv_protocol_name = params.get("priv_protocol")
        priv_key = params.get("priv_key")

        # 安全级别校验: priv 需要 auth
        if priv_protocol_name and not auth_protocol_name:
            raise ValueError("加密需要先启用认证")

        kwargs: dict[str, Any] = {}

        if auth_protocol_name:
            auth_proto = AUTH_PROTOCOLS.get(auth_protocol_name.upper())
            if auth_proto is None:
                raise ValueError("不支持的认证协议: %s，支持: %s" % (auth_protocol_name, list(AUTH_PROTOCOLS.keys())))
            if not auth_key:
                raise ValueError("认证协议 %s 需要提供 auth_key" % auth_protocol_name)
            kwargs["authKey"] = auth_key
            kwargs["authProtocol"] = auth_proto

        if priv_protocol_name:
            priv_proto = PRIV_PROTOCOLS.get(priv_protocol_name.upper())
            if priv_proto is None:
                raise ValueError("不支持的加密协议: %s，支持: %s" % (priv_protocol_name, list(PRIV_PROTOCOLS.keys())))
            if not priv_key:
                raise ValueError("加密协议 %s 需要提供 priv_key" % priv_protocol_name)
            kwargs["privKey"] = priv_key
            kwargs["privProtocol"] = priv_proto

        return UsmUserData(username, **kwargs)

    async def disconnect(self) -> None:
        """断开连接 — 释放 SnmpEngine 资源"""
        if self._engine is not None:
            try:
                # pysnmp 7.x 需要显式关闭 dispatcher
                self._engine.close_dispatcher()
            except Exception as e:
                logger.warning("SNMP 引擎关闭时出错: %s", e)
        self._engine = None
        self._auth_data = None
        self._transport = None
        self._state = AdapterState.DISCONNECTED
        self._connected_since = None
        logger.info("SNMP 已断开")

    async def read_points(self, points: list[PointConfig]) -> dict[str, PointValue]:
        """读取多个点位，单点失败不影响其他点位"""
        results: dict[str, PointValue] = {}

        for point in points:
            try:
                operation, oid = _parse_oid(point.address)

                if operation == "get":
                    value, quality = await self._read_get(oid, point)
                else:
                    value, quality = await self._read_walk(oid, point)

                results[point.point_id] = PointValue(
                    point_id=point.point_id,
                    value=value,
                    quality=quality,
                    timestamp=datetime.now(timezone.utc),
                )
                if quality == DataQuality.NORMAL:
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

    async def _snmp_get(self, oid: str) -> tuple:
        """执行单次 SNMP GET"""
        return await get_cmd(
            self._engine,
            self._auth_data,
            self._transport,
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
        )

    async def _read_get(self, oid: str, point: PointConfig) -> tuple[Any, DataQuality]:
        """GET 操作 — 含超时重试"""
        error_indication, error_status, error_index, var_binds = await self._snmp_get(oid)

        # 超时重试一次
        if _is_timeout(error_indication):
            logger.warning("点位 %s GET 超时，重试一次", point.point_id)
            error_indication, error_status, error_index, var_binds = await self._snmp_get(oid)
            if _is_timeout(error_indication):
                logger.warning("点位 %s GET 重试仍超时", point.point_id)
                self._consecutive_failures += 1
                return None, DataQuality.UNRELIABLE

        if error_indication:
            logger.error("点位 %s GET 错误: %s", point.point_id, error_indication)
            return None, DataQuality.ABNORMAL

        if error_status:
            logger.warning("点位 %s SNMP 协议错误: %s", point.point_id, error_status.prettyPrint())
            return None, DataQuality.ABNORMAL

        # 检查 OID 不存在
        if var_binds:
            _, val = var_binds[0]
            if isinstance(val, (NoSuchObject, NoSuchInstance)):
                logger.warning("点位 %s OID 不存在: %s", point.point_id, oid)
                return None, DataQuality.ABNORMAL

            return _normalize_value(val, point)

        return None, DataQuality.ABNORMAL

    async def _read_walk(self, oid: str, point: PointConfig) -> tuple[Any, DataQuality]:
        """WALK 操作 — 取第一个叶子节点的值，超时重试一次"""
        for attempt in range(2):
            try:
                async for error_indication, error_status, error_index, var_binds in bulk_walk_cmd(
                    self._engine,
                    self._auth_data,
                    self._transport,
                    ContextData(),
                    0,  # non_repeaters
                    25,  # max_repetitions
                    ObjectType(ObjectIdentity(oid)),
                ):
                    # 超时 → 跳出本次 walk，进入下一次 attempt
                    if _is_timeout(error_indication):
                        if attempt == 0:
                            logger.warning("点位 %s WALK 超时，重试一次", point.point_id)
                            break
                        logger.warning("点位 %s WALK 重试仍超时", point.point_id)
                        self._consecutive_failures += 1
                        return None, DataQuality.UNRELIABLE

                    if error_indication:
                        logger.error("点位 %s WALK 错误: %s", point.point_id, error_indication)
                        return None, DataQuality.ABNORMAL

                    if error_status:
                        logger.warning("点位 %s WALK 协议错误: %s", point.point_id, error_status.prettyPrint())
                        return None, DataQuality.ABNORMAL

                    # 取第一个叶子节点
                    if var_binds:
                        _, val = var_binds[0]
                        if isinstance(val, (NoSuchObject, NoSuchInstance)):
                            logger.warning("点位 %s WALK OID 不存在: %s", point.point_id, oid)
                            return None, DataQuality.ABNORMAL
                        return _normalize_value(val, point)
                else:
                    # async for 正常结束（无 break）— 没有数据或遍历完毕无结果
                    logger.warning("点位 %s WALK 无结果: %s", point.point_id, oid)
                    return None, DataQuality.ABNORMAL

                # break 出来的（超时），继续下一次 attempt
                continue

            except Exception as e:
                logger.error("点位 %s WALK 异常: %s", point.point_id, e)
                return None, DataQuality.ABNORMAL

        # 两次 attempt 都 break（不应到达，但防御性返回）
        self._consecutive_failures += 1
        return None, DataQuality.UNRELIABLE

    async def write_point(self, point_id: str, value: Any) -> bool:
        """SNMP 适配器不支持写入操作"""
        logger.warning("SNMP 适配器不支持写入操作，点位: %s", point_id)
        return False

    async def test_connection(self) -> ConnectionResult:
        """测试连接 — 读取 sysDescr，超时 10 秒"""
        try:

            async def _test() -> ConnectionResult:
                if self._engine is None:
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
                error_indication, error_status, error_index, var_binds = await get_cmd(
                    self._engine,
                    self._auth_data,
                    self._transport,
                    ContextData(),
                    ObjectType(ObjectIdentity(_SYS_DESCR_OID)),
                )
                latency = (time.monotonic() - start) * 1000

                if error_indication:
                    return ConnectionResult(
                        success=False,
                        message="连接测试失败: %s" % error_indication,
                    )

                if error_status:
                    return ConnectionResult(
                        success=False,
                        message="SNMP 协议错误: %s" % error_status.prettyPrint(),
                    )

                sys_descr = var_binds[0][1].prettyPrint() if var_binds else "unknown"
                return ConnectionResult(
                    success=True,
                    message="连接测试成功",
                    latency_ms=round(latency, 2),
                    sample_data={"sysDescr": sys_descr},
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
