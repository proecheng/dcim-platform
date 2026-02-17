"""
事件总线 — 联动引擎核心消息通道
Story 9-1: 联动引擎核心框架
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)


class EventPriority(str, Enum):
    """事件优先级"""
    fire_signal = "fire_signal"   # 消防信号（最高优先级）
    critical = "critical"         # 紧急
    normal = "normal"             # 普通


@dataclass
class Event:
    """事件数据"""
    event_type: str                          # 事件类型，如 alarm.triggered
    source: str                              # 事件来源，如 alarm_engine
    priority: EventPriority                  # 优先级
    payload: dict                            # 事件载荷
    timestamp: datetime = field(default_factory=datetime.now)
    is_test: bool = False                    # 是否为测试事件


class EventBus(ABC):
    """事件总线抽象基类"""

    @abstractmethod
    async def publish(self, channel: str, event: Event) -> None:
        """发布事件到指定通道"""
        ...

    @abstractmethod
    async def subscribe(self, channel: str, handler: Callable) -> None:
        """订阅指定通道"""
        ...

    @abstractmethod
    async def unsubscribe(self, channel: str, handler: Callable) -> None:
        """取消订阅"""
        ...


class InMemoryEventBus(EventBus):
    """基于内存的事件总线实现 — 直接派发模式"""

    def __init__(self) -> None:
        self._handlers: Dict[str, List[Callable]] = {}

    async def publish(self, channel: str, event: Event) -> None:
        """发布事件，直接调用所有订阅者"""
        handlers = self._handlers.get(channel, [])
        if not handlers:
            logger.debug("事件总线: 通道 %s 无订阅者，事件被丢弃", channel)
            return
        logger.info(
            "事件总线: 发布事件 channel=%s type=%s priority=%s",
            channel, event.event_type, event.priority.value,
        )
        await asyncio.gather(*[h(event) for h in handlers], return_exceptions=True)

    async def subscribe(self, channel: str, handler: Callable) -> None:
        """订阅通道"""
        if channel not in self._handlers:
            self._handlers[channel] = []
        if handler not in self._handlers[channel]:
            self._handlers[channel].append(handler)
            logger.info("事件总线: 订阅通道 %s", channel)

    async def unsubscribe(self, channel: str, handler: Callable) -> None:
        """取消订阅"""
        if channel in self._handlers and handler in self._handlers[channel]:
            self._handlers[channel].remove(handler)
            logger.info("事件总线: 取消订阅通道 %s", channel)


# 全局单例
_event_bus_instance: EventBus | None = None


def get_event_bus() -> EventBus:
    """获取事件总线单例"""
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = InMemoryEventBus()
    return _event_bus_instance
