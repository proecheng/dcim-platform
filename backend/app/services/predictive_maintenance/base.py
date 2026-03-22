"""劣化分析插件基类与数据结构 — Story 36.1"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class DegradationResult:
    """劣化分析结果"""
    device_id: int
    score: float                    # 0~100 劣化评分（100=健康）
    confidence: float               # 0~1 评估置信度
    available_points: int           # 实际可用数据点数
    total_points: int               # 理想数据点数
    trend_factors: dict[str, float] = field(default_factory=dict)
    primary_concern: str | None = None
    data_sufficiency: str = "minimal"  # full | partial | minimal
    detail: dict | None = None       # 各指标详细分析结果（供 36.3 使用）


class DegradationPlugin(ABC):
    """劣化分析插件抽象基类"""

    @abstractmethod
    def get_device_type(self) -> str:
        """返回插件支持的设备类型标识"""
        ...

    @abstractmethod
    def get_required_points(self) -> list[str]:
        """返回必需的 point_code 后缀模式列表"""
        ...

    @abstractmethod
    def get_optional_points(self) -> list[str]:
        """返回可选的 point_code 后缀模式列表"""
        ...

    @abstractmethod
    async def analyze(
        self,
        device_id: int,
        point_history: dict[str, list],
        window_days: int = 30,
    ) -> DegradationResult:
        """执行劣化分析，返回分析结果"""
        ...
