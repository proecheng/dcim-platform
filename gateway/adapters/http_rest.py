"""HTTP REST 协议适配器 — 通过 HTTP 请求采集第三方系统数据 — Story 15.2

设计说明:
  HttpRestAdapter 是拉模式适配器，与 Modbus TCP 类似:
  - connect() 验证配置并测试连通性
  - read_points() 发送 HTTP 请求，按 JSON 路径提取点位数据
  - 支持 GET/POST 请求方式
  - 支持 Basic Auth 和 Bearer Token 认证
  - 支持自定义请求头和请求体
  - 使用 httpx 异步 HTTP 客户端
"""
import asyncio
import logging
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
from .utils import build_json_extractor as _build_json_extractor

logger = logging.getLogger(__name__)


@register_adapter("http_rest")
class HttpRestAdapter(BaseProtocolAdapter):
    """HTTP REST 协议适配器 — 通过 HTTP 请求采集第三方系统数据

    connection_config 示例:
    {
        "base_url": "https://api.example.com",      # 基础 URL
        "method": "GET",                              # 请求方式: GET / POST
        "endpoint": "/api/v1/sensors/data",           # 请求路径
        "auth_type": "none",                          # 认证方式: none / basic / bearer
        "auth_config": {                              # 认证配置
            "username": "admin",                      # Basic Auth 用户名
            "password": "secret",                     # Basic Auth 密码
            "token": "eyJhbGciOi..."                  # Bearer Token
        },
        "headers": {                                  # 自定义请求头（可选）
            "X-API-Key": "abc123"
        },
        "request_body": {                             # POST 请求体（可选）
            "device_ids": ["sensor_01", "sensor_02"]
        },
        "timeout": 10,                                # 请求超时（秒）
        "verify_ssl": true,                           # 是否验证 SSL 证书
        "response_root": "data"                       # 响应数据根路径（可选）
    }

    DataSourcePoint.address 格式:
      JSON 路径，如 "temperature" 或 "sensors[0].value" 或 "readings.temp_01"
      如果配置了 response_root，则从 root 节点开始提取
    """

    def __init__(self) -> None:
        self._config: Optional[DataSourceConfig] = None
        self._state: AdapterState = AdapterState.DISCONNECTED
        self._connected_since: Optional[datetime] = None
        self._last_read_time: Optional[datetime] = None
        self._consecutive_failures: int = 0
        self._error_message: Optional[str] = None

        # HTTP 客户端（延迟创建）
        self._client: Any = None

        # 配置缓存
        self._base_url: str = ""
        self._method: str = "GET"
        self._endpoint: str = ""
        self._auth_type: str = "none"
        self._auth_config: dict = {}
        self._headers: dict[str, str] = {}
        self._request_body: Optional[dict] = None
        self._timeout: float = 10.0
        self._verify_ssl: bool = True
        self._response_root: str = ""

        # 点位地址 → 提取器缓存
        self._extractors: dict[str, Callable] = {}

    async def connect(self, config: DataSourceConfig) -> bool:
        """验证配置并建立 HTTP 客户端（仅验证配置，不发送探测请求；需调用 test_connection() 验证网络连通性）"""
        self._config = config
        params = config.connection_params

        # 解析必要配置
        self._base_url = params.get("base_url", "").rstrip("/")
        if not self._base_url:
            self._state = AdapterState.CONFIG_ERROR
            self._error_message = "缺少 base_url 配置"
            return False

        self._method = params.get("method", "GET").upper()
        if self._method not in ("GET", "POST"):
            self._state = AdapterState.CONFIG_ERROR
            self._error_message = f"不支持的请求方式: {self._method}，仅支持 GET/POST"
            return False

        self._endpoint = params.get("endpoint", "")
        self._auth_type = params.get("auth_type", "none").lower()
        self._auth_config = params.get("auth_config", {})
        self._headers = params.get("headers", {})
        self._request_body = params.get("request_body")
        self._timeout = params.get("timeout", 10)
        self._verify_ssl = params.get("verify_ssl", True)
        self._response_root = params.get("response_root", "")

        # 验证认证配置
        if self._auth_type == "basic":
            if not self._auth_config.get("username"):
                self._state = AdapterState.CONFIG_ERROR
                self._error_message = "Basic Auth 缺少 username"
                return False
        elif self._auth_type == "bearer":
            if not self._auth_config.get("token"):
                self._state = AdapterState.CONFIG_ERROR
                self._error_message = "Bearer Token 认证缺少 token"
                return False
        elif self._auth_type != "none":
            self._state = AdapterState.CONFIG_ERROR
            self._error_message = f"不支持的认证方式: {self._auth_type}，仅支持 none/basic/bearer"
            return False

        # 预编译点位提取器
        self._extractors.clear()
        for point in config.points:
            self._extractors[point.point_id] = _build_json_extractor(point.address)

        # 创建 httpx 客户端
        try:
            import httpx

            auth = None
            if self._auth_type == "basic":
                auth = httpx.BasicAuth(
                    username=self._auth_config["username"],
                    password=self._auth_config.get("password", ""),
                )

            headers = dict(self._headers)
            if self._auth_type == "bearer":
                headers["Authorization"] = f"Bearer {self._auth_config['token']}"

            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                auth=auth,
                timeout=httpx.Timeout(self._timeout),
                verify=self._verify_ssl,
            )

            self._state = AdapterState.CONNECTED
            self._connected_since = datetime.now(timezone.utc)
            self._consecutive_failures = 0
            self._error_message = None
            logger.info(
                "HTTP REST 适配器已启动: %s %s%s (auth=%s)",
                self._method, self._base_url, self._endpoint, self._auth_type,
            )
            return True

        except ImportError:
            self._state = AdapterState.CONFIG_ERROR
            self._error_message = "httpx 未安装"
            logger.error("HTTP REST 适配器: httpx 未安装")
            return False
        except Exception as e:
            self._state = AdapterState.DISCONNECTED
            self._error_message = str(e)
            logger.error("HTTP REST 适配器初始化失败: %s", e)
            return False

    async def disconnect(self) -> None:
        """关闭 HTTP 客户端"""
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass
            self._client = None
        self._state = AdapterState.DISCONNECTED
        self._connected_since = None
        self._extractors.clear()
        logger.info("HTTP REST 适配器已断开")

    async def read_points(self, points: list[PointConfig]) -> dict[str, PointValue]:
        """发送 HTTP 请求并从响应中提取点位数据"""
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

        try:
            # 发送 HTTP 请求
            if self._method == "GET":
                response = await self._client.get(self._endpoint)
            else:
                response = await self._client.post(
                    self._endpoint,
                    json=self._request_body,
                )

            response.raise_for_status()
            data = response.json()

            # 如果配置了 response_root，先定位到根节点
            if self._response_root:
                root_extractor = _build_json_extractor(self._response_root)
                data = root_extractor(data)

            # 逐点位提取
            for point in points:
                try:
                    extractor = self._extractors.get(point.point_id)
                    if extractor is None:
                        extractor = _build_json_extractor(point.address)
                        self._extractors[point.point_id] = extractor

                    value = extractor(data)
                    results[point.point_id] = PointValue(
                        point_id=point.point_id,
                        value=value,
                        quality=DataQuality.NORMAL,
                        timestamp=datetime.now(timezone.utc),
                    )
                except (KeyError, IndexError, TypeError) as e:
                    logger.warning(
                        "点位 %s 数据提取失败 (address=%s): %s",
                        point.point_id, point.address, e,
                    )
                    results[point.point_id] = PointValue(
                        point_id=point.point_id,
                        value=None,
                        quality=DataQuality.ABNORMAL,
                        timestamp=datetime.now(timezone.utc),
                    )

            self._consecutive_failures = 0
            self._error_message = None

        except Exception as e:
            self._consecutive_failures += 1
            self._error_message = str(e)
            logger.error("HTTP REST 请求失败: %s", e)

            # 请求失败时，所有未填充的点位标记为 ABNORMAL
            for point in points:
                if point.point_id not in results:
                    results[point.point_id] = PointValue(
                        point_id=point.point_id,
                        value=None,
                        quality=DataQuality.ABNORMAL,
                        timestamp=datetime.now(timezone.utc),
                    )

            # 连续失败过多，标记通信中断
            if self._consecutive_failures >= (
                self._config.retry_max_failures if self._config else 5
            ):
                self._state = AdapterState.COMMUNICATION_INTERRUPTED

        self._last_read_time = datetime.now(timezone.utc)
        return results

    async def write_point(self, point_id: str, value: Any) -> bool:
        """HTTP REST 适配器暂不支持写入

        未来可扩展为 PUT/PATCH 请求写入。
        """
        logger.warning("HTTP REST 适配器暂不支持写入: point_id=%s", point_id)
        return False

    async def test_connection(self) -> ConnectionResult:
        """测试 HTTP 连接 — 发送一次请求验证连通性"""
        if self._client is None:
            return ConnectionResult(
                success=False,
                message="HTTP 客户端未初始化",
            )

        try:
            start = time.monotonic()

            if self._method == "GET":
                response = await self._client.get(self._endpoint)
            else:
                response = await self._client.post(
                    self._endpoint,
                    json=self._request_body,
                )

            latency = (time.monotonic() - start) * 1000
            response.raise_for_status()

            data = response.json()
            # 截取部分样本数据
            sample = {}
            if isinstance(data, dict):
                keys = list(data.keys())[:5]
                sample = {k: str(data[k])[:100] for k in keys}
            elif isinstance(data, list):
                sample = {"count": len(data), "first": str(data[0])[:100] if data else None}

            return ConnectionResult(
                success=True,
                message=f"HTTP {self._method} 请求成功 (status={response.status_code})",
                latency_ms=round(latency, 2),
                sample_data=sample,
            )

        except asyncio.TimeoutError:
            return ConnectionResult(success=False, message=f"HTTP 请求超时 ({self._timeout}s)")
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
