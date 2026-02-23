"""适配器注册表 — 字典映射 + 装饰器"""

from typing import Type
from .base import BaseProtocolAdapter

ADAPTER_REGISTRY: dict[str, Type[BaseProtocolAdapter]] = {}


def register_adapter(protocol_type: str):
    """装饰器 — 注册协议适配器到 ADAPTER_REGISTRY"""

    def decorator(cls: Type[BaseProtocolAdapter]) -> Type[BaseProtocolAdapter]:
        ADAPTER_REGISTRY[protocol_type] = cls
        return cls

    return decorator


def get_adapter(protocol_type: str) -> Type[BaseProtocolAdapter]:
    """获取协议适配器类"""
    if protocol_type not in ADAPTER_REGISTRY:
        raise ValueError(f"未知协议类型: {protocol_type}")
    return ADAPTER_REGISTRY[protocol_type]


def list_adapters() -> list[str]:
    """列出所有已注册的协议类型"""
    return list(ADAPTER_REGISTRY.keys())
