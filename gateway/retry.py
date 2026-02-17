"""指数退避重试策略"""


class RetryPolicy:
    """指数退避重试策略 — 参数从 DataSourceConfig 读取，支持按数据源独立配置"""

    def __init__(self, base_delay: float = 1.0, max_delay: float = 60.0, max_failures: int = 5):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_failures = max_failures
        self._failure_count = 0

    def record_failure(self) -> float:
        """记录失败，返回下次重试延迟（秒）"""
        self._failure_count += 1
        delay = min(self.base_delay * (2 ** (self._failure_count - 1)), self.max_delay)
        return delay

    def record_success(self) -> None:
        """记录成功，重置计数器"""
        self._failure_count = 0

    @property
    def is_interrupted(self) -> bool:
        """是否达到通信中断阈值"""
        return self._failure_count >= self.max_failures

    @property
    def failure_count(self) -> int:
        return self._failure_count

    def reset(self) -> None:
        """重置重试状态"""
        self._failure_count = 0
