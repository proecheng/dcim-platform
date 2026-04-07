"""通用枚举定义

Story 28.2: 数据来源和电价时段枚举
"""

from enum import Enum as PyEnum


class DataSourceType(str, PyEnum):
    """数据来源类型枚举"""

    SEED = "seed"  # 种子数据
    DEMO = "demo"  # 演示数据
    REAL = "real"  # 真实数据


class PricingPeriodType(str, PyEnum):
    """电价时段类型枚举（五级制）"""

    SHARP_PEAK = "sharp_peak"  # 尖峰
    PEAK = "peak"  # 峰
    FLAT = "flat"  # 平
    VALLEY = "valley"  # 谷
    DEEP_VALLEY = "deep_valley"  # 深谷
