"""
诊断引擎熔断器 - Story 24.7
状态机 + 滑动窗口，保护 L2/L3 推理路径
"""

import asyncio
import time
import logging
from collections import deque
from datetime import datetime, timezone
from enum import Enum
from typing import Tuple, Optional, Callable

logger = logging.getLogger(__name__)


class BreakerState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """诊断引擎熔断器 -- 状态机 + 滑动窗口"""

    def __init__(
        self,
        *,
        error_threshold: float = 0.30,  # 修正：30% 失败率阈值
        window_size: int = 10,  # 修正：10 次请求的滑动窗口
        consecutive_failures_threshold: int = 3,
        cooldown_seconds: int = 30,
        probe_timeout_seconds: int = 10,
        on_state_change: Optional[Callable] = None,
        time_func: Optional[Callable] = None,
    ):
        self._state = BreakerState.CLOSED
        self._error_threshold = error_threshold
        self._window_size = window_size
        self._consecutive_failures_threshold = consecutive_failures_threshold
        self._cooldown_seconds = cooldown_seconds
        self._probe_timeout_seconds = probe_timeout_seconds
        self._on_state_change = on_state_change

        # 滑动窗口: deque of (success: bool) - 固定大小窗口
        self._window: deque = deque(maxlen=window_size)
        self._consecutive_failures = 0
        self._last_trip_time: Optional[float] = None
        self._half_open_in_flight = False
        self._lock: Optional[asyncio.Lock] = None  # 延迟初始化
        self._time_func = time_func or time.time
        self._degraded_since: Optional[float] = None

    def _ensure_lock(self):
        if self._lock is None:
            self._lock = asyncio.Lock()

    # ---- 只读属性 (健康检查用) ----

    @property
    def state(self) -> BreakerState:
        return self._state

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    @property
    def error_rate(self) -> float:
        total = len(self._window)
        if total == 0:
            return 0.0
        failed = sum(1 for success in self._window if not success)
        return failed / total

    @property
    def total_in_window(self) -> int:
        return len(self._window)

    @property
    def failed_in_window(self) -> int:
        return sum(1 for success in self._window if not success)

    @property
    def last_trip_time_iso(self) -> Optional[str]:
        if self._last_trip_time is None:
            return None
        return datetime.fromtimestamp(self._last_trip_time, tz=timezone.utc).isoformat()

    @property
    def degraded_since_iso(self) -> Optional[str]:
        if self._degraded_since is None:
            return None
        return datetime.fromtimestamp(self._degraded_since, tz=timezone.utc).isoformat()

    # ---- 核心方法 ----

    async def allow_request(self, inference_level: str = "L2") -> Tuple[bool, bool]:
        """
        判断请求是否放行

        Returns: (allowed, degraded)
        - L1 请求: 直接返回 (True, False)，跳过所有熔断逻辑
        - CLOSED: (True, False)
        - OPEN + 冷却期未到: (True, True) -- 降级到 L1
        - OPEN + 冷却期已到: 转 HALF_OPEN，(True, False) -- 试探放行
        - HALF_OPEN 且无 in-flight: (True, False) -- 试探放行
        - HALF_OPEN 且有 in-flight: (True, True) -- 并发请求降级
        """
        # L1 请求完全跳过熔断检查
        if inference_level == "L1":
            return (True, False)

        self._ensure_lock()
        async with self._lock:
            if self._state == BreakerState.CLOSED:
                return (True, False)

            if self._state == BreakerState.OPEN:
                now = self._time_func()
                if self._last_trip_time is not None and (now - self._last_trip_time >= self._cooldown_seconds):
                    # 冷却期已到，转 HALF_OPEN
                    await self._set_state(BreakerState.HALF_OPEN, reason="cooldown_expired")
                    self._half_open_in_flight = True
                    return (True, False)  # 试探放行
                else:
                    return (True, True)  # 降级

            # HALF_OPEN
            if not self._half_open_in_flight:
                self._half_open_in_flight = True
                return (True, False)  # 试探放行
            else:
                return (True, True)  # 并发请求降级

    async def record_success(self):
        """推理成功"""
        self._ensure_lock()
        async with self._lock:
            self._window.append(True)
            self._consecutive_failures = 0
            self._half_open_in_flight = False

            if self._state == BreakerState.HALF_OPEN:
                await self._set_state(BreakerState.CLOSED, reason="probe_success")
                self._window.clear()
                self._degraded_since = None

    async def record_failure(self):
        """推理失败"""
        self._ensure_lock()
        async with self._lock:
            now = self._time_func()
            self._window.append(False)
            self._consecutive_failures += 1
            self._half_open_in_flight = False

            if self._state == BreakerState.HALF_OPEN:
                # 试探失败，回到 OPEN
                self._last_trip_time = now
                await self._set_state(BreakerState.OPEN, reason="probe_failed")
                return

            if self._state == BreakerState.CLOSED:
                await self._check_trip(now)

    async def record_timeout(self):
        """推理超时 -- 等同 failure"""
        await self.record_failure()

    # ---- 内部方法 ----

    async def _check_trip(self, now: float):
        """检查是否应触发熔断"""
        total = len(self._window)

        # 连续失败检查（快速熔断）
        if self._consecutive_failures >= self._consecutive_failures_threshold:
            self._last_trip_time = now
            self._degraded_since = now
            await self._set_state(
                BreakerState.OPEN,
                reason="consecutive_failures",
            )
            return

        # 失败率检查（窗口已满时）
        if total >= self._window_size:
            failed = sum(1 for success in self._window if not success)
            rate = failed / total
            if rate > self._error_threshold:
                self._last_trip_time = now
                self._degraded_since = now
                await self._set_state(
                    BreakerState.OPEN,
                    reason="error_rate_exceeded",
                    error_rate=round(rate, 4),
                )

    async def _set_state(self, new_state: BreakerState, reason: str = "", **kwargs):
        """状态变更 + 回调"""
        old_state = self._state
        if old_state == new_state:
            return
        self._state = new_state
        logger.warning(
            "CircuitBreaker 状态变更: %s -> %s (reason=%s)",
            old_state.value,
            new_state.value,
            reason,
        )

        if self._on_state_change:
            try:
                cb_data = {
                    "state": new_state.value,
                    "previous_state": old_state.value,
                    "reason": reason,
                    "timestamp": datetime.fromtimestamp(self._time_func(), tz=timezone.utc).isoformat(),
                    **kwargs,
                }
                result = self._on_state_change(cb_data)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass  # 回调失败不应影响熔断器，回调内部自行记录日志

    async def force_open(self):
        """演练专用：安全地强制熔断器为 OPEN 状态"""
        self._ensure_lock()
        async with self._lock:
            now = self._time_func()
            self._last_trip_time = now
            self._degraded_since = now
            await self._set_state(BreakerState.OPEN, reason="chaos_drill")

    async def reset(self):
        """P1-3 修复: 重置为 CLOSED（调度器重启时使用）- 异步 + 锁保护"""
        self._ensure_lock()
        async with self._lock:
            self._state = BreakerState.CLOSED
            self._window.clear()
            self._consecutive_failures = 0
            self._last_trip_time = None
            self._half_open_in_flight = False
            self._degraded_since = None
            logger.info("CircuitBreaker 已重置为 CLOSED 状态")
