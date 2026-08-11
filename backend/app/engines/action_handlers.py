"""
联动动作处理器
Story 9-1: 联动引擎核心框架
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional

from .event_bus import Event

logger = logging.getLogger(__name__)


@dataclass
class ActionResult:
    """动作执行结果"""

    success: bool
    status: str
    error_message: Optional[str] = None
    duration_ms: int = 0


class ActionHandler(ABC):
    """动作处理器抽象基类"""

    @property
    @abstractmethod
    def action_type(self) -> str:
        """动作类型标识"""
        ...

    @abstractmethod
    async def execute(self, config: dict, event: Event) -> ActionResult:
        """执行动作"""
        ...


class AlarmNotifyHandler(ActionHandler):
    """告警通知动作 — 通过 WebSocket 广播告警"""

    @property
    def action_type(self) -> str:
        return "ALARM_NOTIFY"

    async def execute(self, config: dict, event: Event) -> ActionResult:
        start = time.time()
        try:
            from ..services.websocket import ws_manager

            message = config.get("message", "联动告警通知")
            if event.is_test:
                message = f"[测试] {message}"

            alarm_data = {
                "action": "linkage_notify",
                "alarm_level": config.get("alarm_level", "info"),
                "alarm_message": message,
                "source": event.source,
                "payload": event.payload,
            }
            await ws_manager.broadcast_alarm(alarm_data, site_id=event.payload.get("site_id"))

            duration = int((time.time() - start) * 1000)
            return ActionResult(success=True, status="success", duration_ms=duration)
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            logger.error("AlarmNotifyHandler 执行失败: %s", e)
            return ActionResult(success=False, status="failed", error_message=str(e), duration_ms=duration)


class WebhookHandler(ActionHandler):
    """Webhook 动作 — HTTP POST 回调"""

    @property
    def action_type(self) -> str:
        return "WEBHOOK"

    async def execute(self, config: dict, event: Event) -> ActionResult:
        start = time.time()
        try:
            url = config.get("url", "")
            if not url:
                return ActionResult(success=False, status="failed", error_message="未配置 webhook URL")

            if event.is_test:
                duration = int((time.time() - start) * 1000)
                return ActionResult(
                    success=True,
                    status="success",
                    error_message="测试模式: 跳过实际 HTTP 请求",
                    duration_ms=duration,
                )

            import httpx

            headers = config.get("headers", {})
            body = {
                "event_type": event.event_type,
                "source": event.source,
                "payload": event.payload,
                "timestamp": event.timestamp.isoformat(),
            }
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=body, headers=headers)
                resp.raise_for_status()

            duration = int((time.time() - start) * 1000)
            return ActionResult(success=True, status="success", duration_ms=duration)
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            logger.error("WebhookHandler 执行失败: %s", e)
            return ActionResult(success=False, status="failed", error_message=str(e), duration_ms=duration)


class MqttCommandHandler(ActionHandler):
    """MQTT 指令动作 — 未实现"""

    @property
    def action_type(self) -> str:
        return "MQTT_COMMAND"

    async def execute(self, config: dict, event: Event) -> ActionResult:
        return ActionResult(success=False, status="skipped", error_message="动作类型未实现")


class VideoRecordHandler(ActionHandler):
    """视频录制动作 — 查找关联摄像头并触发录像"""

    @property
    def action_type(self) -> str:
        return "VIDEO_RECORD"

    async def execute(self, config: dict, event: Event) -> ActionResult:
        import time as _time

        start = _time.time()
        try:
            from ..core.database import async_session
            from ..services import video_service

            device_id = event.payload.get("device_id") if event.payload else None
            area_code = event.payload.get("area_code") if event.payload else None
            alarm_id = event.payload.get("alarm_id") if event.payload else None

            cameras = []
            async with async_session() as db:
                # 先按设备查找
                if device_id:
                    cameras = await video_service.get_cameras_by_device(db, int(device_id))
                # 再按区域查找
                if not cameras and area_code:
                    cameras = await video_service.get_cameras_by_area(db, str(area_code))

                if not cameras:
                    duration = int((_time.time() - start) * 1000)
                    return ActionResult(
                        success=True,
                        status="success",
                        error_message="未找到关联摄像头，跳过录像",
                        duration_ms=duration,
                    )

                # 为每个摄像头触发录像
                for cam in cameras[:4]:  # 最多 4 路同时录像
                    await video_service.start_recording(
                        db,
                        cam.id,
                        "linkage",
                        alarm_id=int(alarm_id) if alarm_id else None,
                    )

            duration = int((_time.time() - start) * 1000)
            return ActionResult(success=True, status="success", duration_ms=duration)
        except Exception as e:
            duration = int((_time.time() - start) * 1000)
            logger.error("VideoRecordHandler 执行失败: %s", e)
            return ActionResult(success=False, status="failed", error_message=str(e), duration_ms=duration)


class VideoPopupHandler(ActionHandler):
    """视频弹窗动作 — 查找关联摄像头并通过 WebSocket 广播"""

    @property
    def action_type(self) -> str:
        return "VIDEO_POPUP"

    async def execute(self, config: dict, event: Event) -> ActionResult:
        import time as _time

        start = _time.time()
        try:
            from ..core.database import async_session
            from ..services.websocket import ws_manager
            from ..services import video_service

            device_id = event.payload.get("device_id") if event.payload else None
            area_code = event.payload.get("area_code") if event.payload else None

            cameras = []
            async with async_session() as db:
                # 先按设备查找
                if device_id:
                    cameras = await video_service.get_cameras_by_device(db, int(device_id))
                # 再按区域查找
                if not cameras and area_code:
                    cameras = await video_service.get_cameras_by_area(db, str(area_code))

            if not cameras:
                duration = int((_time.time() - start) * 1000)
                return ActionResult(
                    success=True,
                    status="success",
                    error_message="未找到关联摄像头",
                    duration_ms=duration,
                )

            camera_list = [
                {
                    "id": c.id,
                    "name": c.name,
                    "code": c.code,
                    "rtsp_url": c.rtsp_url,
                    "hls_url": c.hls_url,
                    "camera_type": c.camera_type,
                }
                for c in cameras[:9]  # 最多 9 个（3x3 分屏）
            ]

            popup_data = {
                "action": "video_popup",
                "cameras": camera_list,
                "area_code": area_code,
                "device_id": device_id,
                "source": event.source,
            }
            await ws_manager.broadcast_alarm(popup_data, site_id=event.payload.get("site_id"))

            duration = int((_time.time() - start) * 1000)
            return ActionResult(success=True, status="success", duration_ms=duration)
        except Exception as e:
            duration = int((_time.time() - start) * 1000)
            logger.error("VideoPopupHandler 执行失败: %s", e)
            return ActionResult(success=False, status="failed", error_message=str(e), duration_ms=duration)


class ActionHandlerRegistry:
    """动作处理器注册表"""

    def __init__(self) -> None:
        self._handlers: Dict[str, ActionHandler] = {}

    def register(self, handler: ActionHandler) -> None:
        """注册处理器"""
        self._handlers[handler.action_type] = handler
        logger.debug("注册动作处理器: %s", handler.action_type)

    def get_handler(self, action_type: str) -> Optional[ActionHandler]:
        """获取处理器"""
        return self._handlers.get(action_type)

    def list_types(self) -> list[dict]:
        """列出所有已注册的动作类型"""
        return [
            {
                "action_type": h.action_type,
                "handler_class": h.__class__.__name__,
            }
            for h in self._handlers.values()
        ]


def default_registry() -> ActionHandlerRegistry:
    """创建默认注册表，注册所有内置处理器"""
    registry = ActionHandlerRegistry()
    registry.register(AlarmNotifyHandler())
    registry.register(WebhookHandler())
    registry.register(MqttCommandHandler())
    registry.register(VideoRecordHandler())
    registry.register(VideoPopupHandler())
    return registry
