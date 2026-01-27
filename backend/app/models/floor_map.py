"""楼层平面图模型"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.sql import func
from ..core.database import Base


class FloorMap(Base):
    """楼层平面图"""
    __tablename__ = "floor_maps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    floor_code = Column(String(10), nullable=False, index=True, comment="楼层代码 B1/F1/F2/F3")
    floor_name = Column(String(50), nullable=False, comment="楼层名称")
    map_type = Column(String(10), nullable=False, comment="图类型 2d/3d")
    map_data = Column(Text, nullable=False, comment="图数据 JSON格式")
    thumbnail = Column(Text, comment="缩略图 Base64")
    is_default = Column(Boolean, default=False, comment="是否默认显示")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
