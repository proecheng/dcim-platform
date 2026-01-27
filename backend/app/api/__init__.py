"""
API 路由
"""
from .auth import router as auth_router
from .point import router as point_router
from .realtime import router as realtime_router
from .alarm import router as alarm_router
from .history import router as history_router
from .threshold import router as threshold_router

__all__ = [
    "auth_router",
    "point_router",
    "realtime_router",
    "alarm_router",
    "history_router",
    "threshold_router"
]
