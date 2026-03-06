"""
诊断服务模块 - Story 24.1, 24.2, 24.4, 24.6
"""

from .l1_engine import L1RuleEngine
from .rule_manager import RuleManager
from .priority_queue import CancellablePriorityQueue, PriorityTask
from .result_store import DiagnosisResultStore
from .push_service import DiagnosisPushService

# scheduler/hmac_manager/version_manager 依赖 redis_client，测试环境可能不可用
try:
    from .hmac_manager import HMACManager
except ImportError:
    HMACManager = None  # type: ignore

try:
    from .version_manager import VersionManager
except ImportError:
    VersionManager = None  # type: ignore

try:
    from .scheduler import DiagnosisScheduler, get_scheduler
except ImportError:
    DiagnosisScheduler = None  # type: ignore
    get_scheduler = None  # type: ignore

__all__ = [
    "L1RuleEngine",
    "RuleManager",
    "DiagnosisScheduler",
    "get_scheduler",
    "CancellablePriorityQueue",
    "PriorityTask",
    "HMACManager",
    "VersionManager",
    "DiagnosisResultStore",
    "DiagnosisPushService",
]
