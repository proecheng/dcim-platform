"""
HTTP 缓存工具 — 为 API 响应添加 Cache-Control 头
"""

from fastapi import Response


def set_cache_headers(response: Response, max_age: int = 60, private: bool = True) -> None:
    """设置 Cache-Control 响应头

    Args:
        response: FastAPI Response 对象
        max_age: 缓存有效期（秒），默认 60 秒
        private: 是否为私有缓存（默认 True，仅浏览器缓存）
    """
    scope = "private" if private else "public"
    response.headers["Cache-Control"] = f"{scope}, max-age={max_age}"


# 预定义缓存策略
CACHE_SHORT = 30       # 30 秒 — 实时性要求较高的统计数据
CACHE_MEDIUM = 300     # 5 分钟 — 概览/仪表盘数据
CACHE_LONG = 1800      # 30 分钟 — 配置/字典等低频变更数据
CACHE_STATIC = 86400   # 24 小时 — 几乎不变的参考数据
