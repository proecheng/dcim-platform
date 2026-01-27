"""
WebSocket 服务
"""
from typing import List, Dict
from fastapi import WebSocket
import json


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {
            "realtime": [],
            "alarms": [],
            "control": []
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
                except Exception:
                    pass

    async def broadcast_realtime(self, point_data: dict):
        """广播实时数据"""
        message = {
            "type": "realtime",
            "data": point_data
        }
        await self.broadcast(message, "realtime")

    async def broadcast_alarm(self, alarm_data: dict):
        """广播告警"""
        message = {
            "type": "alarm",
            "data": alarm_data
        }
        await self.broadcast(message, "alarms")


# 全局连接管理器
ws_manager = ConnectionManager()
