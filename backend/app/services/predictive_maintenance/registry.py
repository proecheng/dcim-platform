"""劣化分析插件注册表（装饰器模式）— Story 36.1"""

from typing import Type
from .base import DegradationPlugin

DEGRADATION_PLUGIN_REGISTRY: dict[str, Type[DegradationPlugin]] = {}


def register_degradation_plugin(device_type: str):
    """装饰器 — 注册劣化分析插件"""

    def decorator(cls: Type[DegradationPlugin]) -> Type[DegradationPlugin]:
        DEGRADATION_PLUGIN_REGISTRY[device_type] = cls
        return cls

    return decorator


def get_degradation_plugin(device_type: str) -> Type[DegradationPlugin] | None:
    """获取指定设备类型的劣化分析插件类"""
    return DEGRADATION_PLUGIN_REGISTRY.get(device_type)


def list_degradation_plugins() -> list[str]:
    """列出所有已注册的插件设备类型"""
    return list(DEGRADATION_PLUGIN_REGISTRY.keys())
