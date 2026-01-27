"""
日志配置模块
Centralized logging configuration for the application.
"""
import logging
import sys
from typing import Optional

from .config import get_settings


def setup_logging(name: Optional[str] = None) -> logging.Logger:
    """
    获取配置好的日志记录器

    Args:
        name: 日志记录器名称，通常使用 __name__

    Returns:
        配置好的 Logger 实例

    Usage:
        from app.core.logging import setup_logging
        logger = setup_logging(__name__)
        logger.info("Something happened")
        logger.error("Error occurred", exc_info=True)
    """
    settings = get_settings()

    logger = logging.getLogger(name or "dcim")

    # 避免重复添加 handler
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)

        # 根据调试模式设置日志级别
        if settings.debug:
            logger.setLevel(logging.DEBUG)
            handler.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
            handler.setLevel(logging.INFO)

        # 设置日志格式
        formatter = logging.Formatter(
            fmt='[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    获取日志记录器的便捷方法

    Args:
        name: 日志记录器名称，通常使用 __name__

    Returns:
        Logger 实例
    """
    return setup_logging(name)


# 默认日志记录器
default_logger = setup_logging("dcim")
