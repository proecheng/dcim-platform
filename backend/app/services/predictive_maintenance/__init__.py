"""劣化分析插件框架 — Story 36.1 / 36.5"""

import logging

logger = logging.getLogger(__name__)

# 自动导入插件（触发装饰器注册）
try:
    from . import hvac_plugin  # noqa: F401
except Exception as e:
    logger.warning("HVAC 劣化分析插件加载失败: %s", e)

try:
    from . import ups_plugin  # noqa: F401
except Exception as e:
    logger.warning("UPS 劣化分析插件加载失败: %s", e)

try:
    from . import pdu_plugin  # noqa: F401
except Exception as e:
    logger.warning("PDU 劣化分析插件加载失败: %s", e)

try:
    from . import battery_plugin  # noqa: F401
except Exception as e:
    logger.warning("Battery 劣化分析插件加载失败: %s", e)
