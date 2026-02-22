"""
日志配置模块
Centralized logging configuration with JSON structured logging support.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional

from .config import get_settings

# 请求 ID 上下文变量 — 供中间件设置，供 JSONFormatter 读取
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class JSONFormatter(logging.Formatter):
    """结构化 JSON 日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(""),
        }

        # 附加额外字段
        extra = {}
        if record.exc_info and record.exc_info[0] is not None:
            extra["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "duration_ms"):
            extra["duration_ms"] = record.duration_ms
        if hasattr(record, "status_code"):
            extra["status_code"] = record.status_code
        if extra:
            log_entry["extra"] = extra

        return json.dumps(log_entry, ensure_ascii=False)


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

        # 调试模式使用可读文本格式，生产模式使用 JSON 格式
        if settings.debug:
            formatter = logging.Formatter(
                fmt="[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        else:
            formatter = JSONFormatter()

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
