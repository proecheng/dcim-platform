"""数据质量相关 Schema"""

from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime


class DataQualityPointInfo(BaseModel):
    point_id: int
    point_code: str
    point_name: str
    device_type: Optional[str] = None
    quality: int
    quality_text: str
    status: Optional[str] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DataQualityStatus(BaseModel):
    total: int
    normal_count: int
    uncertain_count: int
    unreliable_count: int
    unreliable_points: List[DataQualityPointInfo] = []
