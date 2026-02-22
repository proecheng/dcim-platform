"""
全局异常处理器
捕获未处理的异常，记录完整上下文，返回结构化错误响应。
"""

import logging
import traceback
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from starlette.responses import JSONResponse

try:
    from ..core.logging import request_id_var
except (ImportError, AttributeError):
    request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

logger = logging.getLogger(__name__)


def _get_request_id() -> str:
    """获取当前请求 ID，如果不存在则生成一个"""
    try:
        rid = request_id_var.get()
        if rid and rid != "-":
            return rid
    except LookupError:
        pass
    return uuid.uuid4().hex[:16]


def _build_error_response(status_code: int, message: str, request_id: str, details: list | None = None) -> dict:
    """构建统一错误响应体"""
    body: dict = {
        "error": {
            "code": status_code,
            "message": message,
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    }
    if details is not None:
        body["error"]["details"] = details
    return body


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """HTTP 异常处理器 — 结构化错误响应，保留 detail 字段兼容旧客户端"""
    request_id = _get_request_id()
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    logger.warning(
        "HTTP %s %s -> %d: %s [request_id=%s]",
        request.method,
        request.url.path,
        exc.status_code,
        message,
        request_id,
    )
    body = _build_error_response(exc.status_code, message, request_id)
    # 保留 detail 字段，兼容 FastAPI 默认格式
    body["detail"] = message
    headers = getattr(exc, "headers", None) or {}
    return JSONResponse(status_code=exc.status_code, content=body, headers=headers)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """请求验证异常处理器 — 422 带字段级错误详情"""
    request_id = _get_request_id()
    details = []
    for err in exc.errors():
        details.append(
            {
                "field": ".".join(str(loc) for loc in err.get("loc", [])),
                "message": err.get("msg", ""),
                "type": err.get("type", ""),
            }
        )
    logger.warning(
        "Validation error on %s %s: %d field(s) [request_id=%s]",
        request.method,
        request.url.path,
        len(details),
        request_id,
    )
    body = _build_error_response(422, "请求参数验证失败", request_id, details)
    return JSONResponse(status_code=422, content=body)


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """通用异常处理器 — 捕获所有未处理异常，记录完整堆栈，返回 500"""
    request_id = _get_request_id()
    logger.exception(
        "Unhandled exception on %s %s [request_id=%s]: %s",
        request.method,
        request.url.path,
        request_id,
        exc,
    )
    body = _build_error_response(500, "内部服务器错误", request_id)
    return JSONResponse(status_code=500, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    """在 FastAPI 应用上注册所有异常处理器"""
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
