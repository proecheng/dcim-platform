"""
资产管理模型
"""
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, Boolean, Float, Text, DateTime, Date, ForeignKey, Enum
from sqlalchemy.orm import relationship

from ..core.database import Base


# ==================== 枚举定义 ====================

class AssetStatus(str, PyEnum):
    """资产状态枚举"""
    in_stock = "in_stock"           # 库存中
    in_use = "in_use"               # 使用中
    borrowed = "borrowed"           # 借出
    maintenance = "maintenance"     # 维护中
    scrapped = "scrapped"           # 已报废


class AssetType(str, PyEnum):
    """资产类型枚举"""
    server = "server"               # 服务器
    network = "network"             # 网络设备
    storage = "storage"             # 存储设备
    ups = "ups"                     # UPS
    pdu = "pdu"                     # PDU
    ac = "ac"                       # 空调
    cabinet = "cabinet"             # 机柜
    sensor = "sensor"               # 传感器
    other = "other"                 # 其他


# ==================== 机柜模型 ====================

class Cabinet(Base):
    """机柜表"""
    __tablename__ = "cabinets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cabinet_code = Column(String(50), unique=True, nullable=False, comment="机柜编码")
    cabinet_name = Column(String(100), nullable=False, comment="机柜名称")
    location = Column(String(200), comment="位置")
    row_number = Column(String(20), comment="列号")
    column_number = Column(String(20), comment="排号")
    total_u = Column(Integer, default=42, comment="总U数")
    max_power = Column(Float, comment="最大功率 kW")
    max_weight = Column(Float, comment="最大承重 kg")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    assets = relationship("Asset", back_populates="cabinet")


# ==================== 资产模型 ====================

class Asset(Base):
    """资产表"""
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_code = Column(String(50), unique=True, nullable=False, comment="资产编码")
    asset_name = Column(String(100), nullable=False, comment="资产名称")
    asset_type = Column(Enum(AssetType), nullable=False, comment="资产类型")
    brand = Column(String(100), comment="品牌")
    model = Column(String(100), comment="型号")
    serial_number = Column(String(100), comment="序列号")

    # 机柜位置
    cabinet_id = Column(Integer, ForeignKey("cabinets.id"), comment="机柜ID")
    u_position = Column(Integer, comment="U位起始位置")
    u_height = Column(Integer, comment="占用U数")

    # 资产状态
    status = Column(Enum(AssetStatus), default=AssetStatus.in_stock, comment="资产状态")

    # 采购信息
    purchase_date = Column(Date, comment="采购日期")
    purchase_price = Column(Float, comment="采购价格")
    supplier = Column(String(200), comment="供应商")

    # 保修信息
    warranty_start = Column(Date, comment="保修开始日期")
    warranty_end = Column(Date, comment="保修结束日期")
    maintenance_vendor = Column(String(200), comment="维保厂商")

    # 归属信息
    owner = Column(String(100), comment="负责人")
    department = Column(String(100), comment="所属部门")

    # 其他信息
    specifications = Column(Text, comment="规格参数(JSON格式)")
    remark = Column(Text, comment="备注")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    cabinet = relationship("Cabinet", back_populates="assets")
    lifecycle_records = relationship("AssetLifecycle", back_populates="asset")
    maintenance_records = relationship("MaintenanceRecord", back_populates="asset")


# ==================== 资产生命周期模型 ====================

class AssetLifecycle(Base):
    """资产生命周期记录表"""
    __tablename__ = "asset_lifecycles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False, comment="资产ID")
    action = Column(String(50), nullable=False, comment="操作类型: purchase/deploy/move/maintain/scrap等")
    action_date = Column(DateTime, nullable=False, comment="操作日期")
    operator = Column(String(100), comment="操作人")
    from_location = Column(String(200), comment="原位置")
    to_location = Column(String(200), comment="新位置")
    remark = Column(Text, comment="备注")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    # 关系
    asset = relationship("Asset", back_populates="lifecycle_records")


# ==================== 维护记录模型 ====================

class MaintenanceRecord(Base):
    """维护记录表"""
    __tablename__ = "maintenance_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False, comment="资产ID")
    maintenance_type = Column(String(50), nullable=False, comment="维护类型: routine/repair/upgrade等")
    start_time = Column(DateTime, nullable=False, comment="开始时间")
    end_time = Column(DateTime, comment="结束时间")
    technician = Column(String(100), comment="维护人员")
    vendor = Column(String(200), comment="维护厂商")
    cost = Column(Float, comment="维护费用")
    description = Column(Text, comment="维护描述")
    result = Column(Text, comment="维护结果")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    # 关系
    asset = relationship("Asset", back_populates="maintenance_records")


# ==================== 资产盘点模型 ====================

class AssetInventory(Base):
    """资产盘点表"""
    __tablename__ = "asset_inventories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inventory_code = Column(String(50), unique=True, nullable=False, comment="盘点编码")
    inventory_date = Column(Date, nullable=False, comment="盘点日期")
    operator = Column(String(100), comment="盘点人")
    status = Column(String(20), default="pending", comment="盘点状态: pending/in_progress/completed")
    total_count = Column(Integer, default=0, comment="总数量")
    checked_count = Column(Integer, default=0, comment="已盘点数量")
    matched_count = Column(Integer, default=0, comment="匹配数量")
    unmatched_count = Column(Integer, default=0, comment="不匹配数量")
    remark = Column(Text, comment="备注")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    completed_at = Column(DateTime, comment="完成时间")

    # 关系
    items = relationship("AssetInventoryItem", back_populates="inventory")


class AssetInventoryItem(Base):
    """资产盘点明细表"""
    __tablename__ = "asset_inventory_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inventory_id = Column(Integer, ForeignKey("asset_inventories.id"), nullable=False, comment="盘点ID")
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False, comment="资产ID")
    expected_location = Column(String(200), comment="预期位置")
    actual_location = Column(String(200), comment="实际位置")
    is_matched = Column(Boolean, default=False, comment="是否匹配")
    check_time = Column(DateTime, comment="盘点时间")
    remark = Column(Text, comment="备注")

    # 关系
    inventory = relationship("AssetInventory", back_populates="items")
    asset = relationship("Asset")
