"""演示模块配置"""

from ..core.config import get_settings


def is_demo_enabled() -> bool:
    """检查演示模式是否启用"""
    settings = get_settings()
    return getattr(settings, "demo_enabled", getattr(settings, "simulation_enabled", False))
