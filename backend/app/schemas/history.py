"""
历史数据相关 Schema
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class HistoryQuery(BaseModel):
    """历史数据查询"""
    point_id: int
    start_time: datetime
    end_time: datetime
    interval: str = "raw"  # raw, minute, hour, day


class HistoryData(BaseModel):
    """历史数据"""
    time: datetime
    value: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    quality: int = 0


class TrendData(BaseModel):
    """趋势数据"""
    time: str
    value: Optional[float] = None


class HistoryStatistics(BaseModel):
    """历史数据统计"""
    point_id: int
    point_code: str
    point_name: str
    start_time: datetime
    end_time: datetime
    count: int
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    avg_value: Optional[float] = None
    std_dev: float = 0


class CompareQuery(BaseModel):
    """对比查询"""
    point_ids: list
    start_time: datetime
    end_time: datetime
