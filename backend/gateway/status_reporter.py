"""状态上报心跳 30s。实现 Story: 2.1"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)

# psutil 可选依赖
try:
    import psutil

    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False
    logger.warning("psutil 未安装，系统指标将返回 None")


class StatusReporter:
    """网关状态上报器 — 每 30 秒发布心跳到 MQTT"""

    def __init__(
        self,
        gateway_id: str,
        site_id: int = 1,
        name: str = "",
        version: str = "1.0.0",
        capabilities: Optional[list[str]] = None,
        interval: int = 30,
    ) -> None:
        self._gateway_id = gateway_id
        self._site_id = site_id
        self._name = name or f"gateway-{gateway_id}"
        self._version = version
        self._capabilities = capabilities or []
        self._interval = interval
        self._task: Optional[asyncio.Task] = None
        self._running = False

    @property
    def topic(self) -> str:
        return f"dcim/{self._site_id}/gw/{self._gateway_id}/status"

    def collect_metrics(self) -> dict[str, Optional[float]]:
        """采集系统指标"""
        if not _HAS_PSUTIL:
            return {"cpu": None, "mem": None, "disk": None}
        disk_path = "/" if os.name != "nt" else "C:\\"
        return {
            "cpu": psutil.cpu_percent(interval=0),  # type: ignore[possibly-undefined]
            "mem": psutil.virtual_memory().percent,  # type: ignore[possibly-undefined]
            "disk": psutil.disk_usage(disk_path).percent,  # type: ignore[possibly-undefined]
        }

    def build_status_message(self) -> dict[str, Any]:
        """构建心跳消息"""
        metrics = self.collect_metrics()
        return {
            "gw_id": self._gateway_id,
            "name": self._name,
            "ip": self._get_ip(),
            "version": self._version,
            "capabilities": self._capabilities,
            "cpu": metrics["cpu"],
            "mem": metrics["mem"],
            "disk": metrics["disk"],
            "ts": int(time.time()),
        }

    def _get_ip(self) -> str:
        """获取本机 IP（尽力而为）"""
        import socket

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    async def start(self, publish_fn: Callable[[str, str], Coroutine]) -> None:
        """启动定时上报"""
        self._running = True
        self._task = asyncio.create_task(self._report_loop(publish_fn))
        logger.info("状态上报已启动: topic=%s, interval=%ds", self.topic, self._interval)

    async def stop(self) -> None:
        """停止上报"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("状态上报已停止")

    async def _report_loop(self, publish_fn: Callable[[str, str], Coroutine]) -> None:
        """上报循环"""
        while self._running:
            try:
                msg = self.build_status_message()
                await publish_fn(self.topic, json.dumps(msg))
                logger.debug("心跳已发送: %s", self._gateway_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("心跳发送失败")
            await asyncio.sleep(self._interval)
