"""
确定性模拟数据辅助函数
[V2.11] 替换 random 模块，使用基于种子的确定性计算
从 energy.py 提取，供多模块复用
"""
from datetime import date, datetime


def _deterministic_ratio(seed: int, min_val: float = 0.5, max_val: float = 0.9) -> float:
    """
    基于种子生成确定性比率值

    Args:
        seed: 种子值（可使用 device.id、索引、日期等）
        min_val: 最小值
        max_val: 最大值

    Returns:
        在 [min_val, max_val] 范围内的确定性值
    """
    # 使用简单的线性同余生成器思路
    normalized = ((seed * 1103515245 + 12345) % (2**31)) / (2**31)
    return min_val + normalized * (max_val - min_val)


def _deterministic_offset(seed: int, amplitude: float = 5.0) -> float:
    """
    基于种子生成确定性偏移值（围绕0波动）

    Args:
        seed: 种子值
        amplitude: 波动幅度

    Returns:
        在 [-amplitude, +amplitude] 范围内的值
    """
    normalized = ((seed * 1103515245 + 12345) % (2**31)) / (2**31)
    return (normalized - 0.5) * 2 * amplitude


def _device_seed(device_id: int, phase: int = 0) -> int:
    """为设备生成确定性种子"""
    return device_id * 17 + phase * 31


def _time_seed(dt: datetime, offset: int = 0) -> int:
    """为时间点生成确定性种子"""
    return dt.year * 10000 + dt.month * 100 + dt.day + dt.hour * 3 + offset


def _date_seed(d: date, offset: int = 0) -> int:
    """为日期生成确定性种子"""
    return d.year * 10000 + d.month * 100 + d.day + offset
