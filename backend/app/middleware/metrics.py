"""
性能指标收集器
纯内存实现，收集请求计数、延迟、错误率等指标。
"""

import asyncio
import time


class MetricsCollector:
    """应用性能指标收集器（单例）"""

    def __init__(self) -> None:
        self._request_count: int = 0
        self._error_count: int = 0
        self._request_durations: list[float] = []  # 最近 1000 次请求耗时 (ms)
        self._status_codes: dict[int, int] = {}  # status_code -> count
        self._endpoint_durations: dict[str, list[float]] = {}  # path -> 最近 100 次耗时
        self._start_time: float = time.time()
        self._lock = asyncio.Lock()

    async def record_request(self, method: str, path: str, status_code: int, duration_ms: float) -> None:
        """记录一次请求的指标（线程安全）"""
        async with self._lock:
            self._request_count += 1

            if status_code >= 400:
                self._error_count += 1

            # 保留最近 1000 次请求耗时
            self._request_durations.append(duration_ms)
            if len(self._request_durations) > 1000:
                self._request_durations = self._request_durations[-1000:]

            # 状态码计数
            self._status_codes[status_code] = self._status_codes.get(status_code, 0) + 1

            # 按端点记录耗时，保留最近 100 次
            key = "%s %s" % (method, path)
            if key not in self._endpoint_durations:
                self._endpoint_durations[key] = []
            self._endpoint_durations[key].append(duration_ms)
            if len(self._endpoint_durations[key]) > 100:
                self._endpoint_durations[key] = self._endpoint_durations[key][-100:]

    async def get_metrics(self) -> dict:
        """返回所有指标"""
        async with self._lock:
            uptime = time.time() - self._start_time
            durations = self._request_durations

            # 计算延迟统计
            latency: dict = {}
            if durations:
                sorted_d = sorted(durations)
                latency = {
                    "avg_ms": round(sum(sorted_d) / len(sorted_d), 2),
                    "min_ms": round(sorted_d[0], 2),
                    "max_ms": round(sorted_d[-1], 2),
                    "p50_ms": round(sorted_d[len(sorted_d) // 2], 2),
                    "p95_ms": round(sorted_d[int(len(sorted_d) * 0.95)], 2),
                    "p99_ms": round(sorted_d[min(int(len(sorted_d) * 0.99), len(sorted_d) - 1)], 2),
                }

            # 按端点汇总
            endpoints: dict = {}
            for key, durs in self._endpoint_durations.items():
                if durs:
                    endpoints[key] = {
                        "count": len(durs),
                        "avg_ms": round(sum(durs) / len(durs), 2),
                        "max_ms": round(max(durs), 2),
                    }

            error_rate = round(self._error_count / self._request_count * 100, 2) if self._request_count > 0 else 0.0

            return {
                "uptime_seconds": round(uptime, 1),
                "requests": {
                    "total": self._request_count,
                    "errors": self._error_count,
                    "error_rate_percent": error_rate,
                },
                "latency": latency,
                "status_codes": dict(self._status_codes),
                "endpoints": endpoints,
            }


# 全局单例
metrics_collector = MetricsCollector()
