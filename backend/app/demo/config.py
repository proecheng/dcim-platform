"""演示模块配置"""

from ..core.config import get_settings


def is_demo_enabled() -> bool:
    """检查演示模式是否启用"""
    settings = get_settings()
    return settings.demo_enabled or settings.simulation_enabled
