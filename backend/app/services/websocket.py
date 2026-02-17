"""
WebSocket 服务
"""
import logging
from typing import List, Dict
from fastapi import WebSocket
import json

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {
            "realtime": [],
            "alarms": [],
            "control": [],
            "system": [],
            "linkage": []
        }

    async def connect(self, websocket: WebSocket, channel: str = "realtime"):
        """建立连接"""
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)

    def disconnect(self, websocket: WebSocket, channel: str = "realtime"):
        """断开连接"""
        if channel in self.active_connections:
            if websocket in self.active_connections[channel]:
                self.active_connections[channel].remove(websocket)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """发送个人消息"""
        await websocket.send_json(message)

    async def broadcast(self, message: dict, channel: str = "realtime"):
        """广播消息"""
        if channel in self.active_connections:
            for connection in self.active_connections[channel]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.warning(f"Failed to send message to WebSocket client: {e}")

    async def broadcast_realtime(self, point_data: dict):
        """广播实时数据"""
        message = {
            "type": "realtime",
            "data": point_data
        }
        await self.broadcast(message, "realtime")

    async def broadcast_alarm(self, alarm_data: dict):
        """广播告警 — 提取 action 字段到消息顶层，兼容前端路由逻辑"""
        action = alarm_data.get("action", "new")
        # 构建消息时排除 action 字段，避免重复
        data = {k: v for k, v in alarm_data.items() if k != "action"}
        message = {
            "type": "alarm",
            "action": action,
            "data": data
        }
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
