"""劣化分析插件框架 — Story 36.1"""

import logging

logger = logging.getLogger(__name__)

# 自动导入插件（触发装饰器注册）
try:
    from . import hvac_plugin  # noqa: F401
except Exception as e:
    logger.warning("HVAC 劣化分析插件加载失败: %s", e)
