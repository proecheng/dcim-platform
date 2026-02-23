"""OPC-UA 协议适配器 — 通过 OPC-UA 协议采集工业设备数据 — Story 15.4

设计说明:
  OpcUaAdapter 是拉模式适配器:
  - connect() 创建 asyncua.Client，配置认证，建立连接
  - read_points() 使用 client.read_values() 批量读取节点值
  - write_point() 通过 node.write_value() 写入
  - 支持匿名、用户名密码、证书三种认证方式
  - 支持节点浏览和订阅模式（扩展方法）

  每个 OpcUaAdapter 持有独立的 asyncua.Client 实例
  （OPC-UA 没有端口绑定限制，每个连接是独立的 TCP session）
"""

import asyncio
import logging
import re
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

# ─── 安全策略映射 ─────────────────────────────────────────────

SECURITY_POLICY_MAP: dict[str, str] = {
    "none": "None",
    "basic128rsa15": "Basic128Rsa15",
    "basic256": "Basic256",
    "basic256sha256": "Basic256Sha256",
    "aes128sha256rsaoaep": "Aes128Sha256RsaOaep",
    "aes256sha256rsapss": "Aes256Sha256RsaPss",
}

# ─── NodeId 验证 ──────────────────────────────────────────────

# OPC-UA NodeId 格式: [ns=N;]{i=数字|s=字符串|g=GUID|b=Base64}
_NODEID_PATTERN = re.compile(r"^(ns=\d+;)?(i=\d+|s=.+|g=[0-9a-fA-F\-]+|b=[A-Za-z0-9+/=]+)$")


def validate_node_id(address: str) -> bool:
    """验证 OPC-UA NodeId 格式

    支持格式:
      - ns=2;i=1001      命名空间2，数字标识符
      - ns=2;s=Temperature  命名空间2，字符串标识符
      - i=2258            命名空间0（默认），数字标识符
      - ns=2;g=xxx-guid   GUID 标识符
      - ns=2;b=base64     Opaque (Base64) 标识符
    """
    return bool(_NODEID_PATTERN.match(address))


# ─── OPC-UA 适配器 ───────────────────────────────────────────


@register_adapter("opc_ua")
class OpcUaAdapter(BaseProtocolAdapter):
    """OPC-UA 协议适配器 — 采集工业设备数据

    connection_config 示例:
    {
        "endpoint_url": "opc.tcp://192.168.1.100:4840",
        "security_policy": "none",
        "security_mode": "none",
        "auth_type": "anonymous",
        "auth_config": {
            "username": "admin",
            "password": "secret",
            "certificate_path": "/path/to/cert.der",
            "private_key_path": "/path/to/key.pem",
            "server_certificate_path": "/path/to/server.der"
        },
        "timeout": 10,
        "session_timeout": 3600000
    }

    DataSourcePoint.address 格式:
      OPC-UA NodeId 字符串，如 "ns=2;i=1001" 或 "ns=2;s=Temperature"
    """

    def __init__(self) -> None:
        self._config: Optional[DataSourceConfig] = None
        self._state: AdapterState = AdapterState.DISCONNECTED
        self._connected_since: Optional[datetime] = None
        self._last_read_time: Optional[datetime] = None
        self._consecutive_failures: int = 0
        self._error_message: Optional[str] = None

        # asyncua Client 实例
        self._client: Any = None

        # 配置缓存
        self._endpoint_url: str = ""
        self._timeout: float = 10.0

        # 订阅管理
        self._subscription: Any = None
        self._sub_handles: list[Any] = []

    async def connect(self, config: DataSourceConfig) -> bool:
        """连接 OPC-UA 服务器"""
        # 防止重复 connect 导致资源泄漏
        if self._client is not None:
            await self.disconnect()

        self._config = config
        params = config.connection_params

        # 解析必要配置
        self._endpoint_url = params.get("endpoint_url", "")
        if not self._endpoint_url:
            self._state = AdapterState.CONFIG_ERROR
            self._error_message = "缺少 endpoint_url 配置"
            return False

        self._timeout = params.get("timeout", 10)
        session_timeout = params.get("session_timeout", 3600000)
        auth_type = params.get("auth_type", "anonymous").lower()
        auth_config = params.get("auth_config", {})
        security_policy = params.get("security_policy", "none").lower()
        security_mode = params.get("security_mode", "none").lower()

        # 验证认证配置
        if auth_type == "username":
            if not auth_config.get("username"):
                self._state = AdapterState.CONFIG_ERROR
                self._error_message = "用户名认证缺少 username"
                return False
        elif auth_type == "certificate":
            if not auth_config.get("certificate_path") or not auth_config.get("private_key_path"):
                self._state = AdapterState.CONFIG_ERROR
                self._error_message = "证书认证缺少 certificate_path 或 private_key_path"
                return False
        elif auth_type != "anonymous":
            self._state = AdapterState.CONFIG_ERROR
            self._error_message = f"不支持的认证方式: {auth_type}，仅支持 anonymous/username/certificate"
            return False

        # 验证安全策略
        if security_policy != "none" and security_policy not in SECURITY_POLICY_MAP:
            self._state = AdapterState.CONFIG_ERROR
            self._error_message = f"不支持的安全策略: {security_policy}，支持: {list(SECURITY_POLICY_MAP.keys())}"
            return False

        # 验证点位地址格式
        for point in config.points:
            if not validate_node_id(point.address):
                self._state = AdapterState.CONFIG_ERROR
                self._error_message = f"点位 {point.point_id} 地址无效: {point.address}"
                return False

        # 创建 asyncua Client 并连接
        try:
            from asyncua import Client

            self._client = Client(url=self._endpoint_url, timeout=self._timeout)
            self._client.session_timeout = session_timeout

            # 配置认证
            if auth_type == "username":
                self._client.set_user(auth_config["username"])
                self._client.set_password(auth_config.get("password", ""))

            # 配置安全策略（证书认证或加密通信）
            if security_policy != "none":
                await self._setup_security(security_policy, security_mode, auth_config)

            # 连接
            await asyncio.wait_for(
                self._client.connect(),
                timeout=self._timeout,
            )

            self._state = AdapterState.CONNECTED
            self._connected_since = datetime.now(timezone.utc)
            self._consecutive_failures = 0
            self._error_message = None
            logger.info(
                "OPC-UA 适配器已连接: %s (auth=%s, security=%s)",
                self._endpoint_url,
                auth_type,
                security_policy,
            )
            return True

        except ImportError:
            self._client = None
            self._state = AdapterState.CONFIG_ERROR
            self._error_message = "asyncua 未安装"
            logger.error("OPC-UA 适配器: asyncua 未安装")
            return False
        except asyncio.TimeoutError:
            self._client = None
            self._state = AdapterState.DISCONNECTED
            self._error_message = f"连接超时 ({self._timeout}s)"
            logger.error("OPC-UA 适配器连接超时: %s", self._endpoint_url)
            return False
        except Exception as e:
            self._client = None
            self._state = AdapterState.DISCONNECTED
            self._error_message = str(e)
            logger.error("OPC-UA 适配器连接失败: %s", e)
            return False

    async def _setup_security(
        self,
        security_policy: str,
        security_mode: str,
        auth_config: dict,
    ) -> None:
        """配置 OPC-UA 安全策略和证书"""
        try:
            import asyncua.crypto.security_policies as sp
            from asyncua import ua
        except ImportError as e:
            raise ImportError(f"asyncua 安全模块不可用: {e}") from e

        # 动态获取安全策略类
        policy_name = SECURITY_POLICY_MAP.get(security_policy, "Basic256Sha256")
        default_policy = getattr(sp, "SecurityPolicyBasic256Sha256", None)
        policy_cls = getattr(sp, f"SecurityPolicy{policy_name}", default_policy)

        if policy_cls is None:
            raise ValueError(f"安全策略类 SecurityPolicy{policy_name} 不可用")

        cert_path = auth_config.get("certificate_path", "")
        key_path = auth_config.get("private_key_path", "")
        server_cert = auth_config.get("server_certificate_path", "")

        # security_mode 映射
        mode_map = {
            "none": ua.MessageSecurityMode.None_,
            "sign": ua.MessageSecurityMode.Sign,
            "signandencrypt": ua.MessageSecurityMode.SignAndEncrypt,
        }
        mode = mode_map.get(security_mode.lower(), ua.MessageSecurityMode.SignAndEncrypt)

        await self._client.set_security(
            policy_cls,
            cert_path,
            key_path,
            server_cert,
            mode,
        )

    async def disconnect(self) -> None:
        """断开 OPC-UA 连接"""
        # 先清理订阅
        await self._cleanup_subscription()

        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception as e:
                logger.warning("OPC-UA 断开连接异常: %s", e)
            self._client = None

        self._state = AdapterState.DISCONNECTED
        self._connected_since = None
        logger.info("OPC-UA 适配器已断开: %s", self._endpoint_url)

    async def read_points(self, points: list[PointConfig]) -> dict[str, PointValue]:
        """批量读取 OPC-UA 节点值"""
        results: dict[str, PointValue] = {}

        if self._client is None:
            for point in points:
                results[point.point_id] = PointValue(
                    point_id=point.point_id,
                    value=None,
                    quality=DataQuality.ABNORMAL,
                    timestamp=datetime.now(timezone.utc),
                )
            return results

        # 尝试批量读取
        try:
            nodes = [self._client.get_node(p.address) for p in points]
            values = await asyncio.wait_for(
                self._client.read_values(nodes),
                timeout=self._timeout,
            )

            for point, value in zip(points, values):
                # asyncua 返回 ua.StatusCode 时表示读取失败
                if hasattr(value, "is_good") and callable(getattr(value, "is_good", None)):
                    if not value.is_good():
                        results[point.point_id] = PointValue(
                            point_id=point.point_id,
                            value=None,
                            quality=DataQuality.ABNORMAL,
                            timestamp=datetime.now(timezone.utc),
                        )
                    else:
                        # StatusCode 是 Good 但无实际值
                        results[point.point_id] = PointValue(
                            point_id=point.point_id,
                            value=None,
                            quality=DataQuality.UNRELIABLE,
                            timestamp=datetime.now(timezone.utc),
                        )
                elif value is None:
                    results[point.point_id] = PointValue(
                        point_id=point.point_id,
                        value=None,
                        quality=DataQuality.UNRELIABLE,
                        timestamp=datetime.now(timezone.utc),
                    )
                else:
                    results[point.point_id] = PointValue(
                        point_id=point.point_id,
                        value=value,
                        quality=DataQuality.NORMAL,
                        timestamp=datetime.now(timezone.utc),
                    )

            self._consecutive_failures = 0
            self._error_message = None

        except Exception as e:
            logger.debug("OPC-UA 批量读取失败，回退逐点位读取: %s", e)

            # Fallback: 逐点位读取
            try:
                await self._read_points_individually(points, results)
                self._consecutive_failures = 0
                self._error_message = None
            except Exception as fallback_err:
                self._consecutive_failures += 1
                self._error_message = str(fallback_err)
                logger.error("OPC-UA 读取失败: %s", fallback_err)

                for point in points:
                    if point.point_id not in results:
                        results[point.point_id] = PointValue(
                            point_id=point.point_id,
                            value=None,
                            quality=DataQuality.ABNORMAL,
                            timestamp=datetime.now(timezone.utc),
                        )

                if self._consecutive_failures >= (self._config.retry_max_failures if self._config else 5):
                    self._state = AdapterState.COMMUNICATION_INTERRUPTED

        self._last_read_time = datetime.now(timezone.utc)
        return results

    async def _read_points_individually(
        self,
        points: list[PointConfig],
        results: dict[str, PointValue],
    ) -> None:
        """逐点位读取 — fallback

        当所有点位均读取失败时抛出 RuntimeError，
        以便 read_points() 触发 consecutive_failures 递增。
        """
        failure_count = 0
        for point in points:
            if point.point_id in results:
                continue
            try:
                node = self._client.get_node(point.address)
                value = await asyncio.wait_for(
                    node.read_value(),
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

        if failure_count == len(points):
            raise RuntimeError(f"所有 {len(points)} 个点位读取均失败")

    async def write_point(self, point_id: str, value: Any) -> bool:
        """写入 OPC-UA 节点值"""
        if not self._config or not self._config.write_enabled:
            logger.warning("写入被禁用，无法写入点位 %s", point_id)
            return False

        if self._client is None:
            logger.error("OPC-UA 未连接，无法写入点位 %s", point_id)
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
            node = self._client.get_node(point_cfg.address)
            await asyncio.wait_for(
                node.write_value(value),
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
        """测试 OPC-UA 连接 — 读取 Server_ServerStatus_CurrentTime"""
        if self._client is None:
            return ConnectionResult(
                success=False,
                message="OPC-UA 客户端未初始化",
            )

        try:
            start = time.monotonic()

            # 读取服务器当前时间验证连通性 (i=2258 = Server_ServerStatus_CurrentTime)
            node = self._client.get_node("i=2258")
            server_time = await asyncio.wait_for(
                node.read_value(),
                timeout=self._timeout,
            )

            latency = (time.monotonic() - start) * 1000

            return ConnectionResult(
                success=True,
                message=f"OPC-UA 连接测试成功 ({self._endpoint_url})",
                latency_ms=round(latency, 2),
                sample_data={
                    "endpoint_url": self._endpoint_url,
                    "server_time": str(server_time) if server_time else None,
                },
            )

        except asyncio.TimeoutError:
            return ConnectionResult(
                success=False,
                message=f"OPC-UA 连接超时 ({self._timeout}s)",
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

    # ─── 扩展方法: 节点浏览 ──────────────────────────────────

    async def browse_nodes(self, node_id: str = "i=85", max_depth: int = 3) -> list[dict]:
        """浏览 OPC-UA 节点树

        Args:
            node_id: 起始节点 ID（默认 i=85 = Objects 文件夹）
            max_depth: 最大递归深度

        Returns:
            [{"id": "ns=2;i=1001", "name": "Temperature", "class": "Variable", "children": [...]}, ...]
        """
        if self._client is None:
            return []

        try:
            node = self._client.get_node(node_id)
            return await asyncio.wait_for(
                self._browse_recursive(node, max_depth, 0),
                timeout=self._timeout * max_depth,
            )
        except asyncio.TimeoutError:
            logger.warning("OPC-UA 节点浏览超时")
            return []
        except Exception as e:
            logger.warning("OPC-UA 节点浏览失败: %s", e)
            return []

    async def _browse_recursive(self, node: Any, max_depth: int, current_depth: int) -> list[dict]:
        """递归浏览节点"""
        if current_depth >= max_depth:
            return []

        result = []
        try:
            from asyncua import ua

            children = await node.get_children()
            for child in children:
                try:
                    node_class = await child.read_node_class()
                    display_name = await child.read_display_name()

                    entry: dict[str, Any] = {
                        "id": child.nodeid.to_string(),
                        "name": display_name.Text if display_name else "",
                        "class": node_class.name if hasattr(node_class, "name") else str(node_class),
                    }

                    # 只递归 Object 和 Variable 节点
                    if node_class in (ua.NodeClass.Object, ua.NodeClass.Variable):
                        entry["children"] = await self._browse_recursive(child, max_depth, current_depth + 1)
                    else:
                        entry["children"] = []

                    result.append(entry)
                except Exception:
                    continue
        except Exception as e:
            logger.debug("浏览节点子项失败: %s", e)

        return result

    # ─── 扩展方法: 订阅模式 ──────────────────────────────────

    async def subscribe_data_change(
        self,
        points: list[PointConfig],
        handler: Any,
        interval: int = 500,
    ) -> bool:
        """订阅数据变化通知

        Args:
            points: 要订阅的点位列表
            handler: 订阅处理器，需实现 datachange_notification(node, val, data) 方法
            interval: 发布间隔（毫秒）

        Returns:
            是否订阅成功
        """
        if self._client is None:
            logger.error("OPC-UA 未连接，无法订阅")
            return False

        try:
            # 清理已有订阅
            await self._cleanup_subscription()

            self._subscription = await self._client.create_subscription(interval, handler)

            nodes = [self._client.get_node(p.address) for p in points]
            handles = await self._subscription.subscribe_data_change(nodes)

            # subscribe_data_change 可能返回单个 handle 或 handle 列表
            if isinstance(handles, list):
                self._sub_handles = handles
            else:
                self._sub_handles = [handles]

            logger.info("OPC-UA 订阅已创建: %d 个节点, 间隔=%dms", len(points), interval)
            return True

        except Exception as e:
            logger.error("OPC-UA 订阅失败: %s", e)
            return False

    async def unsubscribe(self) -> None:
        """取消所有订阅"""
        await self._cleanup_subscription()

    async def _cleanup_subscription(self) -> None:
        """清理订阅资源"""
        if self._subscription is not None:
            try:
                if self._sub_handles:
                    await self._subscription.unsubscribe(self._sub_handles)
                    self._sub_handles.clear()

                await self._subscription.delete()
                logger.info("OPC-UA 订阅已清理")
            except Exception as e:
                logger.warning("OPC-UA 订阅清理异常: %s", e)
            finally:
                self._subscription = None
                self._sub_handles = []
