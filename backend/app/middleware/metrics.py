"""
性能指标收集器
纯内存实现，收集请求计数、延迟、错误率等指标。
"""

import asyncio
import math
import time
from collections import deque
from collections.abc import Callable


class MetricsCollector:
    """应用性能指标收集器（单例）"""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        rolling_window_seconds: int = 300,
        max_duration_samples: int = 1000,
        max_endpoint_samples: int = 100,
    ) -> None:
        self._clock = clock
        self._rolling_window_seconds = rolling_window_seconds
        self._max_duration_samples = max_duration_samples
        self._max_endpoint_samples = max_endpoint_samples
        self._request_count: int = 0
        self._error_count: int = 0
        self._request_durations: list[float] = []
        self._status_codes: dict[int, int] = {}  # status_code -> count
        self._endpoint_durations: dict[str, list[float]] = {}
        self._endpoint_counts: dict[str, int] = {}
        self._request_buckets: deque[tuple[float, int, int]] = deque()
        self._start_time: float = self._clock()
        self._lock = asyncio.Lock()

    @staticmethod
    def _percentile(sorted_values: list[float], percentile: float) -> float:
        rank = max(1, math.ceil(percentile * len(sorted_values)))
        return sorted_values[rank - 1]

    def _prune_rolling_buckets(self, now: float) -> None:
        cutoff = now - self._rolling_window_seconds
        while self._request_buckets and self._request_buckets[0][0] <= cutoff:
            self._request_buckets.popleft()

    async def record_request(self, method: str, path: str, status_code: int, duration_ms: float) -> None:
        """记录一次请求的指标（线程安全）"""
        async with self._lock:
            now = self._clock()
            self._request_count += 1
            is_error = status_code >= 400

            if is_error:
                self._error_count += 1

            if self._request_buckets and self._request_buckets[-1][0] == now:
                timestamp, requests, errors = self._request_buckets.pop()
                self._request_buckets.append((timestamp, requests + 1, errors + int(is_error)))
            else:
                self._request_buckets.append((now, 1, int(is_error)))
            self._prune_rolling_buckets(now)

            self._request_durations.append(duration_ms)
            if len(self._request_durations) > self._max_duration_samples:
                self._request_durations = self._request_durations[-self._max_duration_samples :]

            # 状态码计数
            self._status_codes[status_code] = self._status_codes.get(status_code, 0) + 1

            # 按端点记录耗时，保留最近 100 次
            key = "%s %s" % (method, path)
            if key not in self._endpoint_durations:
                self._endpoint_durations[key] = []
            self._endpoint_counts[key] = self._endpoint_counts.get(key, 0) + 1
            self._endpoint_durations[key].append(duration_ms)
            if len(self._endpoint_durations[key]) > self._max_endpoint_samples:
                self._endpoint_durations[key] = self._endpoint_durations[key][-self._max_endpoint_samples :]

    async def reset(self) -> None:
        """清空运行时指标，供测试和受控进程重置使用。"""
        async with self._lock:
            self._request_count = 0
            self._error_count = 0
            self._request_durations.clear()
            self._status_codes.clear()
            self._endpoint_durations.clear()
            self._endpoint_counts.clear()
            self._request_buckets.clear()
            self._start_time = self._clock()

    async def get_metrics(self) -> dict:
        """返回所有指标"""
        async with self._lock:
            now = self._clock()
            self._prune_rolling_buckets(now)
            uptime = now - self._start_time
            durations = self._request_durations

            # 计算延迟统计
            latency: dict = {}
            if durations:
                sorted_d = sorted(durations)
                latency = {
                    "avg_ms": round(sum(sorted_d) / len(sorted_d), 2),
                    "min_ms": round(sorted_d[0], 2),
                    "max_ms": round(sorted_d[-1], 2),
                    "p50_ms": round(self._percentile(sorted_d, 0.50), 2),
                    "p95_ms": round(self._percentile(sorted_d, 0.95), 2),
                    "p99_ms": round(self._percentile(sorted_d, 0.99), 2),
                }

            # 按端点汇总
            endpoints: dict = {}
            for key, durs in self._endpoint_durations.items():
                if durs:
                    endpoints[key] = {
                        "count": self._endpoint_counts[key],
                        "avg_ms": round(sum(durs) / len(durs), 2),
                        "max_ms": round(max(durs), 2),
                    }

            error_rate = round(self._error_count / self._request_count * 100, 2) if self._request_count > 0 else 0.0
            rolling_requests = sum(requests for _, requests, _ in self._request_buckets)
            rolling_errors = sum(errors for _, _, errors in self._request_buckets)
            rolling_error_rate = round(rolling_errors / rolling_requests * 100, 2) if rolling_requests else 0.0

            return {
                "uptime_seconds": round(uptime, 1),
                "requests": {
                    "total": self._request_count,
                    "errors": self._error_count,
                    "error_rate_percent": error_rate,
                },
                "rolling_window": {
                    "window_seconds": self._rolling_window_seconds,
                    "requests": rolling_requests,
                    "errors": rolling_errors,
                    "request_rate_per_second": round(rolling_requests / self._rolling_window_seconds, 4),
                    "error_rate_percent": rolling_error_rate,
                },
                "latency": latency,
                "status_codes": dict(self._status_codes),
                "endpoints": endpoints,
            }


# 全局单例
metrics_collector = MetricsCollector()
