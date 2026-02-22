"""
请求日志中间件
Structured request logging with request ID propagation.
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..core.logging import request_id_var

logger = logging.getLogger("dcim.request")

# 不记录日志的路径（高频健康检查）
_SKIP_PATHS = {"/api/health", "/api/readiness"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件 — 生成 request_id、记录请求耗时"""

    async def dispatch(self, request: Request, call_next) -> Response:
        # 生成请求 ID
        rid = uuid.uuid4().hex
        token = request_id_var.set(rid)

        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            # 重置 ContextVar 后重新抛出
            request_id_var.reset(token)
            raise

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        # 设置响应头
        response.headers["X-Request-ID"] = rid

        # 跳过高频路径
        path = request.url.path
        if path not in _SKIP_PATHS:
            ua = (request.headers.get("user-agent") or "")[:100]
            logger.info(
                "%s %s %s %.2fms rid=%s ua=%s",
                request.method,
                path,
                response.status_code,
                duration_ms,
                rid,
                ua,
            )

        request_id_var.reset(token)
        return response
