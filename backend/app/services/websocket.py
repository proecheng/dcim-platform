"""
WebSocket 服务 — 含心跳检测与死连接清理
"""

import asyncio
import logging
import time
from typing import List, Dict, Optional
from fastapi import WebSocket
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)

# 心跳间隔（秒）
HEARTBEAT_INTERVAL = 30
# 心跳超时（秒）— 超过此时间未收到 pong 则判定死连接
HEARTBEAT_TIMEOUT = 10


class ConnectionManager:
    """WebSocket 连接管理器 — 支持心跳检测与死连接自动清理"""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {
            "realtime": [],
            "alarms": [],
            "control": [],
            "system": [],
            "linkage": [],
        }
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket, channel: str = "realtime"):
        """建立连接"""
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)
        logger.debug("WebSocket 连接建立: channel=%s, 当前连接数=%d", channel, len(self.active_connections[channel]))

    def disconnect(self, websocket: WebSocket, channel: str = "realtime"):
        """断开连接"""
        if channel in self.active_connections:
            if websocket in self.active_connections[channel]:
                self.active_connections[channel].remove(websocket)
                logger.debug("WebSocket 连接断开: channel=%s, 剩余连接数=%d", channel, len(self.active_connections[channel]))

    def start_heartbeat(self):
        """启动心跳检测后台任务"""
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info("WebSocket 心跳检测已启动 (间隔=%ds, 超时=%ds)", HEARTBEAT_INTERVAL, HEARTBEAT_TIMEOUT)

    def stop_heartbeat(self):
        """停止心跳检测"""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            logger.info("WebSocket 心跳检测已停止")

    async def _heartbeat_loop(self):
        """心跳检测循环 — 定期向所有连接发送 ping，清理无响应的死连接"""
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await self._ping_all()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("心跳检测异常: %s", e)
                await asyncio.sleep(5)

    async def _ping_all(self):
        """向所有通道的所有连接发送 ping 消息，清理失败的连接"""
        dead_connections: List[tuple] = []

        for channel, connections in self.active_connections.items():
            for ws in connections:
                try:
                    if ws.client_state != WebSocketState.CONNECTED:
                        dead_connections.append((ws, channel))
                        continue
                    await asyncio.wait_for(
                        ws.send_json({"type": "ping", "ts": time.time()}),
                        timeout=HEARTBEAT_TIMEOUT,
                    )
                except (asyncio.TimeoutError, Exception):
                    dead_connections.append((ws, channel))

        # 批量清理死连接
        for ws, channel in dead_connections:
            self.disconnect(ws, channel)
            try:
                await ws.close(code=1000, reason="heartbeat timeout")
            except Exception:
                pass
        if dead_connections:
            logger.info("心跳清理: 移除 %d 个死连接", len(dead_connections))

    @property
    def total_connections(self) -> int:
        """当前总连接数"""
        return sum(len(conns) for conns in self.active_connections.values())

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """发送个人消息"""
        await websocket.send_json(message)

    async def broadcast(self, message: dict, channel: str = "realtime"):
        """广播消息 — 发送失败的连接自动清理"""
        if channel not in self.active_connections:
            return
        dead: List[WebSocket] = []
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning("WebSocket 广播失败，标记清理: %s", e)
                dead.append(connection)
        for ws in dead:
            self.disconnect(ws, channel)

    async def broadcast_realtime(self, point_data: dict):
        """广播实时数据"""
        message = {"type": "realtime", "data": point_data}
        await self.broadcast(message, "realtime")

    async def broadcast_alarm(self, alarm_data: dict):
        """广播告警 — 提取 action 字段到消息顶层，兼容前端路由逻辑"""
        action = alarm_data.get("action", "new")
        data = {k: v for k, v in alarm_data.items() if k != "action"}
        message = {"type": "alarm", "action": action, "data": data}
        await self.broadcast(message, "alarms")

    async def broadcast_system(self, system_data: dict):
        """广播系统状态消息"""
        message = {"type": "system", "data": system_data}
        await self.broadcast(message, "system")

    async def broadcast_linkage(self, linkage_data: dict):
        """广播联动执行结果"""
        message = {"type": "linkage", "data": linkage_data}
        await self.broadcast(message, "linkage")


# 全局连接管理器
ws_manager = ConnectionManager()
