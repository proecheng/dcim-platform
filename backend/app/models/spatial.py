"""
空间拓扑模型 — 站点/楼层/房间/行/布局模板
"""

from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    String,
    Float,
    Text,
    DateTime,
    JSON,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from ..core.database import Base


class Site(Base):
    """站点表"""

    __tablename__ = "sites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    site_code = Column(String(50), unique=True, nullable=False, comment="站点编码")
    site_name = Column(String(100), nullable=False, comment="站点名称")
    address = Column(String(200), comment="地址")
    contact_person = Column(String(50), comment="联系人")
    contact_phone = Column(String(20), comment="联系电话")
    contact_email = Column(String(100), comment="联系邮箱")
    network_config = Column(JSON, comment="网络配置(VPN/专线信息)")
    status = Column(String(20), default="active", comment="状态: active/inactive/maintenance")
    description = Column(Text, comment="描述")
    data_source = Column(String(50), comment="数据来源: seed/demo/real")
    is_demo = Column(Boolean, default=False, nullable=False, comment="是否为演示数据")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    floors = relationship("Floor", back_populates="site", lazy="selectin")


class Floor(Base):
    """楼层表"""

    __tablename__ = "floors"
    __table_args__ = (UniqueConstraint("site_id", "floor_code", name="uq_floor_site_code"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    floor_code = Column(String(50), nullable=False, comment="楼层编码")
    floor_name = Column(String(100), nullable=False, comment="楼层名称")
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False, comment="所属站点ID")
    sort_order = Column(Integer, default=0, comment="排序")
    data_source = Column(String(50), comment="数据来源: seed/demo/real")
    is_demo = Column(Boolean, default=False, nullable=False, comment="是否为演示数据")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    site = relationship("Site", back_populates="floors")
    rooms = relationship("Room", back_populates="floor", lazy="selectin")


class Room(Base):
    """房间表"""

    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("floor_id", "room_code", name="uq_room_floor_code"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_code = Column(String(50), nullable=False, comment="房间编码")
    room_name = Column(String(100), nullable=False, comment="房间名称")
    floor_id = Column(Integer, ForeignKey("floors.id"), nullable=False, comment="所属楼层ID")
    grid_cols = Column(Integer, default=20, comment="网格列数")
    grid_rows = Column(Integer, default=20, comment="网格行数")
    area_sqm = Column(Float, comment="面积(平方米)")
    description = Column(Text, comment="描述")
    data_source = Column(String(50), comment="数据来源: seed/demo/real")
    is_demo = Column(Boolean, default=False, nullable=False, comment="是否为演示数据")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    floor = relationship("Floor", back_populates="rooms")
    rows = relationship("Row", back_populates="room", lazy="selectin")


class Row(Base):
    """行表（机柜排）"""

    __tablename__ = "rows"
    __table_args__ = (UniqueConstraint("room_id", "row_code", name="uq_row_room_code"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    row_code = Column(String(50), nullable=False, comment="行编码")
    row_name = Column(String(100), nullable=False, comment="行名称")
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False, comment="所属房间ID")
    aisle_type = Column(String(10), default="none", comment="通道类型: cold/hot/none")
    sort_order = Column(Integer, default=0, comment="排序")
    is_demo = Column(Boolean, default=False, nullable=False, comment="是否为演示数据")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    room = relationship("Room", back_populates="rows")
    cabinets = relationship("Cabinet", back_populates="row", lazy="selectin")


class LayoutTemplate(Base):
    """布局模板表"""

    __tablename__ = "layout_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    template_code = Column(String(50), unique=True, nullable=False, comment="模板编码")
    template_name = Column(String(100), nullable=False, comment="模板名称")
    description = Column(Text, comment="描述")
    template_data = Column(Text, comment="JSON格式模板数据")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
