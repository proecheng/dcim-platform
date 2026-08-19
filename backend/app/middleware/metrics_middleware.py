"""
性能指标中间件
基于 BaseHTTPMiddleware 记录每个请求的耗时和状态码。
"""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from .metrics import metrics_collector

logger = logging.getLogger(__name__)

# 不记录指标的探针和抓取路径
_SKIP_PATHS = {
    "/api/health",
    "/api/readiness",
    "/api/metrics",
    "/api/metrics/prometheus",
    "/api/v1/system/health",
    "/api/v1/system/observability",
}


class MetricsMiddleware(BaseHTTPMiddleware):
    """请求性能指标收集中间件"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if path in _SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            await metrics_collector.record_request(
                method=request.method,
                path=path,
                status_code=500,
                duration_ms=round(duration_ms, 2),
            )
            logger.exception(
                "Unhandled request exception",
                extra={
                    "request_method": request.method,
                    "request_path": path,
                    "status_code": 500,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        await metrics_collector.record_request(
            method=request.method,
            path=path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        return response
